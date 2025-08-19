# 🚀 QuizBuilder AI

A simple, clean AI practice question generator that works with multiple AI engines (GPT, Gemini, Anthropic, xAI) to create practice questions in any language and subject.

## ✨ Features

- **Multi-AI Support**: Generate questions using OpenAI GPT, Google Gemini, Anthropic Claude, and xAI Grok
- **Multi-Language**: Questions can be generated in any language while keeping the UI in English
- **Question Types**: Support for various question types (Numerical, Verbal, Fractions, Percents, Management, etc.)
- **Smart Review Loop**: Add tutor comments to get improved versions of questions
- **Selection Round (Tournament)**: Cross-evaluate candidates across engines, show per-engine scores, ranks, points, and winner
- **Tabbed Interface**: Organize questions by status (In Progress, Approved, Deleted)
- **CSV Export**: Export approved questions to CSV (one CSV per day) and download any historical CSV via a file picker
- **Clean UI**: Minimal, functional design with no over-design or animations
- **Single Server**: Consolidated frontend and backend in one server

## 🏗️ Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, LangChain
- **Frontend**: Plain HTML + CSS + JavaScript (no frameworks)
- **AI Providers**: 
  - OpenAI gpt-4o-mini
  - Google Gemini 2.0 Flash
  - Anthropic Claude 3.5 Sonnet
  - xAI Grok
- **Storage**: In-memory for session data, CSV export to disk
- **Architecture**: Single server serving both frontend and backend

## 📁 Project Structure

```
Prompt2Quiz/
├── backend/
│   ├── main.py          # FastAPI application with static file serving
│   ├── providers.py     # AI provider implementations
│   ├── schemas.py       # Pydantic data models
│   ├── services.py      # Business logic
│   ├── requirements.txt # Python dependencies
│   └── run.py          # Startup script
├── frontend/
│   ├── index.html       # Main HTML file
│   ├── src/
│   │   ├── main.js      # Application entry point
│   │   ├── app.js       # Main application logic
│   │   ├── api.js       # API client
│   │   ├── components/
│   │   │   ├── QuestionCard.js      # Question display component
│   │   │   ├── ApprovedQuestionCard.js # Approved questions
│   │   │   └── DeletedQuestionCard.js  # Deleted questions
│   │   └── app.css      # Styles
│   └── data/            # CSV export directory
├── install_macos.sh     # macOS installation script
├── start_single_server.sh # Single server startup script
├── .env.example         # Environment variables template
└── README.md            # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key (required)
- Google Gemini API key (optional)
- Anthropic API key (optional)
- xAI API key (optional)

### 🍎 macOS Setup (Recommended)

1. **Automated installation:**
   ```bash
   chmod +x install_macos.sh
   ./install_macos.sh
   ```

2. **Set environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start the single server:**
   ```bash
   ./start_single_server.sh
   ```

4. **Open your browser** and go to: http://localhost:8000

### 🔧 Manual Setup

#### Backend Setup

1. **Install Python dependencies:**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip3 install -r requirements.txt
   deactivate
   cd ..
   ```

2. **Set environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run the single server:**
   ```bash
   cd backend
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   python3 run.py
   ```

4. **Access the app** at: http://localhost:8000

## 🔑 Environment Variables

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional - Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
# OR
GOOGLE_API_KEY=your_google_api_key_here

# Optional - Anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-latest

# Optional - xAI
XAI_API_KEY=your_xai_api_key_here
XAI_MODEL=grok-1
XAI_BASE_URL=https://api.xai.com/v1
```

## 📱 Usage

### Generating Questions

1. Fill out the form with:
   - **Exam Name**: e.g., GMAT, CCAT, SAT, Math, SJT, Personality
   - **Language**: e.g., English, Hebrew, Arabic, Spanish
   - **Question Type**: e.g., Numerical, Verbal, Fractions, Percents, Management
   - **Difficulty**: 1-10 scale
   - **Notes**: Additional context for the AI
   - **AI Engines**: Select GPT, Gemini, Anthropic, xAI, or any combination
  
  The app currently generates one candidate per selected engine per round (the form defaults to 1 request).

2. Click "Generate Questions"

### Managing Questions

The app has three main tabs:

#### 📝 In Progress
- Shows draft and revised questions
- Actions: Improve, Approve, Delete

#### ✅ Approved
- Shows approved questions ready for export
- Actions: Download CSV, Unapprove

#### 🗑️ Deleted
- Shows soft-deleted questions
- Actions: Restore, Remove Permanently

### Question Actions

- **Send Comment & Improve**: Add tutor feedback to get an improved version
- **Approve & Add to CSV**: Mark question as approved and export to CSV
- **Delete**: Soft-delete question (moves to Deleted tab)

### Selection Round Panel

- After generating, a "Selection Round Results" panel appears above the in‑progress list.
- Tabs: one tab per engine candidate (ordered by rank), plus a STATS tab.
- Each candidate tab shows the full question card and an "Evaluations" table (per-engine scores, verdicts, confidence, issues).

### Export

- **Download CSV**: Click the "Download CSV" button to open a file picker listing all CSVs in the data directory (newest first). Select a file to download.
- The backend writes one CSV per day (UTC): `export_YYYYMMDD.csv`.
- CSV includes: `exam_name, language, question_type, difficulty, engine, question, options, answer, explanation, version, approved_at` and uses UTF‑8 BOM for Hebrew support.

## 🔌 API Endpoints

- `GET /` - Serve frontend
- `GET /health` - Health check
- `POST /generate` - Generate questions
- `POST /improve` - Improve question based on comment
- `POST /approve` - Approve a question
- `POST /unapprove` - Unapprove a question
- `POST /delete` - Soft-delete a question
- `POST /undelete` - Restore a deleted question
- `POST /export` - Export question to CSV
- `GET /csv` - Download today's CSV file
- `GET /csv/list` - List available CSV files
- `GET /csv/file/{filename}` - Download a specific CSV file by name
- `GET /questions` - Get questions by status
<!-- /verify endpoint removed -->

## 🧪 Test the Setup

### Generate Test Questions

1. **Exam Name**: Math Test
2. **Language**: English
3. **Question Type**: Fractions
4. **Difficulty**: 5
5. **Notes**: Basic fraction operations
6. **AI Engines**: GPT (uncheck others if you don't have the keys)

Click "Generate Questions" (or press Enter in the form; Ctrl/Cmd+Enter in the notes textarea) and wait for the AI to create questions.

### Expected Results

- Candidate question cards appear in the Selection Round tabs (winner first), and the in‑progress list reflects your current queue.
- Each card shows the question, answer, explanation, and status.
- You can add tutor comments and request improvements.
- You can approve questions and export them to CSV.

## 🔧 Troubleshooting

### Common Issues

1. **"No AI engines are configured"**
   - Check your `.env` file has the correct API keys
   - Ensure the backend is running on port 8000

2. **"ModuleNotFoundError: No module named 'uvicorn'"**
   - Run `./install_macos.sh` to install dependencies
   - Or manually: `cd backend && venv/bin/pip3 install uvicorn[standard]`

3. **"localhost:8000 refused to connect"**
   - Make sure the server is running: `./start_single_server.sh`
   - Check that port 8000 is not in use by another process

4. **Python/pip not found (macOS)**
   - Run `./install_macos.sh` to set up Python environment
   - Make sure Python 3.11+ is installed from python.org
   - Check that Python is added to PATH during installation

5. **Anthropic provider errors**
   - The app now uses LangChain wrapper to avoid proxy issues
   - Check your `ANTHROPIC_API_KEY` is correct

### Backend Logs

Check the terminal where you're running the server for:
- API request logs
- Error messages
- AI provider responses

### Frontend Debugging

Open browser developer tools (F12) and check:
- Console tab for JavaScript errors
- Network tab for API request failures

## 📱 Usage Examples

### Generate Hebrew Math Questions
- **Language**: Hebrew
- **Question Type**: Percents
- **Difficulty**: 6
- **Notes**: Business mathematics applications

### Create Spanish Management Questions
- **Language**: Spanish
- **Question Type**: Management
- **Difficulty**: 8
- **Notes**: Leadership and team management scenarios

### Build English SAT Prep
- **Language**: English
- **Question Type**: Verbal
- **Difficulty**: 7
- **Notes**: Critical reading and vocabulary

## 🎯 Development

### Adding New AI Providers

1. Create a new provider class in `backend/providers.py`
2. Implement the required methods: `generate_questions()`, `improve_question()`, and `verify_question()`
3. Add the provider to the `QuestionService.generate_questions()` method

### Modifying the UI

The frontend uses vanilla JavaScript and CSS. Modify the files in `frontend/src/` to customize the appearance and behavior.

### Server Architecture

The app now uses a single server approach:
- FastAPI backend serves the frontend static files
- Frontend makes same-origin API calls
- No CORS issues or separate servers needed

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review the backend logs for error details
3. Ensure all dependencies are properly installed
4. For macOS users, try running `./install_macos.sh` first
5. Check that your API keys have sufficient credits/quota

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**Happy Question Building! 🎓**
