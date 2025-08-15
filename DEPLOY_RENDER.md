# Deploy QuizBuilder AI to Render

## Prerequisites
- A Render account (free tier available)
- Your AI API keys ready

## Deployment Steps

### 1. Connect Your Repository
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub/GitLab repository
4. Select the QuizBuilder AI repository

### 2. Configure the Service
- **Name**: `quizbuilder-ai` (or your preferred name)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r backend/requirements.txt`
- **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Set Environment Variables
Add these environment variables in Render:
- `OPENAI_API_KEY`: Your OpenAI API key
- `GEMINI_API_KEY`: Your Google Gemini API key
- `XAI_API_KEY`: Your xAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key (optional)

### 4. Deploy
Click "Create Web Service" and wait for the build to complete.

### 5. Access Your App
Your app will be available at: `https://your-app-name.onrender.com`

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `XAI_API_KEY` | xAI API key | No |
| `ANTHROPIC_API_KEY` | Anthropic API key | No |

## Troubleshooting

### Build Failures
- Check that all dependencies are in `backend/requirements.txt`
- Ensure Python version compatibility

### Runtime Errors
- Check environment variables are set correctly
- Review Render logs for detailed error messages

### Static Files Not Loading
- Ensure frontend files are in the correct location
- Check the static files mount path in production

## Cost
- **Free Tier**: 750 hours/month, auto-sleep after 15 minutes of inactivity
- **Paid Plans**: Start at $7/month for always-on service

## Benefits of Render
- ✅ Easy deployment from Git
- ✅ Automatic HTTPS
- ✅ Global CDN
- ✅ Auto-scaling
- ✅ Built-in monitoring
- ✅ Free tier available
