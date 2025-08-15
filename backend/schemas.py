from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime
from enum import Enum

class EngineType(str, Enum):
    gpt = "gpt"
    gemini = "gemini"
    anthropic = "anthropic"
    xai = "xai"

class QuestionStatus(str, Enum):
    draft = "draft"
    revised = "revised"
    approved = "approved"
    deleted = "deleted"

class GenerateRequest(BaseModel):
    exam_name: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    question_type: str = Field(..., min_length=1)
    difficulty: int = Field(..., ge=1, le=10)
    notes: str = ""
    num_questions: int = Field(..., ge=1, le=50)
    engines: List[EngineType] = Field(default_factory=lambda: [EngineType.gpt, EngineType.gemini])

class Question(BaseModel):
    id: str
    engine: EngineType
    exam_name: str
    language: str
    question_type: str
    difficulty: int
    notes: str
    question: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str
    improvement_explanation: Optional[str] = None
    version: int = 1
    status: QuestionStatus = QuestionStatus.draft
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

class ImproveRequest(BaseModel):
    question_id: str
    comment: Optional[str] = ""

class ApproveRequest(BaseModel):
    question_id: str

class DeleteRequest(BaseModel):
    question_id: str

class ExportRequest(BaseModel):
    question_id: str

class UnapproveRequest(BaseModel):
    question_id: str

class UndeleteRequest(BaseModel):
    question_id: str

class VerifyRequest(BaseModel):
    id: str
    engine: EngineType
    exam_name: str
    language: str
    question_type: str
    difficulty: int
    question: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str

class ModelVote(BaseModel):
    score: float
    verdict: str
    issues: List[str]
    confidence: float

class VerificationResponse(BaseModel):
    model_votes: dict[str, ModelVote]
    aggregate: dict[str, Union[str, float, bool, List[str]]]
    proposed_fix_hint: Optional[str] = None

class GenerateResponse(BaseModel):
    questions: List[Question]

class ImproveResponse(BaseModel):
    question: Question

class ApproveResponse(BaseModel):
    question: Question

class DeleteResponse(BaseModel):
    success: bool

class ExportResponse(BaseModel):
    success: bool
    file_path: str
