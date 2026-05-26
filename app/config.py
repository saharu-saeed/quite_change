"""Central config: tickers, period pair, thresholds, paths."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# Load .env from project root before anything reads os.environ. Idempotent;
# safe to call again elsewhere. Keeps secrets (EDINET_API_KEY, etc.) out of
# shell profiles while still being available to every module that imports
# from app.config (which the whole project transitively does).
load_dotenv(ROOT / ".env")

DATA_RAW = ROOT / "data" / "raw"
DATA_MANUAL = ROOT / "data" / "manual"
DATA_CACHE = ROOT / "data" / "cache"
OUTPUTS = ROOT / "outputs"
for _p in (DATA_RAW, DATA_MANUAL, DATA_CACHE, OUTPUTS):
    _p.mkdir(parents=True, exist_ok=True)


@dataclass
class Company:
    code: str           # 4-digit Japanese ticker
    name: str
    role: str           # "template" | "candidate"
    template_key: str | None = None   # which pattern: growth_driven / gradual_improvement / crisis_forced
    template_segment: str | None = None


@dataclass
class Config:
    companies: list[Company] = field(default_factory=lambda: [
        # Correction 4 integration: templates live in app/templates/library.py.
        # These rows are candidates ONLY — do not add role="template" entries
        # here. The old り そなHD / ヤーマン / ワールド template rows were
        # retired because the template library is now the single source of
        # truth (10 templates, EDINET-sourced).
        Company("4755", "楽天グループ", "candidate"),
        Company("3923", "ラクス",      "candidate"),
        Company("9984", "ソフトバンクグループ", "candidate"),
        Company("6758", "ソニーグループ",       "candidate"),
        Company("5233", "太平洋セメント",   "candidate"),
        Company("1928", "積水ハウス",       "candidate"),
        Company("3040", "ソリトン",         "candidate"),
        Company("3565", "アセンテック",     "candidate"),
    ])
    period_prev: str = "2024Q4"
    period_curr: str = "2025Q3"
    car_window: tuple[int, int] = (-1, 5)
    # Correction 3: market-model estimation window parameters.
    car_estimation_window: int = 120    # trading days for OLS of α/β
    car_estimation_gap: int = 30        # trading days between est window and event day
    car_min_estimation_days: int = 100  # skip company if fewer valid obs
    change_score_high: float = 0.20     # segment_Δ=0 caps composite max; 0.20 is realistic cutoff
    price_reaction_low: float = 0.03    # |CAR| cutoff (3%)
    # TOPIX benchmark. yfinance doesn't carry the raw TOPIX index reliably,
    # so we use NEXT FUNDS TOPIX ETF (1306.T), which tracks TOPIX.
    benchmark_ticker: str = "1306.T"
    # Bedrock-hosted Claude model ID (overridable via BEDROCK_MODEL_ID env)
    claude_model: str = "us.anthropic.claude-opus-4-6-v1"


CONFIG = Config()
