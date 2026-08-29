# Setup on Another Laptop

## What’s included
- Full backend (FastAPI + LangGraph + Playwright agents)
- Full frontend (Next.js dashboard)
- `.env.example` — copy to `.env` and add your API keys

## What’s NOT included (reinstall on new laptop)
- `backend/.venv` — Python virtual environment
- `frontend/node_modules` — npm packages
- `.env` — your secrets (create fresh)
- `backend/data/jobhunt.db` — database (auto-created on first run)

---

## Step 1 — Copy the folder
Copy `job-hunt-agent` (or unzip `job-hunt-agent.zip`) to the new laptop.

## Step 2 — Install prerequisites
- **Python 3.11+** — https://python.org
- **Node.js 18+** — https://nodejs.org
- **Git** (optional)

## Step 3 — Backend setup

```bash
cd job-hunt-agent/backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium

# Create env file
copy ..\.env.example ..\.env        # Windows
cp ../.env.example ../.env          # Mac/Linux
```

Edit `.env` and add your Azure OpenAI keys:
```
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

Start backend:
```bash
uvicorn app.main:app --reload --port 8000
```

## Step 4 — Frontend setup

Open a **new terminal**:

```bash
cd job-hunt-agent/frontend
npm install
npm run dev
```

Open **http://localhost:3000**

## Step 5 — First use
1. Go to **Profile** → upload your resume (PDF/DOCX)
2. **Dashboard** → click **Scan for Jobs**
3. **Approvals** → approve matches
4. **Applications** → submit when ready

---

## Targeting rules (built-in)
- **Companies:** Product MNCs only (Microsoft, Google, Amazon, NVIDIA, Flipkart, etc.)
- **Excluded:** TCS, Infosys, Wipro, Accenture, etc.
- **Roles:** AI Engineer, Software Engineer, Data Engineer, ML Engineer
- **Location:** India on-site OK; outside India = remote/WFH only

## API docs
http://localhost:8000/docs
