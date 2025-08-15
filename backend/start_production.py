#!/usr/bin/env python3
"""
Production startup script for QuizBuilder AI on Render
"""

import os
import uvicorn
from main import app

if __name__ == "__main__":
    # Get port from Render environment variable
    port = int(os.environ.get("PORT", 8000))
    
    print("🚀 Starting QuizBuilder AI Production Server...")
    print(f"📍 Server will be available on port: {port}")
    print("🌍 Environment: Production (Render)")
    print("🔧 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    # Start the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Bind to all interfaces for Render
        port=port,
        reload=False,  # Disable reload in production
        log_level="info"
    )
