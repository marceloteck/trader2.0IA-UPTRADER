// Dashboard App - Trading Brains L7 (Dashboard Enhancements)

const API_BASE = '';
const REFRESH_INTERVAL = 3000; // 3 seconds

// ============================================================================
// Utilities
// ============================================================================

async function fetchJson(path) {
  try {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`Error fetching ${path}:`, e);
    return null;
  }
}

function formatTime(isoString) {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDate(isoString) {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return date.toLocaleDateString('pt-BR', { month: '2-digit', day: '2-digit' });
}

function updateSafetyStatus(status) {
  const banner = document.getElementById('mode-banner');
  const warning = document.getElementById('live-warning');
  const locksList = document.getElementById('safety-locks');

  if (banner) {
    const effectiveMode = (status.live_mode_effective || status.live_mode || 'SIM').toUpperCase();
    const isReal = effectiveMode === 'REAL';
    banner.textContent = isReal ? 'REAL' : 'SIMULAÇÃO';
    banner.classList.toggle('real', isReal);
    banner.classList.toggle('sim', !isReal);
  }

  if (warning) {
    if ((status.live_mode_effective || '').toUpperCase() === 'REAL') {
      warning.textContent = '🚨 MODO REAL ATIVO - RISCO ALTO 🚨';
      warning.style.animation = 'pulse 1s infinite';
    } else {
      warning.textContent = '';
      warning.style.animation = 'none';
    }
  }

  if (locksList) {
    locksList.innerHTML = '';
    const locks = status.safety_locks || [];
    if (locks.length === 0) {
      locksList.innerHTML = '<li class="lock-item">Sem dados de travas.</li>';
      return;
    }
    locks.forEach(lock => {
      const li = document.createElement('li');
      li.className = 'lock-item';
      const label = document.createElement('span');
      label.textContent = lock.label;
      const chip = document.createElement('span');
      const active = Boolean(lock.active);
      chip.className = `lock-chip ${active ? 'active' : 'ok'}`;
      chip.textContent = active ? 'ATIVA' : 'OK';
      li.appendChild(label);
      li.appendChild(chip);
      locksList.appendChild(li);
    });
  }
}

// ============================================================================
// Symbol Management (L7)
// ============================================================================

async function loadSymbolList() {
  const data = await fetchJson('/symbols/list');
  if (!data) return;
  
  const dropdown = document.getElementById('symbol-dropdown');
  const currentSymbol = data.current;
  
  dropdown.innerHTML = '';
  
  if (data.symbols && data.symbols.length > 0) {
    data.symbols.forEach(sym => {
      const option = document.createElement('option');
      option.value = sym.name;
      option.textContent = `${sym.name} (spread: ${sym.spread})`;
      if (sym.name === currentSymbol) option.selected = true;
      dropdown.appendChild(option);
    });
  } else {
    const option = document.createElement('option');
    option.textContent = currentSymbol || 'Nenhum';
    option.value = currentSymbol || '';
    dropdown.appendChild(option);
  }
  
  // Update health badge
  updateSymbolHealth(data.mt5_connected);
}

async function setSymbol(symbol) {
  if (!symbol) return;
  
  try {
    const res = await fetch('/symbols/set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol })
    });
    
    if (res.ok) {
      const result = await res.json();
      console.log('Symbol changed:', result);
      loadSymbolList();
    } else {
      alert(`Erro: ${res.status}`);
    }
  } catch (e) {
    console.error('Error setting symbol:', e);
  }
}

function updateSymbolHealth(connected) {
  const badge = document.getElementById('symbol-health');
  if (connected) {
    badge.textContent = '● Conectado';
    badge.className = 'health-badge connected';
  } else {
    badge.textContent = '● Desconectado';
    badge.className = 'health-badge error';
  }
}

// ============================================================================
// Market Status (L7)
// ============================================================================

async function loadMarketStatus() {
  const data = await fetchJson('/market-status/current');
  if (!data) return;
  
  const headline = document.getElementById('status-headline');
  const phase = document.getElementById('status-phase');
  const riskEl = document.getElementById('status-risk');
  
  headline.textContent = data.headline || 'Aguardando análise...';
  phase.textContent = data.phase || '';
  
  riskEl.textContent = `Risco: ${data.risk_state || 'OK'}`;
  riskEl.className = `status-risk ${(data.risk_state || 'OK').toLowerCase()}`;
}

// ============================================================================
// Scoreboard (L7)
// ============================================================================

async function loadScoreboard() {
  const data = await fetchJson('/scoreboard/live');
  if (!data) return;
  
  const counters = data.counters || {};
  const metrics = data.metrics || {};
  
  // Counters
  document.getElementById('score-buy').textContent = counters.buy_signals || 0;
  document.getElementById('score-sell').textContent = counters.sell_signals || 0;
  document.getElementById('score-hold').textContent = counters.hold_signals || 0;
  
  document.getElementById('score-trades').textContent = counters.trades_total || 0;
  document.getElementById('score-win').textContent = counters.trades_win || 0;
  document.getElementById('score-loss').textContent = counters.trades_loss || 0;
  
  document.getElementById('score-news-blocks').textContent = counters.blocks_news || 0;
  document.getElementById('score-corr-blocks').textContent = counters.blocks_correlation || 0;
  
  // Metrics
  document.getElementById('score-pnl').textContent = `$${(metrics.pnl_today || 0).toFixed(2)}`;
  document.getElementById('score-wr').textContent = `${((metrics.winrate_today || 0) * 100).toFixed(1)}%`;
  document.getElementById('score-pf').textContent = (metrics.pf_today || 0).toFixed(2);
  
  // Recent events
  loadRecentEvents(data.recent_events);
}

function loadRecentEvents(events) {
  const tbody = document.getElementById('recent-events');
  tbody.innerHTML = '';
  
  if (!events || events.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center">Sem eventos recentes</td></tr>';
    return;
  }
  
  events.slice(0, 20).forEach(event => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${formatTime(event.timestamp)}</td>
      <td><strong>${event.type}</strong></td>
      <td>${JSON.stringify(event.payload).substring(0, 100)}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ============================================================================
// Legacy Endpoints
// ============================================================================

async function loadLegacyData() {
  const status = await fetchJson('/status');
  if (status) {
    updateSafetyStatus(status);
  }
  
  const signals = await fetchJson('/signals?limit=10');
  if (signals) {
    document.getElementById('signals').textContent = JSON.stringify(signals, null, 2);
  }
  
  const trades = await fetchJson('/trades?limit=10');
  if (trades) {
    document.getElementById('trades').textContent = JSON.stringify(trades, null, 2);
  }
  
  const regime = await fetchJson('/regime/current');
  if (regime) {
    document.getElementById('regime').textContent = JSON.stringify(regime, null, 2);
  }
  
  const levels = await fetchJson('/levels/current');
  if (levels) {
    document.getElementById('levels').textContent = JSON.stringify(levels, null, 2);
  }
  
  const risk = await fetchJson('/risk/status');
  if (risk) {
    document.getElementById('risk').textContent = JSON.stringify(risk, null, 2);
  }
}

// ============================================================================
// Kill Switch
// ============================================================================

document.getElementById('kill-btn').addEventListener('click', async () => {
  if (confirm('Tem certeza que quer PARAR o trading?')) {
    const res = await fetch('/control/kill', { method: 'POST' });
    const result = await res.json();
    if (result.status === 'ok') {
      alert('Trading PARADO ✓');
    } else {
      alert('Parada desabilitada no dashboard');
    }
  }
});

// ============================================================================
// Symbol Dropdown Event
// ============================================================================

document.getElementById('symbol-dropdown').addEventListener('change', (e) => {
  const symbol = e.target.value;
  if (symbol) {
    setSymbol(symbol);
  }
});

// ============================================================================
// Main Refresh
// ============================================================================

async function refresh() {
  loadSymbolList();
  loadMarketStatus();
  loadScoreboard();
  loadLegacyData();
}

// ============================================================================
// Initialization
// ============================================================================

document.getElementById('refresh').addEventListener('click', refresh);

// Initial load
refresh();

// Auto-refresh every 3 seconds
setInterval(refresh, REFRESH_INTERVAL);

// Pulse animation for live warning
const style = document.createElement('style');
style.textContent = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
`;
document.head.appendChild(style);
