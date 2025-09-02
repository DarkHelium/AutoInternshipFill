# 🤖 AI Career Co-pilot

An intelligent Chrome extension that analyzes job descriptions, tailors resumes with AI, and automatically fills job application forms like Simplify.jobs but with advanced AI capabilities.

## ✨ Features

### 🎯 **Smart Job Analysis**
- AI-powered job description analysis
- Match score calculation (how well you fit the role)
- Requirement extraction and skill gap identification
- Salary range and remote policy detection

### 📝 **AI Resume Tailoring**
- Automatically tailors your resume for each job
- Maintains truthfulness while optimizing keywords
- ATS-friendly formatting and optimization
- Real-time ATS preview showing how systems will parse your resume

### 🔄 **Intelligent Auto-Fill**
- Context-aware form filling for major ATS platforms
- Supports Greenhouse, Lever, Ashby, Workday, LinkedIn, and more
- Uses tailored resume data for optimal applications
- Validates form completion before submission

### 📊 **Outcome Tracking & Learning**
- Track application outcomes (interviews, offers, rejections)
- AI learns from your success patterns
- Continuous improvement of matching and tailoring
- Performance analytics and insights

## 🏗️ Architecture

```
┌─────────────────┐    API Calls    ┌──────────────────┐
│  Chrome         │ ──────────────→ │  FastAPI         │
│  Extension      │                 │  Backend         │
│                 │                 │                  │
│  • Job Detection│                 │  • AI Services   │
│  • Form Filling │                 │  • Job Analysis  │
│  • UI/UX        │                 │  • Resume Engine │
└─────────────────┘                 └──────────────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  OpenAI/Claude   │
                                    │  APIs            │
                                    └──────────────────┘
```

## 🚀 Quick Start

### 1. Backend Setup

```bash
cd AutoInternshipFill
docker-compose up backend
```

The backend will be available at `http://localhost:8000`

### 2. Chrome Extension Installation

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right toggle)
3. Click "Load unpacked" and select the `chrome-extension` folder
4. Pin the extension to your toolbar

### 3. Web App (Paste Job Link)

1. Start the Next.js app
```
cd AutoInternshipFill/web
npm install
npm run dev
```
2. Open http://localhost:3100
3. Paste a job link and your info, then submit
4. A new tab opens with `?autofill=1&runId=...` and the extension autofills the page

### 3. Configuration

1. Click the extension icon and go to Settings
2. Add your OpenAI API key
3. Configure your preferences and constraints
4. Upload your base resume via the API

## ⚙️ Configuration

### API Keys
- **OpenAI API Key**: Required for AI analysis and resume tailoring
- Get yours at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### User Preferences
- **Experience Level**: Entry, Mid, Senior, Lead
- **Target Roles**: Software Engineer, Product Manager, etc.
- **Location Preferences**: Remote, specific cities
- **Salary Expectations**: Min/max salary ranges
- **Constraints**: Dealbreakers and preferences

## 🎮 How to Use

### 1. Upload Base Resume
```bash
curl -X POST http://localhost:8000/uploads/resumeUrl
# Use the returned URLs to upload your PDF
```

### 2. Job Analysis
1. Visit any job posting (LinkedIn, company career pages, etc.)
2. Extension automatically detects the job
3. Click "Analyze Job" for AI-powered analysis
4. Get match score and requirements breakdown

### 3. Resume Tailoring
1. After job analysis, click "Tailor Resume"
2. AI optimizes your resume for the specific role
3. Review changes and ATS preview
4. Download tailored PDF

### 4. Auto-Fill Application
1. Navigate to the job application form
2. Click "Auto-Fill Form" in the extension
3. Watch as fields are intelligently populated
4. Review and submit

## 🔧 API Endpoints

### Job Analysis
```http
POST /ai/analyze-job
{
  "job_url": "https://example.com/job",
  "job_description": "Software Engineer position..."
}
```

### Resume Tailoring
```http
POST /ai/tailor-resume
{
  "job_id": "job_123",
  "user_constraints": {...}
}
```

### ATS Preview
```http
POST /ai/ats-preview
{
  "job_id": "job_123"
}
```

### Outcome Tracking
```http
POST /ai/track-outcome
{
  "job_id": "job_123",
  "status": "interview",
  "notes": "Great conversation with hiring manager"
}
```

## 🛠️ Development

### Backend Development
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Extension Development
1. Make changes to extension files
2. Go to `chrome://extensions/`
3. Click refresh button on your extension
4. Test on job sites

### Environment Variables
```bash
OPENAI_API_KEY=your_openai_api_key
CORS_ORIGINS=*
FILES_DIR=/files
```

## 📋 Supported ATS Platforms

- **Greenhouse** (`*.greenhouse.io`)
- **Lever** (`jobs.lever.co`)
- **Ashby** (`*.ashbyhq.com`)
- **Workday** (`*.myworkdayjobs.com`)
- **iCIMS** (`*.icims.com`)
- **LinkedIn** (`linkedin.com/jobs`)
- **BambooHR** (`*.bamboohr.com`)
- And many more...

## 🔒 Privacy & Security

- Your API key is stored locally in Chrome
- Resume data is processed locally when possible
- No data is shared with third parties
- All AI processing uses your own API credentials

## 📊 Success Metrics

Track your job application success with built-in analytics:
- Application-to-response rate
- Interview conversion rate
- Match score vs. outcome correlation
- AI suggestion effectiveness

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

---

**Transform your job search with AI-powered intelligence! 🚀**
