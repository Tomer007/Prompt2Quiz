from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
import logging
import time
 
from typing import Optional

from schemas import (
    GenerateRequest, GenerateResponse, ImproveRequest, ImproveResponse,
    ApproveRequest, ApproveResponse, DeleteRequest, DeleteResponse,
    ExportRequest, ExportResponse, UnapproveRequest, UndeleteRequest
)
from services import QuestionService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="QuizBuilder AI", version="1.0.0")

# Static files mount (serve frontend)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Add production environment detection
IS_PRODUCTION = os.getenv("RENDER", "false").lower() == "true"

# Update the static files mount for production
if IS_PRODUCTION:
    # In production, serve static files from the same directory
    FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
else:
    # In development, use the original path
    FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:3000", 
        "http://127.0.0.1:5173",
        "http://[::]:5173",
        "http://[::1]:5173"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize the question service
logger.info("Initializing QuizBuilder AI application...")
question_service = QuestionService()
logger.info("Question service initialized successfully")

@app.middleware("http")
async def log_requests(request, call_next):
    """Log all incoming requests"""
    start_time = time.time()
    
    # Log request details
    logger.info(f"Request: {request.method} {request.url.path}")
    logger.info(f"Client: {request.client.host}:{request.client.port}")
    logger.info(f"User-Agent: {request.headers.get('user-agent', 'Unknown')}")
    
    # Process request
    response = await call_next(request)
    
    # Log response details
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    return response

@app.get("/")
async def root():
    """Serve the frontend index.html"""
    logger.info("Frontend index requested")
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# Health check endpoint moved to /health
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"message": "QuizBuilder AI API", "version": "1.0.0"}

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle CORS preflight requests"""
    logger.info(f"CORS preflight request for: {full_path}")
    return {"message": "OK"}

@app.post("/generate", response_model=GenerateResponse)
async def generate_questions(request: GenerateRequest):
    """Generate practice questions using AI engines"""
    logger.info(f"Generate request received: {request.exam_name}, {request.language}, {request.question_type}, difficulty {request.difficulty}, {request.num_questions} questions, engines: {request.engines}")
    
    try:
        start_time = time.time()
        
        # Use async concurrent pipeline
        questions, evaluations, winner_id = await question_service.async_generate_questions(
            exam_name=request.exam_name,
            language=request.language,
            question_type=request.question_type,
            difficulty=request.difficulty,
            notes=request.notes,
            num_questions=request.num_questions,
            engines=request.engines
        )
        
        process_time = time.time() - start_time
        
        if not questions:
            logger.error("No questions generated - no AI engines configured")
            raise HTTPException(
                status_code=503, 
                detail="No AI engines are configured. Please check your API keys."
            )
        
        logger.info(f"Successfully generated {len(questions)} questions in {process_time:.3f}s")
        try:
            logger.info(f"Questions from engines: {[q.engine for q in questions]}")
        except Exception:
            pass
        
        return GenerateResponse(questions=questions, evaluations=evaluations, winner_id=winner_id)
        
    except ValueError as e:
        logger.error(f"Validation error in generate request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in generate request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/improve", response_model=ImproveResponse)
async def improve_question(request: ImproveRequest):
    """Improve a question based on tutor comment"""
    logger.info(f"Improve request received for question {request.question_id[:8]}...")
    logger.info(f"Comment: {request.comment[:100]}...")
    
    try:
        start_time = time.time()
        
        improved_question = await question_service.async_improve_question(
            question_id=request.question_id,
            comment=request.comment
        )
        
        process_time = time.time() - start_time
        
        if not improved_question:
            logger.error(f"Question not found for improve: {request.question_id}")
            raise HTTPException(status_code=404, detail="Question not found")
        
        logger.info(f"Successfully improved question {request.question_id[:8]}... in {process_time:.3f}s")
        logger.info(f"New version: {improved_question.version}, Engine: {improved_question.engine}")
        
        return ImproveResponse(question=improved_question)
        
    except Exception as e:
        logger.error(f"Error revising question {request.question_id[:8]}...: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/approve", response_model=ApproveResponse)
async def approve_question(request: ApproveRequest):
    """Approve a question"""
    logger.info(f"Approve request received for question {request.question_id[:8]}...")
    
    try:
        approved_question = question_service.approve_question(
            question_id=request.question_id
        )
        
        if not approved_question:
            logger.error(f"Question not found for approval: {request.question_id}")
            raise HTTPException(status_code=404, detail="Question not found")
        
        logger.info(f"Successfully approved question {request.question_id[:8]}...")
        logger.info(f"Question details: {approved_question.exam_name}, {approved_question.language}, {approved_question.engine}")
        
        return ApproveResponse(question=approved_question)
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error approving question {request.question_id[:8]}...: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/delete", response_model=DeleteResponse)
async def delete_question(request: DeleteRequest):
    """Delete a question"""
    logger.info(f"Delete request received for question {request.question_id[:8]}...")
    
    try:
        success = question_service.delete_question(
            question_id=request.question_id
        )
        
        if not success:
            logger.error(f"Question not found for deletion: {request.question_id}")
            raise HTTPException(status_code=404, detail="Question not found")
        
        logger.info(f"Successfully deleted question {request.question_id[:8]}...")
        
        return DeleteResponse(success=True)
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error deleting question {request.question_id[:8]}...: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/export", response_model=ExportResponse)
async def export_question(request: ExportRequest):
    """Export an approved question to CSV"""
    logger.info(f"Export request received for question {request.question_id[:8]}...")
    
    try:
        success = question_service.export_question_to_csv(
            question_id=request.question_id
        )
        
        if not success:
            logger.error(f"Export failed for question {request.question_id[:8]}... - not approved")
            raise HTTPException(
                status_code=400, 
                detail="Question must be approved before export"
            )
        
        logger.info(f"Successfully exported question {request.question_id[:8]}... to CSV")
        
        return ExportResponse(
            success=True,
            file_path=question_service.get_csv_file_path()
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error exporting question {request.question_id[:8]}...: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/csv")
async def download_csv():
    """Download the accumulated CSV file"""
    logger.info("CSV download request received")
    
    try:
        csv_file_path = question_service.get_csv_file_path()
        
        if not os.path.exists(csv_file_path):
            logger.error("CSV file not found")
            raise HTTPException(status_code=404, detail="CSV file not found")
        
        logger.info(f"CSV download successful: {csv_file_path}")
        
        return FileResponse(
            path=csv_file_path,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={os.path.basename(csv_file_path)}"
            }
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error downloading CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get('/csv/list')
async def list_csv_files():
    """List available CSV files under the data directory so users can choose which to download."""
    try:
        base_path = question_service.get_data_dir()
        if not os.path.isdir(base_path):
            return {"files": []}
        files = []
        for name in os.listdir(base_path):
            if not name.lower().endswith('.csv'):
                continue
            full = os.path.join(base_path, name)
            if not os.path.isfile(full):
                continue
            stat = os.stat(full)
            files.append({
                "filename": name,
                "size_bytes": stat.st_size,
                "modified_at": int(stat.st_mtime)
            })
        # Sort by modified desc
        files.sort(key=lambda f: f["modified_at"], reverse=True)
        return {"files": files}
    except Exception as e:
        logger.error(f"Error listing CSV files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get('/csv/file/{filename}')
async def download_specific_csv(filename: str):
    """Download a specific CSV file from the data directory by its filename (no paths)."""
    try:
        base_path = question_service.get_data_dir()
        # Prevent directory traversal
        safe_name = os.path.basename(filename)
        target = os.path.join(base_path, safe_name)
        if not os.path.isfile(target):
            raise HTTPException(status_code=404, detail="CSV file not found")
        return FileResponse(
            path=target,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={safe_name}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading specific CSV '{filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/questions")
async def get_questions(status: Optional[str] = None):
    """Get questions in storage, optionally filtered by status"""
    logger.info(f"Get questions request received with status filter: {status}")
    
    try:
        if status:
            questions = question_service.get_questions_by_status(status)
            logger.info(f"Returning {len(questions)} questions with status '{status}'")
        else:
            questions = question_service.get_all_questions()
            logger.info(f"Returning {len(questions)} questions (no status filter)")
        
        return {"questions": questions}
        
    except Exception as e:
        logger.error(f"Error getting questions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/unapprove", response_model=ApproveResponse)
async def unapprove_question(request: UnapproveRequest):
    """Unapprove a question (set status back to revised)"""
    logger.info(f"Unapprove request received for question {request.question_id[:8]}...")
    
    try:
        unapproved_question = question_service.unapprove_question(
            question_id=request.question_id
        )
        
        if not unapproved_question:
            logger.error(f"Question not found for unapproval: {request.question_id}")
            raise HTTPException(status_code=404, detail="Question not found")
        
        logger.info(f"Successfully unapproved question {request.question_id[:8]}...")
        
        return ApproveResponse(question=unapproved_question)
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error unapproving question {request.question_id[:8]}...: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/undelete", response_model=ApproveResponse)
async def undelete_question(request: UndeleteRequest):
    """Undelete a question (set status back to revised)"""
    logger.info(f"Undelete request received for question {request.question_id[:8]}...")
    
    try:
        undeleted_question = question_service.undelete_question(
            question_id=request.question_id
        )
        
        if not undeleted_question:
            logger.error(f"Question not found for undeletion: {request.question_id}")
            raise HTTPException(status_code=404, detail="Question not found")
        
        logger.info(f"Successfully undeleted question {request.question_id[:8]}...")
        
        return ApproveResponse(question=undeleted_question)
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error undeleting question {request.question_id[:8]}...: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/can-export/{question_id}")
async def can_export_question(question_id: str):
    """Check if a question can be exported to CSV"""
    logger.info(f"Can-export check request received for question {question_id[:8]}...")
    
    try:
        can_export = question_service.can_export_question(question_id)
        
        if can_export:
            logger.info(f"Question {question_id[:8]}... can be exported (status: approved)")
        else:
            logger.info(f"Question {question_id[:8]}... cannot be exported (not approved or not found)")
        
        return {"can_export": can_export}
        
    except Exception as e:
        logger.error(f"Error checking export eligibility for question {question_id[:8]}...: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("🚀 QuizBuilder AI Backend starting up...")
    logger.info(f"Environment: {'Production (Render)' if IS_PRODUCTION else 'Development'}")
    logger.info(f"Python version: {os.sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Frontend directory: {FRONTEND_DIR}")
    
    # Check environment variables
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    xai_key = os.getenv("XAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if openai_key:
        logger.info("✅ OPENAI_API_KEY configured")
    else:
        logger.warning("⚠️ OPENAI_API_KEY not configured")
    
    if gemini_key:
        logger.info("✅ GEMINI_API_KEY configured")
    else:
        logger.warning("⚠️ GEMINI_API_KEY not configured")
    
    if xai_key:
        logger.info("✅ XAI_API_KEY configured")
    else:
        logger.warning("⚠️ XAI_API_KEY not configured")
    
    if anthropic_key:
        logger.info("✅ ANTHROPIC_API_KEY configured")
    else:
        logger.warning("⚠️ ANTHROPIC_API_KEY not configured")
    
    logger.info("🎉 QuizBuilder AI Backend startup complete!")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("🛑 QuizBuilder AI Backend shutting down...")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server...")
    uvicorn.run(app, host="::", port=8000, reload=True, log_level="info")
