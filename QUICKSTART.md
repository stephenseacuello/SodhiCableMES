# SodhiCable MES v4.0 — Quick Start Guide

> **TL;DR:** `pip install flask && python init_db.py && ./start.sh`
> Open http://localhost:5001 — OPC-UA + ERP simulators auto-start.

## Prerequisites
- Python 3.8+
- pip

## Installation

```bash
cd sodhicable_flask
pip install flask anthropic    # anthropic optional (enables AI queries)
python init_db.py              # Creates DB: 78 tables, 32,000+ rows
./start.sh                     # http://localhost:5001 with AI + live sims
```

## What You'll See

### 5-Minute Tour
1. **Dashboard** `/` — 6 KPIs, OEE by WC, scrap Pareto (auto-refreshes 5s, fully filterable)
2. **Executive** `/executive` — Strategic KPIs with date/WC/shift/family/product filters
3. **ERP** `/erp` — Level 4 (5 tabs): Dashboard, Planning (S&OP + MRP), Orders (OTC pipeline + ATP), Supply Chain (POs + inventory + suppliers), ISA-95
4. **SCADA** `/scada` — Click any WC → Level 2 (PLC/energy) → Level 1 (sensors)
5. **AI** `/ai` → Ask Claude any question, or view Isolation Forest / Gradient Boost predictions
6. **System** `/system` → Start OPC-UA sim, run live demo scenarios, view DB stats
7. **Demo** `/demo` → Run full shift walkthrough with dot + swim-lane timeline
8. **F5 Data Collection** `/datacollect` → 58 sensors grouped by WC, sparklines, SSE live stream, click any sensor for trend
9. **F8 Process** `/process` → Live readings, CUSUM/EWMA, alarm cascade, PID sim
9. **F9 Maintenance** `/equipment` → Downtime analysis, Weibull CDF curves (varied per equipment), Complete PM button (resets failure clock), PM schedule
10. **F10 Traceability** `/traceability` → Tree/Graph toggle, splice zones, C of C generation

### Live Demo Scenarios (on `/system` page)
| Scenario | Duration | What to watch |
|----------|----------|---------------|
| Spark Failure | 45s | Dashboard OEE, SCADA CV-1, F8 alarms, Notifications |
| CUSUM Drift | 40s | SCADA DRAW-1, F8 CUSUM chart, F9 maintenance |
| Breakdown | 50s | Dashboard OEE drop, F9 downtime, Executive scrap |
| Quality Crisis | 55s | F10 trace, AI risk scores, 3 new holds |
| Shift Handover | 35s | F11 reports, Dashboard OEE, F6 handoff |

### All Pages (35+)
| Category | Pages |
|----------|-------|
| Dashboards | Dashboard, Executive, ERP (Level 4), SCADA, AI Insights |
| MESA-11 | F1-F11 (all 11 functions) |
| Operations | Work Orders (+ detail page), Wire & Cable |
| Analytics | DES, Bottleneck |
| System | Factory Floor, Demo, About, System Metrics |

## Data Model
- **78 tables** + 9 views
- **26 work centers** including STRAND-1
- **69 equipment** with per-line breakdown
- **244 API endpoints**
- **17 engine modules** (pure Python, no numpy/scipy)

## API Examples
```bash
curl http://localhost:5001/api/health
curl http://localhost:5001/api/scada/plant_overview
curl http://localhost:5001/api/ai/isolation_forest
curl http://localhost:5001/api/traceability/certificate/WO-2026-001
curl http://localhost:5001/api/scenario/list
```

## ISE 573 Lab Setup
- `pip install flask` — single dependency
- Reproducible seed data, offline-capable (Chart.js vendored)
- All algorithms visible in `engines/` (pure Python)
- 5 demo scenarios for classroom demonstrations

## Troubleshooting
| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: flask` | `pip install flask` |
| `no such table` | `python init_db.py` |
| Port 5001 in use | `PORT=5002 python app.py` |
| AI queries not working | Set `ANTHROPIC_API_KEY` or use `./start.sh` |

## Resetting
```bash
python init_db.py    # Deletes and recreates everything fresh
```
