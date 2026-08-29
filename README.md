# Personal AI Job Hunting Agent

Multi-agent job application system for **AI Engineer**, **Software Engineer**, and **Data Engineer** roles — with optional human approval before apply.

## What this agent actually does

| Step | Automated? | Reliability |
|------|------------|-------------|
| Find jobs (Naukri, LinkedIn, Amazon, etc.) | ✅ Yes | High |
| Score & rank matches | ✅ Yes | High |
| Tailor ATS resume per job | ✅ Yes | High |
| **Apply on Naukri** | 🌐 **Assisted** (default) | High — opens Chrome, you finish chatbot |
| Apply on LinkedIn / careers pages | 🌐 Assisted | High — opens page, you submit |
| Full hands-off Naukri apply | ⚠️ Optional (`NAUKRI_APPLY_MODE=full`) | Low — chatbot breaks often |

**Honest workflow:** `./run.sh scan` → `approve #ID` → `./run.sh apply #ID` → finish in browser → `./run.sh track #ID applied`

## Modes

- **Manual (`scan` → `pending` → `approve`):** You review every job before tailoring.
- **Auto (`./run.sh auto`):** Discovers, tailors, opens browser for top matches. You complete apply in ~2 min each.

## Target Roles

- AI Engineer / Gen AI Engineer / ML Engineer
- Software Engineer / Backend Engineer / Full Stack Engineer
- Data Engineer / Analytics Engineer

## Location Rules

- **India:** on-site, hybrid, and remote roles are all eligible
- **Outside India:** only **remote / WFH / online** roles are kept — on-site abroad roles are filtered out

## Features

- Profile management with resume upload (PDF/DOCX)
- Multi-source job discovery: Naukri, Foundit (product MNCs only), Microsoft, Google, Amazon, NVIDIA careers
- Hybrid job ranking (keyword heuristics + optional Groq LLM scoring)
- Resume tailoring and cover letter generation (no fabrication guardrails)
- Playwright semi-automated apply (Naukri) with submit approval
- Application tracking and weekly reports
- LangGraph workflow with approval interrupts
- Scheduled auto-apply when backend runs (`SCAN_INTERVAL_HOURS`, default 24h)

## Quick Start (Simple — CLI only, no Node.js)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
pip install -r requirements.txt
playwright install chromium
cp ../.env.example ../.env         # Add GROQ_API_KEY

python -m app                      # Interactive chat agent
```

**Example session:**
```
🤖 You: upload ~/resume.pdf
🤖 You: scan
🤖 You: pending
🤖 You: approve #611    # job ID from pending list
🤖 You: apply #5        # application ID shown after approve
🤖 You: status
```

One-shot commands: `python -m app scan`, `python -m app pending`, `python -m app approve 5`

## Quick Start (Full — with web dashboard)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
copy ..\.env.example ..\.env  # Add GROQ_API_KEY (free at console.groq.com)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Workflow

1. Upload your master resume on the **Profile** page
2. Click **Scan for Jobs** on the dashboard
3. Review matches in **Approvals** — approve or skip
4. Approved jobs get tailored resume + cover letter
5. Submit applications from the **Applications** tracker

## Environment Variables

See [.env.example](.env.example). Set `GROQ_API_KEY` for AI ranking and resume tailoring (free tier at [console.groq.com](https://console.groq.com)). **Job discovery uses Playwright on Naukri/LinkedIn — no API key needed for scraping.** Without Groq, heuristic scoring and rule-based tailoring still work.

## Architecture

- **Backend:** FastAPI + LangGraph + Playwright + SQLite
- **Frontend:** Next.js dashboard
- **Agents:** Discovery → Ranking → Approval → Tailoring → Apply → Track

## Company Focus

**Default:** All companies are eligible — TCS, Infosys, startups, FAANG, etc. No blocklist unless you set `FILTER_EXCLUDED_COMPANIES=true` in `.env`.

**Discovery:** Naukri + LinkedIn + Foundit + career pages (Amazon, Microsoft, Google, NVIDIA when `INCLUDE_FAANG_CAREERS=true`).

**Apply:** `AUTO_APPLY_SOURCES=*` (default) — Naukri gets full auto-submit; LinkedIn and career pages open in Chrome for you to finish (login/forms vary by site).

## Security Notes

- LinkedIn/Indeed full automation is not included (ToS risk). LinkedIn assist mode opens browser for manual submit.
- Browser sessions stored locally in `backend/data/browser_sessions/` (gitignored).
- Max 5 applications per day by default.

## API Docs

http://localhost:8000/docs
