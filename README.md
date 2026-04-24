# SodhiCable MES v4.0

**Best-in-class Manufacturing Execution System for Wire & Cable Production**

Complete MESA-11 + 20 beyond-MESA capabilities. 250 API endpoints, 36 pages, Claude AI (Isolation Forest, Gradient Boosted Stumps, Weibull RUL), ISA-95 SCADA with throughput monitoring, ERP Level 4 simulation, OPC-UA simulator, SSE streaming, visual genealogy with splice/cycle detection, Certificate of Compliance, LP optimization with before/after comparison, and 5 live demo scenarios. Built for ISE 573 (URI) — Spring 2026.

## Quick Start

```bash
cd sodhicable_flask
pip install flask anthropic    # anthropic optional
python init_db.py              # 75 tables, 23,000+ rows
./start.sh                     # http://localhost:5001 (auto-starts OPC-UA + ERP sims)
```

## What's Inside

### 250 Endpoints, 36 Pages

| Category | Pages |
|----------|-------|
| **Dashboards** | Production (5s, filterable), Executive (5s, filterable), ERP Level 4 (5 tabs), SCADA ISA-95 (5s, throughput + utilization), AI Insights |
| **MESA-11** | F1-F11: Resource Allocation (LP with before/after comparison), Scheduling (12 solvers with descriptions), Dispatching (Dispatch Next), Documents (recipe compare), Data Collection (live grid + SSE), Labor (5 what-if), Quality/SPC, Process Control (CUSUM/EWMA/PID/cascade), Maintenance (Weibull RUL), Traceability (visual genealogy + C of C), Performance (OEE + Quality + Scrap + On-Time + Utilization Trend) |
| **Operations** | Work Orders (detail page), Wire & Cable |
| **Analytics** | DES, Bottleneck (with LP shadow prices) |
| **System** | Factory Floor (SSE), Demo (dot + swim-lane + live scenarios), About, System Metrics |

### Key Capabilities

- **Claude AI** — natural language → SQL, Isolation Forest anomaly detection, Gradient Boosted quality prediction
- **LP Optimization** — product mix LP with setup times in capacity constraints, before/after comparison showing current vs optimized profit, shadow prices identifying bottlenecks
- **ERP Level 4** — 5-tab unified module: Dashboard (KPIs + financials + sim control), Planning (S&OP + forecast + MRP/BOM), Orders (OTC pipeline + ATP), Supply Chain (POs + inventory + suppliers + risk), ISA-95 (L3/L4 message boundary)
- **SCADA ISA-95** — L3→L2→L1 drill-down, throughput efficiency (actual vs rated ft/hr), actual utilization bar, energy monitoring, PLC simulation, spark tests
- **OPC-UA + ERP Simulators** — cross-correlated sensor readings (speed↔temp↔tension↔OD), sustained die-wear drift injection, both auto-start on launch
- **Bottleneck Analysis** — Kingman's G/G/1, what-if capacity scenarios, LP shadow prices linking to optimization results
- **12 Scheduling Solvers** — P1-P11 with plain-English descriptions (objective, constraints, when to use)
- **F5 Data Collection** — 58 sensors across 17 WCs grouped by work center, sparklines, units, SSE live stream, click-to-trend with spec limits
- **5 Demo Scenarios** — spark failure, CUSUM drift, breakdown, quality crisis, shift handover
- **Weibull RUL** — failure probability CDF curves, remaining useful life predictions
- **Certificate of Compliance** — auto-generated C of C per work order with test results + genealogy
- **Splice Zone Detection** — identifies mixed-lot reels for MIL-SPEC traceability
- **Risk-Scored Quarantine** — forward trace with quality scoring (reduce quarantine scope 60-80%)
- **Utilization Trend** — daily utilization per work center with multi-line chart and 85% target
- **SSE Streaming** — real-time process data and alarm streams
- **S&OP Forecasting** — demand forecast engine with production plan alignment

### Data Model

- **75 tables** + 9 views, 23,000+ rows
- **26 work centers** (COMPOUND → DRAW → STRAND → extrusion → shield/braid → cable → armor → test → cut/pack)
- **69 equipment** with per-line breakdown
- **33 products**, 137+ WOs, 34 personnel, 20 customers, 17 engines

### Equipment Model

| Line | Components |
|------|-----------|
| CV-1 | 2 extruders, payoff, caterpillar, takeup, CV tube |
| CV-2 | 1 extruder (3000fpm), payoff, caterpillar, takeup, CV tube |
| CV-3 | 2 extruders, 2 payoffs, caterpillar, takeup, CV tube |
| PLCV-1 | 3 extruders, 2 payoffs, caterpillar, takeup, CV tube (pressurized) |
| LPML-1 | 3 extruders, 2 payoffs, caterpillar, takeup |
| PX-1 | 1 FEP/ETFE extruder, payoff, caterpillar, takeup |
| PT-1 | Fiber draw tower, preform payoff, capstan, takeup |
| STRAND-1 | Multi-payoff creel (7-61 bobbins), stranding machine, takeup |

## Technology

- **Backend:** Python 3.x + Flask 3.0 (250 endpoints)
- **AI/ML:** Pure Python (Isolation Forest, Gradient Boosting, Weibull, Mahalanobis) + Claude API
- **Database:** SQLite3 (WAL, FK constraints, 75 tables)
- **Frontend:** Chart.js 4.4, vanilla JS, CSS Grid, dark/light theme
- **Real-time:** OPC-UA sim, ERP sim, SSE streaming, 5s auto-refresh
- **Algorithms:** 17 pure-Python modules (no external deps beyond Flask)

## ISA-95 Architecture

```
Level 4 — ERP/Business      → /erp (Dashboard, Planning, Orders, Supply Chain, ISA-95)
Level 3 — MES/MOM           → All MESA-11 functions (F1-F11)
Level 2 — SCADA/PLC         → /scada (drill-down, throughput, utilization), /process (PID, alarms)
Level 1 — Sensing           → /scada (sensors), SSE streams, OPC-UA sim
Level 0 — Physical Process  → /simulation (DES), /des (queueing)
```

## Research

> No peer-reviewed publication presents a complete MESA-11 implementation for wire & cable manufacturing.

**Paper:** *"AI-Augmented MES: A Complete MESA-11 Reference Implementation for Wire and Cable Manufacturing"*
**Targets:** IFAC MIM 2027, IEEE CASE 2027, Journal of Manufacturing Systems
**Paper:** `paper/Eacuello_MES_Design_Prototype.pdf` (39 pages, 24 references)

## License

Educational — ISE 573, University of Rhode Island, Spring 2026.
