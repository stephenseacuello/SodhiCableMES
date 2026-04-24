# SodhiCable MES v4.0 — Flask Edition

## Overview
Best-in-class Manufacturing Execution System for wire & cable production. All 11 MESA functions + 20 beyond-MESA capabilities including Claude AI (text-to-SQL, Isolation Forest, Gradient Boosted Stumps), ISA-95 SCADA, ERP Level 4 simulation, OPC-UA simulator, Weibull RUL predictive maintenance, visual genealogy with splice/cycle detection, Certificate of Compliance generation, S&OP demand forecasting, and SSE real-time streaming. 244 API endpoints, 78 tables, 32,000+ rows.

## Quick Start
```bash
pip install flask anthropic   # anthropic optional
python init_db.py             # 78 tables, 32,000+ rows
./start.sh                    # http://localhost:5001 (auto-starts OPC-UA + ERP sims)
```

## Architecture
```
app.py              — Flask factory, 244 routes, health/audit/search/notifications/SSE streams
config.py           — Thresholds, SIM_WRITE_OPERATIONAL flag
init_db.py          — DB: schema → seed → views → migrations → ERP data → comprehensive data

database/           — 78 tables (64 schema + 5 MRP runtime + 9 ERP/financial), 9 views
engines/            — 17 pure-Python modules
  solver.py         — LP/IP solver (simplex + branch-and-bound)
  des_engine.py     — DES + queueing (M/M/1, M/M/c, M/G/1)
  mrp_engine.py     — MRP with 7 lot-sizing + kanban + pegging
  scheduling.py     — P1-P11 solvers
  spc.py            — X-bar/R, CUSUM, EWMA, Cpk, Western Electric
  oee.py            — OEE = A×P×Q, FPY, 6 Big Losses
  dispatch.py       — F3 weighted priority dispatch
  pid_control.py    — PID controller + alarm classification
  maintenance_calc.py — MTBF, MTTR, Weibull RUL, PM intervals
  labor.py          — IP shift rostering
  simulation.py     — Real-time SSE factory sim (writes to operational tables)
  opcua_sim.py      — OPC-UA tag simulator (5s interval, cross-correlated sensors, sustained drift injection)
  erp_sim.py        — ERP Level 4 simulator (POs, invoices, shipments, ISA-95 messages)
  forecast.py       — S&OP demand forecasting
  demo_scenarios.py — 5 scripted live demo scenarios
  predictive.py     — Failure probability, Weibull CDF, cost-of-delay
  bottleneck.py     — Kingman's G/G/c
  supply_risk.py    — Coverage, single-source analysis

blueprints/         — 25 Flask blueprints (incl. api_erp, api_system)
utils/              — audit.py, validation.py, lot_number.py
templates/          — 35 HTML pages
static/             — CSS (dark+light), JS (search, notifications, SSE), Chart.js 4.4
```

## Database (78 tables, 9 views)
- **Core MES:** 64 tables (MESA-11 functions + simulation + energy + audit)
- **MRP Runtime:** 5 tables (mrp_items, mrp_bom, mrp_demand, mrp_planned_orders, mrp_inventory_log)
- **ERP/Financial:** 9 tables (purchase_orders, goods_receipts, shipments, invoices, financial_ledger, demand_forecast, isa95_messages, erp_sim_state, sop_plan)
- **26 work centers** including STRAND-1
- **69 equipment** with realistic per-line breakdown
- **33 products**, 271 WOs, 34 personnel, 20 customers

## Key Features
- **Filterable Dashboards** — Production + Executive both support 6 filters: datetime range, WC, shift, family, product. Cascading family→product dropdown. Charts destroy/recreate on filter change. Per-chart timestamps.
- **Production Dashboard** — 9 charts: OEE by WC, scrap Pareto, downtime by category, downtime by WC, scrap by WC, throughput trend (dual-axis), WO status, schedule adherence, PM status + timeline
- **Executive Dashboard** — 7 KPI cards (OEE, OTD, cost/KFT, scrap, revenue, margin, energy), OEE trend, cost waterfall by family (6-component decomposition), on-time by business unit, period-over-period comparison, material risk, top issues
- **Complete PM Workflow** — `POST /api/equipment/complete_pm` updates last_pm_date, schedules next PM, inserts maintenance record, logs PM downtime, resets CDF failure clock, writes audit trail. Button on PM Schedule tab.
- **Weibull CDF** — Fitted from actual time-between-failure data per equipment. Varied beta (shape) and eta (scale) by equipment type. 10% PM target line. CDF resets after PM completion.
- **Global Search** — sidebar search across WOs, products, equipment, personnel, lots
- **Notification Center** — bell icon at top of sidebar with 30s auto-refresh
- **SSE Streaming** — `/api/stream/process_data`, `/api/stream/alarms`, `/api/des/stream`
- **Certificate of Compliance** — `/api/traceability/certificate/<wo_id>`
- **Splice/Cycle/Multi-site** — splice zone detection, regrind cycle check, NJ-EXT boundary trace
- **5 Live Demo Scenarios** — spark failure, CUSUM drift, breakdown, quality crisis, shift handover
- **OPC-UA + ERP Simulators** — continuous live data generation (both auto-start)
- **SVG Factory Floor** — inline SVG with status-light circles per WC, flow arrows

## AI/ML (Pure Python — no sklearn/numpy)
- **Isolation Forest** — 100-tree ensemble anomaly detection on process data
- **Gradient Boosted Stumps** — 50-round scrap prediction with feature importance + RMSE
- **Weibull/Exponential RUL** — remaining useful life with CDF curves, fitted from failure history
- **Mahalanobis Distance** — multivariate anomaly detection (2x2/3x3 covariance inverse)
- **Z-Score Anomaly Detection** — threshold-based flagging
- **Claude API** — natural language to SQL with parallel tool use + 3-model fallback
- **Changeover Learning** — static vs actual setup time comparison + auto-update
- **Rules Engine** — 7-rule recommendation system
- **ASTM B193** — temperature correction for conductor resistance

## MESA-11 + Beyond (25+ capabilities)
F1-F11 + AI/ML (6 models), SCADA, DES, MRP (9 lot-sizing + kanban + pegging), Predictive (Weibull CDF + Complete PM), Bottleneck, Supply Risk, Energy (kWh/KFT), ERP/L4 (5-tab unified: Dashboard/Planning/Orders/Supply Chain/ISA-95), OPC-UA + ERP simulators, Visual Genealogy, Recipe Compare, C of C, Splice Detection, Cycle Detection, Multi-Site Trace, Risk Quarantine, Adaptive Changeover, Demo Scenarios, SSE Streaming, Global Search, Notifications, Shift Report Gen, S&OP Forecast, System Metrics, Print Marking Verification, ASTM B193

## ISA-95 Mapping
- L4 (Business): `/erp` — 5 tabs: Dashboard (KPIs + financials + sim), Planning (S&OP + forecast + MRP/BOM), Orders (OTC pipeline + ATP), Supply Chain (POs + inventory + suppliers + risk), ISA-95 (L3/L4 messages)
- L3 (MOM/MES): All MESA-11 (F1-F11) + Complete PM + C of C + Genealogy edge cases
- L2 (SCADA/PLC): `/scada` (drill-down), `/process` (PID, alarms)
- L1 (Sensing): `/scada` (sensors), process_data_live, SSE streaming, OPC-UA sim
- L0 (Physical): `/simulation` (SVG factory floor), `/des` (DES + queueing)
