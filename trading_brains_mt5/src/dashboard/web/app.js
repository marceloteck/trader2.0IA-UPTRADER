async function fetchJson(path) {
  const res = await fetch(path);
  return res.json();
}

async function refresh() {
  const status = await fetchJson('/status');
  document.getElementById('status').textContent = JSON.stringify(status, null, 2);
  const warning = document.getElementById('live-warning');
  warning.textContent = status.live_enabled ? 'MODO REAL ATIVO - RISCO ALTO' : '';
  const signals = await fetchJson('/signals?limit=10');
  document.getElementById('signals').textContent = JSON.stringify(signals, null, 2);
  const trades = await fetchJson('/trades?limit=10');
  document.getElementById('trades').textContent = JSON.stringify(trades, null, 2);
  const scoreboard = await fetchJson('/brains/scoreboard?limit=10');
  document.getElementById('scoreboard').textContent = JSON.stringify(scoreboard, null, 2);
  const regime = await fetchJson('/regime/current');
  document.getElementById('regime').textContent = JSON.stringify(regime, null, 2);
  const levels = await fetchJson('/levels/current');
  document.getElementById('levels').textContent = JSON.stringify(levels, null, 2);
  const risk = await fetchJson('/risk/status');
  document.getElementById('risk').textContent = JSON.stringify(risk, null, 2);
}

document.getElementById('refresh').addEventListener('click', refresh);
refresh();
