# SodhiCable MES v4.0 — User Guide

## System Overview
SodhiCable MES is a web-based Manufacturing Execution System for wire & cable production implementing all 11 MESA functions plus 20 beyond-MESA capabilities including AI/ML (Isolation Forest, Gradient Boosting, Weibull RUL, Claude API), ISA-95 SCADA, ERP Level 4 simulation, OPC-UA tag simulator, and S&OP demand forecasting.

**244 API endpoints, 78 database tables, 35 pages, 17 engine modules.**

---

## Dashboard Hierarchy

| Level | Page | Audience | Features | Refresh |
|-------|------|----------|----------|---------|
| Operator | Factory Floor, SCADA, Data Collection | Operators | Status tiles, sensor readings, alarms, SSE streams | 5s / real-time |
| Supervisor | Dashboard | Supervisors | 6 KPIs, OEE by WC, Pareto, downtime, schedule adherence | 5s auto |
| Manager | F11 Performance | Managers | OEE drill-down, Quality, Scrap, On-Time (4 tabs) | On demand |
| Executive | Executive | Plant Manager | Strategic KPIs, trends, top issues, filterable | 5s auto |
| Enterprise | ERP (Level 4) | Finance/Supply Chain | 5 tabs: Dashboard, Planning, Orders, Supply Chain, ISA-95 | 15s auto |

**All dashboards support filtering** by date range, work center, shift, product family, and product/part number with cascading dropdowns.

---

## Pages & Features

### Dashboards

**Production Dashboard (/)** — 6 KPI cards (OEE, throughput, WIP, on-time, FPY, utilization), 9 charts: OEE by WC (AxPxQ stacked), scrap Pareto, downtime by category (6 Big Losses), downtime by WC (stacked), scrap by WC (stacked), throughput trend (dual-axis: footage + OEE%), WO status donut, schedule adherence (KPI cards + table), PM status by WC (stacked) + PM timeline (horizontal bar, color by overdue/due-soon/ok). Fully filterable by datetime range, work center, shift, product family, and product/part number with cascading dropdowns. 5s auto-refresh respects active filters.

**Executive Dashboard (/executive)** — 7 KPI cards: Plant OEE (with trend arrow vs previous period), On-Time Delivery, Cost/KFT, Scrap $, Revenue/KFT, Gross Margin %, Energy Cost. Charts: OEE trend (14-day line + 85% target), cost waterfall by product family (material/labor/overhead/scrap/energy/margin stacked), on-time by business unit (Defense/Infrastructure/Oil&Gas/Industrial stacked), on-time vs late donut. Sections: period-over-period comparison (auto-compares current vs previous equal-length period when date range set), material risk (low-stock/stockout items with lead times), top 5 issues (filtered by WC). Fully filterable by datetime range, work center, shift, product family, and product/part number. 5s auto-refresh.

**ERP Level 4 (/erp)** — ISA-95 Level 4 unified module with 5 tabs:
- **Dashboard** — KPIs (open SOs/POs, gross margin, AR balance, forecast accuracy, ISA-95 messages), ERP simulator controls (demo speed + normal), Revenue vs COGS chart, AR aging donut, ISA-95 message flow, cost breakdown by family. 15s auto-refresh.
- **Planning** — S&OP planning grid with editable production plan cells, demand forecast (SES/DES with adjustable alpha), capacity utilization by family, MRP BOM explosion (7 lot-sizing methods), time-phased MRP grid.
- **Orders** — Order-to-cash pipeline (6 stages: Order Received → WO Created → In Production → Shipped → Invoiced → Paid) with action buttons (Create WO, Ship, Invoice). Collapsible ATP check.
- **Supply Chain** — Purchase order management (create/approve/receive with ISA-95 logging), material availability with deficit flagging, supplier scorecards, supply risk coverage chart, buffer inventory status cards.
- **ISA-95** — L3↔L4 boundary message log with direction filters (All/L4→L3/L3→L4), message flow chart by type. Demonstrates ISA-95 B2MML message exchange.

**SCADA (/scada)** — ISA-95 L3→L2→L1 drill-down. Plant floor tiles (26 WCs), PLC/controller simulation, energy monitoring, spark test results for TEST WCs. Level 0 process descriptions. 5s auto-refresh.

**AI Insights (/ai)** — 3 tabs: Ask Claude (NLP → SQL), AI Insights (z-score anomalies + Isolation Forest + Gradient Boost quality + Weibull maintenance + changeover learning), Recommendations (prioritized actions with MESA function links).

### MESA-11 Functions

**F1 Resource Allocation (/resources)** — Capacity heatmap, WO assignment board, capacity-vs-load chart, LP optimizer.

**F2 Scheduling (/scheduling)** — 12 solvers (P1-P11), Gantt chart, drag-and-drop reorder.

**F3 Dispatching (/dispatch)** — Priority-scored queue, Dispatch Next button, score breakdown, cert validation.

**F4 Document Control (/documents)** — Document Library (recipes + technical docs), recipe version comparison, compliance metrics.

**F5 Data Collection (/datacollect)** — 58 sensors across 17 WCs grouped by work center with filter by WC and alarm status. Each sensor card shows live value with units (°F, lbf, fpm, in, PSI, RPM, kW), setpoint + USL/LSL limits, mini sparkline bar, and status dot (green/yellow/red pulsing). 6 KPI cards: total sensors, critical alarms, warnings, capture rate, WC count, data freshness. Click any sensor for 200-point trend chart with setpoint/limit reference lines. SSE live stream with polling fallback. Alarm banner flashes when critical. Cross-correlated sensor readings via OPC-UA simulator (speed↔temp↔tension↔OD linked by shared process noise + sustained die-wear drift injection on DRAW-1 and CV-1).

**F6 Labor Management (/labor)** — 3 tabs: Labor Hours (default — bar chart + efficiency), Workforce & Certs (filterable by name/role/shift/WC/cert status, flexibility index per operator, cross-training coverage heatmap, cert days-until-expiry), Shift Handoff & What-If (auto-populate from live WO/equipment/quality state, 5 what-if scenarios: callout, cross-training, overtime, fatigue, training pipeline).

**F7 Quality / SPC (/quality)** — X-bar/R control charts, Cpk process capability, NCR workflow, spark test summary, CSV export.

**F8 Process Control (/process)** — 2 tabs: Process Monitor (live readings, CUSUM/EWMA deep-dive, alarm rationalization chain F5→F7→F8→F10, resolve/acknowledge, environmental overlay, scrap correlation), PID Simulation.

**F9 Maintenance (/equipment)** — 4 tabs with single global filter bar (WC, equipment, datetime range):
- **Downtime Analysis** (default) — Pareto by category + stacked by WC, MTBF/MTTR KPIs computed from filtered data.
- **Predictive Maintenance** — Weibull/Exponential CDF curves fitted from actual failure history (varied beta/eta per equipment type), 7-day failure probability KPI cards, RUL predictions, recommended PM table. CDF includes 10% PM target line and explanation of shape parameter meaning.
- **Equipment Inventory** — 69 assets with calibration status, filterable.
- **PM Schedule** — Sorted by urgency with **Complete PM** button on overdue/due-soon items. Completing a PM: updates last_pm_date, schedules next PM by frequency, inserts maintenance record, logs PM downtime, resets the CDF failure clock (days_since_pm → 0), writes audit trail.

**F10 Traceability (/traceability)** — Forward/backward genealogy via recursive CTEs. Tree/Graph visual toggle. 8 documented edge cases. Splice zone detection. Print marking verification. Certificate of Compliance generation. Risk-scored quarantine.

**F11 Performance (/performance)** — 4 tabs: OEE Drill-Down (filters, waterfall, 6 Big Losses, trend, by-WC, CSV export), Quality (FPY, Cpk, NCRs), Scrap Analysis (Pareto, by-WC, trend), On-Time Delivery (by-family, status detail).

### Operations

**Work Orders (/workorders)** — CRUD with validation, audit trail, auto lot numbering, CSV export. Clickable WO IDs link to detail page.

**Work Order Detail (/workorder/WO-2026-001)** — Full lifecycle: status timeline, operations table, quality (NCRs + tests + holds), genealogy, scrap, audit trail.

**Wire & Cable (/wire-cable)** — 2 tabs: Production Data (reels, spark tests, print marking, downtime), Environmental.

### Analytics

**DES Simulation (/des, /simulation)** — 8-stage factory, queueing analytics, what-if scenarios, SSE streaming. Simulation writes to operational tables for live dashboard integration.

**Bottleneck (/bottleneck)** — Kingman's G/G/c, shifting bottleneck, capacity what-if.

### System

**Demo (/demo)** — Full shift walkthrough (23 events), dot + swim-lane timeline toggle.

**About (/about)** — 5 tabs: Company Profile (competitive landscape), ISA-95 Architecture (pyramid + data flows), Beyond MESA-11 (20 capabilities), Technology, References (24 citations, research gap statement).

**System Metrics (/system)** — Endpoints, DB size, table stats, data freshness. OPC-UA start/stop. 5 live demo scenarios (spark failure, CUSUM drift, breakdown, quality crisis, shift handover).

---

## Factory Process Flow

```
COMPOUND → DRAW → STRAND → CV/PLCV/LPML/PX/PT → FOIL/TAPE → BRAID → CABLE → ARMOR → TEST → CUT → PACK
```

- **Compounding:** Batch process in pounds (lb/hr)
- **Stranding:** 7-61 wires twisted (multi-conductor products only)
- **Extrusion:** 7 lines with extruders, payoffs, caterpillars, takeups, CV tubes
- **All lines monitor:** Temperature, line speed, OD/diameter, tension (lbf)

---

## AI/ML Capabilities (Pure Python)
- **Isolation Forest** — 100-tree ensemble for multivariate anomaly detection
- **Gradient Boosted Stumps** — scrap rate prediction from process features
- **Weibull/Exponential RUL** — remaining useful life with CDF visualization
- **Mahalanobis Distance** — multivariate statistical anomaly detection
- **Z-Score Detection** — univariate threshold-based flagging
- **Claude API** — natural language → SQL with tool_use agentic loop
- **Changeover Learning** — static vs actual setup time analysis
- **Adaptive Changeover** — auto-update matrix from historical data
- **Risk-Scored Quarantine** — quality-based quarantine scope reduction

---

## ISA-95 Levels
- **Level 4 (ERP):** `/erp` — 5 tabs: Dashboard (KPIs + financials), Planning (S&OP + MRP), Orders (OTC + ATP), Supply Chain (POs + inventory + suppliers), ISA-95 (message boundary)
- **Level 3 (MES):** All MESA-11 functions (F1-F11) — the core MES layer
- **Level 2 (SCADA):** `/scada` PLC simulation, `/process` PID/alarms
- **Level 1 (Sensing):** `/scada` sensors, SSE streams, OPC-UA simulator
- **Level 0 (Physical):** `/simulation` DES, `/des` queueing analytics
