/* SodhiCable MES v4.0 — Common JavaScript */

// Fetch helper with error handling + optional loading/error UI
async function apiFetch(url, options = {}) {
  try {
    const resp = await fetch(url, options);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.message || `HTTP ${resp.status}`);
    return data;
  } catch (err) {
    showToast(err.message, 'error');
    throw err;
  }
}

// Wrap a chart-loading function with loading skeleton + error boundary
async function loadWithState(containerId, loadFn) {
  const el = document.getElementById(containerId);
  if (!el) return loadFn();
  const card = el.closest('.chart-card');
  if (card) card.classList.add('loading');
  try {
    await loadFn();
  } catch(e) {
    el.innerHTML = `<div class="error-boundary">
      <div style="font-size:14px;margin-bottom:4px">Failed to load data</div>
      <div style="font-size:11px;color:var(--text-muted)">${e.message || 'Network error'}</div>
      <button onclick="loadWithState('${containerId}', ${loadFn.name || 'null'})">Retry</button>
    </div>`;
  } finally {
    if (card) card.classList.remove('loading');
  }
}

async function apiPost(url, body = {}) {
  return apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

// Toast notifications
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, duration);
}

// Update "Last Updated" timestamp
function updateTimestamp() {
  const el = document.getElementById('lastUpdated');
  if (el) el.textContent = 'Updated: ' + new Date().toLocaleTimeString();
}

// Tab switching
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.closest('.tab-bar').dataset.group || 'default';
      document.querySelectorAll(`.tab-btn`).forEach(b => b.classList.remove('active'));
      document.querySelectorAll(`.tab-content`).forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add('active');
    });
  });
}

// Color helpers for KPI cards
function kpiColor(value, thresholds) {
  if (!thresholds) return 'blue';
  const [yellow, green] = thresholds;
  if (value >= green) return 'green';
  if (value >= yellow) return 'yellow';
  return 'red';
}

// Chart.js defaults for dark theme with smooth animations
if (typeof Chart !== 'undefined') {
  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = '#1e293b';
  Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 8;
  Chart.defaults.animation = { duration: 800, easing: 'easeOutQuart' };
  Chart.defaults.elements.line.tension = 0.3;
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.bar.borderRadius = 4;
  Chart.defaults.elements.bar.borderSkipped = false;
  Chart.defaults.scales.x = Chart.defaults.scales.x || {};
  Chart.defaults.scales.y = Chart.defaults.scales.y || {};
}

// SSE client
function connectSSE(url, onMessage) {
  const source = new EventSource(url);
  source.onmessage = (e) => { try { onMessage(JSON.parse(e.data)); } catch (err) { console.error('SSE parse error:', err); } };
  source.onerror = () => { showToast('Connection lost. Reconnecting...', 'error'); };
  return source;
}

// Format number with commas
function fmt(n, decimals = 0) {
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

// Animated counter — numbers count up when KPI loads
function animateValue(el, start, end, duration = 800) {
  if (!el) return;
  const isFloat = String(end).includes('.') || end % 1 !== 0;
  const decimals = isFloat ? (String(end).split('.')[1] || '').length || 1 : 0;
  const range = end - start;
  const startTime = performance.now();

  function step(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = start + range * eased;
    el.textContent = decimals > 0 ? current.toFixed(decimals) : Math.round(current).toLocaleString();
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// Set KPI with animation
function setKPIAnimated(cardId, value, unit, color) {
  const card = document.getElementById(cardId);
  if (!card) return;
  const valEl = card.querySelector('.kpi-value');
  const unitEl = card.querySelector('.kpi-unit');
  if (valEl) {
    const numVal = parseFloat(value);
    if (!isNaN(numVal)) {
      animateValue(valEl, 0, numVal);
    } else {
      valEl.textContent = value;
    }
  }
  if (unitEl && unit !== undefined) unitEl.textContent = unit;
  if (color) card.className = 'kpi-card ' + color;
}

// Mini sparkline (tiny inline chart in a KPI card)
function drawSparkline(canvasId, data, color = '#3b82f6') {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data || !data.length) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width = canvas.offsetWidth || 120;
  const h = canvas.height = canvas.offsetHeight || 30;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = w / (data.length - 1);

  ctx.clearRect(0, 0, w, h);
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  data.forEach((v, i) => {
    const x = i * step;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Fill gradient
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + '30');
  grad.addColorStop(1, color + '05');
  ctx.fillStyle = grad;
  ctx.fill();
}

// Theme toggle (#15)
function toggleTheme() {
  const current = document.documentElement.dataset.theme || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('mesTheme', next);
  // Update Chart.js defaults for theme
  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = next === 'light' ? '#475569' : '#94a3b8';
    Chart.defaults.borderColor = next === 'light' ? '#e2e8f0' : '#1e293b';
  }
}

// ── Global Search ──────────────────────────────────────────────
let _searchTimer = null;
function debounceSearch(q) {
  clearTimeout(_searchTimer);
  const panel = document.getElementById('searchResults');
  if (!q || q.length < 2) { panel.style.display = 'none'; return; }
  _searchTimer = setTimeout(async () => {
    try {
      const d = await apiFetch('/api/search?q=' + encodeURIComponent(q));
      const r = d.results || {};
      if (d.total === 0) { panel.innerHTML = '<p style="color:var(--text-muted);font-size:12px;padding:8px">No results</p>'; panel.style.display = 'block'; return; }
      let html = '';
      const sections = [
        {key:'work_orders', label:'Work Orders', icon:'📋', linkFn: i => `/workorder/${i.wo_id}`, textFn: i => `${i.wo_id} — ${i.product_id} (${i.status})`},
        {key:'products', label:'Products', icon:'📦', linkFn: i => '/quality', textFn: i => `${i.product_id} — ${i.name} [${i.family}]`},
        {key:'equipment', label:'Equipment', icon:'🔧', linkFn: i => '/equipment', textFn: i => `${i.equipment_code} — ${i.description}`},
        {key:'personnel', label:'Personnel', icon:'👤', linkFn: i => '/labor', textFn: i => `${i.employee_name} (${i.role})`},
        {key:'lots', label:'Lots', icon:'🏷️', linkFn: i => `/traceability`, textFn: i => `${i.output_lot} (WO: ${i.wo_id||'?'})`},
      ];
      sections.forEach(s => {
        const items = r[s.key] || [];
        if (!items.length) return;
        html += `<div style="font-size:10px;text-transform:uppercase;color:var(--text-muted);margin:6px 0 3px;font-weight:600">${s.icon} ${s.label}</div>`;
        items.forEach(i => {
          html += `<a href="${s.linkFn(i)}" style="display:block;padding:4px 8px;font-size:12px;color:var(--text-primary);text-decoration:none;border-radius:4px;margin:1px 0" onmouseover="this.style.background='rgba(59,130,246,0.1)'" onmouseout="this.style.background=''">${s.textFn(i)}</a>`;
        });
      });
      panel.innerHTML = html;
      panel.style.display = 'block';
    } catch(e) { panel.style.display = 'none'; }
  }, 300);
}
// Close search on click outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('#globalSearch') && !e.target.closest('#searchResults')) {
    const p = document.getElementById('searchResults'); if (p) p.style.display = 'none';
  }
});

// ── Notification Center ────────────────────────────────────────
function toggleNotifications() {
  const p = document.getElementById('notifPanel');
  if (!p) return;
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
  if (p.style.display === 'block') loadNotifications();
}
async function loadNotifications() {
  try {
    const d = await apiFetch('/api/notifications');
    const badge = document.getElementById('notifBadgeTop');
    const countLabel = document.getElementById('notifCountLabel');
    const list = document.getElementById('notifList');
    if (badge) { badge.textContent = d.count; badge.style.display = d.count > 0 ? 'flex' : 'none'; }
    if (countLabel) { countLabel.textContent = d.count > 0 ? d.count + ' active' : 'All clear'; }
    if (!list) return;
    if (!d.items.length) { list.innerHTML = '<p style="color:var(--accent-green);font-size:12px">All clear — no active notifications.</p>'; return; }
    const sevColors = {critical:'#ef4444',warning:'#f59e0b',info:'#3b82f6'};
    list.innerHTML = d.items.map(n =>
      `<a href="${n.link}" style="display:block;padding:6px 8px;margin:2px 0;border-radius:4px;border-left:3px solid ${sevColors[n.severity]||'#64748b'};text-decoration:none;font-size:11px;color:var(--text-primary);background:var(--bg-secondary)" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
        <strong>${n.title}</strong>
        ${n.ts ? `<div style="font-size:9px;color:var(--text-muted)">${n.ts}</div>` : ''}
      </a>`
    ).join('');
  } catch(e) {}
}

// DOM ready
document.addEventListener('DOMContentLoaded', () => {
  // Restore saved theme
  document.documentElement.dataset.theme = localStorage.getItem('mesTheme') || 'dark';
  initTabs();
  updateTimestamp();
  // Load notification count on every page
  loadNotifications();
  // Refresh notification count every 30 seconds
  setInterval(loadNotifications, 30000);
});
