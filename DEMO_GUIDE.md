# SodhiCable MES v4.0 — Demo & Presentation Guide

**ISE 573 | Spring 2026 | Stephen Eacuello**

---

## Setup (2 minutes before presenting)

```bash
cd sodhicable_flask
python init_db.py        # Fresh DB: 389 shift reports, 74 tables, ~22K rows
./start.sh               # Auto-starts OPC-UA sim + ERP sim
```

Wait 30 seconds for live data to start flowing. Open 3 browser tabs:
- **Tab 1:** Dashboard (`http://localhost:5001/`)
- **Tab 2:** System (`http://localhost:5001/system`) — for triggering scenarios
- **Tab 3:** Keep free for drill-downs

---

## Presentation Flow (15-20 minutes)

### Act 1: "The Plant is Running" (3 min)

1. Show **Dashboard** (`/`) — point out the 6 KPIs auto-refreshing every 5s
2. Click the **?** button in the sidebar footer → guided tour walks through each KPI and chart
3. Note: "This refreshes live — the OPC-UA simulator is generating correlated sensor data right now"
4. Point out a Suspect/Bad reading appearing (lowered thresholds mean ~15% show yellow)
5. Show the filter bar — filter by WC, shift, product family, date range

### Act 2: "ISA-95 Drill-Down" (3 min)

1. Click **SCADA** (`/scada`) → show the 26 WC tiles grouped by factory stage
   - Production flow strip at top: COMPOUND → DRAW & STRAND → EXTRUSION → SHIELD & BRAID → CABLE & ARMOR → TEST → CUT & SHIP
2. Click **CV-1** → Level 2: PLC status, energy monitoring, live parameters, active recipe
   - Point out the ISA-95 badge changing from "Level 3" to "Level 2"
   - Show the data flow panel: L1 Sensors → L2 Control → L3 MES → L4 Business
3. Click **Temperature_F** → Level 1: trend chart with CUSUM/EWMA analysis
   - Point out the ISA-95 badge changing to "Level 1 — Sensing & Actuation"
   - Show the Level 0 process description card

### Act 3: "Something Goes Wrong" (5 min) — THE DRAMATIC MOMENT

1. Switch to **System** tab (`/system`) → click **"Spark Test Failure"** scenario button
2. Switch immediately to **Dashboard** tab — watch:
   - OEE card drops (visible because seed reports are only 389, not 1,000+)
   - Notification bell count goes up
   - Scrap Pareto chart updates
3. Click **notification bell** → see "Critical: SparkTest on CV-1" → click it → goes to F8 Process Control
4. Show the **alarm rationalization chain**: Deviations → NCRs → Holds → Quarantined (visual flow with arrows)
5. Click **"Chain"** button on the deviation → visual cascade: Deviation Detected → NCR Auto-Created → Hold Placed → Lot Quarantined
6. Go to **Traceability** (`/traceability`) → enter the affected lot → click **Trace Forward**
   - Toggle to **Graph View** → show visual node/edge genealogy
7. Show **risk-scored quarantine**: "3 lots HIGH risk (re-inspect), 2 MEDIUM (review), 3 LOW (release immediately)"
   - Key message: "We reduced quarantine scope from 100% to 37.5%"

### Act 4: "AI Asks the Right Question" (3 min)

1. Go to **AI Insights** (`/ai`) → **Ask Claude** tab
2. Type: **"What caused the CV-1 failure?"** → Claude generates SQL, queries DB, explains the result
3. Type: **"What is the OEE for each work center?"** → shows breakdown with CV-1 now lower
4. Type: **"Who can run CV-1 on the night shift?"** → queries personnel certs
5. Point out: "This is Claude Sonnet analyzing our 78-table database in real-time — no pre-built queries"
6. Switch to **AI Insights** tab → show Isolation Forest anomalies, Gradient Boost quality predictions

### Act 5: "The System Recovers" (2 min)

1. Go to **F9 Maintenance** (`/equipment`) → **Predictive Maintenance** tab
   - Show Weibull CDF curves — "Each curve shows failure probability over time"
   - Point out the 10% PM target line
2. Click **Complete PM** on an overdue item → "CDF clock resets, next PM scheduled"
3. Go to **Executive** dashboard (`/executive`) → show strategic KPIs with scrap cost impact
4. Go to **ERP** (`/erp`) → show how L4 financial impact flows up (ISA-95 L3→L4)
   - Purchase orders, invoices, shipments, ISA-95 message log

### Act 6: "What Makes This Different" (2 min)

1. Go to **About** page (`/about`) → **Architecture** tab
   - Show ISA-95 pyramid with 3 data flow worked examples
2. Switch to **Beyond MESA-11** tab → "20 capabilities beyond the original 1997 framework"
3. Switch to **References** tab → show the **Research Gap Statement**:
   - "No peer-reviewed publication presents a complete MESA-11 for wire & cable"
4. Show terminal: `pytest tests/ -v` → **41 tests all pass in 6 seconds**
5. Show: `docker-compose up` → "Runs anywhere with one command"
6. Show: `python validate.py` → quantitative validation with before/after metrics

---

## If Time Allows: Additional Scenarios

### Run "Breakdown" Scenario (adds drama)
- System → click **"Unplanned Breakdown on PLCV-1"**
- Dashboard OEE drops visibly (generates 3 low-OEE shift reports: 20-38%)
- F9 shows downtime spike, maintenance dispatched
- Executive dashboard scrap $ increases

### Run "Quality Crisis" Scenario
- System → click **"Compound Batch Contamination"**
- Shows forward trace → risk-scored quarantine → 3 holds placed
- Demonstrates the full F5→F7→F8→F10 MESA chain

### Run "Shift Handover" Scenario
- System → click **"End of Shift + Report Generation"**
- 7 new shift reports generated → F11 OEE drill-down updates
- Shift handoff created → visible on F6 Labor page

---

## Professor Questions — Quick Reference

| Question | Where to Show | Key Talking Point |
|----------|--------------|-------------------|
| "How do I run this?" | `./start.sh` or `docker-compose up` | Single command, zero infrastructure |
| "How does ISA-95 fit?" | About → Tab 2 (pyramid), SCADA (drill-down) | Full L0-L4 with data flow examples |
| "What about AI?" | AI → Ask Claude + Isolation Forest + Gradient Boost | Pure Python ML, no sklearn needed |
| "Show me genealogy" | Traceability → Graph View → risk scoring | 8 edge cases documented (splice, regrind, remnants) |
| "What about labor?" | Labor → run fatigue or training pipeline scenario | 5 what-if scenarios, Folkard & Tucker citation |
| "Can it handle a crisis?" | System → Quality Crisis scenario | Watch the cascade across 5 MESA functions |
| "Is this publishable?" | About → References → Research Gap | No published wire/cable MES exists in literature |
| "What are the tests?" | `pytest tests/ -v` → 41 passed | 8 test files covering all MESA functions + AI |
| "How realistic is the data?" | Correlated sensors, WO progression, 5 scenarios | Cross-parameter correlation, sustained drift injection |
| "What about OEE?" | F11 → OEE Drill-Down tab | Full waterfall, 6 Big Losses, trend, by-WC, CSV export |
| "Energy management?" | SCADA → Level 2 → Energy card | 4,800 energy readings, kWh/KFT per WC |
| "Certificate of Compliance?" | `/api/traceability/certificate/WO-2026-001` | Auto-generated C of C with test results + genealogy |

---

## Technical Stats to Cite

| Metric | Value |
|--------|-------|
| API Endpoints | 245 |
| Database Tables | 74 + 9 views |
| Seed Data Rows | ~22,000 |
| Engine Modules | 17 (pure Python) |
| Test Cases | 41 (all passing) |
| Work Centers | 26 (including STRAND-1) |
| Equipment Items | 69 |
| Products | 33 across 9 families |
| Paper | 39 pages, 24 references |
| External Dependencies | Flask + anthropic (optional) |
| API Response Time | Avg 8.8ms, Max 52.8ms |
| Genealogy Trace | <5ms (target was <10,000ms) |

---

## Common Pitfalls to Avoid

1. **Don't re-init during the demo** — `python init_db.py` takes 15 seconds and kills live data
2. **Don't run all 5 scenarios back-to-back** — each takes 35-55 seconds, pick 2 max
3. **Have Claude API key set** — without it, AI tab shows fallback queries only
4. **Don't resize browser** — charts re-render but can glitch. Set window size before starting
5. **Keep System tab open** — you need it to trigger scenarios quickly
6. **Port 5001 must be free** — kill any prior Flask instances first: `pkill -f "python app.py"`

---

## Backup Plan

If something breaks during the demo:
- **App won't start?** → `PORT=5002 python app.py` (use different port)
- **DB locked?** → `pkill -f python && python init_db.py && ./start.sh`
- **AI not working?** → Show the fallback pre-built queries tab instead
- **Charts not loading?** → Hard refresh browser (Cmd+Shift+R)
- **Scenario not firing?** → Check `/api/scenario/status` — one may already be running

---

## Post-Demo: What to Hand In

1. **Paper:** `paper/Eacuello_MES_Design_Prototype.pdf` (39 pages, 24 references)
2. **Validation:** `python validate.py` output showing before/after metrics
3. **Tests:** `pytest tests/ -v` output showing 41 tests passing
4. **Code:** The entire `sodhicable_flask/` directory (or Docker image)
5. **This guide:** `DEMO_GUIDE.md` for reproducing the demo
