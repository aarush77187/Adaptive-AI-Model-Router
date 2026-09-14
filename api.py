"""
api.py — FastAPI wrapper around router_core.py
-------------------------------------------------
Exposes:
    GET  /health         -> {"status": "ok"}
    POST /route           -> classify + call a model + return the result

Setup:
    pip install fastapi uvicorn groq
    export GROQ_API_KEY="your_key_here"

Run:
    uvicorn api:app --reload

Then try it at http://127.0.0.1:8000/docs (FastAPI's auto-generated
Swagger UI — good for demoing the endpoint without the Streamlit UI).
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import router_core as core


@asynccontextmanager
async def lifespan(app: FastAPI):
    core.init_db()
    yield


app = FastAPI(title="AI Model Router", lifespan=lifespan)


class RouteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The user's prompt")
    priority: str = Field(
        default="balanced",
        description="One of: balanced, speed, cost, quality",
    )


class RouteResponse(BaseModel):
    tier: str
    model_label: str
    model_name: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    output_text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/route", response_model=RouteResponse)
def route_endpoint(req: RouteRequest):
    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set on the server")

    if req.priority not in core.VALID_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail=f"priority must be one of {sorted(core.VALID_PRIORITIES)}",
        )

    try:
        result = core.route(req.prompt, priority=req.priority)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model call failed: {e}")

    return RouteResponse(
        tier=result.tier,
        model_label=result.label,
        model_name=result.model_name,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
        output_text=result.output_text,
    )
