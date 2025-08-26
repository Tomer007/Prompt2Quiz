import csv
import os
import uuid
import logging
import asyncio
import random
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone
from schemas import Question, EngineType, QuestionStatus
from providers import OpenAIProvider, GeminiProvider, AnthropicProvider, XAIProvider

# Configure logging for services
logger = logging.getLogger(__name__)

class QuestionService:
    def __init__(self):
        logger.info("Initializing QuestionService...")
        self.questions: List[Question] = []
        # Resolve data directory to an absolute path next to the backend folder
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
        # Use one CSV file per day (UTC): <data_dir>/export_YYYYMMDD.csv
        self.csv_file_path = self._current_csv_path_for_today()
        # Provider cache for reuse (keep-alive clients/sessions)
        self._provider_cache: Dict[EngineType, object] = {}
        self._ensure_csv_directory()
        self._initialize_csv()
        logger.info(f"QuestionService initialized with CSV path: {self.csv_file_path}")
    
    def _ensure_csv_directory(self):
        """Ensure the CSV directory exists"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            logger.debug(f"CSV directory ensured: {self.data_dir}")
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

    def _current_csv_path_for_today(self) -> str:
        """Build the CSV path for today's date (UTC)."""
        today_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        return os.path.join(self.data_dir, f"export_{today_str}.csv")

    def _rotate_csv_if_new_day(self):
        """Ensure the CSV file path points to today's file; re-init if day changed."""
        expected_path = self._current_csv_path_for_today()
        if self.csv_file_path != expected_path:
            self.csv_file_path = expected_path
            self._ensure_csv_directory()
            self._initialize_csv()
            logger.info(f"Rotated CSV to today's file: {self.csv_file_path}")

    def get_csv_file_path(self) -> str:
        """Public accessor that also rotates file at day boundaries."""
        self._rotate_csv_if_new_day()
        return self.csv_file_path

    def get_data_dir(self) -> str:
        """Absolute path to the data directory containing CSV files."""
        # Ensure directory exists before returning
        self._ensure_csv_directory()
        return self.data_dir
    
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
                           engines: List[EngineType]) -> Tuple[List[Question], Dict[str, Dict[str, dict]], Optional[str]]:
        """Tournament-style generation and cross-evaluation.

        Flow:
        1) Each engine generates ONE candidate question.
        2) Each engine evaluates ALL candidates (not including its own) and produces a score.
        3) For each evaluator, rank candidates by score (desc) and assign points N..1.
        4) Sum points across evaluators and declare a winner.

        Returns: (questions, evaluations, winner_id)
        - questions: list of all candidate questions
        - evaluations: mapping question_id -> engine -> ranked vote payload
        - winner_id: id of best-scoring question
        """

        logger.info(
            "Tournament generation for %s (%s, %s, difficulty %s) using engines: %s",
            exam_name, language, question_type, difficulty, engines
        )

        def provider_for(engine: EngineType):
            if engine == EngineType.gpt:
                return OpenAIProvider()
            if engine == EngineType.gemini:
                return GeminiProvider()
            if engine == EngineType.anthropic:
                return AnthropicProvider()
            if engine == EngineType.xai:
                return XAIProvider()
            raise ValueError(f"Unknown engine type: {engine}")

        # 1) Each engine generates exactly one candidate question
        candidates: Dict[EngineType, Question] = {}
        for engine in engines:
            try:
                provider = provider_for(engine)
                generated = provider.generate_questions(
                    exam_name, language, question_type, difficulty, notes, 1
                )
                if not generated:
                    logger.warning("%s did not return a question", engine)
                    continue
                q = generated[0]
                candidates[engine] = q
                logger.info("Engine %s produced candidate %s", engine, q.id[:8])
            except Exception as e:
                logger.error("Error generating with %s: %s", engine, e, exc_info=True)

        if not candidates:
            logger.error("No candidates were generated")
            return [], {}, None

        # 2) Cross-evaluate all candidates with each engine
        evaluations: Dict[str, Dict[str, dict]] = {}
        engines_effective = list(candidates.keys())
        num_cands = len(engines_effective)

        def build_payload(question: Question) -> dict:
            return {
                "id": question.id,
                "engine": question.engine,
                "exam_name": question.exam_name,
                "language": question.language,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "question": question.question,
                "options": question.options,
                "answer": question.answer,
                "explanation": question.explanation,
            }

        # Raw scores per evaluator for ranking
        for evaluator in engines_effective:
            try:
                eval_provider = provider_for(evaluator)
            except Exception as e:
                logger.warning("Evaluator %s unavailable: %s", evaluator, e)
                continue

            scores_for_evaluator: List[Tuple[str, float, dict]] = []  # (qid, score, vote)
            for cand_engine, cand in candidates.items():
                # Skip self-evaluation: an engine must not evaluate its own candidate
                if cand_engine == evaluator:
                    continue
                try:
                    parsed = eval_provider.verify_question(build_payload(cand))
                    score = float(parsed.get("score", 0.0))
                    vote = {
                        "score": score,
                        "verdict": str(parsed.get("verdict", "needs_revision")),
                        "issues": parsed.get("issues", [])[:3] or [],
                        "confidence": float(parsed.get("confidence", 0.0)),
                    }
                    scores_for_evaluator.append((cand.id, score, vote))
                except Exception as e:
                    logger.warning("Evaluator %s failed on %s: %s", evaluator, cand.id[:8], e)

            # Rank by score desc; tie-break by question id for determinism
            scores_for_evaluator.sort(key=lambda t: (t[1], t[0]), reverse=True)
            for rank_index, (qid, _score, vote) in enumerate(scores_for_evaluator, start=1):
                points = max(num_cands - rank_index + 1, 1)
                vote_with_rank = {**vote, "rank": rank_index, "points": points}
                evaluations.setdefault(qid, {})[evaluator.value] = vote_with_rank
            

        # 3) Sum points across evaluators to find winner
        totals: Dict[str, int] = {}
        for qid, engine_votes in evaluations.items():
            totals[qid] = sum(v.get("points", 0) for v in engine_votes.values())

        if not totals:
            logger.error("No evaluations available; returning candidates without winner")
            # Add candidates to storage and return
            all_candidates = list(candidates.values())
            self.questions.extend(all_candidates)
            logger.info(f"All candidates: {all_candidates}")
            return all_candidates, evaluations, None

        # Winner: highest total points, tie-break by mean score then id
        def mean_score(qid: str) -> float:
            votes = evaluations.get(qid, {}).values()
            scores = [v.get("score", 0.0) for v in votes]
            return sum(scores) / len(scores) if scores else 0.0

        winner_id = max(totals.keys(), key=lambda qid: (totals[qid], mean_score(qid), qid))

        # 4) Add candidates to storage
        all_candidates = list(candidates.values())
        self.questions.extend(all_candidates)
        logger.info("Tournament winner: %s", winner_id[:8])
        logger.info(f"All candidates: {all_candidates}")
        logger.info(f"Evaluations: {evaluations}")
        logger.info(f"Winner: {winner_id}")

        return all_candidates, evaluations, winner_id

    # -------------------------
    # Async concurrent variant
    # -------------------------
    async def async_generate_questions(self, exam_name: str, language: str, question_type: str,
                                       difficulty: int, notes: str, num_questions: int,
                                       engines: List[EngineType]) -> Tuple[List[Question], Dict[str, Dict[str, dict]], Optional[str]]:
        """Concurrent tournament-style generation and cross-evaluation using asyncio.

        1) Generate one candidate per engine concurrently (provider.generate_questions in thread pool)
        2) Evaluate all candidates concurrently (skip self-evaluation), with a global semaphore cap
        3) Rank per-evaluator, assign points, then pick a winner by total points (tie-break by mean score)
        """

        logger.info(
            "[async] Tournament generation for %s (%s, %s, difficulty %s) using engines: %s",
            exam_name, language, question_type, difficulty, engines
        )

        def provider_for(engine: EngineType):
            return self._get_provider(engine)

        # Helper: run blocking call in thread with timeout and light retries
        async def _to_thread_with_retry(callable_fn, *args, timeout: float = 30.0, retries: int = 1, jitter: float = 0.3):
            attempt = 0
            last_exc = None
            while attempt <= retries:
                try:
                    return await asyncio.wait_for(asyncio.to_thread(callable_fn, *args), timeout=timeout)
                except Exception as exc:  # timeout or provider error
                    last_exc = exc
                    if attempt >= retries:
                        break
                    # backoff with jitter
                    await asyncio.sleep((2 ** attempt) * (0.5 + random.random() * jitter))
                    attempt += 1
            raise last_exc

        # 1) Concurrent generation: one candidate per engine
        async def _gen_one(engine: EngineType) -> Optional[Question]:
            try:
                provider = provider_for(engine)
                generated = await _to_thread_with_retry(
                    provider.generate_questions,
                    exam_name, language, question_type, difficulty, notes, 1,
                    timeout=40.0, retries=1,
                )
                if not generated:
                    return None
                q = generated[0]
                logger.info("[async] Engine %s produced candidate %s", engine, q.id[:8])
                return q
            except Exception as e:
                logger.error("[async] Error generating with %s: %s", engine, e, exc_info=True)
                return None

        gen_tasks = [asyncio.create_task(_gen_one(engine)) for engine in engines]
        gen_results = await asyncio.gather(*gen_tasks)
        candidates: Dict[EngineType, Question] = {}
        for engine, res in zip(engines, gen_results):
            if res is not None:
                candidates[engine] = res

        if not candidates:
            logger.error("[async] No candidates were generated")
            return [], {}, None

        # 2) Concurrent cross-evaluation
        engines_effective = list(candidates.keys())
        num_cands = len(engines_effective)

        def build_payload(question: Question) -> dict:
            return {
                "id": question.id,
                "engine": question.engine,
                "exam_name": question.exam_name,
                "language": question.language,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "question": question.question,
                "options": question.options,
                "answer": question.answer,
                "explanation": question.explanation,
            }

        # Global concurrency cap for verification calls
        sem = asyncio.Semaphore(8)

        async def _verify_one(evaluator: EngineType, cand: Question) -> Optional[Tuple[str, str, float, dict]]:
            # returns (evaluator_name, qid, score, vote)
            if evaluator == cand.engine:
                return None  # skip self-evaluation
            try:
                eval_provider = provider_for(evaluator)
            except Exception as e:
                logger.warning("[async] Evaluator %s unavailable: %s", evaluator, e)
                return None
            async with sem:
                try:
                    parsed = await _to_thread_with_retry(
                        eval_provider.verify_question,
                        build_payload(cand),
                        timeout=30.0, retries=1,
                    )
                    score = float(parsed.get("score", 0.0))
                    vote = {
                        "score": score,
                        "verdict": str(parsed.get("verdict", "needs_revision")),
                        "issues": parsed.get("issues", [])[:3] or [],
                        "confidence": float(parsed.get("confidence", 0.0)),
                    }
                    return evaluator.value, cand.id, score, vote
                except Exception as e:
                    logger.warning("[async] Evaluator %s failed on %s: %s", evaluator, cand.id[:8], e)
                    return None

        verify_tasks = []
        for evaluator in engines_effective:
            for cand in candidates.values():
                verify_tasks.append(asyncio.create_task(_verify_one(evaluator, cand)))

        verify_results = await asyncio.gather(*verify_tasks)

        # Fold results per evaluator to rank
        per_evaluator: Dict[str, List[Tuple[str, float, dict]]] = {}
        for item in verify_results:
            if not item:
                continue
            evaluator_name, qid, score, vote = item
            per_evaluator.setdefault(evaluator_name, []).append((qid, score, vote))

        evaluations: Dict[str, Dict[str, dict]] = {}
        for evaluator_name, rows in per_evaluator.items():
            # rank by score desc, tie-break by question id
            rows.sort(key=lambda t: (t[1], t[0]), reverse=True)
            for rank_index, (qid, _score, vote) in enumerate(rows, start=1):
                points = max(num_cands - rank_index + 1, 1)
                vote_with_rank = {**vote, "rank": rank_index, "points": points}
                evaluations.setdefault(qid, {})[evaluator_name] = vote_with_rank

        # 3) Winner
        totals: Dict[str, int] = {}
        for qid, engine_votes in evaluations.items():
            totals[qid] = sum(v.get("points", 0) for v in engine_votes.values())

        if not totals:
            logger.error("[async] No evaluations available; returning candidates without winner")
            all_candidates = list(candidates.values())
            self.questions.extend(all_candidates)
            return all_candidates, evaluations, None

        def mean_score(qid: str) -> float:
            votes = evaluations.get(qid, {}).values()
            scores = [v.get("score", 0.0) for v in votes]
            return sum(scores) / len(scores) if scores else 0.0

        winner_id = max(totals.keys(), key=lambda qid: (totals[qid], mean_score(qid), qid))

        # Add to storage
        all_candidates = list(candidates.values())
        self.questions.extend(all_candidates)
        logger.info("[async] Tournament winner: %s", winner_id[:8])
        return all_candidates, evaluations, winner_id

    # Provider reuse helper
    def _get_provider(self, engine: EngineType):
        cached = self._provider_cache.get(engine)
        if cached is not None:
            return cached
        if engine == EngineType.gpt:
            provider = OpenAIProvider()
        elif engine == EngineType.gemini:
            provider = GeminiProvider()
        elif engine == EngineType.anthropic:
            provider = AnthropicProvider()
        elif engine == EngineType.xai:
            provider = XAIProvider()
        else:
            raise ValueError(f"Unknown engine type: {engine}")
        self._provider_cache[engine] = provider
        return provider

    async def _to_thread_with_retry(self, callable_fn, *args, timeout: float = 30.0, retries: int = 1, jitter: float = 0.3):
        attempt = 0
        last_exc = None
        while attempt <= retries:
            try:
                return await asyncio.wait_for(asyncio.to_thread(callable_fn, *args), timeout=timeout)
            except Exception as exc:
                last_exc = exc
                if attempt >= retries:
                    break
                await asyncio.sleep((2 ** attempt) * (0.5 + random.random() * jitter))
                attempt += 1
        raise last_exc

    async def async_improve_question(self, question_id: str, comment: str = "") -> Optional[Question]:
        """Improve a question using non-blocking provider call with timeout/retry, reusing provider client."""
        logger.info(f"[async] Improving question {question_id[:8]}... with comment: {comment[:50]}...")
        question = self.get_question_by_id(question_id)
        if not question:
            logger.error(f"[async] Cannot improve question - not found: {question_id}")
            return None

        try:
            provider = self._get_provider(question.engine)
            # Run blocking improve in thread with timeout/retry
            improved_question = await self._to_thread_with_retry(
                provider.improve_question,
                question,
                comment,
                timeout=20.0,
                retries=2,
            )

            # Update storage
            for i, q in enumerate(self.questions):
                if q.id == question_id:
                    self.questions[i] = improved_question
                    break

            logger.info(f"[async] Question {question_id[:8]}... improved successfully to version {improved_question.version}")
            return improved_question
        except Exception as e:
            logger.error(f"[async] Error improving question {question_id[:8]}...: {e}", exc_info=True)
            return None
    
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
        
        question.status = QuestionStatus.approved
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
        
        if question.status == QuestionStatus.deleted:
            logger.warning(f"Question {question_id[:8]}... is already deleted")
            return True
        
        question.status = QuestionStatus.deleted
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
        if question.status != QuestionStatus.approved:
            logger.error(f"SECURITY VIOLATION: Attempted to export non-approved question {question_id[:8]}... - status is {question.status}, not approved")
            return False
        
        logger.info(f"Question {question_id[:8]}... is approved, proceeding with CSV export")
        # Ensure we are writing to today's CSV file
        self._rotate_csv_if_new_day()
        
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
        return question.status == QuestionStatus.approved

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
            filtered_questions = [q for q in self.questions if q.status in [QuestionStatus.draft, QuestionStatus.revised]]
            logger.debug(f"Returning {len(filtered_questions)} in-progress questions")
        elif status == "approved":
            filtered_questions = [q for q in self.questions if q.status == QuestionStatus.approved]
            logger.debug(f"Returning {len(filtered_questions)} approved questions")
        elif status == "deleted":
            filtered_questions = [q for q in self.questions if q.status == QuestionStatus.deleted]
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
        
        if question.status != QuestionStatus.approved:
            logger.error(f"Cannot unapprove question {question_id[:8]}... - status is {question.status}, not approved")
            return None
        
        question.status = QuestionStatus.revised
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
        
        if question.status != QuestionStatus.deleted:
            logger.error(f"Cannot undelete question {question_id[:8]}... - status is {question.status}, not deleted")
            return None
        
        question.status = QuestionStatus.revised
        question.deleted_at = None
        question.updated_at = datetime.now(timezone.utc)
        
        # Update in storage
        for i, q in enumerate(self.questions):
            if q.id == question_id:
                self.questions[i] = question
                break
        
        logger.info(f"Question {question_id[:8]}... undeleted successfully")
        return question
    
 
