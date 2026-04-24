/**
 * SodhiCable MES — Interactive Tour Engine
 * Usage: startTour(tourName) where tourName matches a key in TOURS
 */
const TOURS = {
  dashboard: [
    {selector: '.kpi-grid .kpi-card:first-child', text: 'Plant OEE — the single most important KPI. Target is 85% (world class). Color-coded: green ≥85%, yellow ≥60%, red <60%.', position: 'bottom'},
    {selector: '#oeeChart', text: 'OEE breakdown by work center showing Availability × Performance × Quality. Click any bar to drill into that WC on the SCADA page.', position: 'top'},
    {selector: '#paretoChart', text: 'Scrap Pareto — top causes of waste ranked by footage. Attack the tallest bar first (Focused Improvement from TPM).', position: 'top'},
    {selector: '#downtimeChart', text: 'Downtime by category maps to the 6 Big Losses from TPM: Equipment Failure, Setup, Idling, Reduced Speed, Defects, Startup.', position: 'top'},
    {selector: '#woChart', text: 'Work order status donut — shows the distribution across Pending, InProcess, Complete, QCHold. Updates in real-time as WOs progress.', position: 'top'},
  ],
  scada: [
    {selector: '.kpi-grid', text: 'Plant overview KPIs — total work centers, how many are running, idle count, and active alarm count across the plant.', position: 'bottom'},
    {selector: '#plantFloor', text: 'Factory floor — 26 work centers grouped by production stage. Green glow = running, yellow = setup, red pulse = breakdown. Click any tile to drill down.', position: 'top'},
    {selector: '#isaBadge', text: 'ISA-95 level indicator — shows which level you\'re viewing. Level 3 (plant), Level 2 (PLC/control), Level 1 (sensors). Click tiles to drill deeper.', position: 'bottom'},
  ],
  ai: [
    {selector: '#nlpInput', text: 'Ask any question about the manufacturing data in plain English. Claude analyzes the 78-table schema, generates SQL, executes it, and explains the results.', position: 'bottom'},
    {selector: '.kpi-grid', text: 'AI summary KPIs — anomalies detected by z-score analysis, predicted equipment failures, and active recommendations from the rules engine.', position: 'bottom'},
  ],
  equipment: [
    {selector: '.kpi-grid', text: 'Maintenance KPIs — MTBF (mean time between failures), MTTR (mean time to repair), PM compliance %, equipment count, and overdue PM items.', position: 'bottom'},
    {selector: '#cdfChart', text: 'Weibull failure probability curves — each line shows the cumulative probability of failure over time for a piece of equipment. Steeper = less reliable. The 10% line shows the optimal PM intervention point.', position: 'top'},
  ],
};

let _tourActive = false;
let _tourSteps = [];
let _tourStep = 0;

function startTour(name) {
  const steps = TOURS[name];
  if (!steps || !steps.length) { showToast('No tour available for this page', 'info'); return; }
  _tourSteps = steps;
  _tourStep = 0;
  _tourActive = true;
  _showTourStep();
}

function _showTourStep() {
  // Remove existing overlay
  _removeTourOverlay();
  if (_tourStep >= _tourSteps.length) { _endTour(); return; }

  const step = _tourSteps[_tourStep];
  const el = document.querySelector(step.selector);

  // Create overlay
  const overlay = document.createElement('div');
  overlay.id = 'tourOverlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;z-index:9998;pointer-events:none';

  // Spotlight on target element
  if (el) {
    const rect = el.getBoundingClientRect();
    overlay.style.background = `radial-gradient(ellipse ${rect.width+40}px ${rect.height+40}px at ${rect.left+rect.width/2}px ${rect.top+rect.height/2}px, transparent 50%, rgba(0,0,0,0.7) 51%)`;
    el.scrollIntoView({behavior:'smooth', block:'nearest'});
  } else {
    overlay.style.background = 'rgba(0,0,0,0.5)';
  }

  // Tooltip
  const tooltip = document.createElement('div');
  tooltip.id = 'tourTooltip';
  tooltip.style.cssText = `position:fixed;z-index:9999;max-width:350px;padding:16px 20px;background:var(--bg-card,#1e293b);border:2px solid var(--accent-blue,#3b82f6);border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.5);color:var(--text-primary,#e2e8f0);font-size:13px;line-height:1.6;pointer-events:auto`;

  // Position tooltip
  if (el) {
    const rect = el.getBoundingClientRect();
    if (step.position === 'bottom') {
      tooltip.style.top = (rect.bottom + 12) + 'px';
      tooltip.style.left = Math.max(10, rect.left) + 'px';
    } else {
      tooltip.style.top = Math.max(10, rect.top - 200) + 'px';
      tooltip.style.left = Math.max(10, rect.left) + 'px';
    }
  } else {
    tooltip.style.top = '50%'; tooltip.style.left = '50%';
    tooltip.style.transform = 'translate(-50%,-50%)';
  }

  tooltip.innerHTML = `
    <div style="margin-bottom:10px">${step.text}</div>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:11px;color:var(--text-muted,#94a3b8)">${_tourStep+1} / ${_tourSteps.length}</span>
      <div style="display:flex;gap:8px">
        ${_tourStep > 0 ? '<button onclick="_tourPrev()" style="padding:4px 12px;border:1px solid var(--border-color,#334155);background:none;color:var(--text-secondary,#94a3b8);border-radius:4px;cursor:pointer;font-size:12px">Back</button>' : ''}
        <button onclick="_tourNext()" style="padding:4px 16px;background:var(--accent-blue,#3b82f6);color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:600">${_tourStep < _tourSteps.length-1 ? 'Next' : 'Finish'}</button>
        <button onclick="_endTour()" style="padding:4px 8px;background:none;border:none;color:var(--text-muted,#94a3b8);cursor:pointer;font-size:11px">Skip</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  document.body.appendChild(tooltip);
}

function _tourNext() { _tourStep++; _showTourStep(); }
function _tourPrev() { if (_tourStep > 0) { _tourStep--; _showTourStep(); } }
function _endTour() { _tourActive = false; _removeTourOverlay(); showToast('Tour complete!', 'success'); }
function _removeTourOverlay() {
  const o = document.getElementById('tourOverlay'); if (o) o.remove();
  const t = document.getElementById('tourTooltip'); if (t) t.remove();
}
