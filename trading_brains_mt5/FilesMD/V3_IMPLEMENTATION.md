"""
V3 Implementation: Continuous Learning & Adaptive Trading System

STATUS: PHASE 1 COMPLETE (Core Modules)
═══════════════════════════════════════════════════════════════════════════════

MODULES IMPLEMENTED:

1. ✅ MetaBrain (src/brains/meta_brain.py) [~350 lines]
   └─ Cérebro dos cérebros que avalia performance histórica de cada um
   ├─ Input: regime, hour, volatilidade, brain_scores
   ├─ Output: weight_adjustment, confidence_global, allow_trading
   ├─ Learning: Ajusta pesos baseado em win_rate × profit_factor
   ├─ Decay: Reduz confiança de dados antigos (half-life: 30 dias)
   └─ Feature: Detecta anomalias (perdas consecutivas, drawdown)

2. ✅ Regime Detector (src/features/regime_detector.py) [~280 lines]
   └─ Detecta regimes automaticamente (5 tipos: UP, DOWN, RANGE, HIGH_VOL, UNKNOWN)
   ├─ Fallback: Heurístico com MAs e volatilidade se HMM não disponível
   ├─ HMM: Gaussian HMM com 4 estados se hmmlearn disponível
   ├─ Learning: Rastreia transições de regime para prever mudanças
   └─ Feature: Calcula regime_transition_probability

3. ✅ Light Reinforcement Learning (src/training/reinforcement.py) [~320 lines]
   └─ Q-learning simples sem deep learning
   ├─ Estado: regime × hora × vol × trend × RSI (discretizado)
   ├─ Ações: ENTER (operar) ou SKIP (não operar)
   ├─ Aprendizado: Q(s,a) ← Q(s,a) + α * [R + γ * max Q(s',a') - Q(s,a)]
   ├─ Recompensa: loss/100 para perdas, profit × Sharpe para ganhos
   ├─ Exploração: ε-greedy (20% aleatório, 80% exploita)
   └─ Métricas: Policy entropy para detectar convergência

4. ✅ Knowledge Decay (src/models/decay.py) [~280 lines]
   └─ 4 estratégias de envelhecimento de dados
   ├─ Temporal: exp(-t / half_life) → 50% aos 30 dias
   ├─ Regime-aware: reduz se regime muda, mais se duração é longa
   ├─ Performance-aware: reduz se win_rate cai
   ├─ Catalyst-based: reduz mais em volatilidade extrema
   └─ Analyzer: Recalcula métricas com decay aplicado

5. ✅ Self-Diagnosis System (src/monitoring/self_diagnosis.py) [~300 lines]
   └─ Monitora 6 dimensões de saúde
   ├─ Drawdown: GREEN (<5%), YELLOW (<10%), RED (>10%)
   ├─ Loss rate: Perdas consecutivas e taxa de perda
   ├─ Performance: Detecta degradação comparando periodos
   ├─ Regime: Alerta se desconhecido ou baixa confiança
   ├─ Volatilidade: Extrema (>5%), Alta (>3%), Normal
   ├─ Dados: Staleness check
   └─ Output: HealthReport com status (GREEN/YELLOW/RED) e recomendações

6. ✅ Database V3 (src/db/schema.py + repo.py)
   └─ 5 novas tabelas
   ├─ brain_performance: histórico de performance por cérebro × regime
   ├─ meta_decisions: log de decisões do MetaBrain
   ├─ regime_transitions: histórico de mudanças de regime
   ├─ reinforcement_policy: Q-table persistida
   └─ replay_priority: priorização de experiências para aprendizado


ARQUITETURA V3:
═══════════════════════════════════════════════════════════════════════════════

                              DECISION PIPELINE (V3)
                              ════════════════════════════════════════

    Market Data (OHLCV)
         │
         ├─→ [Feature Store]
         │   ├─ MAs, RSI, ATR, Pivots
         │   └─ Extract: vol, trend, rsi
         │
         ├─→ [Regime Detector]
         │   ├─ Detect: regime type
         │   └─ Output: regime, confidence
         │
         ├─→ [Individual Brains] (10 brains)
         │   ├─ WyckoffRange, Elliott, Gann, etc
         │   └─ Output: scores[], signals[]
         │
         └─→ [MetaBrain] ◄──── [Brain Performance DB]
             ├─ Evaluate: past win_rate × profit_factor
             ├─ Adjust: weights by regime + decay
             ├─ Filter: anomaly detection
             └─ Output: weight_adjustment[], confidence
         
         ─→ [RL Policy] ◄──── [Q-Table DB]
             ├─ State: discretized (regime, hour, vol, trend, rsi)
             ├─ Action: ENTER vs SKIP
             └─ Output: RL action recommendation
         
         ─→ [Self-Diagnosis] ◄──── [Recent Trades]
             ├─ Score: health on 6 dimensions
             ├─ Status: GREEN/YELLOW/RED
             └─ Output: position_size_factor


APRENDIZADO CONTÍNUO (Feedback Loop):
═══════════════════════════════════════════════════════════════════════════════

1. Antes de Trade:
   ─────────────
   - [Regime Detector] analisa últimas 100 velas
   - [MetaBrain] avalia performance histórica de cada cérebro
   - [RL Policy] recomenda ação baseado em estado discretizado
   - [Self-Diagnosis] verifica se sistema é saudável
   → Decisão: entrar com posição_size_factor de saúde

2. Durante Trade:
   ──────────────
   - Rastreia MFE/MAE
   - Se drawdown > limite: alerta

3. Após Trade (Feedback):
   ──────────────────────
   repo.insert_replay_priority(trade_id, loss_magnitude, regime)
   ↓
   MetaBrain.update_performance(brain_id, regime, [trades])
   ├─ Calcula novo win_rate, profit_factor
   ├─ Atualiza confidence (grow log com trades)
   └─ Persiste em brain_performance table
   ↓
   RegimeDetector detecta se mudou de regime
   ├─ Log transição em regime_transitions
   └─ Aplica decay maior em conhecimento antigo
   ↓
   LightReinforcementLearner.update(state, action, reward)
   ├─ Calcula Q-value update
   ├─ Explora mais em regiões fracas (ε-greedy)
   └─ Persiste em reinforcement_policy table
   ↓
   SelfDiagnosis.diagnose():
   ├─ Recalcula health score
   ├─ Se degradação: recomenda reduzir size
   └─ Se crítico: pausar


EXEMPLO DE FLUXO (15:32 BUY TRADE):
═══════════════════════════════════════════════════════════════════════════════

1. ANTES:
   ─────
   Regime: TREND_UP, confidence: 85%, duration: 47 candles
   Volatility: 1.8% (MEDIUM)
   Hour: 15
   
   Brain Scores:
   ├─ WyckoffRange: 0.75 (normal)
   ├─ Elliott: 0.82 (strong)
   ├─ Gann: 0.68 (weak)
   ├─ TrendPullback: 0.70
   └─ ... (10 total)
   
   MetaBrain Analysis:
   ├─ Elliott em TREND_UP: win_rate 52%, PF 1.1 → weight 1.2x
   ├─ WyckoffRange em TREND_UP: win_rate 48%, PF 0.9 → weight 0.8x
   ├─ Gann em TREND_UP: win_rate 65%, PF 1.3 → weight 1.8x
   ├─ Global confidence: 72% (múltiplos sinais bons)
   └─ Allow trading: YES
   
   RL Policy:
   ├─ State: TREND_UP_15_MEDIUM_UP_NEUTRAL
   ├─ Q(state, ENTER) = 0.45
   ├─ Q(state, SKIP) = -0.15
   ├─ Action: ENTER (learned from past success)
   └─ RL confidence: 68%
   
   Self-Diagnosis:
   ├─ Health: GREEN (score 0.85)
   ├─ Position factor: 1.0 (full size)
   └─ Recent performance: 53% win rate (stable)
   
   ✓ DECISION: BUY with full size
   Position = risk_amount / (entry - SL) × health_factor × meta_confidence
   
2. TRADE:
   ───────
   Entry: 1.0850, SL: 1.0820 (30 pips), TP: 1.0950 (100 pips)
   MFE: 95 pips, MAE: 5 pips, Duration: 45 min
   
3. EXIT:
   ──────
   Atingiu TP: +100 pips = +$1000 (assumed 1 lot)
   
4. FEEDBACK:
   ──────────
   a) Replay Priority:
      loss_magnitude = 0 (ganho)
      priority_score = 0 (não prioritário, pois ganhou)
      → Insert em replay_priority (baixa prioridade)
   
   b) MetaBrain Update:
      Todos os 10 brains que sinalizaram (Elliott, WyckoffRange, etc):
      ├─ Adiciona esta trade ao histórico
      ├─ Elliott (que acertou): win_rate sobe 52%→53%, PF 1.1→1.12
      ├─ Calcula novo confidence (baseado em # trades)
      └─ Próxima vez: Elliott terá weight ainda maior
   
   c) Regime Check:
      ├─ Detecta ainda em TREND_UP, duration: 48 candles
      ├─ Sem mudança → sem decay extra
      └─ Próxima trade em mesmo regime usará dados frescos
   
   d) RL Update:
      Reward = +100 pips / 100 = +1.0 (normalized)
      Q(TREND_UP_15_MEDIUM_UP_NEUTRAL, ENTER) ← 0.45 + 0.1 * (+1.0 + 0.95*max_next - 0.45)
                                               ← 0.45 + 0.1 * (1.55)
                                               ← 0.60 ↑
      → Próxima vez que esse estado ocorrer, Q(ENTER) > Q(SKIP)
   
   e) Self-Diagnosis:
      ├─ Health: Ainda GREEN
      ├─ Win rate: 54% (estável ou melhorando)
      └─ Próxima trade: tamanho normal


INTEGRAÇÃO COM BOSSBRAIN (Próxima Etapa):
═══════════════════════════════════════════════════════════════════════════════

BossBrain passará a usar:

1. weight_adjustment do MetaBrain:
   final_score[brain] = base_score[brain] × meta_weights[brain]

2. allow_trading do MetaBrain:
   if not meta_decision.allow_trading:
       return SKIP (veto absoluto)

3. RL confidence como modificador:
   confluence_gate_threshold = 2 + (1 - rl_confidence) * 0.5
   → Se RL tiver baixa confiança, exigir mais convergência

4. Health factor para position sizing:
   final_position_size = base_size × health.position_size_factor


PRÓXIMAS ETAPAS (Fase 2):
═══════════════════════════════════════════════════════════════════════════════

□ Integrar MetaBrain + RL + Decay com BossBrain
□ Update Dashboard V3 com métricas do MetaBrain
□ Testes do RL com dados históricos
□ Fine-tuning de parâmetros (half_life, learning_rate, etc)
□ Implementar Priority Replay Buffer (aprender mais de perdas)
□ Update Live/Simulator com health checks
□ Dashboard V3: Mostrar thinking do MetaBrain e RL


CONFIGURAÇÃO (settings.py):
═══════════════════════════════════════════════════════════════════════════════

# MetaBrain
meta_brain_enabled: bool = True
meta_min_confidence: float = 0.3
meta_decay_half_life_days: float = 30.0

# Regime Detector
regime_detector_enabled: bool = True
regime_use_hmm: bool = True  # Se hmmlearn disponível
regime_min_duration: int = 3

# RL Policy
rl_enabled: bool = True
rl_learning_rate: float = 0.1
rl_epsilon: float = 0.2
rl_discount: float = 0.95

# Self-Diagnosis
health_check_enabled: bool = True
health_pause_on_red: bool = True
health_reduce_on_yellow: bool = True
"""

# Core Modules Overview
MODULES = {
    "meta_brain": {
        "path": "src/brains/meta_brain.py",
        "class": "MetaBrain",
        "lines": 350,
        "purpose": "Evaluates brain performance and adjusts weights dynamically",
    },
    "regime_detector": {
        "path": "src/features/regime_detector.py",
        "class": "RegimeDetector",
        "lines": 280,
        "purpose": "Automatic market regime detection (HMM or heuristic)",
    },
    "reinforcement_learner": {
        "path": "src/training/reinforcement.py",
        "class": "LightReinforcementLearner",
        "lines": 320,
        "purpose": "Q-learning based policy for entry/exit decisions",
    },
    "knowledge_decay": {
        "path": "src/models/decay.py",
        "class": "KnowledgeDecayPolicy",
        "lines": 280,
        "purpose": "Temporal and regime-aware knowledge decay",
    },
    "self_diagnosis": {
        "path": "src/monitoring/self_diagnosis.py",
        "class": "SelfDiagnosisSystem",
        "lines": 300,
        "purpose": "Health monitoring with GREEN/YELLOW/RED status",
    },
}

# Database Tables
DB_TABLES = {
    "brain_performance": {
        "purpose": "Historical performance of each brain by regime",
        "key_fields": ["brain_id", "regime", "win_rate", "profit_factor", "confidence"],
    },
    "meta_decisions": {
        "purpose": "Log of MetaBrain decisions for analysis",
        "key_fields": ["regime", "allow_trading", "global_confidence", "risk_level"],
    },
    "regime_transitions": {
        "purpose": "Track regime changes and duration in each regime",
        "key_fields": ["from_regime", "to_regime", "from_duration", "timestamp"],
    },
    "reinforcement_policy": {
        "purpose": "Q-table for RL policy (state → q_values)",
        "key_fields": ["state_hash", "q_value", "visit_count", "last_update"],
    },
    "replay_priority": {
        "purpose": "Prioritize learning from losses, not just wins",
        "key_fields": ["trade_id", "priority_score", "loss_magnitude", "regime"],
    },
}

if __name__ == "__main__":
    print(__doc__)
