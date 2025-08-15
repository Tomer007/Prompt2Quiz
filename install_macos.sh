#!/bin/bash

echo "🍎 QuizBuilder AI - macOS Installation Script"
echo "============================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    echo "💡 Please install Python 3 first:"
    echo "   1. Visit https://www.python.org/downloads/"
    echo "   2. Download and install Python 3.11+ for macOS"
    echo "   3. Make sure to check 'Add Python to PATH' during installation"
    echo "   4. Restart your terminal and run this script again"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYTHON_VERSION found"

# Check if pip3 is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not available"
    echo "💡 Installing pip3..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py --user
    rm get-pip.py
    echo "✅ pip3 installed"
else
    echo "✅ pip3 found"
fi

# Create virtual environment
echo "📦 Setting up Python virtual environment..."
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Deactivate virtual environment
deactivate
cd ..

echo ""
echo "🎉 Installation completed successfully!"
echo ""
echo "🚀 To start the application:"
echo "   1. Backend: ./start_backend.sh"
echo "   2. Frontend: ./start_frontend.sh"
echo ""
echo "💡 Make sure to set up your API keys in the .env file first!"
echo "   cp env.example .env"
echo "   # Edit .env with your OPENAI_API_KEY"
