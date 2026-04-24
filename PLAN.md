# SodhiCable MES Flask — Best-in-Class Plan

## Context

Stephen has a complete 21K-line tkinter SodhiCable MES (v3.0) covering all ISE 573 weeks 1-9. His week 10 design prototype (`Eacuello_MES_Design_Prototype.pdf`, 1,459 LaTeX lines, 47 tables, 11 algorithms) was submitted April 14. For weeks 11-13 he must implement the design doc as a working system.

Week 11 course materials (TPM + Dashboards lectures) provide critical design guidance:
- **Dashboard hierarchy:** Operator → Supervisor → Manager → Executive (each level shows appropriate detail)
- **5-Second Rule:** User understands key message in ≤5 seconds, biggest metric top-left
- **Refresh rates:** Operator: 1-5s, Supervisor: 30-60s, Manager: 5-15 min, Executive: hourly
- **Stephen Few's rule:** "If it doesn't help someone make a better decision faster, it doesn't belong"
- **TPM-MES integration:** OEE waterfall, loss Pareto, AM compliance, CMMS integration, predictive maintenance
- **Hidden factory:** Manual OEE is 15-20% overstated vs. MES-driven; our system closes that gap
- **Course pivot:** All remaining graded work is MES development — no more quizzes or discussion posts

**Location:** `ISE573/sodhicable_flask/` — top-level alongside `project/` and `week10/`

**Strategy:** Rebuild as a Flask web app, reusing 4 proven engine modules (solver, DES, MRP, scheduling — 3,300 lines total), the rich domain data from the GUI (31 products, 25 WCs, 100 personnel), and the existing HTML dashboard generator pattern (`mes_dashboard.py` already uses Chart.js + dark theme). This gives a best-in-class MES that is:
- Web-based (more impressive demo than tkinter)
- Architecturally clean (blueprints per MESA function)
- Fully aligned to the submitted design doc
- Wire & cable specific (reels, spark test, footage tracking, environmental monitoring)
- **TPM-aware** — dashboard hierarchy, 6 Big Losses, AM compliance, predictive maintenance
- **Dashboard best-practices** — 5-9 KPIs per view, semantic colors, drill-down, responsive

---

## Domain Data Inventory (What We Have)

### 31 Products in 9 Families

| Family | Products | Key Characteristics |
|---|---|---|
| A: Shielded Instrumentation | INST-3C16-FBS, INST-3C16-TP, INST-6P22-OS, INST-12P22-OS, INST-2C18-FBS | Foil/braid shield, PVC, 2-12 conductors |
| B: Armored Control | CTRL-2C12-XA, CTRL-4C12-XA, CTRL-6C14-XA, PWR-2/0-ARM | XLPE, AIA armor, 2-37 conductors |
| C: DHT (Down Hole) | DHT-1C12-260, DHT-2C12-H2S, DHT-3C10-ESP, DHT-FP-FEP | FEP/ETFE, high-temp 260°C |
| S: Shipboard/Fiber | LSOH-3C12-SB, LSOH-7C14-SB, SB-FIBER-4SM, FIBER-SM-FEP | LSOH, fiber optic |
| U: Fire-Rated | UL2196-2C14, UL2196-6C10, UL2196-4C2-4C10, UL2196-4C12 | UL 2196 certification |
| R: Utility/Building Wire | RHW2-2AWG, IC-10AWG-THHN, SOOW-4C12, MC-12-2, TRAY-3C10 | High volume, low margin |
| I: Insulated Conductors | IC-12AWG-XLPE, IC-2AWG-XLPE, IC-6AWG-XLPE, BARE-4-0 | MTS, simple routing |
| D: Down Hole Special | DHT-FP-3T, TUBE-SM-WELD | Multi-site, NJ welded tube |
| M: Medium Voltage | MV105-500MCM | Triple layer, 500MCM |

Each product has: `product_id, name, family, revenue_per_kft, cost_per_kft, max_order_qty_kft` plus AWG, conductors, shield/jacket/armor type.

### 25 Work Centers

| ID | Name | Type | Util Target | Notes |
|---|---|---|---|---|
| COMPOUND-1 | Compounding (Banbury) | Compound | 75% | Compound mixing |
| DRAW-1 | Drawing Machine 1 | Draw | 85% | Copper rod → wire |
| CV-1, CV-2, CV-3 | Extrusion Lines | CV | 80% | PVC/XLPE/FEP insulation |
| FOIL-1 | Foil Shield Application | Foil | 78% | Aluminum foil wrap |
| TAPE-1 | Tape Machine 1 | Tape | 82% | Mylar/mica tape |
| BRAID-1, BRAID-2, BRAID-3 | Braiding Machines | Braid | 85% | 16/24/36 carrier |
| CABLE-1, CABLE-2 | Cabling Machines | Cable | 88% | 2-19 / 19-37 conductors |
| PLCV-1 | Pressurized Liquid Continuous Vulcanization | Jacket | 85% | PVC/XLPE jacket |
| LPML-1 | Large Poly Mold Line | Jacket | 75% | Large-diameter jacketing |
| PX-1 | Plastisol Extruder | Jacket | 80% | FEP/ETFE jacket |
| ARMOR-1 | Armoring Line | Armor | 82% | AIA/steel armor |
| CCCW-1 | Continuous Coil Winding | Armor | 82% | Fire-rated wrap |
| PT-1 | Fiber Extrusion | PT | 70% | Optical fiber |
| COMB-1 | Combine Station | Combine | 80% | Multi-element assembly |
| TEST-1, TEST-2 | Testing Labs | Test | 65% | Spark, hipot, resistance, flame |
| CUT-1 | Cutting Station | Cut | 90% | Cut to length |
| PACK-1 | Packaging | Pack | 90% | Reel, box, ship prep |
| NJ-EXT | External (NJ Welded Tube) | External | 50% | Off-site assembly |

### Routing Patterns by Family

- **Family A:** COMPOUND → DRAW → CV → FOIL/TAPE → BRAID → CABLE → PLCV → TEST → CUT → PACK
- **Family B:** COMPOUND → DRAW → CV → BRAID → CABLE → PLCV → ARMOR → TEST → CUT → PACK
- **Family C:** DRAW → CV → (CABLE) → PX-1 → TEST → CUT → PACK
- **Family U:** COMPOUND → DRAW → TAPE → CV → CABLE → TAPE → PLCV → CCCW → TEST → CUT → PACK
- **Family R:** DRAW → CV → TEST → CUT → PACK (simpler routing)
- **Family S:** Varies — fiber products route through PT-1

### 16 Materials

| ID | Name | Type | Unit Cost | Lead Time |
|---|---|---|---|---|
| MAT-001 | Copper Rod 14mm | Conductor | $8.50/kg | 7 days |
| MAT-004 | PVC Compound | Insulation | $3.20/kg | 5 days |
| MAT-005 | XLPE | Insulation | $4.75/kg | 7 days |
| MAT-006 | FEP | Insulation | $12.50/kg | 10 days |
| MAT-007 | ETFE | Insulation | $15.00/kg | 10 days |
| MAT-008 | Steel Braid Wire 0.25mm | Shielding | $5.50/kg | 5 days |
| MAT-009 | Steel Armor Strip | Armor | $4.80/kg | 7 days |
| MAT-010 | Aluminum Foil 6μm | Shielding | $22.00/roll | 3 days |
| MAT-011 | Mylar Tape | Shielding | $15.50/roll | 4 days |
| MAT-012 | Tinned Cu Drain Wire | Conductor | $11.20/kg | 5 days |
| MAT-013 | Paper Wrap | Packaging | $2.10/kg | 3 days |
| MAT-014 | Polyester Tape | Jacketing | $8.75/roll | 4 days |
| MAT-015 | Nylon Jacket Compound | Jacketing | $6.50/kg | 6 days |

### 5 Reel Types

| Type | Max Footage | Material | Tare Weight |
|---|---|---|---|
| RT-24W | 2,500 ft | Wood | 15 lb |
| RT-36W | 5,000 ft | Wood | 35 lb |
| RT-48S | 10,000 ft | Steel | 85 lb |
| RT-30P | 3,000 ft | Plastic | 8 lb |
| RT-DRUM | 25,000 ft | Steel | 120 lb |

### 3 Plants (for P9 Transportation)

| Plant | Location | Capacity |
|---|---|---|
| PLANT-RI | Rhode Island | 500 kft |
| PLANT-SC | South Carolina | 300 kft |
| PLANT-TX | Texas | 200 kft |

### 20 Customers across 4 Business Units
- Defense (NAVSEA, MIL specs) — highest margin, tightest deadlines
- Infrastructure (utilities, grid) — 30% volume
- Industrial (OEM, general) — 35% volume
- Oil & Gas (H2S/CO2 resistant) — 30% volume

### Changeover Matrix
- Same family: 15-30 min setup, 50-150 ft scrap
- Cross-family: 45-90 min setup, 100-300 ft scrap
- Dark compound change (C/D families): +30 min penalty

### DES Configuration (8 stages)
1. COMPOUND: 1 server, 1.5 hrs mean
2. DRAW: 1 server, 2.0 hrs mean
3. EXTRUDE: 2 servers, 3.0 hrs mean
4. ASSEMBLY: 2 servers, 2.5 hrs mean
5. JACKET: 1 server, 2.5 hrs mean
6. ARMOR: 1 server, 2.0 hrs mean
7. TEST: 2 servers, 1.5 hrs mean
8. FINISH: 1 server, 1.0 hrs mean

Default λ=0.30 jobs/hr, dispatch rules: FIFO/SPT/EDD/WSPT/campaign

### OEE Configuration
- World class: ≥85%, Acceptable: ≥60%
- 6 Big Losses tracked: Equipment failure, Setup/changeover, Minor stoppages, Reduced speed, Startup rejects, Production rejects
- Fallback quality: 97%, Fallback performance: 80%

### KPI Thresholds (color-coded)

| KPI | Yellow | Green |
|---|---|---|
| Profit ($K) | 150 | 200 |
| Throughput (u/h) | 0.1 | 0.3 |
| Utilization (%) | 70 | 90 |
| WIP (units) | 5 | 15 |
| On-Time (%) | 80 | 95 |
| OEE (%) | 60 | 85 |

### Scrap Cause Distribution
STARTUP: 25%, CHANGEOVER: 20%, SPARK_FAULT: 18%, OD_EXCURSION: 15%, MATERIAL_DEFECT: 12%, COMPOUND_BLEED: 10%

### Wire & Cable Test Types (14)
ConductorRes, JacketThickness, InsulationThickness, OD, Spark, Hipot, VW-1, FT4, IEEE383, PrintVerification, TensileStrength, Elongation, ShieldCoverage, CapacitanceBalance

### Spark Test Parameters
- Voltage: 2.5-4.0 kV
- Pass rate: 99.5%
- Auto-hold trigger: ≥3 faults on a reel

### Environmental Monitoring
- Extrusion zones: 175°F ± 8°F (optimal 160-200°F)
- Humidity: 45% ± 10% (optimal 40-60%)
- Monitored WCs: CV-1, CV-2, PLCV-1, PX-1

---

## Schema Strategy

**Write NEW schema.sql from the design doc** using snake_case column names (matching `sodhicable_scheduling.py`). Do NOT copy the existing PascalCase schema.

### Column Name Alignment

The scheduling module queries columns like `product_id, revenue_per_kft, wc_id, capacity_hrs_per_week, process_time_min_per_100ft` — these match the design doc exactly. The existing project schema uses `ProductID, UnitPrice, WorkCenterID, AvailHoursDay, StdTimePerUnit`. Using the design doc's names means the scheduling module works without changes.

### Target: 47+ Tables

**From design doc (37 explicit):**
- products, work_centers, materials, customers, plants, reel_types, unit_conversions
- work_orders, routings, changeover_matrix, schedule
- dispatch_queue, dispatch_log
- recipes, recipe_parameters, recipe_ingredients, documents
- process_data_live, spark_test_log, events
- personnel, personnel_certs, shift_handoff
- spc_readings, ncr, test_results
- hold_release, process_deviations
- equipment, maintenance, downtime_log
- lot_tracking, reel_inventory, inventory
- kpis, scrap_log, shift_reports

**Supporting (from existing project, needed for solvers & features):**
- sales_orders, sales_order_lines (customer order tracking)
- bom_products, bom_materials (multi-level BOM)
- buffer_inventory (tier-based safety stock)
- audit_trail (version control, compliance)
- packaging_specs (customer-specific packaging — for Tab 10)
- shipping_costs (for P9 transportation solver)
- scheduler_config, schedule_results (solver history)
- test_protocols (test type definitions with temp correction)

**MRP (created at runtime by engine):**
- mrp_items, mrp_bom, mrp_demand, mrp_planned_orders, mrp_inventory_log

**New for Flask simulation:**
- simulation_events, simulation_state

### 8 Analytical Views (adapted to snake_case)
- vw_OEE, vw_MaterialAvailability, vw_WOStatusSummary, vw_BufferStatus
- vw_ScheduleAdherence, vw_ScrapPareto, vw_CertExpirations, vw_MaintenanceDue

---

## Engine Modules — Exact Reuse

### 1. `sodhicable_solver.py` → `engines/solver.py` (624 lines)
**Copy verbatim.** No DB, no GUI. PuLP-compatible API.
- Classes: LpVariable, LpAffineExpression, LpConstraint, LpProblem
- Algorithms: Two-phase simplex, branch-and-bound, sensitivity analysis
- Used by: scheduling.py for all LP/IP formulations

### 2. `sodhicable_des.py` → `engines/des_engine.py` (1034 lines)
**Copy verbatim.** No DB, no GUI. Stdlib only (heapq, random, math, statistics).
- `QueueingAnalytics`: mm1(), mmc(), mg1(), sensitivity_sweep() — static methods
- `SodhiCableDES(config)`: 8-stage factory sim, 5 dispatch rules, breakdowns, buffers, rework, setup times, campaign mode
- `SimulationStatistics`: welch warmup detection, run_replications(n=10), paired_t_test()
- `WhatIfRunner`: 3 pre-built scenarios, get_default_config()

### 3. `sodhicable_mrp.py` → `engines/mrp_engine.py` (817 lines)
**Copy verbatim.** Only needs sqlite3 Connection.
- Creates own 5 tables via create_mrp_tables(conn)
- Seeds 31 SodhiCable items via populate_sodhicable_bom(conn)
- 7 lot sizing: L4L, FOQ, EOQ, EPQ, POQ, Silver-Meal, Wagner-Whitin
- explode_bom(), get_bom_tree(), run_mrp(), simulate_demand(), compute_nervousness()

### 4. `sodhicable_scheduling.py` → `engines/scheduling.py` (851 lines)
**One import fix:** `from sodhicable_solver import` → `from engines.solver import`
- 12 solvers, all accept `conn: sqlite3.Connection`:
  - P1: solve_p1_product_mix() — LP, reads products/work_centers/routings
  - P2: solve_p2_wo_acceptance() — Binary IP
  - P3: solve_p3_single_machine(method="wspt") — WSPT/EDD/Moore's
  - P4: solve_p4_parallel_machines() — LPT on CV-1/CV-2
  - P5: solve_p5_flow_shop() / solve_p5_flow_shop_neh() — Johnson's / NEH
  - P6: solve_p6_supply_chain() — Multi-period LP
  - P7: solve_p7_metaheuristics(method="sa") — SA/GA
  - P8: solve_p8_resource_allocation() — Assignment LP
  - P9: solve_p9_transportation() — Transport LP (needs plants, shipping_costs)
  - P10: solve_p10_campaign_batch() — TSP/2-opt (needs changeover_matrix)
  - P11: solve_p11_cut_reel() — FFD bin-packing (needs reel_types, packaging_specs)

### Existing HTML Dashboard Pattern
`gui/mes_dashboard.py` (994 lines) already generates self-contained HTML with:
- Chart.js 4.4.0 from CDN
- Dark navy-to-blue gradient theme
- 4 KPI cards, 4 charts, 4 operational tables
- Responsive CSS Grid layout
- Color-coded status badges
Use this as a **template for Flask templates** — same aesthetics, same Chart.js patterns.

---

## New Engine Code Needed

### `engines/spc.py` (~250 lines) — F7 Quality
```python
def xbar_r_chart(samples, n=5):
    """Returns UCL/CL/LCL for X-bar and R charts.
    A2=0.577, D3=0, D4=2.114, d2=2.326 (for n=5)"""

def compute_cpk(samples, usl, lsl):
    """Returns Cp, Cpk. σ̂ = R̄/d2. Target Cpk ≥ 1.33"""

def cusum(values, target, k=0.5, h=5):
    """Cumulative sum. C⁺ = max(0, z-k+C⁺ₙ₋₁). Signal when C⁺>h or C⁻>h"""

def ewma(values, lambda_=0.2, L=3):
    """Exponentially weighted. Zᵢ = λxᵢ + (1-λ)Zᵢ₋₁. Asymptotic limits"""

def western_electric_rules(values, ucl, cl, lcl):
    """8 rules: beyond 3σ, 2/3 beyond 2σ, 4/5 beyond 1σ, 8 same side, etc."""
```

### `engines/oee.py` (~150 lines) — F11 Performance
```python
def compute_oee(conn, wc_id, shift_date=None):
    """OEE = A × P × Q from downtime_log, work_orders, scrap_log.
    A = (planned - downtime) / planned
    P = actual_output / rated_output (from work_centers.capacity_ft_per_hr)
    Q = 1 - (scrap_ft / total_ft)
    6 Big Losses breakdown included"""

def compute_fpy(conn, wc_id):
    """First Pass Yield = ∏(1 - defect_rate_k) across K steps"""

def compute_shift_report(conn, wc_id, shift_code, shift_date):
    """Full shift KPIs: OEE, FPY, throughput, scrap, labor efficiency"""
```

### `engines/dispatch.py` (~80 lines) — F3 Dispatching
```python
def score_dispatch(wo, current_time, changeover_time):
    """Sᵢ = 0.4·(1/(dᵢ-t)) + 0.4·Pᵢ + 0.2·(1/(sᵢⱼ+1))
    Checks operator cert via F6 before dispatch"""

def dispatch_next(conn, wc_id):
    """Select max-score job from dispatch_queue, write to dispatch_log"""
```

### `engines/pid_control.py` (~120 lines) — F8 Process
```python
def pid_step(setpoint, actual, Kp=2.0, Ki=0.1, Kd=0.5, prev_error=0, integral=0, dt=1):
    """PID control law: u(t) = Kp·e + Ki·∫e + Kd·de/dt (Ziegler-Nichols)"""

def classify_alarm(deviation, spec_limit, tolerance_consumed_pct):
    """Warning: EWMA signal, ±2σ → logged, PID auto-corrects
    Minor: CUSUM signal, within spec → operator notified
    Major: CUSUM, >80% tolerance → job paused
    Critical: exceeds spec → immediate hold, NCR, lot quarantine"""
```

### `engines/maintenance_calc.py` (~80 lines) — F9 Maintenance
```python
def compute_mtbf(conn, equipment_id):
    """MTBF = Σ uptime_hours / Σ failures"""

def compute_mttr(conn, equipment_id):
    """MTTR = Σ repair_hours / Σ repairs"""

def compute_pm_interval(mtbf, reliability_target=0.90):
    """T_PM = -MTBF × ln(0.90) ≈ 0.105 × MTBF"""

def schedule_next_pm(conn, equipment_id):
    """Updates equipment.next_pm_date"""
```

### `engines/labor.py` (~100 lines) — F6 Labor
```python
def solve_rostering(conn, shift_demands):
    """IP via solver.py: min Σxws s.t. coverage ≥ Ds per shift,
    max 5 shifts/wk per worker (OSHA), cert requirements per WC"""

def compute_labor_efficiency(conn, shift_date, shift_code):
    """η = standard_hours_earned / actual_hours_worked"""
```

### `engines/predictive.py` (~120 lines) — Predictive Maintenance
```python
def failure_probability(mtbf, time_since_last_pm):
    """P(fail before t) = 1 - e^(-t/MTBF) — exponential CDF
    Returns probability curve and current risk level"""

def cost_of_delay(mtbf, mttr, cost_per_hour_downtime, pm_cost):
    """Expected cost if PM delayed by Δt:
    E[cost] = P(fail|Δt) × (MTTR × cost_per_hour + scrap_cost) + (1-P) × 0
    vs PM_cost now. Shows break-even point"""

def optimal_pm_schedule(conn, equipment_id):
    """Age-based replacement: minimize cost rate = (Cp·R(T) + Cf·F(T)) / (T + MTTR·F(T))
    Returns optimal T_PM with confidence interval"""

def risk_dashboard(conn):
    """For each equipment: days since last PM, MTBF, current risk %, 
    predicted failure date, recommended action (OK/Schedule PM/Urgent)
    Color: GREEN (>30 days), YELLOW (7-30), RED (<7 days)"""
```

### `engines/bottleneck.py` (~100 lines) — Bottleneck Analysis
```python
def kingman_approximation(lam, mu, ca_sq, cs_sq):
    """E[Wq] ≈ ((Ca²+Cs²)/2) × (ρ/(1-ρ)) × E[τs]
    Shows how queue time explodes as ρ → 1"""

def identify_bottleneck(conn):
    """For each WC: compute utilization, queue time, WIP.
    Bottleneck = WC with highest utilization OR longest queue.
    Returns ranked list with metrics"""

def what_if_add_server(conn, wc_id):
    """Recalculate with c+1 servers: new ρ = λ/(c+1)μ, new E[Wq].
    Shows % queue reduction from adding one machine"""

def bottleneck_shift_analysis(conn):
    """If bottleneck WC gets 10% faster (process improvement):
    what's the new bottleneck? Shows shifting bottleneck effect"""
```

### `engines/supply_risk.py` (~100 lines) — Supply Chain Risk
```python
def compute_coverage_days(conn):
    """For each material: coverage = qty_on_hand / daily_usage_rate.
    Returns days of supply, flags materials with < safety_stock coverage"""

def single_source_analysis(conn):
    """Identifies materials with only 1 supplier (single-source risk).
    Risk score = (1/num_suppliers) × (lead_time_days / 7) × criticality_weight"""

def lead_time_scenario(conn, material_id, multiplier=2.0):
    """What if lead time doubles? Shows which WOs would be delayed,
    which products affected, revenue at risk"""

def risk_heat_map(conn):
    """Material × Risk matrix: rows=materials, columns=risk factors
    (single source, long lead time, low coverage, high cost).
    Color: RED/YELLOW/GREEN per cell. Overall risk score per material"""
```

### `engines/simulation.py` (~400 lines) — Real-time Factory Sim
```python
class FactorySimulation:
    """Wraps SodhiCableDES for step-by-step SSE streaming.
    
    Background thread executes DES events one-at-a-time with configurable delay.
    After each event:
    - Writes to simulation_events table
    - Pushes JSON to thread-safe queue.Queue
    - Updates simulation_state (WC status: running/idle/setup/breakdown)
    
    Supports scripted failure injection:
    1. Spark test FAIL on CV-2 → F7 NCR → F10 lot quarantine → forward trace
    2. Drawing die wear on DRAW-1 → F8 CUSUM → F9 corrective maintenance
    3. SPC OOC on wire diameter → F7 Cpk recalc → CAPA
    
    Speed control: 100ms/500ms/1s/2s delay between events
    """
```

---

## Project Structure

```
sodhicable_flask/
├── app.py                          # Flask factory, get_db(), blueprint registration
├── config.py                       # DATABASE, SECRET_KEY, DEBUG, MES_CONFIG thresholds
├── init_db.py                      # Creates DB: schema → seed → views; validates FK integrity
├── requirements.txt                # Flask>=3.0
│
├── database/
│   ├── schema.sql                  # 47+ tables (snake_case, from design doc)
│   ├── seed_data.sql               # 31 products, 25 WCs, 100 personnel, 20 customers,
│   │                               # 50 reels, 50+ SPC readings, 50+ spark tests,
│   │                               # 30+ downtime events, 20+ WOs, full routings/BOMs
│   └── views.sql                   # 8 analytical views
│
├── engines/
│   ├── __init__.py
│   ├── solver.py                   # Verbatim: LP/IP solver (624 lines)
│   ├── des_engine.py               # Verbatim: DES + queueing (1034 lines)
│   ├── mrp_engine.py               # Verbatim: MRP engine (817 lines)
│   ├── scheduling.py               # 1 import fix: P1-P11 solvers (851 lines)
│   ├── spc.py                      # NEW: X-bar/R, CUSUM, EWMA, Cpk, W.E. rules
│   ├── oee.py                      # NEW: OEE=A×P×Q, FPY, 6 Big Losses, shift reports
│   ├── dispatch.py                 # NEW: F3 weighted priority scorer
│   ├── pid_control.py              # NEW: PID + CUSUM/EWMA detection + alarm classification
│   ├── maintenance_calc.py         # NEW: MTBF, MTTR, PM interval scheduling
│   ├── labor.py                    # NEW: IP rostering via solver.py
│   ├── simulation.py              # NEW: Real-time SSE factory sim orchestrator
│   ├── predictive.py              # NEW: Failure probability, cost-of-delay, PM optimization
│   ├── bottleneck.py              # NEW: Kingman's G/G/1 approximation, bottleneck identification
│   └── supply_risk.py             # NEW: Lead time analysis, single-source detection, coverage calc
│
├── blueprints/
│   ├── __init__.py
│   ├── dashboard.py                # GET / — KPI cards, OEE gauges, factory overview
│   ├── api_scheduling.py           # P1-P11 solvers + Gantt data
│   ├── api_des.py                  # DES + queueing analytics + what-if
│   ├── api_mrp.py                  # BOM tree, MRP grid, lot sizing, pegging (redirects /mrp → /erp?tab=planning)
│   ├── api_quality.py              # SPC charts, NCR, CAPA, Cpk, spark test
│   ├── api_process.py              # PID sim, CUSUM/EWMA, hold/release, alarms
│   ├── api_equipment.py            # Equipment status, maintenance, MTBF/MTTR
│   ├── api_traceability.py         # Forward/backward genealogy trace, reel inventory
│   ├── api_labor.py                # Rostering, cert tracking, shift handoff
│   ├── api_workorders.py           # WO CRUD, status transitions, audit trail
│   ├── api_inventory.py            # Material availability, buffer status (redirects /inventory → /erp?tab=supply)
│   ├── api_performance.py          # OEE trends, scrap Pareto, KPI dashboard
│   ├── api_documents.py            # Recipe versions, document control, compliance
│   ├── api_wire_cable.py           # Reel mgmt, footage tracking, packaging, environmental
│   ├── api_simulation.py           # SSE stream, start/stop/config, scripted failures
│   ├── api_erp.py                  # ERP Level 4: sim control, S&OP, POs, OTC, ISA-95, financials
│   │
│   │   # ── "Best-in-Class" Screens ──
│   ├── api_executive.py            # Executive cockpit: plant OEE trend, cost/KFT, on-time %, scrap $
│   ├── api_bottleneck.py           # Bottleneck analyzer: DES utilization + Kingman's formula, what-if
│   ├── api_sales.py                # Sales orders + ATP API (redirects /sales → /erp?tab=orders)
│   ├── api_suppliers.py            # Supplier scorecards (redirects /suppliers → /erp?tab=supply)
│   └── api_extras.py               # Predictive maint, supply risk, wire-cable, footage, shift export
│
├── queries/                        # 11 SQL modules (adapted column names)
│   ├── 01_wo_management.sql        # 6 queries: WO list, BOM explosion, auto upstream WO
│   ├── 02_scheduling.sql           # 5 queries: pending ops, capacity, Gantt data
│   ├── 03_inventory.sql            # 5 queries: availability, aging, buffer, days-of-supply
│   ├── 04_quality.sql              # 5 queries: SPC data, inspection, NCR aging, spark trend
│   ├── 05_traceability.sql         # 4 queries: backward/forward trace, CoC, genealogy
│   ├── 06_document_control.sql     # 4 queries: revision history, links, compliance
│   ├── 07_equipment.sql            # 5 queries: status, PM compliance, MTBF, MTTR, Pareto
│   ├── 08_data_collection.sql      # 3 queries: data quality, completeness, real-time
│   ├── 09_process_mgmt.sql         # 4 queries: recipe download, versions, setpoint compliance
│   ├── 10_labor.sql                # 4 queries: allocation, coverage, cert status, hours
│   └── 11_performance.sql          # 5 queries: OEE dashboard, KPI trends, production summary
│
├── templates/
│   ├── base.html                   # Sidebar nav with dashboard hierarchy indicator,
│   │                               # dark navy theme, SSE listener, Chart.js CDN, toast,
│   │                               # "Last Updated" timestamp per Week 11 guidance
│   │
│   │   # ── DASHBOARD HIERARCHY (Week 11: Operator → Supervisor → Manager → Executive) ──
│   ├── dashboard.html              # DEFAULT: Supervisor-level dashboard (most useful for demo)
│   │                               # 6 KPI cards (OEE, throughput, WIP, on-time, FPY, util)
│   │                               # OEE waterfall (A×P×Q breakdown — TPM 6 Big Losses link)
│   │                               # Loss Pareto (top 5 stop reasons — Focused Improvement)
│   │                               # Capacity utilization bars (all WCs)
│   │                               # Follows 5-Second Rule: biggest KPI top-left, 5-9 metrics
│   ├── simulation.html             # OPERATOR-level: Factory floor status (Andon-style)
│   │                               # SVG map (8 stages), WC status lights (green/yellow/red/gray),
│   ├── scheduling.html             # P1-P11 selector, params, Gantt chart, sensitivity
│   ├── des.html                    # DES config (λ, dispatch, breakdowns), results + charts
│   ├── erp.html                    # ERP Level 4 — 5-tab unified module:
│   │                               #   Dashboard (KPIs, financials, sim controls, 15s auto-refresh)
│   │                               #   Planning (S&OP grid + forecast + MRP BOM explosion)
│   │                               #   Orders (OTC pipeline + collapsible ATP)
│   │                               #   Supply Chain (POs + inventory + suppliers + risk + buffers)
│   │                               #   ISA-95 (L3/L4 message log + flow chart)
│   ├── quality.html                # X-bar/R + CUSUM + EWMA charts, NCR table, Cpk gauge
│   ├── workorders.html             # WO table, create/edit modal, status board, audit
│   ├── equipment.html              # Equipment grid, maintenance calendar, MTBF/MTTR cards
│   ├── traceability.html           # Genealogy tree, forward/backward trace, reel inventory
│   ├── labor.html                  # Shift schedule, cert matrix, rostering
│   ├── performance.html            # OEE trends, 6 Big Losses Pareto, KPI dashboard
│   ├── documents.html              # Recipe versions, doc links, compliance matrix
│   ├── process.html                # PID control view, alarm log, deviation table
│   ├── wire_cable.html             # Reel management, footage tracking, spark test monitor,
│   │                               # downtime logging, environmental monitor, packaging
│   │
│   │   # ── "Best-in-Class" Pages ──
│   ├── executive.html              # EXECUTIVE-level: strategic KPIs, OEE trend, cost waterfall
│   ├── bottleneck.html             # Bottleneck analyzer: Kingman's G/G/c, what-if
│   └── des.html                    # DES config + results + queueing analytics
│
└── static/
    ├── css/
    │   └── mes.css                 # Dark navy-to-blue gradient (from mes_dashboard.py),
    │                               # gold accents, card shadows, status badges,
    │                               # factory floor map colors, responsive grid
    └── js/
        ├── mes-common.js           # fetch helpers, toast notifications, SSE EventSource client
        ├── dashboard-charts.js     # OEE doughnut gauges (A/P/Q), capacity bars, WO pie
        ├── spc-charts.js           # X-bar/R, CUSUM, EWMA with UCL/CL/LCL annotations
        ├── gantt.js                # Horizontal floating-bar Gantt for P3-P5/P7/P10
        ├── simulation.js           # SSE consumer, factory floor SVG updater
        ├── mrp-grid.js             # MRP time-phased grid (weeks × items)
        ├── traceability-tree.js    # Lot genealogy collapsible tree
        ├── des-viz.js              # Queue length animation, WIP trends, utilization heatmap
        ├── executive-charts.js    # OEE trend sparklines, cost waterfall, on-time gauge
        ├── predictive-charts.js   # Failure probability curves (exponential CDF), risk timeline
        ├── bottleneck-charts.js   # Utilization bars, Kingman curve (E[Wq] vs ρ), what-if overlay
        ├── supply-risk.js         # Risk heat map grid, coverage bar chart, lead time comparison
        └── footage-tracker.js     # Digital tote board counters, progress bars, cumulative chart
```

---

## Week-by-Week Implementation

### Week 11: Database + Seed Data + Flask + Dashboard (Due ~April 22)

**Design doc commits:** All 47 tables, 20+ rows in entity tables, 50+ in event/reading tables, 4 cross-function queries.

#### Days 1-2: Schema
- Write `schema.sql` from design doc table specs (snake_case columns)
- All 47+ tables with proper FK constraints and indexes
- Include supporting tables for solvers: plants, shipping_costs, packaging_specs, reel_types
- `init_db.py` with PRAGMA foreign_keys=ON, WAL mode

#### Days 2-3: Seed Data (CRITICAL — this makes or breaks the demo)
- **Products:** All 31 products with revenue/cost/max_qty, family, AWG, conductors
- **Work Centers:** All 25 with capacity_hrs_per_week, capacity_ft_per_hr, utilization_target, setup_time_min
- **Routings:** Full routing for each product (6-10 steps with process_time_min_per_100ft)
- **Materials:** 16 materials with costs, lead times, safety stock
- **BOMs:** Multi-level for all families (product → sub-products → materials)
- **Personnel:** 100 people (33/shift), 5 departments, roles, certs
- **Customers:** 20 across 4 business units with quality levels (Standard, MIL-Spec, UL-Listed, API)
- **Work Orders:** 20+ across all statuses (Pending, Released, InProcess, QCHold, Complete)
- **Changeover Matrix:** All family-to-family setup times and scrap amounts
- **Equipment:** Equipment for each WC with calibration dates, PM schedules
- **Recipes:** Active recipes for all products with parameters (temp, speed, pressure, limits)
- **SPC Readings:** 50+ (wire diameter, insulation thickness) with some OOC points
- **Spark Test Log:** 50+ entries (99.5% PASS, some FAILs with fault locations)
- **Downtime Log:** 30+ events across 7 categories
- **Scrap Log:** 20+ entries across 6 cause codes with footage amounts
- **Reel Inventory:** 50 reels across 5 types in various statuses
- **Lot Tracking:** 30+ parent-child relationships for genealogy traces
- **Process Data:** 50+ sensor readings (temperature, line speed, tension)
- **Events:** 50+ production events for timeline
- **Environmental:** Temperature/humidity readings for extrusion WCs
- **Plants:** 3 plants with capacities
- **Shipping Costs:** Plant × customer cost matrix

#### Day 3: Views
- 8 analytical views adapted to snake_case columns

#### Day 4: 4 Cross-Function Queries (design doc commitment)
1. **OEE calculation** — joins downtime_log + work_orders + scrap_log → shift_reports
2. **Forward genealogy trace** — recursive CTE on lot_tracking (target: <10 sec)
3. **Dispatch queue ranking** — weighted priority joining dispatch_queue + work_orders + changeover_matrix
4. **Labor efficiency per shift** — joins personnel + shift_handoff + kpis

#### Days 5-6: Flask Scaffold
- `app.py` with create_app(), get_db() via Flask g
- `base.html`: Dark navy sidebar matching mes_dashboard.py aesthetics, Chart.js 4.x CDN
- Dashboard blueprint with 6 KPI cards pulling from views
- Chart.js OEE doughnut gauges, capacity utilization bars

#### Day 7: Wire All Query APIs
- Blueprint stubs for all 11 MESA functions + wire_cable
- 55 queries from SQL files callable as JSON APIs
- Dashboard shows live data from seed data

### Week 12: Algorithm Integration + All Pages (Due ~April 29)

**Design doc commits:** 6 algorithms (LP assignment F1, SPT/EDD F2, weighted dispatch F3, X-bar/R+Cpk F7, CUSUM F8, MTBF PM F9).

#### Day 1: Copy Engines + Verify
- Copy 4 engine files, fix scheduling.py import
- Test each solver against new schema (column names must match)
- Run P1 product mix LP — verify optimal profit and shadow prices
- Run P3 single machine — verify WSPT/EDD/Moore's on CABLE-1

#### Days 2-3: New Algorithm Engines
- Write `engines/spc.py`: X-bar/R, CUSUM, EWMA, Cpk, Western Electric rules
- Write `engines/oee.py`: OEE=A×P×Q, FPY, 6 Big Losses, shift_report
- Write `engines/dispatch.py`: F3 weighted priority scorer with cert gating
- Write `engines/pid_control.py`: PID step, alarm classification (Warning/Minor/Major/Critical)
- Write `engines/maintenance_calc.py`: MTBF, MTTR, PM interval
- Write `engines/labor.py`: IP rostering via solver.py

#### Days 3-5: Frontend Pages (high-impact first)
1. **scheduling.html** — P1-P11 selector dropdown, parameter overrides, results table, Gantt chart
2. **quality.html** — SPC charts with UCL/CL/LCL annotations (Chart.js + annotation plugin), CUSUM/EWMA tabs, NCR table, Cpk display with target ≥1.33
3. **des.html** — Config panel (λ slider, dispatch rule, breakdowns toggle), run button, queue viz, WIP trends, utilization heatmap
4. **mrp.html** — Product selector, BOM tree (collapsible divs), MRP grid (time-phased table), lot sizing comparison (7 methods side-by-side)
5. **wire_cable.html** — 7 sections matching existing Tab 10:
   - Reel management (table with status badges, new/full/ship actions)
   - Footage tracking (% complete bars per WO)
   - Spark test monitor (results table + fault location map)
   - Downtime logging (form + Pareto chart)
   - Environmental monitor (temp/humidity with alarm colors)
   - Packaging & shipping (specs table, verification checklist)
   - Shift handoff (form + history)

#### Days 5-6: Best-in-Class Screens + ERP Level 4

1. **executive.html** — Executive cockpit:
   - 7 KPI cards, OEE trend, cost waterfall by family, on-time by business unit
   - Period-over-period comparison, material risk, top issues
   - Fully filterable by datetime/WC/shift/family/product

2. **erp.html** — ERP Level 4 (unified 5-tab module):
   - **Dashboard** — KPIs, sim controls, Revenue vs COGS chart, AR aging, ISA-95 flow, cost breakdown
   - **Planning** — S&OP grid (editable production plans), forecast (SES/DES), capacity chart, MRP BOM explosion + time-phased grid
   - **Orders** — Order-to-cash pipeline (6 stages with action buttons), collapsible ATP check
   - **Supply Chain** — PO create/approve/receive, material availability, supplier scorecards, supply risk coverage, buffer inventory
   - **ISA-95** — L3↔L4 message log with direction filters, message flow chart
   - ERP simulator background thread generates live business activity (demand → orders → shipments → invoices)

3. **bottleneck.html** — Kingman's G/G/c, utilization bars, what-if slider

#### Days 6-7: Remaining Pages
- workorders.html, equipment.html, traceability.html, labor.html
- performance.html, documents.html, process.html, wire_cable.html
- Each: data table + 1-2 charts from query results

### Week 13: Live Simulation + Demo (Due ~May 6)

**Design doc commits:** 20+ jobs across all lines, 3 scripted failures, end-of-shift KPI report, recall drill <10 sec.

#### Days 1-2: Simulation Engine
- Write `engines/simulation.py` — FactorySimulation class
- Background thread wrapping SodhiCableDES step-by-step
- SSE endpoint: `GET /api/simulation/stream` (text/event-stream)
- Controls: `POST /api/simulation/start|stop|config`
- Scripted failure injection at configurable simulation time

#### Days 2-3: Factory Floor Visualization
- `simulation.html` with SVG factory floor map:
  - 8 stages laid out as flow diagram
  - Each WC = box with status color (green=running, yellow=setup, red=breakdown, gray=idle)
  - Queue indicators (dots or numbers) at each stage
  - WIP counter, throughput ticker
- SSE consumer updates map + charts in real-time
- Speed control slider (10x/50x/100x)
- Event log panel (scrolling list)

#### Days 3-4: Cross-Function Event Chains
Match the design doc's Integration Timeline:

| Time | Event | Functions Triggered | What to Show |
|---|---|---|---|
| 07:00 | Shift meeting — review shift_handoff | F6, F4 | Handoff form auto-populated |
| 07:15 | Schedule released for 5 CV-2 jobs | F1, F2, F3 | Gantt chart updates |
| 07:20 | First job dispatched on CV-2, cert checked | F3, F6 | Dispatch log entry |
| 08:30 | SPC sample on DRAW-1, X̄=0.0253" (OK) | F5, F7 | SPC chart point added |
| **09:45** | **Spark test FAIL at 1,247 ft** | F5→F7→F8→F10 | NCR auto-created, lot quarantined, toast alert |
| 10:00 | Forward trace on compound batch CB-0330 | F10 | Genealogy tree shows 3 affected reels |
| **10:30** | **Drawing die wear — CUSUM detects drift** | F5→F8→F9 | CUSUM chart signals, maintenance dispatched |
| 11:00 | Die replaced, DRAW-1 back online | F9, F1, F11 | Downtime logged, OEE impact shown |
| 11:15 | Extruder temp alarm on PLCV-1, PID corrects | F5, F8 | PID chart shows correction |
| 13:30 | Job completes, lot genealogy recorded | F10, F5 | Lot tree updated |
| 14:45 | End-of-shift KPI report | F11, F6 | OEE, FPY, schedule adherence, labor efficiency |

#### Day 5: Recall Drill
- Forward trace on compound batch → recursive CTE → all affected reels identified
- Target: <10 seconds wall-clock time
- Display as interactive genealogy tree

#### Days 6-7: Polish + Demo Prep
- Dark control-room theme polish (navy/gold from mes_dashboard.py)
- Toast notifications for alarms and events
- Test all 12 scheduling solvers end-to-end
- Record 5-minute demo video as backup
- Demo script: 5-minute walkthrough covering all 11 MESA functions + simulation

---

## "Above and Beyond" Features (Prioritized)

| # | Feature | Effort | Impact | Status |
|---|---|---|---|---|
| 1 | Flask web app (vs tkinter) | — | High | Core architecture |
| 2 | Dark control-room theme (navy/gold, from mes_dashboard.py) | Low | High | Week 11 |
| 3 | OEE doughnut gauges (A/P/Q concentric) per WC | Low | High | Week 11 |
| 4 | Gantt charts for scheduling results | Low | Medium | Week 12 |
| 5 | Interactive SPC charts with rule violation color coding | Medium | High | Week 12 |
| 6 | 7 Wire & Cable operations sections (reel, spark, footage, etc.) | Medium | Very High | Week 12 |
| 7 | Real-time factory simulation via SSE | High | Very High | Week 13 |
| 8 | Scripted failure injection with cross-function event chains | High | Very High | Week 13 |
| 9 | Interactive what-if DES sliders | Medium | Medium | Week 12 |
| 10 | Collapsible BOM tree visualization | Medium | Medium | Week 12 |
| 11 | Factory floor SVG map with live status | Medium | High | Week 13 |
| 12 | CUSUM + EWMA charts (beyond X-bar/R) | Medium | High | Week 12 |
| 13 | PID control simulation with animated chart | High | High | Week 13 |
| 14 | Lot genealogy tree as interactive SVG/HTML | Medium | High | Week 13 |
| 15 | Recall drill demo (<10 sec genealogy trace) | Low | High | Week 13 |
| | | | | |
| | **NEW Best-in-Class Screens** | | | |
| 16 | Executive Cockpit — plant-level OEE/cost/delivery trends with drill-down | Medium | Very High | Week 12 |
| 17 | Predictive Maintenance — MTBF projections, failure probability curves, cost-of-delay | Medium | Very High | Week 12 |
| 18 | Bottleneck Analyzer — Kingman's formula visualization, what-if add server | Medium | Very High | Week 12 |
| 19 | Supply Chain Risk Map — lead times, single-source flags, coverage heat map | Medium | High | Week 12 |
| 20 | Production Footage Tracker — digital tote board, shift targets vs actual, % bars | Low | High | Week 12 |

---

## Week 11 Course Alignment: TPM + Dashboard Design

### Dashboard Hierarchy (4 Levels)
Our Flask app implements the full dashboard hierarchy from the Week 11 lectures:

| Level | Page | Audience | Metrics | Refresh | Design |
|---|---|---|---|---|---|
| **Machine/Cell** | simulation.html, footage.html | Operator | Status lights, queue counts, footage counters | SSE real-time | Large fonts, Andon-style, 72pt+, viewable from 20ft |
| **Line/Area** | dashboard.html, wire_cable.html | Supervisor | OEE by WC, loss Pareto, shift trends, SPC | 30-60 sec | 5-9 KPIs, trend lines, exception alerts |
| **Plant** | performance.html, bottleneck.html | Manager | Multi-WC comparison, targets, variance | 5-15 min | KPI cards + drill-down, heatmaps |
| **Enterprise** | executive.html | Executive | 3-4 big KPIs, clean & minimal | Hourly/daily | Sparklines, no clutter, strategic only |

### TPM-MES Integration Points
- **Autonomous Maintenance (Pillar 1):** Shift handoff form = digital CIL, checklist completion tracking
- **Planned Maintenance (Pillar 2):** MTBF/MTTR from downtime_log, auto PM triggers via maintenance_calc.py
- **Quality Maintenance (Pillar 3):** Real-time SPC charts, Cpk tracking, NCR→CAPA workflow
- **Focused Improvement (Pillar 4):** Loss Pareto on dashboard (auto-generated, not manual), Kaizen impact measurable via OEE delta
- **Predictive Maintenance:** Failure probability curves, cost-of-delay analysis, goes beyond basic TPM Pillar 2

### Dashboard Design Rules (from Week 11)
1. **5-Second Rule:** Key message understood in ≤5 seconds
2. **F-pattern hierarchy:** Biggest KPI top-left
3. **5-9 metrics per view** — no information overload
4. **Semantic colors:** Red=critical, Yellow=warning, Green=good, Blue=neutral, Gray=inactive
5. **Always show context:** Target line, trend arrow, timeframe, "Last Updated" timestamp
6. **OEE Waterfall:** Show A × P × Q breakdown (not just the number) — exposes the 6 Big Losses
7. **Loss Pareto:** Top 5 stop reasons, sorted descending, color-coded severity — drives Focused Improvement
8. **No chartjunk:** "If it doesn't help someone make a better decision faster, remove it"

### Hidden Factory Gap
The lectures emphasize that manual OEE reporting is typically 15-20% overstated. Our MES closes this gap by:
- Automated downtime detection (from simulation events, not manual entry)
- Second-by-second OEE resolution (aggregated for dashboards)
- Reason codes on every stop event
- Historical database for trend analysis (not just current shift)

---

## Gap 1: Error Handling Strategy

Every user-facing action needs graceful failure handling:

**Backend (Flask blueprints):**
```python
@bp.route('/solve/p1', methods=['POST'])
def run_p1():
    try:
        result = solve_p1_product_mix(get_db())
        return jsonify({'status': 'ok', 'data': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
```

**Frontend (JavaScript):**
- All `fetch()` calls wrapped in try/catch
- On error: show red toast notification with message, hide loading spinner
- On success: show green toast with summary ("P1 solved: $215K profit")
- Loading state: disable submit button, show spinner during solver/DES runs

**Specific failure modes:**
| Scenario | Handling |
|---|---|
| Solver infeasible | Return status="Infeasible", show "No feasible solution — check constraints" |
| Solver unbounded | Return status="Unbounded", show "Problem unbounded — check objective" |
| DES timeout (>60s) | Kill thread, show "Simulation timed out — reduce arrival rate or jobs" |
| DB locked | Retry once after 100ms, then show "Database busy — try again" |
| SSE connection lost | Auto-reconnect with exponential backoff (1s, 2s, 4s), show "Reconnecting..." |
| Empty query result | Show "No data available" placeholder, not a blank page |
| MRP no demand | Show "No demand found — seed demand data first" |

**Fallback UI:**
- Every page has a `<div id="error-banner">` hidden by default
- On any API error, banner appears with message + retry button
- Charts show "No data" placeholder instead of crashing

---

## Gap 2: Flask Demo Script (Week 13)

**5-Minute Demo Flow:**

**0:00 — Login & Dashboard (30s)**
- Open browser to localhost:5000
- Dashboard loads: 6 KPI cards, OEE doughnut gauges, loss Pareto
- Point out: "This is the Supervisor-level view — 5 KPIs, follows the 5-Second Rule from Week 11"

**0:30 — Executive Cockpit (30s)**
- Navigate to Executive page
- Show: Plant OEE trend, cost/KFT waterfall, on-time delivery gauge
- "Executive sees 3-4 strategic metrics only — no information overload"

**1:00 — Start Simulation (30s)**
- Navigate to Simulation page
- Click "Start Simulation" — factory floor map lights up
- WC status colors change (green/yellow/red), event log scrolls
- "Real-time SSE streaming — operator Andon view"

**1:30 — Scripted Spark Test Failure (60s)**
- Simulation triggers spark test FAIL at 09:45
- Toast alert: "SPARK TEST FAIL on CV-2, Reel R-4521"
- Navigate to Quality → NCR auto-created (NCR-2026-0089)
- Navigate to Traceability → forward trace on compound batch CB-0330
- "In <10 seconds, we identified 3 other affected reels — full genealogy trace"

**2:30 — CUSUM Drift Detection (45s)**
- Simulation triggers wire diameter drift at 10:30
- Navigate to Process → CUSUM chart shows C⁺ > h signal
- Maintenance dispatched automatically
- "F8 detected sustained drift → F9 dispatched corrective maintenance"

**3:15 — Scheduling & Optimization (45s)**
- Navigate to Scheduling → run P1 Product Mix LP
- Show: optimal quantities, profit, shadow prices
- Run P3 Single Machine → show Gantt chart
- "12 optimization solvers, all running in the browser"

**4:00 — MRP & Supply Chain (30s)**
- Navigate to MRP → select product, show BOM tree
- Run MRP explosion → show planned orders by week
- Navigate to Supply Risk → show material coverage heat map
- "Multi-level BOM with 7 lot-sizing methods + supply chain risk analysis"

**4:30 — End-of-Shift Report (30s)**
- Navigate to Performance → show OEE per WC
- Navigate to Bottleneck → Kingman's curve with current utilization
- Navigate to Predictive → equipment failure probability curves
- "Full TPM integration: OEE waterfall, loss Pareto, predictive PM"

**Backup paths if time allows:**
- Wire & Cable Operations (reel management, spark test analytics, footage tracker)
- SPC charts with Western Electric rule violations
- DES with what-if scenario sliders
- Shift handoff form

---

## Gap 3: Seed Data Generator (`seed_generator.py`)

Hand-writing 50+ SPC readings in SQL is tedious and produces unrealistic data. Instead, a Python script generates correlated, realistic data.

```python
# seed_generator.py — generates INSERT statements for event/reading tables

def generate_spc_readings(n=100):
    """Generate SPC readings for wire diameter on DRAW-1.
    - Normal operation: μ=0.0253, σ=0.0003 (in spec, Cpk~1.4)
    - Introduce drift at reading 60-75: μ shifts to 0.0256 (CUSUM will detect)
    - One OOC point at reading 42: value = 0.0265 (beyond UCL)
    - Western Electric Rule 2 at readings 80-82: 2 of 3 beyond 2σ"""

def generate_spark_tests(n=80):
    """Generate spark test results.
    - 99.5% pass rate (realistic)
    - FAIL locations clustered around 1200-1400ft range (suggests die wear pattern)
    - Correlate FAILs with compound batch CB-0330 (for genealogy trace demo)"""

def generate_downtime_events(n=40):
    """Generate downtime events across 7 categories.
    - Distribution: Breakdown 25%, Setup 25%, MaterialWait 15%, QualityHold 10%, PM 15%, NoOrders 5%, Other 5%
    - Breakdown durations: 30-180 min (long-tail)
    - Setup durations: 15-90 min (matches changeover_matrix)
    - DRAW-1 has more breakdowns (supports die-wear CUSUM demo)"""

def generate_process_data(n=200):
    """Generate sensor readings for extrusion temperature.
    - Baseline: 375°F ± 2°F (in control)
    - Introduce gradual drift from reading 120-160 (EWMA will detect)
    - One spike at reading 95: 383°F (PID auto-corrects within 3 readings)"""

def generate_lot_tracking(n=40):
    """Generate parent-child lot relationships.
    - Compound batch CB-0330 → 5 output lots (for forward trace demo)
    - 3 levels deep: raw material → compound → insulated wire → finished cable
    - Include the suspect lot path for recall drill"""

def generate_scrap_log(n=30):
    """Generate scrap events by cause code.
    - Match design doc distribution: STARTUP 25%, CHANGEOVER 20%, etc.
    - Scrap amounts: 50-800 ft (realistic for wire/cable)"""

def generate_environmental(n=100):
    """Generate temp/humidity for extrusion WCs.
    - CV-1, CV-2, PLCV-1, PX-1
    - Temp: 175°F ± 8°F, one excursion to 195°F (alarm)
    - Humidity: 45% ± 10%, one excursion to 72% (material concern)"""

def generate_events(n=80):
    """Generate production events for timeline.
    - Match design doc Integration Timeline events
    - Ensure chronological consistency across shifts"""
```

**Output:** `database/seed_data_generated.sql` — appended after `seed_data.sql` in `init_db.py`

**Key design:** Data is specifically crafted so that:
1. SPC X-bar/R chart shows a clean process with one OOC point → demonstrates rule detection
2. CUSUM chart shows a sustained drift starting at reading 60 → demonstrates F8 detection
3. EWMA chart shows gradual trend in temperature → demonstrates F8 trend detection
4. Forward trace from CB-0330 finds exactly 3 affected reels → demonstrates F10 recall
5. Downtime Pareto shows Breakdown as #1 cause → matches TPM Focused Improvement logic
6. OEE calculation produces a realistic 78-85% range → matches Week 11 "typical plant" benchmarks

---

## Gap 4: Offline Chart.js + Query Loader + CLAUDE.md

### Offline Chart.js
CDN will fail if demo room has no WiFi. Vendor locally:
```
static/vendor/
├── chart.min.js                    # Chart.js 4.x (~200KB)
└── chartjs-plugin-annotation.min.js # For SPC UCL/CL/LCL lines
```
`base.html` loads from `/static/vendor/` not CDN. Zero network dependency.

### Query Loader (`query_loader.py`)
55 SQL queries across 11 files need a clean loading pattern:
```python
# query_loader.py
import os, re

_cache = {}

def load_queries(filename):
    """Parse SQL file with named queries. Format:
    -- name: wo_list_by_priority
    SELECT ... ;
    Returns dict: {'wo_list_by_priority': 'SELECT ...'}"""
    if filename in _cache:
        return _cache[filename]
    path = os.path.join(os.path.dirname(__file__), 'queries', filename)
    with open(path) as f:
        text = f.read()
    queries = {}
    for match in re.finditer(r'--\s*name:\s*(\w+)\s*\n(.*?)(?=--\s*name:|\Z)', text, re.DOTALL):
        queries[match.group(1)] = match.group(2).strip().rstrip(';')
    _cache[filename] = queries
    return queries
```
Blueprints use: `queries = load_queries('04_quality.sql'); db.execute(queries['spc_chart_data'])`

### CLAUDE.md for New Project
Create `sodhicable_flask/CLAUDE.md` with:
- Architecture overview (Flask + blueprints + engines + SQLite)
- File structure with one-line descriptions
- How to run: `pip install flask && python init_db.py && flask run`
- Engine reuse notes (which files are verbatim copies, which have changes)
- Database: 47+ tables, snake_case columns, design doc alignment
- Key config: MES_CONFIG thresholds, OEE targets, KPI color coding
- Query naming convention (`-- name: query_name` in SQL files)

---

## Technical Decisions

- **Schema:** New snake_case schema from design doc (not copy of PascalCase existing)
- **No ORM:** Raw SQL via sqlite3 — queries already written, academic context
- **No SPA:** Jinja templates + vanilla JS + fetch() — 90% interactivity, 30% effort
- **Chart.js 4.x via CDN:** Single script tag + annotation plugin for SPC control limits
- **No auth:** Hardcoded demo user — auth is not a week 11-13 requirement
- **DB rebuilt from scripts:** `python init_db.py` for reproducibility every time
- **SSE for simulation:** Simpler than WebSocket, no extra dependency. Fallback: polling every 2s
- **Dark theme from mes_dashboard.py:** Navy-to-blue gradient already proven beautiful

---

## Dependencies

**Python:** Flask>=3.0 (only pip install)
**Frontend (CDN):** Chart.js 4.x + chartjs-plugin-annotation
**No npm, webpack, Docker, build step**

---

## Verification Checklist

### Week 11
- [ ] `python init_db.py` creates 47+ tables with FK integrity
- [ ] Seed data: 31 products, 25 WCs, 100 personnel, 20 customers, 50 reels, 50+ events
- [ ] 8 views return correct data
- [ ] 4 cross-function queries work (OEE, genealogy trace, dispatch ranking, labor efficiency)
- [ ] `flask run` serves dashboard at localhost:5000
- [ ] 6 KPI cards show data from seed, OEE gauges render

### Week 12
- [ ] All 12 scheduling solvers (P1-P11 + cut-reel) return correct results via API
- [ ] DES runs with 5 dispatch rules, returns queue stats
- [ ] MRP BOM explosion works for all 9 families, 7 lot sizing methods correct
- [ ] SPC X-bar/R chart renders with UCL/CL/LCL, Western Electric rules detect violations
- [ ] CUSUM detects sustained drift in seeded data
- [ ] EWMA shows gradual trend detection
- [ ] OEE = A×P×Q matches manual calculation from seed data
- [ ] Wire & cable page: reel CRUD, spark test display, footage tracking, downtime Pareto
- [ ] Executive cockpit: OEE trend sparklines, cost waterfall, on-time gauge
- [ ] Predictive maintenance: risk cards with failure probability curves, cost-of-delay
- [ ] Bottleneck analyzer: utilization bars, Kingman's curve with current ρ marked
- [ ] Supply chain risk: heat map grid, coverage bars, single-source flags
- [ ] Production footage tracker: tote board with shift target % bars
- [ ] All 20 template pages load and display data

### Week 13
- [ ] Simulation streams events via SSE, factory floor map updates
- [ ] Scripted spark test failure triggers NCR + lot quarantine + forward trace
- [ ] Scripted CUSUM drift triggers maintenance dispatch + downtime log
- [ ] PID correction visible on process chart
- [ ] Forward trace on compound batch completes in <10 seconds
- [ ] End-of-shift report shows OEE, FPY, schedule adherence, labor efficiency
- [ ] Full demo scenario plays through all Integration Timeline events
- [ ] 5-minute demo video recorded as backup
