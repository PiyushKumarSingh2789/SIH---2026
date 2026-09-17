import os
from dotenv import load_dotenv

# Load .env BEFORE anything else reads os.getenv() -- must be the very first thing that runs,
# and main.py must be the entrypoint (not imported by something else first) for this to work.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.risk import router as risk_router
from app.api.v1.projects import router as projects_router
from app.api.v1.imports import router as imports_router
from app.api.v1.cases import router as cases_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.audit import router as audit_router
from app.api.v1.compliance import router as compliance_router

app = FastAPI(title="SIH26102 - MPLADS Risk Intelligence Platform", version="0.1.0")

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(imports_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
