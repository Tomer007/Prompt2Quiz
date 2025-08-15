import csv
import os
import uuid
import logging
from typing import List, Optional
from datetime import datetime, timezone
from schemas import Question, EngineType
from providers import OpenAIProvider, GeminiProvider, AnthropicProvider, XAIProvider

# Configure logging for services
logger = logging.getLogger(__name__)

class QuestionService:
    def __init__(self):
        logger.info("Initializing QuestionService...")
        self.questions: List[Question] = []
        # Create a unique CSV file per backend session
        unique_suffix = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.csv_file_path = f"../data/export_{unique_suffix}.csv"
        self._ensure_csv_directory()
        self._initialize_csv()
        logger.info(f"QuestionService initialized with CSV path: {self.csv_file_path}")
    
    def _ensure_csv_directory(self):
        """Ensure the CSV directory exists"""
        try:
            os.makedirs(os.path.dirname(self.csv_file_path), exist_ok=True)
            logger.debug(f"CSV directory ensured: {os.path.dirname(self.csv_file_path)}")
        except Exception as e:
            logger.error(f"Error creating CSV directory: {e}")
    
    def _initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        try:
            if not os.path.exists(self.csv_file_path):
                headers = [
                    'exam_name', 'language', 'question_type', 'difficulty', 
                    'engine', 'question', 'options', 'answer', 'explanation', 
                    'version', 'approved_at'
                ]
                # Write with UTF-8 BOM for proper Hebrew support in Excel
                with open(self.csv_file_path, 'wb') as csvfile:
                    # Write UTF-8 BOM
                    csvfile.write(b'\xef\xbb\xbf')
                    # Convert to text mode for CSV writer
                    csvfile.close()
                    
                with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)
                logger.info(f"CSV file initialized with UTF-8 BOM for Hebrew support: {self.csv_file_path}")
            else:
                # Check if existing CSV has BOM, add if missing
                self._ensure_csv_bom()
                logger.debug(f"CSV file already exists: {self.csv_file_path}")
        except Exception as e:
            logger.error(f"Error initializing CSV file: {e}")
    
    def _ensure_csv_bom(self):
        """Ensure CSV file has UTF-8 BOM for Hebrew support"""
        try:
            with open(self.csv_file_path, 'rb') as csvfile:
                content = csvfile.read()
                
            # Check if BOM exists
            if not content.startswith(b'\xef\xbb\xbf'):
                logger.info("Adding UTF-8 BOM to existing CSV file for Hebrew support")
                # Read existing content
                with open(self.csv_file_path, 'r', encoding='utf-8') as csvfile:
                    existing_content = csvfile.read()
                
                # Write with BOM
                with open(self.csv_file_path, 'wb') as csvfile:
                    csvfile.write(b'\xef\xbb\xbf')
                    csvfile.write(existing_content.encode('utf-8'))
                
                logger.info("UTF-8 BOM added successfully")
            else:
                logger.debug("CSV file already has UTF-8 BOM")
                
        except Exception as e:
            logger.warning(f"Could not ensure CSV BOM: {e}")
    
    def generate_questions(self, exam_name: str, language: str, question_type: str, 
                          difficulty: int, notes: str, num_questions: int, 
                          engines: List[EngineType]) -> List[Question]:
        """Generate questions using the specified AI engines"""
        logger.info(f"Generating {num_questions} questions for {exam_name} ({language}, {question_type}, difficulty {difficulty})")
        logger.info(f"Requested engines: {engines}")
        
        all_questions = []
        
        for engine in engines:
            try:
                logger.info(f"Attempting to generate questions with {engine} engine...")
                
                if engine == EngineType.gpt:
                    provider = OpenAIProvider()
                    logger.debug("OpenAI provider created successfully")
                elif engine == EngineType.gemini:
                    provider = GeminiProvider()
                    logger.debug("Gemini provider created successfully")
                elif engine == EngineType.anthropic:
                    provider = AnthropicProvider()
                    logger.debug("Anthropic provider created successfully")
                elif engine == EngineType.xai:
                    provider = XAIProvider()
                    logger.debug("XAI provider created successfully")
                else:
                    logger.warning(f"Unknown engine type: {engine}")
                    continue
                
                questions = provider.generate_questions(
                    exam_name, language, question_type, difficulty, notes, num_questions
                )
                
                logger.info(f"Successfully generated {len(questions)} questions with {engine} engine")
                all_questions.extend(questions)
                
            except ValueError as e:
                logger.warning(f"Engine {engine} not configured: {e}")
                continue
            except Exception as e:
                logger.error(f"Error generating questions with {engine} engine: {e}", exc_info=True)
                continue
        
        # Add to our in-memory storage
        self.questions.extend(all_questions)
        logger.info(f"Total questions in storage: {len(self.questions)}")
        
        return all_questions
    
    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """Get a question by its ID"""
        question = next((q for q in self.questions if q.id == question_id), None)
        if question:
            logger.debug(f"Found question {question_id[:8]}...")
        else:
            logger.warning(f"Question not found: {question_id}")
        return question
    
    def improve_question(self, question_id: str, comment: str = "") -> Optional[Question]:
        """Improve a question based on tutor comment"""
        logger.info(f"Improving question {question_id[:8]}... with comment: {comment[:50]}...")
        
        question = self.get_question_by_id(question_id)
        if not question:
            logger.error(f"Cannot revise question - not found: {question_id}")
            return None
        
        try:
            logger.info(f"Using {question.engine} engine to improve question")
            
            if question.engine == EngineType.gpt:
                provider = OpenAIProvider()
            elif question.engine == EngineType.gemini:
                provider = GeminiProvider()
            elif question.engine == EngineType.anthropic:
                provider = AnthropicProvider()
            elif question.engine == EngineType.xai:
                provider = XAIProvider()
            else:
                logger.error(f"Unknown engine type for revision: {question.engine}")
                return None
            
            improved_question = provider.improve_question(question, comment)
            
            # Update the question in our storage
            for i, q in enumerate(self.questions):
                if q.id == question_id:
                    self.questions[i] = improved_question
                    break
            
            logger.info(f"Question {question_id[:8]}... improved successfully to version {improved_question.version}")
            return improved_question
            
        except Exception as e:
            logger.error(f"Error improving question {question_id[:8]}...: {e}", exc_info=True)
            return None
    
    def approve_question(self, question_id: str) -> Optional[Question]:
        """Approve a question"""
        logger.info(f"Approving question {question_id[:8]}...")
        
        question = self.get_question_by_id(question_id)
        if not question:
            logger.error(f"Cannot approve question - not found: {question_id}")
            return None
        
        question.status = "approved"
        question.updated_at = datetime.now(timezone.utc)
        
        # Update in storage
        for i, q in enumerate(self.questions):
            if q.id == question_id:
                self.questions[i] = question
                break
        
        logger.info(f"Question {question_id[:8]}... approved successfully")
        return question
    
    def delete_question(self, question_id: str) -> bool:
        """Soft-delete a question (set status to deleted)"""
        logger.info(f"Soft-deleting question {question_id[:8]}...")
        
        question = self.get_question_by_id(question_id)
        if not question:
            logger.error(f"Cannot delete question - not found: {question_id}")
            return False
        
        if question.status == "deleted":
            logger.warning(f"Question {question_id[:8]}... is already deleted")
            return True
        
        question.status = "deleted"
        question.deleted_at = datetime.now(timezone.utc)
        question.updated_at = datetime.now(timezone.utc)
        
        # Update in storage
        for i, q in enumerate(self.questions):
            if q.id == question_id:
                self.questions[i] = question
                break
        
        logger.info(f"Question {question_id[:8]}... soft-deleted successfully")
        return True
    
    def export_question_to_csv(self, question_id: str) -> bool:
        """Export an approved question to CSV"""
        logger.info(f"Exporting question {question_id[:8]}... to CSV")
        
        question = self.get_question_by_id(question_id)
        if not question:
            logger.error(f"Cannot export question - not found: {question_id}")
            return False
        
        # STRICT VALIDATION: Only approved questions can be exported
        if question.status != "approved":
            logger.error(f"SECURITY VIOLATION: Attempted to export non-approved question {question_id[:8]}... - status is {question.status}, not approved")
            return False
        
        logger.info(f"Question {question_id[:8]}... is approved, proceeding with CSV export")
        
        try:
            # Prepare options as string
            options_str = ""
            if question.options:
                options_str = " | ".join(question.options)
            
            # Write to CSV
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    question.exam_name,
                    question.language,
                    question.question_type,
                    question.difficulty,
                    question.engine.value,
                    question.question,
                    options_str,
                    question.answer,
                    question.explanation,
                    question.version,
                    question.updated_at.isoformat()
                ])
            
            logger.info(f"Question {question_id[:8]}... exported to CSV successfully with Hebrew support")
            return True
        
        except Exception as e:
            logger.error(f"Error exporting question {question_id[:8]}... to CSV: {e}", exc_info=True)
            return False
    
    def can_export_question(self, question_id: str) -> bool:
        """Check if a question can be exported to CSV"""
        question = self.get_question_by_id(question_id)
        if not question:
            return False
        
        # Only approved questions can be exported
        return question.status == "approved"

    def verify_question(self, item_payload: dict) -> dict:
        """Run verification via configured providers and return aggregated result"""
        logger.info("Verifying question via providers...")
        model_votes = {}

        # GPT
        try:
            openai_provider = OpenAIProvider()
            parsed = openai_provider.verify_question(item_payload)
            model_votes["gpt"] = {
                "score": float(parsed.get("score", 0.0)),
                "verdict": str(parsed.get("verdict", "needs_revision")),
                "issues": parsed.get("issues", [])[:3] or [],
                "confidence": float(parsed.get("confidence", 0.0)),
            }
        except Exception as e:
            logger.warning(f"GPT verification failed: {e}")

        # Gemini
        try:
            gemini_provider = GeminiProvider()
            parsed = gemini_provider.verify_question(item_payload)
            model_votes["gemini"] = {
                "score": float(parsed.get("score", 0.0)),
                "verdict": str(parsed.get("verdict", "needs_revision")),
                "issues": parsed.get("issues", [])[:3] or [],
                "confidence": float(parsed.get("confidence", 0.1)),
            }
        except Exception as e:
            logger.warning(f"Gemini verification failed: {e}")

        # Anthropic
        try:
            anthropic_provider = AnthropicProvider()
            parsed = anthropic_provider.verify_question(item_payload)
            model_votes["anthropic"] = {
                "score": float(parsed.get("score", 0.0)),
                "verdict": str(parsed.get("verdict", "needs_revision")),
                "issues": parsed.get("issues", [])[:3] or [],
                "confidence": float(parsed.get("confidence", 0.1)),
            }
        except Exception as e:
            logger.warning(f"Anthropic verification failed: {e}")

        # xAI
        try:
            xai_provider = XAIProvider()
            parsed = xai_provider.verify_question(item_payload)
            model_votes["xai"] = {
                "score": float(parsed.get("score", 0.0)),
                "verdict": str(parsed.get("verdict", "needs_revision")),
                "issues": parsed.get("issues", [])[:3] or [],
                "confidence": float(parsed.get("confidence", 0.1)),
            }
        except Exception as e:
            logger.warning(f"xAI verification failed: {e}")

        if not model_votes:
            raise ValueError("No AI providers available for verification")

        scores = [vote["score"] for vote in model_votes.values()]
        mean_score = sum(scores) / len(scores)

        verdicts = [vote["verdict"] for vote in model_votes.values()]
        solver_agreement = len(set(verdicts)) == 1 if len(verdicts) > 1 else True

        if mean_score >= 8.0 and solver_agreement:
            final_verdict = "approve"
        elif mean_score >= 6.0:
            final_verdict = "needs_revision"
        else:
            final_verdict = "reject"

        issues = []
        for vote in model_votes.values():
            issues.extend(vote.get("issues", []))
        combined_issues = list(dict.fromkeys(issues))[:2]

        proposed_fix_hint = (
            f"Consider addressing: {', '.join(combined_issues)}" if final_verdict == "needs_revision" and combined_issues else None
        )

        return {
            "model_votes": model_votes,
            "aggregate": {
                "mean_score": round(mean_score, 1),
                "solver_agreement": solver_agreement,
                "final_verdict": final_verdict,
                "combined_issues": combined_issues,
            },
            "proposed_fix_hint": proposed_fix_hint,
        }
    
    def get_all_questions(self) -> List[Question]:
        """Get all questions in storage"""
        logger.debug(f"Returning {len(self.questions)} questions from storage")
        return self.questions.copy()
    
    def get_questions_by_status(self, status: str) -> List[Question]:
        """Get questions filtered by status"""
        if status == "in_progress":
            # in_progress includes draft and revised questions
            filtered_questions = [q for q in self.questions if q.status in ["draft", "revised"]]
            logger.debug(f"Returning {len(filtered_questions)} in-progress questions")
        elif status == "approved":
            filtered_questions = [q for q in self.questions if q.status == "approved"]
            logger.debug(f"Returning {len(filtered_questions)} approved questions")
        elif status == "deleted":
            filtered_questions = [q for q in self.questions if q.status == "deleted"]
            logger.debug(f"Returning {len(filtered_questions)} deleted questions")
        else:
            # Return all questions if status is not recognized
            filtered_questions = self.questions.copy()
            logger.debug(f"Unknown status '{status}', returning all {len(filtered_questions)} questions")
        
        return filtered_questions
    
    def unapprove_question(self, question_id: str) -> Optional[Question]:
        """Unapprove a question (set status back to revised)"""
        logger.info(f"Unapproving question {question_id[:8]}...")
        
        question = self.get_question_by_id(question_id)
        if not question:
            logger.error(f"Cannot unapprove question - not found: {question_id}")
            return None
        
        if question.status != "approved":
            logger.error(f"Cannot unapprove question {question_id[:8]}... - status is {question.status}, not approved")
            return None
        
        question.status = "revised"
        question.updated_at = datetime.now(timezone.utc)
        
        # Update in storage
        for i, q in enumerate(self.questions):
            if q.id == question_id:
                self.questions[i] = question
                break
        
        logger.info(f"Question {question_id[:8]}... unapproved successfully")
        return question
    
    def undelete_question(self, question_id: str) -> Optional[Question]:
        """Undelete a question (set status back to revised)"""
        logger.info(f"Undeleting question {question_id[:8]}...")
        
        question = self.get_question_by_id(question_id)
        if not question:
            logger.error(f"Cannot undelete question - not found: {question_id}")
            return None
        
        if question.status != "deleted":
            logger.error(f"Cannot undelete question {question_id[:8]}... - status is {question.status}, not deleted")
            return None
        
        question.status = "revised"
        question.deleted_at = None
        question.updated_at = datetime.now(timezone.utc)
        
        # Update in storage
        for i, q in enumerate(self.questions):
            if q.id == question_id:
                self.questions[i] = question
                break
        
        logger.info(f"Question {question_id[:8]}... undeleted successfully")
        return question
    
 
