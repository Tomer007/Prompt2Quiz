#!/bin/bash

echo "🚀 Starting QuizBuilder AI Single Server..."
echo "📍 Frontend & Backend will be available at: http://localhost:8000"
echo "📚 API documentation at: http://localhost:8000/docs"
echo "🔧 Press Ctrl+C to stop the server"
echo "----------------------------------------"

cd backend

# Check if requirements are installed
if [ ! -d "venv" ]; then
    echo "📦 Setting up Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📥 Installing dependencies..."
    pip3 install -r requirements.txt
else
    echo "🔧 Activating virtual environment..."
    source venv/bin/activate
fi

echo "🚀 Starting single server (serves both frontend and backend)..."
echo "🟢 Open http://localhost:8000 in your browser"

# Start the server
python3 run.py
