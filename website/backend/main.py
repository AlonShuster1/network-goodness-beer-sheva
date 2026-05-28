"""
FastAPI app exposing /api/calculate.

Loads the pre-built Beer Sheva Points pickle at startup so the request
handler only has to run the cheap Network construction + formulas.

Run from website/backend:
    uvicorn main:app --reload
"""

import os
import pickle
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from calculations import (
    build_network_from_nodes,
    formula3,
    formula4,
    formula5,
    formula6,
)


HERE = os.path.dirname(os.path.abspath(__file__))
PICKLE_PATH = os.path.join(HERE, "cache", "beer_sheva_points.pkl")
FRONTEND_DIR = os.path.abspath(os.path.join(HERE, "..", "frontend"))


app = FastAPI(title="Network Goodness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Pickle loading
# ---------------------------------------------------------

_points = None


def get_points():
    global _points
    if _points is None:
        if not os.path.exists(PICKLE_PATH):
            # First run: build the cache from the bundled GeoJSONs.
            print(f"[startup] Cache not found at {PICKLE_PATH}. Building (one-time, ~10s)…")
            from build_points_cache import build_and_save
            _points = build_and_save(PICKLE_PATH)
            print(f"[startup] Cache built: {len(_points.demand_zone_centers)} zones, "
                  f"{len(_points._demand_points)} demand points.")
            return _points
        with open(PICKLE_PATH, "rb") as f:
            _points = pickle.load(f)
    return _points


@app.on_event("startup")
def _warm_pickle():
    get_points()


# ---------------------------------------------------------
# Schemas
# ---------------------------------------------------------

class CalculateRequest(BaseModel):
    nodes: List[List[float]] = Field(
        ...,
        description="Ordered list of [lat, lon] pairs defining the network polyline.",
    )
    # Accepted but ignored — kept for spec compatibility. The server uses its
    # pre-loaded Beer Sheva demand points.
    points: Optional[List] = None


class CalculateResponse(BaseModel):
    L: float
    K: int
    network_inertia: float
    score3: float
    score4: float
    score5: float
    score6: float


# ---------------------------------------------------------
# Endpoint
# ---------------------------------------------------------

@app.post("/api/calculate", response_model=CalculateResponse)
def calculate(req: CalculateRequest):
    if len(req.nodes) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 nodes.")

    for i, node in enumerate(req.nodes):
        if len(node) != 2:
            raise HTTPException(status_code=400, detail=f"Node {i} must be [lat, lon].")

    points = get_points()
    net = build_network_from_nodes(req.nodes, points)

    return CalculateResponse(
        L=float(net.L),
        K=int(net.K),
        network_inertia=float(net.network_inertia),
        score3=float(formula3(net)),
        score4=float(formula4(net)),
        score5=float(formula5(net)),
        score6=float(formula6(net)),
    )


@app.get("/api/health")
def health():
    p = get_points()
    return {
        "status": "ok",
        "zones": len(p.demand_zone_centers),
        "demand_points": len(p._demand_points),
    }


# Serve the frontend last so it doesn't shadow /api/* routes.
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
