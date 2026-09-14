"""
router_core.py — shared routing logic
--------------------------------------
Same logic as router_v1.py, refactored so both the FastAPI app and any
standalone script can import it, plus one addition: a `priority`
parameter that lets the caller override the rule-based classification.

Priorities:
    "balanced" -> use classify_prompt() as before (default)
    "speed"    -> force the fastest model
    "cost"     -> force the cheapest model
    "quality"  -> force the most powerful model

Note: in the current 3-model registry, "speed" and "cost" both land on
Model A (it's both the fastest and the cheapest). That's fine for now —
if you add a model that's cheap but not fast (or vice versa), split
this into two separate lookups instead of both pointing at "simple".
"""

import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from dotenv import load_dotenv
from groq import Groq

load_dotenv()  # reads GROQ_API_KEY from a .env file if present
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "router_history.db")


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    name: str
    label: str
    price_in: float   # $ per 1M input tokens
    price_out: float  # $ per 1M output tokens


MODELS = {
    "simple": ModelConfig(
        name="llama-3.1-8b-instant",
        label="Model A (fast/cheap)",
        price_in=0.05,
        price_out=0.08,
    ),
    "medium": ModelConfig(
        name="gemma2-9b-it",
        label="Model B (balanced)",
        price_in=0.20,
        price_out=0.20,
    ),
    "complex": ModelConfig(
        name="llama-3.3-70b-versatile",
        label="Model C (powerful)",
        price_in=0.59,
        price_out=0.79,
    ),
}

PRIORITY_OVERRIDES = {
    "speed": "simple",
    "cost": "simple",
    "quality": "complex",
}
VALID_PRIORITIES = {"balanced", "speed", "cost", "quality"}


# ---------------------------------------------------------------------------
# Classification (used only when priority == "balanced")
# ---------------------------------------------------------------------------

CODE_PATTERN = re.compile(
    r"\b(def|class|import|function|algorithm|regex|SQL|API|code|bug|compile)\b",
    re.IGNORECASE,
)
REASONING_PATTERN = re.compile(
    r"\b(explain|analyze|compare|design|why|trade-?off|architecture|prove|derive|optimi[sz]e)\b",
    re.IGNORECASE,
)


def classify_prompt(prompt: str) -> str:
    """Return 'simple', 'medium', or 'complex' based on cheap heuristics."""
    word_count = len(prompt.split())
    has_code = bool(CODE_PATTERN.search(prompt))
    has_reasoning = bool(REASONING_PATTERN.search(prompt))

    score = 0
    score += min(word_count // 10, 3)
    score += 2 if has_reasoning else 0
    score += 1 if has_code else 0

    if score <= 1:
        return "simple"
    elif score <= 3:
        return "medium"
    else:
        return "complex"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            prompt TEXT NOT NULL,
            word_count INTEGER NOT NULL,
            has_code INTEGER NOT NULL,
            has_reasoning INTEGER NOT NULL,
            priority TEXT NOT NULL,
            tier TEXT NOT NULL,
            model_name TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def log_request(prompt: str, priority: str, result: "RouteResult") -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO requests (
            timestamp, prompt, word_count, has_code, has_reasoning,
            priority, tier, model_name, latency_ms, input_tokens, output_tokens, cost_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            prompt,
            len(prompt.split()),
            int(bool(CODE_PATTERN.search(prompt))),
            int(bool(REASONING_PATTERN.search(prompt))),
            priority,
            result.tier,
            result.model_name,
            result.latency_ms,
            result.input_tokens,
            result.output_tokens,
            result.cost_usd,
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

@dataclass
class RouteResult:
    tier: str
    label: str
    model_name: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    output_text: str


def route(prompt: str, priority: str = "balanced") -> RouteResult:
    """Pick a tier (via rules, or forced by `priority`), call the model, log it."""
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {VALID_PRIORITIES}, got {priority!r}")

    tier = PRIORITY_OVERRIDES[priority] if priority != "balanced" else classify_prompt(prompt)
    config = MODELS[tier]

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=config.name,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = (time.perf_counter() - start) * 1000

    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    cost = (
        (input_tokens / 1_000_000) * config.price_in
        + (output_tokens / 1_000_000) * config.price_out
    )

    result = RouteResult(
        tier=tier,
        label=config.label,
        model_name=config.name,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        output_text=response.choices[0].message.content,
    )
    log_request(prompt, priority, result)
    return result
