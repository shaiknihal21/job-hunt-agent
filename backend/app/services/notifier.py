import asyncio

import httpx

from app.config import settings


async def send_telegram(message: str) -> bool:
    token = settings.notify_telegram_bot_token
    chat_id = settings.notify_telegram_chat_id
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": message})
        return response.status_code == 200


def notify_sync(message: str) -> bool:
    try:
        return asyncio.run(send_telegram(message))
    except Exception:
        return False


async def notify_approval_needed(job_title: str, company: str, score: float, url: str) -> None:
    message = (
        f"Job approval needed\n"
        f"{job_title} @ {company}\n"
        f"Score: {score:.0f}%\n"
        f"{url}"
    )
    await send_telegram(message)


def notify_pending_jobs(jobs: list) -> None:
    if not jobs:
        return
    lines = [f"📋 {len(jobs)} jobs need approval:"]
    for job in jobs[:5]:
        score = job.score.score if job.score else 0
        lines.append(f"• {job.title} @ {job.company} ({score:.0f}%)")
    if len(jobs) > 5:
        lines.append(f"... and {len(jobs) - 5} more")
    notify_sync("\n".join(lines))


def notify_auto_applied(title: str, company: str, score: float) -> None:
    notify_sync(f"✅ Auto-applied\n{title} @ {company}\nScore: {score:.0f}%")


def notify_auto_summary(summary: dict, source_lines: list[str] | None = None) -> None:
    lines = [
        "🤖 Auto cycle complete",
        f"Discovered: {summary.get('discovered', 0)}",
        f"Applied: {summary.get('applied', 0)}",
        f"Needs review: {summary.get('needs_review', 0)}",
    ]
    if source_lines:
        lines.extend(source_lines)
    if summary.get("errors"):
        lines.append("Errors: " + "; ".join(summary["errors"][:2]))
    notify_sync("\n".join(lines))
