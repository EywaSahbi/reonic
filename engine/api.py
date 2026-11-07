"""Engine HTTP API per CONTRACT.md: `uv run uvicorn api:app --port 8000`. No state; the logic is in design.py."""
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from design import PRICES, VERSION, design, explain

app = FastAPI(title="reo engine")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:8001"],
                   allow_methods=["*"], allow_headers=["*"])


class DesignRequest(BaseModel):
    facts: dict = {}
    locks: dict = {}
    prices: dict = {}


class ExplainRequest(DesignRequest):
    component: Literal["pv", "battery", "heatpump", "wallbox"]


@app.get("/health")
def health():
    return {"ok": True, "params_version": VERSION}


@app.get("/prices")
def prices():
    return PRICES


@app.post("/design")
def post_design(req: DesignRequest):
    try:
        return design(req.facts, req.locks, req.prices)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, str(e))


@app.post("/explain")
def post_explain(req: ExplainRequest):
    try:
        return explain(req.facts, req.locks, req.prices, req.component)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, str(e))
