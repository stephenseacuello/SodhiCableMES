/* SodhiCable MES v4.0 — Dashboard Charts (with full filter support) */

let oeeChart, paretoChart, woChart, capacityChart, downtimeChart, downtimeWcChart, scrapWcChart, throughputTrendChart, maintStatusChart, maintTimelineChart;
let _allProducts = []; // cached for cascading filter

// ── Filter helpers ──────────────────────────────────────────────

function dashFilterParams() {
  const ids = ['dashDateFrom','dashDateTo','dashWC','dashFamily','dashProduct','dashShift'];
  const keys = ['date_from','date_to','wc_id','family','product_id','shift'];
  const parts = [];
  ids.forEach((id, i) => {
    const el = document.getElementById(id);
    if (el && el.value) parts.push(keys[i] + '=' + encodeURIComponent(el.value));
  });
  const label = document.getElementById('dashFilterStatus');
  if (label) label.textContent = parts.length ? 'Filtered (' + parts.length + ')' : '';
  return parts.length ? '?' + parts.join('&') : '';
}

function clearDashFilters() {
  ['dashDateFrom','dashDateTo','dashWC','dashFamily','dashProduct','dashShift'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '';
  });
  const label = document.getElementById('dashFilterStatus');
  if (label) label.textContent = '';
  updateProductOptions(); // reset product list
  reloadDashboard();
}

// Cascade: when family changes, filter product dropdown to matching family
function onFamilyChange() {
  updateProductOptions();
  reloadDashboard();
}

function updateProductOptions() {
  const famSel = document.getElementById('dashFamily');
  const prodSel = document.getElementById('dashProduct');
  if (!prodSel) return;
  const fam = famSel ? famSel.value : '';
  const currentVal = prodSel.value;
  prodSel.innerHTML = '<option value="">All Products</option>';
  _allProducts.forEach(p => {
    if (!fam || p.family === fam) {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.id + ' — ' + p.name;
      prodSel.appendChild(o);
    }
  });
  // Restore selection if still valid
  if (currentVal) {
    const stillValid = [...prodSel.options].some(o => o.value === currentVal);
    prodSel.value = stillValid ? currentVal : '';
  }
}

// ── Reload all charts ───────────────────────────────────────────

function stampChart(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const card = canvas.closest('.chart-card');
  if (!card) return;
  let stamp = card.querySelector('.chart-stamp');
  if (!stamp) {
    stamp = document.createElement('div');
    stamp.className = 'chart-stamp';
    stamp.style.cssText = 'font-size:9px;color:var(--text-muted,#64748b);text-align:right;margin-top:4px;opacity:0.7';
    card.appendChild(stamp);
  }
  stamp.textContent = 'Updated ' + new Date().toLocaleTimeString();
}

async function reloadDashboard() {
  await loadDashboard();
  await loadExtraCharts();
}

async function loadDashboard() {
  await Promise.all([loadKPIs(), loadOEEChart(), loadParetoChart(), loadWOChart(), loadCapacityChart(), loadThroughputTrend(), loadScheduleAdherence()]);
  ['oeeChart','paretoChart','woChart','throughputTrendChart'].forEach(id => stampChart(id));
  updateTimestamp();
}

// ── Populate dropdowns (once on load) ───────────────────────────

async function populateWCDropdown() {
  try {
    const data = await apiFetch('/api/dashboard/oee_by_wc');
    const sel = document.getElementById('dashWC');
    if (!sel || sel.options.length > 1) return;
    const wcs = [...new Set(data.map(d => d.wc_id))].sort();
    wcs.forEach(wc => { const o = document.createElement('option'); o.value = wc; o.textContent = wc; sel.appendChild(o); });
  } catch(e) {}
}

async function populateProductDropdown() {
  try {
    const data = await apiFetch('/api/mrp/products');
    const products = data.products || data || [];
    _allProducts = products.map(p => ({id: p.id || p.product_id, name: p.name || '', family: p.family || ''}));
    updateProductOptions();
  } catch(e) {}
}

// ── KPI Cards ───────────────────────────────────────────────────

async function loadKPIs() {
  const d = await apiFetch('/api/dashboard/kpis' + dashFilterParams());
  setKPI('kpi-oee', d.oee, '%', {y: 60, g: 85});
  setKPI('kpi-throughput', d.throughput, 'WOs', {y: 5, g: 10});
  setKPI('kpi-wip', d.wip, 'active', {y: 2, g: 5});
  setKPI('kpi-ontime', d.on_time, '%', {y: 80, g: 95});
  setKPI('kpi-fpy', d.fpy, '%', {y: 95, g: 97});
  setKPI('kpi-util', d.utilization, '%', {y: 70, g: 90});
}

function setKPI(id, value, unit, thresholds) {
  const card = document.getElementById(id);
  if (!card) return;
  const color = value >= thresholds.g ? 'green' : value >= thresholds.y ? 'yellow' : 'red';
  card.className = 'kpi-card ' + color;
  card.querySelector('.kpi-unit').textContent = unit;
  animateValue(card.querySelector('.kpi-value'), 0, parseFloat(value) || 0, 1000);
}

// ── Charts (all destroy before recreate) ────────────────────────

async function loadOEEChart() {
  const data = await apiFetch('/api/dashboard/oee_by_wc' + dashFilterParams());
  const ctx = document.getElementById('oeeChart');
  if (!ctx) return;
  if (oeeChart) oeeChart.destroy();
  if (!data.length) { oeeChart = null; return; }
  oeeChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.wc_id),
      datasets: [
        { label: 'Availability', data: data.map(d => d.availability), backgroundColor: '#3b82f6' },
        { label: 'Performance', data: data.map(d => d.performance), backgroundColor: '#f59e0b' },
        { label: 'Quality', data: data.map(d => d.quality), backgroundColor: '#22c55e' }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, max: 100, title: { display: true, text: '%' } } },
      plugins: { title: { display: false } } }
  });
}

async function loadParetoChart() {
  const data = await apiFetch('/api/dashboard/scrap_pareto' + dashFilterParams());
  const ctx = document.getElementById('paretoChart');
  if (!ctx) return;
  if (paretoChart) paretoChart.destroy();
  if (!data.length) { paretoChart = null; return; }
  paretoChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.cause_code),
      datasets: [{ label: 'Scrap (ft)', data: data.map(d => d.total_ft), backgroundColor: ['#ef4444','#f59e0b','#eab308','#3b82f6','#8b5cf6'] }]
    },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } } }
  });
}

async function loadWOChart() {
  const data = await apiFetch('/api/dashboard/wo_status' + dashFilterParams());
  const ctx = document.getElementById('woChart');
  if (!ctx) return;
  if (woChart) woChart.destroy();
  if (!data.length) { woChart = null; return; }
  const colors = { Pending: '#64748b', Released: '#3b82f6', InProcess: '#f59e0b', QCHold: '#ef4444', Complete: '#22c55e', Cancelled: '#475569' };
  woChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.status),
      datasets: [{ data: data.map(d => d.count), backgroundColor: data.map(d => colors[d.status] || '#64748b') }]
    },
    options: { responsive: true, maintainAspectRatio: false, cutout: '60%',
      plugins: { legend: { position: 'right' } } }
  });
}

async function loadCapacityChart() {
  const data = await apiFetch('/api/dashboard/capacity' + dashFilterParams());
  const ctx = document.getElementById('capacityChart');
  if (!ctx) return;
  if (capacityChart) capacityChart.destroy();
  if (!data.length) { capacityChart = null; return; }
  capacityChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.wc_id),
      datasets: [
        { label: 'Current Load (hrs)', data: data.map(d => d.current_load_hrs), backgroundColor: '#3b82f6' },
        { label: 'Target', data: data.map(d => d.capacity_hrs_per_week * d.utilization_target), type: 'line', borderColor: '#f59e0b', borderDash: [5, 5], pointRadius: 0, fill: false }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false,
      scales: { y: { title: { display: true, text: 'Hours' } } } }
  });
}

// ── Throughput Trend ─────────────────────────────────────────────

async function loadThroughputTrend() {
  const data = await apiFetch('/api/dashboard/throughput_trend' + dashFilterParams());
  const ctx = document.getElementById('throughputTrendChart');
  if (!ctx) return;
  if (throughputTrendChart) throughputTrendChart.destroy();
  if (!data || !data.length) {
    throughputTrendChart = new Chart(ctx, {
      type: 'line', data: { labels: ['No data'], datasets: [{ data: [0], borderColor: '#334155' }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
    return;
  }
  throughputTrendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.day),
      datasets: [
        { label: 'Output (ft)', data: data.map(d => d.output_ft), borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.08)', fill: true, tension: 0.3, pointRadius: 3, borderWidth: 2, yAxisID: 'y' },
        { label: 'OEE %', data: data.map(d => d.avg_oee), borderColor: '#22c55e',
          borderDash: [4,3], tension: 0.3, pointRadius: 2, borderWidth: 2, yAxisID: 'y1' }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false,
      scales: {
        y: { position: 'left', title: { display: true, text: 'Output (ft)' }, beginAtZero: true },
        y1: { position: 'right', title: { display: true, text: 'OEE %' }, min: 0, max: 100, grid: { drawOnChartArea: false } },
        x: { ticks: { maxRotation: 45, font: { size: 10 } } }
      },
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
    }
  });
}

// ── Schedule Adherence ──────────────────────────────────────────

async function loadScheduleAdherence() {
  const kpis = document.getElementById('schedKPIs');
  const tbody = document.querySelector('#schedTable tbody');
  if (!kpis || !tbody) return;
  try {
    const data = await apiFetch('/api/dashboard/schedule_adherence' + dashFilterParams());
    const s = data.summary || {};
    const statusColors = { on_time: 'green', late: 'red', overdue: 'red', in_progress: 'blue' };
    kpis.innerHTML = Object.entries(s).map(([k, v]) => {
      const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      return `<div class="kpi-card ${statusColors[k] || 'blue'}" style="padding:8px"><div class="kpi-label" style="font-size:10px">${label}</div><div class="kpi-value" style="font-size:20px">${v}</div></div>`;
    }).join('');
    const orders = data.orders || [];
    if (!orders.length) { tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">No scheduled WOs</td></tr>'; return; }
    const badgeMap = { 'On Time': 'badge-green', 'Late': 'badge-red', 'Overdue': 'badge-red', 'In Progress': 'badge-blue', 'Pending': 'badge-yellow' };
    tbody.innerHTML = orders.slice(0, 10).map(r => `<tr>
      <td>${r.wo_id}</td>
      <td>${r.product_name || r.product_id}</td>
      <td>${r.due_date || '—'}</td>
      <td><span class="badge ${badgeMap[r.adherence_status] || 'badge-yellow'}">${r.adherence_status}</span></td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">Error loading</td></tr>'; }
}

// ── Extra charts (downtime, scrap by WC, maintenance) ───────────

async function loadExtraCharts() {
  const fp = dashFilterParams();

  // Downtime by Category
  const dtCat = await apiFetch('/api/dashboard/downtime_by_category' + fp);
  const dtCtx = document.getElementById('downtimeChart');
  if (dtCtx) {
    if (downtimeChart) downtimeChart.destroy();
    if (dtCat.length) {
      const lossColors = {Breakdown:'#ef4444',Setup:'#f59e0b',MaterialWait:'#eab308',QualityHold:'#8b5cf6',PM:'#3b82f6',NoOrders:'#64748b',Other:'#475569'};
      downtimeChart = new Chart(dtCtx, {
        type: 'bar', data: {
          labels: dtCat.map(d => d.category),
          datasets: [{ label: 'Minutes', data: dtCat.map(d => d.total_min),
            backgroundColor: dtCat.map(d => lossColors[d.category] || '#64748b') }]
        }, options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { title: { display: true, text: 'Total Downtime (min)' } } } }
      });
    } else { downtimeChart = null; }
  }

  // Downtime by Work Center
  const dtWc = await apiFetch('/api/dashboard/downtime_by_wc' + fp);
  const dtWcCtx = document.getElementById('downtimeWcChart');
  if (dtWcCtx) {
    if (downtimeWcChart) downtimeWcChart.destroy();
    if (dtWc.stacked) {
      const s = dtWc.stacked;
      const catColors = {Breakdown:'#ef4444',Setup:'#f59e0b',MaterialWait:'#eab308',QualityHold:'#8b5cf6',PM:'#3b82f6',NoOrders:'#64748b',Other:'#475569'};
      downtimeWcChart = new Chart(dtWcCtx, {
        type: 'bar', data: {
          labels: s.work_centers,
          datasets: s.categories.map(cat => ({
            label: cat, data: s.data[cat],
            backgroundColor: catColors[cat] || '#64748b',
          }))
        }, options: { responsive: true, maintainAspectRatio: false,
          scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'Downtime (min)' } } },
          plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } } }
      });
    } else { downtimeWcChart = null; }
  }

  // Scrap by Work Center
  const scWc = await apiFetch('/api/dashboard/scrap_by_wc' + fp);
  const scWcCtx = document.getElementById('scrapWcChart');
  if (scWcCtx) {
    if (scrapWcChart) scrapWcChart.destroy();
    if (scWc.stacked) {
      const s = scWc.stacked;
      const causeColors = {STARTUP:'#ef4444',CHANGEOVER:'#f59e0b',SPARK_FAULT:'#eab308',OD_EXCURSION:'#3b82f6',MATERIAL_DEFECT:'#8b5cf6',COMPOUND_BLEED:'#22c55e'};
      scrapWcChart = new Chart(scWcCtx, {
        type: 'bar', data: {
          labels: s.work_centers,
          datasets: s.causes.map(cause => ({
            label: cause, data: s.data[cause],
            backgroundColor: causeColors[cause] || '#64748b',
          }))
        }, options: { responsive: true, maintainAspectRatio: false,
          scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'Scrap (ft)' } } },
          plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } } }
      });
    } else { scrapWcChart = null; }
  }

  // Maintenance Charts (filtered by WC)
  const maint = await apiFetch('/api/dashboard/maintenance_upcoming' + fp);

  // Chart 1: PM Status by Work Center (stacked bar: overdue / due soon / ok)
  const msCtx = document.getElementById('maintStatusChart');
  if (msCtx) {
    if (maintStatusChart) maintStatusChart.destroy();
    if (maint.length) {
      // Group by WC
      const wcMap = {};
      maint.forEach(m => {
        if (!wcMap[m.wc_id]) wcMap[m.wc_id] = { overdue: 0, due_soon: 0, ok: 0 };
        if (m.pm_status === 'OVERDUE') wcMap[m.wc_id].overdue++;
        else if (m.pm_status === 'DUE SOON') wcMap[m.wc_id].due_soon++;
        else wcMap[m.wc_id].ok++;
      });
      const wcs = Object.keys(wcMap).sort();
      maintStatusChart = new Chart(msCtx, {
        type: 'bar',
        data: {
          labels: wcs,
          datasets: [
            { label: 'Overdue', data: wcs.map(w => wcMap[w].overdue), backgroundColor: '#ef4444' },
            { label: 'Due Soon', data: wcs.map(w => wcMap[w].due_soon), backgroundColor: '#f59e0b' },
            { label: 'OK', data: wcs.map(w => wcMap[w].ok), backgroundColor: '#22c55e' }
          ]
        },
        options: { responsive: true, maintainAspectRatio: false,
          scales: { x: { stacked: true, ticks: { font: { size: 10 } } }, y: { stacked: true, title: { display: true, text: 'PM Count' }, beginAtZero: true } },
          plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
        }
      });
    } else { maintStatusChart = null; }
  }

  // Chart 2: Days Until PM Due (horizontal bar per equipment, color by status)
  const mtCtx = document.getElementById('maintTimelineChart');
  if (mtCtx) {
    if (maintTimelineChart) maintTimelineChart.destroy();
    if (maint.length) {
      const sorted = maint.slice().sort((a, b) => a.days_until_due - b.days_until_due);
      maintTimelineChart = new Chart(mtCtx, {
        type: 'bar',
        data: {
          labels: sorted.map(m => m.equipment_code),
          datasets: [{
            label: 'Days Until Due',
            data: sorted.map(m => m.days_until_due),
            backgroundColor: sorted.map(m =>
              m.pm_status === 'OVERDUE' ? '#ef4444' : m.pm_status === 'DUE SOON' ? '#f59e0b' : '#22c55e'
            )
          }]
        },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
          scales: {
            x: { title: { display: true, text: 'Days (negative = overdue)' } },
            y: { ticks: { font: { size: 9 } } }
          },
          plugins: {
            legend: { display: false },
            annotation: {
              annotations: {
                zeroline: { type: 'line', xMin: 0, xMax: 0, borderColor: '#ef4444', borderWidth: 2, borderDash: [4,3] }
              }
            }
          }
        }
      });
    } else { maintTimelineChart = null; }
  }
  ['downtimeChart','downtimeWcChart','scrapWcChart','maintStatusChart','maintTimelineChart'].forEach(id => stampChart(id));
}

// ── Init ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  populateWCDropdown();
  populateProductDropdown();
  reloadDashboard();
  // Auto-refresh every 5 seconds (respects active filters)
  setInterval(() => { loadKPIs(); updateTimestamp(); }, 5000);
});
