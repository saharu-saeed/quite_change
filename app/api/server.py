"""FastAPI surface for the quiet_change agent.

Run with:  uvicorn app.api.server:app --reload
Then open: http://127.0.0.1:8000/
"""
from __future__ import annotations
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.subagents import quiet_change

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Quiet Change API")

UI_PATH = Path(__file__).parent / "ui.html"
DEMO_PATH = Path(__file__).parent / "demo.html"


class QuietChangeRequest(BaseModel):
    codes: list[str] = Field(..., min_length=1, description="4-digit Japanese stock codes")


class MultiYearRequest(BaseModel):
    codes: list[str] = Field(..., min_length=1, description="4-digit Japanese stock codes")
    min_year: int = Field(2020, ge=2000, le=2100, description="Earliest fiscal year (period_end) to include")
    run_tests: bool = Field(False, description="When true, attach internal-consistency self-test results to each pair")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return UI_PATH.read_text(encoding="utf-8")


@app.get("/demo", response_class=HTMLResponse)
def demo() -> str:
    """Senior-demo presentation view of the Quiet Change agent.
    Cleaner / more visual than the analyst UI at /. Added 2026-05-12."""
    return DEMO_PATH.read_text(encoding="utf-8")


@app.post("/quiet-change")
def quiet_change_endpoint(req: QuietChangeRequest) -> dict:
    results = quiet_change.run(req.codes)
    return {"count": len(results), "results": results}


@app.post("/quiet-change/multi-year")
def quiet_change_multi_year_endpoint(req: MultiYearRequest) -> dict:
    results = quiet_change.run_multi_year(
        req.codes, min_year=req.min_year, run_tests=req.run_tests,
    )
    return {"count": len(results), "results": results}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
