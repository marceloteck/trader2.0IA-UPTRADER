"""
V3 QUICK REFERENCE: Guia Rápido de Uso

═══════════════════════════════════════════════════════════════════════════════
1. INICIALIZAR V3 COMPONENTS
═══════════════════════════════════════════════════════════════════════════════

from src.brains.meta_brain import MetaBrain
from src.features.regime_detector import RegimeDetector
from src.training.reinforcement import LightReinforcementLearner
from src.models.decay import KnowledgeDecayPolicy
from src.monitoring.self_diagnosis import SelfDiagnosisSystem
from src.config.settings import Settings

settings = Settings()
db_path = "trading.db"

# Componentes V3
meta_brain = MetaBrain(settings, db_path)
regime_detector = RegimeDetector(settings, db_path)
rl_learner = LightReinforcementLearner(settings, db_path)
decay_policy = KnowledgeDecayPolicy(half_life_days=30)
health_system = SelfDiagnosisSystem()


═══════════════════════════════════════════════════════════════════════════════
2. FLUXO DE DECISÃO (No BossBrain)
═══════════════════════════════════════════════════════════════════════════════

# Input: market data, brain scores
brain_scores = {"Elliott": 0.8, "Gann": 0.6, "Wyckoff": 0.75}
df = get_historical_data(100)  # últimas 100 velas

# 1. Detectar regime
regime_state = regime_detector.detect(df, hour=datetime.now().hour)
print(f"Regime: {regime_state.regime} ({regime_state.confidence:.0%})")

# 2. MetaBrain avalia
meta_decision = meta_brain.evaluate(
    current_regime=regime_state.regime,
    current_hour=regime_state.metadata["hour"],
    current_volatility=regime_state.volatility,
    brain_scores=brain_scores,
    recent_trades=get_recent_trades(50)
)
print(f"MetaBrain: {'ALLOW' if meta_decision.allow_trading else 'BLOCK'}")
print(f"Weights: {meta_decision.weight_adjustment}")

# 3. Aplicar pesos ajustados
adjusted_scores = {
    brain: brain_scores[brain] * meta_decision.weight_adjustment.get(brain, 1.0)
    for brain in brain_scores
}

# 4. RL policy
rl_action = rl_learner.get_action(
    regime=regime_state.regime,
    hour=regime_state.metadata["hour"],
    volatility=regime_state.volatility,
    trend=regime_state.trend_direction,
    rsi=regime_state.metadata.get("rsi", 50),
    base_confidence=meta_decision.global_confidence
)
print(f"RL says: {rl_action.action} (confidence {rl_action.confidence:.0%})")

# 5. Health check
health_report = health_system.diagnose(
    recent_trades=get_recent_trades(50),
    brain_performance=get_brain_performance(),
    current_regime=regime_state.regime,
    current_volatility=regime_state.volatility,
    regime_confidence=regime_state.confidence,
    data_staleness_minutes=0.5
)
print(f"Health: {health_report.status} (score {health_report.overall_score:.2f})")

# 6. Decisão final
if meta_decision.allow_trading and rl_action.action == "ENTER" and health_report.is_healthy:
    # Calcular tamanho
    position_size = base_size * health_report.position_size_factor
    
    # Executar trade
    entry = execute_trade(adjusted_scores, position_size)
    
    # Log
    log_decision({
        "regime": regime_state.regime,
        "meta_confidence": meta_decision.global_confidence,
        "rl_action": rl_action.action,
        "health_status": health_report.status,
        "position_size": position_size
    })
else:
    # Skip
    print("SKIP trade")


═══════════════════════════════════════════════════════════════════════════════
3. FEEDBACK LOOP (Após Trade)
═══════════════════════════════════════════════════════════════════════════════

# Quando trade fecha
trade = {
    "symbol": "EURUSD",
    "opened_at": "2024-01-15T14:30:00",
    "closed_at": "2024-01-15T15:15:00",
    "pnl": 0.5,  # % gain
    "mfe": 100,  # pontos
    "mae": 10,   # pontos
    "side": "BUY",
    "regime": current_regime,
}

# 1. Registrar em replay priority (aprender mais de perdas)
from src.db import repo

if trade["pnl"] < 0:
    # Perda: alta prioridade
    priority = abs(trade["pnl"]) * 2
else:
    # Ganho: baixa prioridade
    priority = abs(trade["pnl"]) * 0.5

repo.insert_replay_priority(
    db_path,
    trade_id=trade["id"],
    priority_score=priority,
    loss_magnitude=max(0, -trade["pnl"]),
    regime=trade["regime"]
)

# 2. Atualizar MetaBrain
brains_used = ["Elliott", "Gann", "Wyckoff"]
meta_brain.update_performance(
    brain_id="Elliott",  # Para cada cérebro usado
    regime=trade["regime"],
    trades=[trade]
)

# 3. Atualizar RL
rl_learner.update(
    regime=current_regime,
    hour=closed_hour,
    volatility=current_volatility,
    trend=current_trend,
    rsi=current_rsi,
    action_taken="ENTER",  # O que foi feito
    reward=trade["pnl"],  # O resultado
    next_state_hash=None  # Próximo estado (opcional)
)


═══════════════════════════════════════════════════════════════════════════════
4. QUERIES DO BANCO DE DADOS
═══════════════════════════════════════════════════════════════════════════════

# MetaBrain performance
from src.db import repo

# Histórico de performance
history = repo.fetch_brain_performance_history(db_path, limit=100)
for h in history:
    print(f"{h['brain_id']} em {h['regime']}: WR={h['win_rate']:.0%}")

# Decisões do MetaBrain
decisions = repo.fetch_meta_decisions(db_path, limit=50)
for d in decisions:
    print(f"{d['regime']}: confidence={d['global_confidence']:.0%}")

# Transições de regime
transitions = repo.fetch_regime_history(db_path, limit=20)
for t in transitions:
    print(f"{t['from_regime']} → {t['to_regime']} ({t['from_duration']} candles)")

# Q-table da RL
q_values = repo.fetch_reinforcement_policy(db_path)
for q in q_values:
    print(f"State {q['state_hash'][:8]}: Q-value={q['q_value']:.3f}")

# Buffer de replay (priorizado)
buffer = repo.fetch_replay_buffer(db_path, regime="TREND_UP", limit=50)
for b in buffer:
    print(f"Trade {b['trade_id']}: priority={b['priority_score']:.2f}")


═══════════════════════════════════════════════════════════════════════════════
5. CONFIGURAÇÃO (settings.py)
═══════════════════════════════════════════════════════════════════════════════

# MetaBrain
meta_brain_enabled = True
meta_min_confidence = 0.3
meta_decay_half_life_days = 30.0

# Regime
regime_detector_enabled = True
regime_use_hmm = True  # Se hmmlearn disponível
regime_min_duration_candles = 3

# RL
rl_enabled = True
rl_learning_rate = 0.1
rl_epsilon_exploration = 0.2
rl_discount_factor = 0.95

# Health
health_check_enabled = True
health_pause_on_red = True
health_reduce_on_yellow = True
health_drawdown_alert_pct = 5.0
health_drawdown_critical_pct = 10.0


═══════════════════════════════════════════════════════════════════════════════
6. DASHBOARD ENDPOINTS V3
═══════════════════════════════════════════════════════════════════════════════

GET /api/v3/meta-brain/status
→ Decisão do MetaBrain atual

GET /api/v3/regime/current
→ Regime detectado e probabilidades de transição

GET /api/v3/rl-policy/action
→ Recomendação RL com Q-values e entropy

GET /api/v3/health/status
→ Diagnóstico de saúde (GREEN/YELLOW/RED)

GET /api/v3/brain-performance
→ Win rates e profit factors por cérebro × regime

GET /api/v3/knowledge-decay
→ Análise de decay temporal


═══════════════════════════════════════════════════════════════════════════════
7. MONITORAMENTO E DEBUGGING
═══════════════════════════════════════════════════════════════════════════════

# Ver saúde do sistema
health = health_system.diagnose(...)
print(f"Status: {health.status}")
for issue in health.issues:
    print(f"  ⚠️ {issue}")
for rec in health.recommendations:
    print(f"  💡 {rec}")

# Ver tendência de saúde
trend = health_system.get_health_trend(lookback=20)
print(f"Trend: {trend}")

# Ver exploração do espaço de estado RL
rl_exploration = rl_learner.get_exploration_score()
print(f"RL exploration: {rl_exploration:.0%}")

# Ver convergência de política
entropy = rl_learner.get_policy_entropy()
print(f"Policy entropy: {entropy:.2f} (0=determinístico, 1=aleatório)")

# Ver transições de regime preditas
next_regime = regime_detector.predict_regime_change()
if next_regime:
    print(f"Próximo regime previsto: {next_regime[0]} ({next_regime[1]:.0%})")

# Análise de decay
analyzer = TradeDecayAnalyzer(decay_policy)
decayed_metrics = analyzer.calculate_decayed_metrics(
    trades=recent_trades,
    current_regime=current_regime,
    current_volatility=volatility
)
print(f"WR bruto: {decayed_metrics['win_rate_raw']:.0%}")
print(f"WR com decay: {decayed_metrics['win_rate_decayed']:.0%}")


═══════════════════════════════════════════════════════════════════════════════
8. TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

PROBLEMA: MetaBrain não detecta cérebros novos
SOLUÇÃO: Criar entrada em brain_performance com trade_count=0, confiança=0.3

PROBLEMA: RL não aprende (Q-values sempre 0)
SOLUÇÃO: Verificar se reward está sendo normalizado corretamente (scale=100)

PROBLEMA: Regime sempre HIGH_VOL
SOLUÇÃO: Checar se dados estão corretos (sem gaps, data_feed limpa)

PROBLEMA: Health sempre RED
SOLUÇÃO: Checar drawdown (pode ser backtest com pouco capital)

PROBLEMA: Sem regime transitions detectadas
SOLUÇÃO: Habilitar logging em RegimeDetector.detect()

PROBLEMA: RL entropy = 1.0 (aleatório)
SOLUÇÃO: Sistema ainda em fase de exploração, rodar mais trades

PROBLEMA: Performance piora com V3 ativado
SOLUÇÃO: Parâmetros não calibrados, fazer parameter sweep


═══════════════════════════════════════════════════════════════════════════════
9. PERFORMANCE TIPS
═══════════════════════════════════════════════════════════════════════════════

1. Cache regime state (não recalcular a cada candle)
2. Batch updates no DB (commit a cada 10 trades, não cada trade)
3. Usar HMM apenas se hmmlearn disponível (fallback rápido)
4. Limpar histórico antigo periodicamente (manter últimas 1000 trades)
5. RL Q-table não cresce infinitamente (estados limitados por discretização)


═══════════════════════════════════════════════════════════════════════════════
10. VALIDAÇÃO
═══════════════════════════════════════════════════════════════════════════════

# Testar módulos V3
pytest tests/test_v3_core.py -v

# Testar integração
pytest tests/test_v3_integration.py -v

# Verificar sem regressão V2
pytest tests/test_v2_regression.py -v

# Coverage
pytest tests/test_v3_*.py --cov=src --cov-report=html
"""

if __name__ == "__main__":
    print(__doc__)
