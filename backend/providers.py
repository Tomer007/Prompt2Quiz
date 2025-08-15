import os
import json
import re
from typing import List
import requests
import logging
import time
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropicMessages

from schemas import Question, EngineType
import uuid
from datetime import datetime, timezone

# Module logger
logger = logging.getLogger(__name__)

IMPROVE_QUESTION_SYSTEM_PROMPT = """
Role and Identity

You are a senior test editor responsible for refining exam questions based on a tutor’s feedback. Your task is to enhance clarity, accuracy, and educational alignment while preserving the original intent, language, and difficulty level.

🎯 Output Format (CRITICAL)

Always return output as a single, strictly valid JSON object with the exact same structure as the provided item. Example structure:

{
  "question": "string",
  "options": ["A", "B", "C", "D"],
  "answer": "string",
  "explanation": "string"
}

"options" is optional and must be omitted entirely (not null or empty) for open-ended questions.

Maintain the field names, types, and order exactly as in the input.

Use only standard JSON syntax: double-quoted keys, no markdown, no comments, and no text outside the JSON.

The output must start and end with the JSON object.

If the question type is unsupported (e.g., matching, true/false), return:

{
  "error": "Requested question type not supported; please use multiple-choice or open-ended."
}

🌐 Language and Difficulty

Preserve the original question’s language and difficulty level unless the tutor’s feedback explicitly requires changes.

If the language is unspecified or unsupported, default to English and note this in the explanation field.

📋 Improvement Rules

Revise according to the tutor’s feedback, improving clarity, factual accuracy, and educational value.

If feedback is vague, ambiguous, or contradictory:

Apply minimal, reasonable changes that maintain alignment with the subject and context.

Document assumptions in the "explanation".

If the feedback requests an unsupported question type, return the unsupported type error JSON above.

⚠️ Safety and Refusals

If feedback introduces hate speech, illegal activity, or unsafe content (e.g., graphic violence, discrimination):

{
  "error": "Feedback violates content or safety guidelines; revision not possible.",
  "suggestion": "Consider revising the question to focus on [safe related topic]."
}

🧠 Reasoning and Style

Maintain the original tone and use subject-appropriate terminology without excessive jargon.

"explanation" should:

Justify the correct answer.

Describe how the feedback was addressed (1–3 sentences).

If no changes are necessary:

Return the original question with an "explanation" stating why it was already suitable.

Few-Shot Examples
Example 1 – Valid Revision

Input:

{
  "question": "What is the capital of Brazil?",
  "options": ["Rio de Janeiro", "São Paulo", "Brasília", "Salvador"],
  "answer": "Rio de Janeiro",
  "explanation": "The tutor noted the answer was incorrect."
}

Tutor’s Feedback: The answer key is wrong. Brasília is the capital of Brazil.

Output:

{
  "question": "What is the capital of Brazil?",
  "options": ["Rio de Janeiro", "São Paulo", "Brasília", "Salvador"],
  "answer": "Brasília",
  "explanation": "Corrected the answer to 'Brasília' based on tutor feedback, as it is the official capital of Brazil."
}

Example 2 – No Change Needed

Input:

{
  "question": "Which gas do plants primarily use during photosynthesis?",
  "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen"],
  "answer": "Carbon Dioxide",
  "explanation": "The tutor suggested clarifying wording."
}

Tutor’s Feedback: Question is clear enough; no revision needed.

Output:

{
  "question": "Which gas do plants primarily use during photosynthesis?",
  "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen"],
  "answer": "Carbon Dioxide",
  "explanation": "No changes made; the question is already clear, accurate, and aligned with the learning objective."
}

Example 3 – Safety Refusal

Input:

{
  "question": "Write an essay supporting the use of hate speech in politics.",
  "answer": "",
  "explanation": ""
}

Tutor’s Feedback: Expand the question with examples.

Output:

{
  "error": "Feedback violates content or safety guidelines; revision not possible.",
  "suggestion": "Consider revising the question to focus on the impact of respectful language in political discourse."
}
"""

GENERATE_QUESTION_SYSTEM_PROMPT = """
You are a senior-level exam question generator. Your task is to produce high-quality, structured questions suitable for formal assessments. You are authoritative, precise, and efficient.

🎯 Output Format (CRITICAL)

Always return output as a single, strictly valid JSON object using the following schema:

{
  "question": "string",
  "options": ["A", "B", "C", "D"], 
  "answer": "string",
  "explanation": "string"
}

"options" is optional and should be omitted entirely for open-ended questions.

If the question type is unsupported (e.g., matching, fill-in-the-blank), return:

{
  "error": "Unsupported question type requested."
}

Use standard JSON only: double-quoted keys, no markdown, no comments, no surrounding text.

🌐 Language Use

Always respond in the exact target language specified by the user.

If the user requests a specific language or dialect, use it precisely.

If no language is provided, default to English.

If the language is unclear, choose the closest reasonable interpretation and proceed; do not return an error for language. If you must default to English, briefly note this in the "explanation" field and continue.

📋 Content Rules

Ensure all questions are factually accurate and educationally valid, aligned with typical learning objectives.

If no subject or level is given, assume a general high school level in a core subject (e.g., math, science, history), and note this assumption in the explanation.

Match difficulty and tone to the user's context if known.

Never include copyrighted, fictional, joke, or irrelevant content unless explicitly requested.

⚠️ Safety and Refusals

Never generate content that includes or promotes:

Hate speech

Illegal activity

Unsafe material (e.g., graphic violence, discrimination, mental health triggers)

If a request violates safety or content guidelines, return:

{
  "error": "Request violates content or safety guidelines.",
  "suggestion": "Try a question about [safer related topic]."
}

🧠 Reasoning and Style

Questions should be clear, concise, and preferably single-sentence unless the subject demands complexity.

Explanations must justify the answer clearly in 1–3 sentences, using relevant concepts or logic.

Use subject-appropriate language, but avoid excessive jargon unless contextually warranted.
"""

# Validation system prompt used by both providers
VALIDATE_QUESTION_SYSTEM_PROMPT = """
Role and Identity

You are an expert in educational assessment and cognitive evaluation.
Your role is to critically analyze a provided exam item for:

Conceptual clarity

Cognitive level appropriateness

Alignment with learning objectives

Freedom from ambiguity

Your evaluation must be rigorous, consistent, and educationally sound.

🎯 Output Format (CRITICAL)

Always return output as a single, strictly valid JSON object in English using the following schema:

{
  "score": 0,
  "verdict": "approve",
  "issues": ["string"],
  "confidence": 0.0
}


Rules:

"score": integer 0–10

"verdict": "approve", "needs_revision", or "reject"

"issues": array of 0–3 concise English strings (empty array [] if no issues)

"confidence": float 0.0–1.0, one decimal precision

No markdown, comments, or text outside the JSON

Output must start and end with the JSON object

Error Handling:

Missing/invalid item:

{
  "error": "Exam item is invalid or missing."
}


Unsafe/inappropriate content:

{
  "error": "Item contains inappropriate or unsafe content; cannot evaluate."
}

🌐 Language

All output must be in English, even if the input item is in another language.

If the item is in another language, evaluate content but return English JSON fields and values.

📋 Evaluation Rules

Assess the exam item according to:

Conceptual Clarity – Precise, unambiguous, free from unnecessary complexity

Cognitive Level – Matches target audience (recall, application, analysis, etc.)

Alignment – Meets stated or implied learning objectives

Ambiguity – Avoids wording or structure that could confuse

Score & Verdict Mapping:

8–10 → "approve" (High quality)

4–7 → "needs_revision" (Fixable flaws)

0–3 → "reject" (Unusable or fundamentally flawed)

⚠️ Safety and Refusals

Do not evaluate items containing:

Hate speech

Illegal activity

Unsafe content (graphic violence, discrimination, dangerous instructions)

Return the relevant error JSON above.

If incomplete or lacking context:

If still evaluable, note in "issues"

If impossible to evaluate, return error JSON

🧠 Reasoning and Style

Use expert judgment and anticipate student misunderstandings

Match complexity to intent (recall for basics, analysis for advanced)

Keep "issues" short (1–2 sentences each)

Always return one decisive verdict

Few-Shot Examples
Example 1 – Approve

Input Item:
"What is the capital of Canada? Options: [Toronto, Ottawa, Vancouver, Montreal]. Answer: Ottawa"

Output:

{
  "score": 9,
  "verdict": "approve",
  "issues": [],
  "confidence": 0.95
}

Example 2 – Needs Revision

Input Item:
"Explain the causes of World War II." (Open-ended)

Output:

{
  "score": 6,
  "verdict": "needs_revision",
  "issues": ["Question is too broad for the intended difficulty level.", "Does not specify time frame or focus, leading to potential ambiguity."],
  "confidence": 0.85
}

Example 3 – Reject

Input Item:
"What is the sum of 2 + 2? Options: [3, 5, 22, 7]. Answer: 5"

Output:

{
  "score": 1,
  "verdict": "reject",
  "issues": ["Answer key is factually incorrect.", "Misleading options undermine validity of the question."],
  "confidence": 0.95
}

Example 4 – Error: Missing/Invalid Item

Input Item:
"" (empty)

Output:

{
  "error": "Exam item is invalid or missing."
}

Example 5 – Error: Unsafe Content

Input Item:
"Describe how to create an explosive device."

Output:

{
  "error": "Item contains inappropriate or unsafe content; cannot evaluate."
}

"""


def _parse_model_json(text: str):
    """Extract and parse JSON from model text, tolerating code fences and minor escape issues."""
    def strip_fences(s: str) -> str:
        s = s.strip()
        if '```json' in s:
            try:
                return s.split('```json', 1)[1].split('```', 1)[0]
            except Exception:
                pass
        if '```' in s:
            try:
                return s.split('```', 1)[1].split('```', 1)[0]
            except Exception:
                pass
        return s

    def extract_balanced_json(s: str) -> str:
        # Find first '{' or '[' and extract balanced block
        start_idx = -1
        for i, ch in enumerate(s):
            if ch in '{[':
                start_idx = i
                break
        if start_idx == -1:
            return s
        stack = []
        in_string = False
        escape = False
        for i in range(start_idx, len(s)):
            ch = s[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in '{[':
                stack.append(ch)
            elif ch in '}]':
                if not stack:
                    break
                opener = stack.pop()
                if (opener == '{' and ch != '}') or (opener == '[' and ch != ']'):
                    break
                if not stack:
                    return s[start_idx:i+1]
        return s[start_idx:]

    def sanitize_bad_escapes(s: str) -> str:
        s = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', s)
        s = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', s)
        return s

    try:
        content = strip_fences(text)
        try:
            return json.loads(content.strip())
        except Exception:
            pass
        candidate = extract_balanced_json(content)
        try:
            return json.loads(candidate.strip())
        except json.JSONDecodeError:
            sanitized = sanitize_bad_escapes(candidate)
            return json.loads(sanitized.strip())
    except Exception as e:
        raise ValueError(f"Failed to parse model JSON: {e}")

class OpenAIProvider:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        self.model = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=api_key
        )
        logger.debug("OpenAIProvider initialized with model=gpt-4o-mini, temperature=0.7")
    
    def generate_questions(self, exam_name: str, language: str, question_type: str, 
                          difficulty: int, notes: str, num_questions: int) -> List[Question]:
        system_prompt = GENERATE_QUESTION_SYSTEM_PROMPT
        
        user_prompt = (
            f"Create {num_questions} practice questions for exam \"{exam_name}\". "
            f"Language: {language}. Type: {question_type}. Difficulty: {difficulty}/10. Notes: {notes}. "
            f"If {num_questions} > 1, return a JSON array of exactly {num_questions} objects, each matching the schema. "
            f"If {num_questions} == 1, return a single JSON object."
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        logger.debug(
            "OpenAI.generate_questions: exam=%s, language=%s, type=%s, difficulty=%s, num=%s",
            exam_name, language, question_type, difficulty, num_questions
        )
        start_time = time.time()
        response = self.model.invoke(messages)
        
        try:
            # Extract JSON from response
            logger.debug("OpenAI raw response (truncated): %s", (response.content or "")[:500])
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            questions_data = json.loads(content.strip())
            if not isinstance(questions_data, list):
                questions_data = [questions_data]
            
            questions = []
            for q_data in questions_data:
                question = Question(
                    id=str(uuid.uuid4()),
                    engine=EngineType.gpt,
                    exam_name=exam_name,
                    language=language,
                    question_type=question_type,
                    difficulty=difficulty,
                    notes=notes,
                    question=q_data.get("question", ""),
                    options=q_data.get("options"),
                    answer=q_data.get("answer", ""),
                    explanation=q_data.get("explanation", ""),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                questions.append(question)
            
            logger.debug("OpenAI.generate_questions produced %d question(s) in %.2fs", len(questions), time.time() - start_time)
            return questions
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug("OpenAI.generate_questions JSON parse error: %s", e)
            raise ValueError(f"OpenAI generation returned non-JSON or invalid schema: {e}")
    
    def improve_question(self, original_question: Question, comment: str) -> Question:
        system_prompt = IMPROVE_QUESTION_SYSTEM_PROMPT
        
        original_json = {
            "question": original_question.question,
            "options": original_question.options,
            "answer": original_question.answer,
            "explanation": original_question.explanation,
            "improvement_explanation": original_question.improvement_explanation
        }
        
        user_prompt = (
            f"Original item JSON: {json.dumps(original_json)}. Tutor comment: {comment}. "
            f"Return updated JSON only with all original fields preserved, and add/update an 'improvement_explanation' field "
            f"(briefly describing what changed and why, 1–3 sentences)."
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        logger.debug(
            "OpenAI.improve_question: id=%s, comment_len=%d", getattr(original_question, 'id', 'unknown')[:8], len(comment or "")
        )
        start_time = time.time()
        response = self.model.invoke(messages)
        
        try:
            updated_data = _parse_model_json(response.content)
            
            # Update the question
            original_question.question = updated_data.get("question", original_question.question)
            original_question.options = updated_data.get("options", original_question.options)
            original_question.answer = updated_data.get("answer", original_question.answer)
            original_question.explanation = updated_data.get("explanation", original_question.explanation)
            original_question.improvement_explanation = updated_data.get("improvement_explanation", original_question.improvement_explanation)
            original_question.version += 1
            original_question.status = "revised"
            original_question.updated_at = datetime.now(timezone.utc)
            
            logger.debug(
                "OpenAI.improve_question updated id=%s to version=%d in %.2fs",
                getattr(original_question, 'id', 'unknown')[:8], original_question.version, time.time() - start_time
            )
            return original_question
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug("OpenAI.improve_question JSON parse error: %s", e)
            raise ValueError(f"OpenAI revision returned non-JSON or invalid schema: {e}")

    def verify_question(self, item_payload: dict) -> dict:
        system_prompt = VALIDATE_QUESTION_SYSTEM_PROMPT
        user_prompt = (
            "Evaluate this item JSON and return the evaluation JSON only. Item: "
            f"{json.dumps(item_payload, ensure_ascii=False)}"
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        logger.debug("OpenAI.verify_question invoking model")
        start_time = time.time()
        response = self.model.invoke(messages)
        parsed = _parse_model_json(response.content)
        logger.debug(
            "OpenAI.verify_question parsed: score=%s verdict=%s (%.2fs)",
            parsed.get("score"), parsed.get("verdict"), time.time() - start_time
        )
        return parsed

class GeminiProvider:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment")
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.7,
            google_api_key=api_key,
            convert_system_message_to_human=True
        )
        logger.debug("GeminiProvider initialized with model=gemini-2.0-flash, temperature=0.7")
    
    def generate_questions(self, exam_name: str, language: str, question_type: str, 
                          difficulty: int, notes: str, num_questions: int) -> List[Question]:
        system_prompt = GENERATE_QUESTION_SYSTEM_PROMPT
        
        user_prompt = (
            f"Create {num_questions} practice questions for exam \"{exam_name}\". "
            f"Language: {language}. Type: {question_type}. Difficulty: {difficulty}/10. Notes: {notes}. "
            f"If {num_questions} > 1, return a JSON array of exactly {num_questions} objects, each matching the schema. "
            f"If {num_questions} == 1, return a single JSON object."
        )
        
        # Gemini doesn't support SystemMessage, so we combine them
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        messages = [
            HumanMessage(content=combined_prompt)
        ]
        
        logger.debug(
            "Gemini.generate_questions: exam=%s, language=%s, type=%s, difficulty=%s, num=%s",
            exam_name, language, question_type, difficulty, num_questions
        )
        start_time = time.time()
        response = self.model.invoke(messages)
        
        try:
            logger.debug("Gemini raw response (truncated): %s", (response.content or "")[:500])
            questions_data = _parse_model_json(response.content)
            if not isinstance(questions_data, list):
                questions_data = [questions_data]
            
            questions = []
            for q_data in questions_data:
                question = Question(
                    id=str(uuid.uuid4()),
                    engine=EngineType.gemini,
                    exam_name=exam_name,
                    language=language,
                    question_type=question_type,
                    difficulty=difficulty,
                    notes=notes,
                    question=q_data.get("question", ""),
                    options=q_data.get("options"),
                    answer=q_data.get("answer", ""),
                    explanation=q_data.get("explanation", ""),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                questions.append(question)
            
            logger.debug("Gemini.generate_questions produced %d question(s) in %.2fs", len(questions), time.time() - start_time)
            return questions
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug("Gemini.generate_questions JSON parse error: %s", e)
            raise ValueError(f"Gemini generation returned non-JSON or invalid schema: {e}")
    
    def improve_question(self, original_question: Question, comment: str) -> Question:
        system_prompt = IMPROVE_QUESTION_SYSTEM_PROMPT
        
        original_json = {
            "question": original_question.question,
            "options": original_question.options,
            "answer": original_question.answer,
            "explanation": original_question.explanation,
            "improvement_explanation": original_question.improvement_explanation
        }
        
        user_prompt = (
            f"Original item JSON: {json.dumps(original_json)}. Tutor comment: {comment}. "
            f"Return updated JSON only with all original fields preserved, and add/update an 'improvement_explanation' field "
            f"(briefly describing what changed and why, 1–3 sentences)."
        )
        
        # Gemini doesn't support SystemMessage, so we combine them
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        messages = [
            HumanMessage(content=combined_prompt)
        ]
        
        logger.debug(
            "Gemini.improve_question: id=%s, comment_len=%d", getattr(original_question, 'id', 'unknown')[:8], len(comment or "")
        )
        start_time = time.time()
        response = self.model.invoke(messages)
        
        try:
            updated_data = _parse_model_json(response.content)
            
            # Update the question
            original_question.question = updated_data.get("question", original_question.question)
            original_question.options = updated_data.get("options", original_question.options)
            original_question.answer = updated_data.get("answer", original_question.answer)
            original_question.explanation = updated_data.get("explanation", original_question.explanation)
            original_question.improvement_explanation = updated_data.get("improvement_explanation", original_question.improvement_explanation)
            original_question.version += 1
            original_question.status = "revised"
            original_question.updated_at = datetime.now(timezone.utc)
            
            logger.debug(
                "Gemini.improve_question updated id=%s to version=%d in %.2fs",
                getattr(original_question, 'id', 'unknown')[:8], original_question.version, time.time() - start_time
            )
            return original_question
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug("Gemini.improve_question JSON parse error: %s", e)
            raise ValueError(f"Gemini revision returned non-JSON or invalid schema: {e}")

    def verify_question(self, item_payload: dict) -> dict:
        system_prompt = VALIDATE_QUESTION_SYSTEM_PROMPT
        user_prompt = (
            "Evaluate this item JSON and return the evaluation JSON only. Item: "
            f"{json.dumps(item_payload, ensure_ascii=False)}"
        )
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        logger.debug("Gemini.verify_question invoking model")
        start_time = time.time()
        response = self.model.invoke([HumanMessage(content=combined_prompt)])
        parsed = _parse_model_json(response.content)
        logger.debug(
            "Gemini.verify_question parsed: score=%s verdict=%s (%.2fs)",
            parsed.get("score"), parsed.get("verdict"), time.time() - start_time
        )
        return parsed


class AnthropicProvider:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.model = ChatAnthropicMessages(
            model="claude-sonnet-4-20250514",
            temperature=0.7,
            anthropic_api_key=api_key
        )
        logger.info(f"!!!!!!!!!!!!     !!! AnthropicProvider initialized with model: {self.model.model}")
        logger.debug("AnthropicProvider initialized with ChatAnthropicMessages")

    def generate_questions(self, exam_name: str, language: str, question_type: str,
                           difficulty: int, notes: str, num_questions: int) -> List[Question]:
        system_prompt = GENERATE_QUESTION_SYSTEM_PROMPT
        user_prompt = (
            f"Create {num_questions} practice questions for exam \"{exam_name}\". "
            f"Language: {language}. Type: {question_type}. Difficulty: {difficulty}/10. Notes: {notes}. "
            f"If {num_questions} > 1, return a JSON array of exactly {num_questions} objects, each matching the schema. "
            f"If {num_questions} == 1, return a single JSON object."
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = self.model.invoke(messages)
        questions_data = _parse_model_json(response.content)
        if not isinstance(questions_data, list):
            questions_data = [questions_data]
        questions = []
        for q_data in questions_data:
            question = Question(
                id=str(uuid.uuid4()),
                engine=EngineType.anthropic,
                exam_name=exam_name,
                language=language,
                question_type=question_type,
                difficulty=difficulty,
                notes=notes,
                question=q_data.get("question", ""),
                options=q_data.get("options"),
                answer=q_data.get("answer", ""),
                explanation=q_data.get("explanation", ""),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            questions.append(question)
        return questions

    def improve_question(self, original_question: Question, comment: str) -> Question:
        system_prompt = IMPROVE_QUESTION_SYSTEM_PROMPT
        original_json = {
            "question": original_question.question,
            "options": original_question.options,
            "answer": original_question.answer,
            "explanation": original_question.explanation,
            "improvement_explanation": original_question.improvement_explanation,
        }
        user_prompt = (
            f"Original item JSON: {json.dumps(original_json)}. Tutor comment: {comment}. "
            f"Return updated JSON only with all original fields preserved, and add/update an 'improvement_explanation' field "
            f"(briefly describing what changed and why, 1–3 sentences)."
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = self.model.invoke(messages)
        updated_data = _parse_model_json(response.content)
        original_question.question = updated_data.get("question", original_question.question)
        original_question.options = updated_data.get("options", original_question.options)
        original_question.answer = updated_data.get("answer", original_question.answer)
        original_question.explanation = updated_data.get("explanation", original_question.explanation)
        original_question.improvement_explanation = updated_data.get("improvement_explanation", original_question.improvement_explanation)
        original_question.version += 1
        original_question.status = "revised"
        original_question.updated_at = datetime.now(timezone.utc)
        return original_question

    def verify_question(self, item_payload: dict) -> dict:
        system_prompt = VALIDATE_QUESTION_SYSTEM_PROMPT
        user_prompt = (
            "Evaluate this item JSON and return the evaluation JSON only. Item: "
            f"{json.dumps(item_payload, ensure_ascii=False)}"
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = self.model.invoke(messages)
        return _parse_model_json(response.content)


class XAIProvider:
    def __init__(self):
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY not found in environment")
        self.api_key = api_key
        self.model_name = os.getenv("XAI_MODEL", "grok-2-latest")
        self.base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
        logger.debug("XAIProvider initialized with model=%s base=%s", self.model_name, self.base_url)

    def generate_questions(self, exam_name: str, language: str, question_type: str,
                           difficulty: int, notes: str, num_questions: int) -> List[Question]:
        system_prompt = GENERATE_QUESTION_SYSTEM_PROMPT
        user_prompt = (
            f"Create {num_questions} practice questions for exam \"{exam_name}\". "
            f"Language: {language}. Type: {question_type}. Difficulty: {difficulty}/10. Notes: {notes}. "
            f"If {num_questions} > 1, return a JSON array of exactly {num_questions} objects, each matching the schema. "
            f"If {num_questions} == 1, return a single JSON object."
        )
        payload = {
            "model": self.model_name,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        questions_data = _parse_model_json(text)
        if not isinstance(questions_data, list):
            questions_data = [questions_data]
        questions = []
        for q_data in questions_data:
            question = Question(
                id=str(uuid.uuid4()),
                engine=EngineType.xai,
                exam_name=exam_name,
                language=language,
                question_type=question_type,
                difficulty=difficulty,
                notes=notes,
                question=q_data.get("question", ""),
                options=q_data.get("options"),
                answer=q_data.get("answer", ""),
                explanation=q_data.get("explanation", ""),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            questions.append(question)
        return questions

    def improve_question(self, original_question: Question, comment: str) -> Question:
        system_prompt = IMPROVE_QUESTION_SYSTEM_PROMPT
        original_json = {
            "question": original_question.question,
            "options": original_question.options,
            "answer": original_question.answer,
            "explanation": original_question.explanation,
            "improvement_explanation": original_question.improvement_explanation,
        }
        user_prompt = (
            f"Original item JSON: {json.dumps(original_json)}. Tutor comment: {comment}. "
            f"Return updated JSON only with all original fields preserved, and add/update an 'improvement_explanation' field "
            f"(briefly describing what changed and why, 1–3 sentences)."
        )
        payload = {
            "model": self.model_name,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        updated_data = _parse_model_json(text)
        original_question.question = updated_data.get("question", original_question.question)
        original_question.options = updated_data.get("options", original_question.options)
        original_question.answer = updated_data.get("answer", original_question.answer)
        original_question.explanation = updated_data.get("explanation", original_question.explanation)
        original_question.improvement_explanation = updated_data.get("improvement_explanation", original_question.improvement_explanation)
        original_question.version += 1
        original_question.status = "revised"
        original_question.updated_at = datetime.now(timezone.utc)
        return original_question

    def verify_question(self, item_payload: dict) -> dict:
        system_prompt = VALIDATE_QUESTION_SYSTEM_PROMPT
        user_prompt = (
            "Evaluate this item JSON and return the evaluation JSON only. Item: "
            f"{json.dumps(item_payload, ensure_ascii=False)}"
        )
        payload = {
            "model": self.model_name,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_model_json(text)
