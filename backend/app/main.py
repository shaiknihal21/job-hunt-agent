import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import applications, approvals, jobs, profile
from app.config import TARGET_ROLES
from app.database import SessionLocal, init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.services.seed import seed_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_profile(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Job Hunt Agent",
    description="Personal AI Job Hunting Agent — AI, Software, and Data Engineer roles at product MNCs",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(approvals.router)
app.include_router(applications.router)


@app.get("/health")
def health():
    return {"status": "ok", "target_roles": TARGET_ROLES, "focus": "product_mncs"}
