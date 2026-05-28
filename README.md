# Network Goodness — Beer Sheva

An interactive web app for scoring and comparing urban transit networks in **Beer Sheva, Israel**, using formulas from an academic paper on *Network Goodness Calculus*.

Draw a network on the map, get scores instantly, save snapshots, and compare multiple alternatives side by side.

![status](https://img.shields.io/badge/status-working-brightgreen)

---

## What's in this repo

```
.
├── solara_app/                 # Original Solara prototype
├── material/                   # Source paper + reference notebook (NG_calculation3.ipynb)
├── ng_demand_points/
│   └── beer_sheva/             # Cached OSM building footprints for 19 neighborhoods
└── website/
    ├── backend/
    │   ├── calculations.py     # Network, Points, formula3-6 (extracted verbatim from notebook)
    │   ├── build_points_cache.py
    │   ├── main.py             # FastAPI app — /api/calculate and static frontend
    │   └── cache/              # Generated pickle (not committed)
    └── frontend/
        ├── index.html          # Single-file Leaflet UI
        └── hoods.json          # 19 neighborhood polygons
```

## How it works

- **Backend (Python / FastAPI)**: pre-loads ~14,000 demand points (one per building, weighted by neighborhood population) for 19 Beer Sheva neighborhoods. Each `/api/calculate` request takes a list of `[lat, lon]` nodes (the network polyline) and returns `L`, `K`, `network_inertia`, and `score3`–`score6`.
- **Frontend (Leaflet)**: click the map to drop draggable markers, see scores update live, save the network as a colored snapshot, and compare multiple networks in a table.

All calculation logic lives in Python; the frontend only handles the map and API calls.

---

## Run it locally

### Prerequisites
- **Python 3.10+** (3.13 tested)

### Quick start — one command

**Windows:**
```bat
git clone https://github.com/AlonShuster1/network-goodness-beer-sheva.git
cd network-goodness-beer-sheva
run.bat
```

**Mac / Linux:**
```bash
git clone https://github.com/AlonShuster1/network-goodness-beer-sheva.git
cd network-goodness-beer-sheva
chmod +x run.sh && ./run.sh
```

The launcher installs Python dependencies, starts the server at `http://127.0.0.1:8765`, and opens it in your browser. The first launch builds a one-time demand-points cache (~10 sec); subsequent launches start instantly.

### Manual / step-by-step

If you'd rather run it without the launcher:

```bash
pip install -r requirements.txt
cd website/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765/`. The cache is built automatically on first request if it doesn't exist yet.

---

## Using the app

| Action | What it does |
|---|---|
| **Click the map** | Drops a draggable marker, draws the red editing polyline, and updates the scores live |
| **Drag a marker** | Reshapes the polyline; scores refresh when you release |
| **Save Snapshot** | Locks the current network as a colored polyline + comparison-table row, then clears the editor so you can draw a new one |
| **New Network** | Clears the current editor without saving (snapshots stay on the map) |
| **Undo Last Node** | Removes the most recently added marker |
| **Clear Saved Snapshots** | Wipes all saved colored polylines and the comparison table |

The **comparison table** lets you quickly eyeball which network scored best under each formula (F3 / F4 / F5 / F6).

---

## API

`POST /api/calculate`

Request:
```json
{ "nodes": [[31.2428, 34.7977], [31.2413, 34.7977], ...] }
```

Response:
```json
{
  "L": 8.88,
  "K": 7,
  "network_inertia": 12612.9,
  "score3": 32.77,
  "score4": 30.65,
  "score5": 20.79,
  "score6": 24.89
}
```

`GET /api/health` — sanity check: returns zone and demand-point counts.

---

## Formulas

All four formulas (`formula3`–`formula6`) live in [`website/backend/calculations.py`](website/backend/calculations.py) and are preserved verbatim from the notebook in `material/NG_calculation3.ipynb`. See the original paper(s) in `material/` for theoretical background.

## License

Research / academic use. Add a license file if you plan to redistribute.
