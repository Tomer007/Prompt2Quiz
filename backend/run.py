#!/usr/bin/env python3
"""
Startup script for QuizBuilder AI Backend
"""

import uvicorn
from main import app

if __name__ == "__main__":
    print("🚀 Starting QuizBuilder AI Backend...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("🔧 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    uvicorn.run(
        "main:app",
        host="::",
        port=8000,
        reload=True,
        log_level="info"
    )
