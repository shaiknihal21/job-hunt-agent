"""Interactive terminal agent — no frontend required."""

import argparse
import sys

from app.agents.chat import parse_command
from app.database import SessionLocal, init_db
from app.config import get_auto_apply_sources, settings
from app.services.llm import llm_status
from app.services.auto_agent import format_auto_summary, run_daily_auto_apply
from app.services.runner import (
    approve_job,
    format_application,
    format_job,
    find_job,
    list_applications,
    list_pending,
    scan_jobs,
    skip_job,
    submit_application,
    update_application_status,
    upload_resume,
    weekly_status,
    format_source_stats_dict,
)
from app.agents.apply.naukri_login import run_naukri_login
from app.services.seed import seed_profile

BANNER = """
╔══════════════════════════════════════════════════╗
║           Job Hunt Agent (CLI Mode)              ║
║  Discovery: Naukri + LinkedIn (no API key)       ║
║  AI: Groq free tier only (not OpenAI)            ║
╚══════════════════════════════════════════════════╝
"""


def _context(db) -> str:
    pending = list_pending(db)
    apps = list_applications(db)
    ready = [a for a in apps if a.status == "pending_submit"]
    lines = [f"Pending approvals: {len(pending)}", f"Ready to submit: {len(ready)}"]
    if pending:
        lines.append("Top pending: " + "; ".join(format_job(j) for j in pending[:3]))
    return "\n".join(lines)


def _print_help():
    print(BANNER)
    print(f"  LLM: {llm_status()}")
    sal_line = f" · salary≥{settings.min_salary_lpa:.0f} LPA" if settings.min_salary_lpa > 0 else ""
    sources_label = "all sources" if get_auto_apply_sources() is None else settings.auto_apply_sources
    mode = settings.naukri_apply_mode
    print(f"  Apply mode: {mode} (Naukri) · auto sources: {sources_label}")
    print(f"  Auto cycle: score≥{settings.auto_apply_min_score} · ATS≥{settings.auto_apply_min_ats_score}{sal_line}")
    sources = ["Naukri"]
    if settings.include_linkedin:
        sources.append("LinkedIn")
    if settings.include_foundit:
        sources.append("Foundit")
    if settings.include_faang_careers:
        sources.append("Amazon/Microsoft/Google/NVIDIA")
    print(f"  Discovery: {', '.join(sources)}")
    print("""
Talk naturally or use commands:
  auto          Run full auto cycle (discover→tailor→apply)
  scan          Find and rank new jobs (manual mode)
  pending       Show approval queue
  approve #5    Approve job #5 (tailors resume)
  skip Microsoft  Skip by company name
  apply #3      Open browser to apply (application #3)
  upload resume.pdf
  login naukri   Save Naukri cookies for auto-apply
  track #3 applied   Mark submitted after you finish in browser
  status        Weekly summary
  help          Show commands
  quit          Exit
""")


def _execute(db, cmd) -> bool:
    """Run a parsed command. Returns False to exit."""
    try:
        if cmd.action == "help":
            _print_help()
            return True

        if cmd.action == "scan":
            print("⏳ Scanning Naukri + LinkedIn + Foundit + MNC career pages...")
            result = scan_jobs(db)
            print(f"✅ Found {result['discovered']} jobs · {result['pending_approval']} need your approval")
            for line in format_source_stats_dict(result.get("sources", [])):
                print(line)
            return True

        if cmd.action == "auto":
            print(f"⏳ Auto cycle: all sources, score≥{settings.auto_apply_min_score}, ATS≥{settings.auto_apply_min_ats_score}...")
            summary = run_daily_auto_apply(db)
            print(format_auto_summary(summary))
            return True

        if cmd.action == "pending":
            jobs = list_pending(db)
            if not jobs:
                print("No jobs pending. Run 'scan' to discover new roles.")
                return True
            print(f"\n📋 {len(jobs)} jobs waiting for approval:\n")
            for job in jobs:
                print(f"  {format_job(job)}")
                if job.score and job.score.red_flags:
                    print(f"     ⚠️  {job.score.red_flags[0]}")
            print("\n→ approve #ID  or  skip CompanyName")
            return True

        if cmd.action == "status":
            s = weekly_status(db)
            print("\n📊 Weekly summary:")
            print(f"  Discovered (7d):   {s['discovered_7d']}")
            print(f"  Applied (7d):      {s['applied_7d']}")
            print(f"  Interviews (7d):   {s['interviews_7d']}")
            print(f"  Rejected (7d):     {s.get('rejected_7d', 0)}")
            print(f"  Offers (7d):       {s.get('offers_7d', 0)}")
            print(f"  Pending approval:  {s['pending_approval']}")
            print(f"  Ready to submit:   {s['ready_to_submit']}")
            print(f"  Response rate:     {s['response_rate']}%")
            return True

        if cmd.action == "upload":
            if not cmd.file_path:
                print("Usage: upload /path/to/resume.pdf")
                return True
            result = upload_resume(db, cmd.file_path)
            print(f"✅ Resume uploaded: {result['filename']} ({result['chars_parsed']} chars parsed)")
            return True

        if cmd.action == "approve":
            job = find_job(db, job_id=cmd.job_id, company_hint=cmd.company_hint)
            if not job:
                print("Job not found. Run 'pending' to see the queue.")
                return True
            print(f"⏳ Tailoring resume for {job.title} @ {job.company}...")
            result = approve_job(db, job.id)
            print(f"✅ Approved → Application #{result['application_id']}")
            print(f"   Role:    {result.get('target_role', '—')}")
            print(f"   ATS:     {result.get('ats_before', '—')} → {result.get('ats_after', '—')}")
            print(f"   Status:  {result.get('validation_status', '—')}")
            print(f"   Summary: {result['summary'][:200]}")
            print(f"   Resume:  {result['resume_path']}")
            if result.get("pdf_path"):
                print(f"   PDF:     {result['pdf_path']}")
            if result.get("gaps_missing"):
                print(f"   Gaps:    {', '.join(result['gaps_missing'][:8])}")
            if result.get("validation_status") == "needs_review" and result.get("validation_errors"):
                print(f"   ⚠️  Review needed before submit")
            print(f"→ apply #{result['application_id']}  when ready to submit")
            return True

        if cmd.action == "skip":
            job = find_job(db, job_id=cmd.job_id, company_hint=cmd.company_hint)
            if not job:
                print("Job not found. Run 'pending' to see the queue.")
                return True
            result = skip_job(db, job.id)
            print(f"⏭️  Skipped: {result['title']} @ {result['company']}")
            return True

        if cmd.action == "apply":
            apps = list_applications(db)
            ready = [a for a in apps if a.status in ("pending_submit", "needs_review", "prepared")]
            app = None
            if cmd.job_id:
                app = next((a for a in ready if a.id == cmd.job_id), None)
            elif cmd.company_hint:
                hint = cmd.company_hint.lower()
                app = next(
                    (a for a in ready if a.job and hint in a.job.company.lower()),
                    None,
                )
            if not app:
                if ready:
                    print("Ready to submit:")
                    for a in ready:
                        print(f"  {format_application(a)}")
                else:
                    print("No applications ready. Approve a job first.")
                return True
            print(f"⏳ Opening browser for {app.job.title} @ {app.job.company}...")
            result = submit_application(db, app.id)
            if result["status"] == "applied":
                print(f"✅ APPLIED: {result['title']} @ {result['company']}")
            elif result["status"] == "awaiting_user":
                print(f"🌐 BROWSER OPEN — finish apply, then run:  track #{app.id} applied")
            else:
                print(f"📝 {result['status'].upper()}: {result['title']} @ {result['company']}")
            return True

        print(cmd.reply or "I didn't understand that. Type 'help'.")
        return True

    except ValueError as e:
        print(f"❌ {e}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return True


def run_interactive():
    init_db()
    db = SessionLocal()
    seed_profile(db)
    _print_help()

    while True:
        try:
            user_input = input("\n🤖 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Bye! Good luck with your job hunt.")
            break

        low = user_input.lower().strip()
        if low.startswith("login naukri"):
            try:
                run_naukri_login()
            except Exception as exc:
                print(f"❌ Login failed: {exc}")
            continue
        if low.startswith("track "):
            parts = user_input.split()
            app_id = next((int(p.lstrip("#")) for p in parts if p.lstrip("#").isdigit()), None)
            status = parts[-1].lower() if parts else ""
            if app_id and status in {"interview", "rejected", "offer", "applied"}:
                result = update_application_status(db, app_id, status)
                print(f"✅ Application #{result['application_id']} → {result['status']} ({result['title']} @ {result['company']})")
            else:
                print("Usage: track #3 interview  |  track #3 rejected  |  track #3 offer")
            continue

        cmd = parse_command(user_input, context=_context(db))
        if cmd.action == "unknown":
            print(cmd.reply or "Try: scan, pending, approve #5, apply #3, status, help")
            continue
        if not _execute(db, cmd):
            break

    db.close()


def run_once(command: str, args: argparse.Namespace):
    init_db()
    db = SessionLocal()
    seed_profile(db)

    try:
        if command == "scan":
            result = scan_jobs(db)
            print(f"Discovered: {result['discovered']}, Pending: {result['pending_approval']}")
            for line in format_source_stats_dict(result.get("sources", [])):
                print(line)
        elif command == "login":
            print(run_naukri_login()["message"])
        elif command == "track":
            result = update_application_status(db, args.id, args.status)
            print(f"{result['status']}: {result['title']} @ {result['company']}")
        elif command == "auto":
            summary = run_daily_auto_apply(db)
            print(format_auto_summary(summary))
        elif command == "pending":
            for job in list_pending(db):
                print(format_job(job))
        elif command == "status":
            print(weekly_status(db))
        elif command == "approve":
            result = approve_job(db, args.id)
            print(f"Approved → application #{result['application_id']}")
        elif command == "skip":
            result = skip_job(db, args.id)
            print(f"Skipped {result['title']} @ {result['company']}")
        elif command == "apply":
            result = submit_application(db, args.id)
            print(f"{result['status']}: {result['title']} @ {result['company']}")
        elif command == "upload":
            result = upload_resume(db, args.path)
            print(f"Uploaded {result['filename']}")
        else:
            run_interactive()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Job Hunt Agent — terminal interface")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Discover and rank jobs")
    sub.add_parser("auto", help="Full auto cycle: discover, tailor ATS resume, apply")
    sub.add_parser("pending", help="Show approval queue")
    sub.add_parser("status", help="Weekly summary")

    approve_p = sub.add_parser("approve", help="Approve a job by ID")
    approve_p.add_argument("id", type=int)

    skip_p = sub.add_parser("skip", help="Skip a job by ID")
    skip_p.add_argument("id", type=int)

    apply_p = sub.add_parser("apply", help="Submit application by ID")
    apply_p.add_argument("id", type=int)

    upload_p = sub.add_parser("upload", help="Upload master resume")
    upload_p.add_argument("path")

    login_p = sub.add_parser("login", help="Log in to Naukri and save session cookies")
    login_p.add_argument("site", nargs="?", default="naukri", choices=["naukri"])

    track_p = sub.add_parser("track", help="Update application status")
    track_p.add_argument("id", type=int)
    track_p.add_argument("status", choices=["interview", "rejected", "offer", "applied"])

    sub.add_parser("chat", help="Interactive chat mode (default)")

    args = parser.parse_args()
    if args.command is None or args.command == "chat":
        run_interactive()
    else:
        run_once(args.command, args)


if __name__ == "__main__":
    main()
