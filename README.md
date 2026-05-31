# 🎯 AI Job Hunter & Mock Interview Coach

A production-ready AI-powered platform that helps you match jobs, generate cover letters, and practice interviews with a **stress-aware adversarial interviewer** — the only mock interview AI that reads your stress and adapts its personality in real time.

## 🏗️ Stack
- **Backend**: FastAPI (Python)
- **Frontend**: React + Tailwind CSS
- **Database**: PostgreSQL (local) → Azure SQL (production)
- **AI**: Azure OpenAI GPT-4 / GPT-4o-mini
- **Audio**: OpenAI Whisper (speech-to-text)
- **Storage**: Azure Blob Storage (resume PDFs)
- **Auth**: Supabase Auth (JWT)
- **Deployment**: Azure App Service + Azure Static Web Apps

## 🚀 Unique Feature
**Stress-Aware Adversarial Interviewer**: Analyzes filler words, hedging language, response latency, and answer brevity to compute a real-time stress score — then shifts the interviewer's persona (Challenger → Neutral → Prober → Supportive) accordingly.

## 📁 Structure
```
ai-job-hunter/
├── backend/
│   ├── agents/          # Router, Orchestrator, Sub-agents
│   ├── api/             # FastAPI route handlers
│   ├── core/            # Config, security, dependencies
│   ├── db/              # Models, migrations, session
│   ├── services/        # Business logic (resume, match, interview)
│   └── tests/           # Unit tests
├── frontend/
│   └── src/
│       ├── components/  # Reusable UI components
│       ├── pages/       # Route-level pages
│       ├── hooks/       # Custom React hooks
│       ├── store/       # State management (Zustand)
│       └── utils/       # API client, helpers
├── deployment/          # Azure deployment configs
└── docs/                # Architecture diagrams, API docs
```

## ⚡ Quick Start
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
alembic upgrade head   # run migrations
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## 🔐 Environment Variables
See `backend/.env.example` for all required variables.

## 📖 Build Steps
1. ✅ Project structure + setup (current)
2. ⏳ Database schema + models
3. ⏳ Resume upload + parsing
4. ⏳ Job matching system
5. ⏳ Interview question generator
6. ⏳ Audio input + stress detector
7. ⏳ Answer evaluation engine
8. ⏳ Memory + adaptive interview
9. ⏳ Frontend (React + Tailwind)
10. ⏳ Dashboard + charts
11. ⏳ Azure deployment
