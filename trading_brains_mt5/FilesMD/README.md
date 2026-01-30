# Trading Brains MT5

## Visão geral
Este projeto implementa um sistema de trading inteligente com múltiplos “cérebros” (detectores/avaliadores), um cérebro chefe (BossBrain) e camadas de execução para backtest, simulação ao vivo (paper) e modo real (com travas). O fluxo padrão é:

1. **Coleta de dados** do MT5 (candles M1/M5/H1).
2. **Feature engineering** (VWAP, médias, RSI, ATR, pivôs, regime).
3. **Cérebros** geram sinais e scores.
4. **BossBrain** filtra e decide (BUY/SELL/HOLD).
5. **Execução** (backtest, simulação, real).
6. **Persistência** em SQLite com logs e relatórios.

## Pré-requisitos
- Windows com Python 3.11+
- MetaTrader 5 instalado e logado
- Símbolo configurado no MT5 (ex.: `WIN$N`)

## Instalação
```bat
INSTALL.bat
```
O script cria ambiente virtual, instala dependências e inicializa o banco.

## Configuração
Copie `.env.example` para `.env` e ajuste conforme necessário:
```ini
ENABLE_LIVE_TRADING=false
LIVE_CONFIRM_KEY=CHANGE_ME
SYMBOL=WIN$N
TIMEFRAMES=M1,M5,H1
```
> **Atenção:** O modo real exige `ENABLE_LIVE_TRADING=true` e `LIVE_CONFIRM_KEY` configurada.

## Como rodar
### Backtest
```bat
RUN_BACKTEST.bat
```
Ou via CLI:
```bash
python -m src.main backtest --from 2024-01-01 --to 2024-06-01
```

### Treino
```bat
RUN_TRAIN.bat
```
Ou via CLI:
```bash
python -m src.main train --replay 3
```

### Live sim (paper)
```bat
RUN_LIVE_SIM.bat
```

### Live real (com travas)
```bat
RUN_LIVE_REAL.bat
```
> **Risco alto:** só use com `ENABLE_LIVE_TRADING=true` e `LIVE_CONFIRM_KEY` válida.

### Dashboard
```bat
RUN_DASHBOARD.bat
```
Acessar em `http://localhost:8000`.

## Banco SQLite
O banco é criado automaticamente em `data/db/trading.db` e contém tabelas:
- `candles`, `features`, `brain_signals`, `decisions`, `trades`
- `models`, `training_state`, `runs`

## Adicionar novos cérebros
1. Crie um arquivo em `src/brains/` com uma classe que herda `Brain`.
2. Implemente `detect`, `score` e `explain`.
3. Registre o cérebro no `BossBrain` em `brain_hub.py`.
4. Ajuste pesos em `src/config/constants.py`.

## Segurança
- **Kill switch**: crie `data/STOP.txt` para interromper loops ao vivo.
- **Limites de risco**: `DAILY_LOSS_LIMIT`, `MAX_TRADES_PER_DAY`, `MAX_CONSEC_LOSSES`.
- **Live trading** desligado por padrão.

## V2 - Evoluções
### Novos cérebros
- **Wyckoff Advanced**: spring/upthrust e range com decay por toque.
- **Elliott Probabilístico**: múltiplas contagens candidatas com invalidação e alvo.
- **Gann Macro**: tendência macro e zonas de suporte/resistência H1.
- **Cluster Proxy**: proxy de fluxo (tick volume, absorção, falhas) para níveis.
- **Liquidity Brain**: consolidação de VWAP, pivôs e níveis arredondados.

### Walk-forward
Use:
```bat
RUN_WALK_FORWARD.bat
```
O sistema treina em janelas de `TRAIN_WINDOW_DAYS` e testa em `TEST_WINDOW_DAYS`, salvando métricas na tabela `metrics_windows`.

### Dashboard V2
O painel mostra placar de cérebros, regime atual, níveis de liquidez e risco diário. Um alerta vermelho indica quando o modo real está ativo.

### Aviso de risco
O modo real exige confirmação dupla (`ENABLE_LIVE_TRADING=true` + `LIVE_CONFIRM_KEY`). Use sempre com limites de risco ativos.


## V3 - Aprendizado Contínuo (NEW! ✨)
### O que é V3?
V3 transforma o sistema de **regras estáticas** → **aprendizado contínuo e adaptativo**.

O sistema agora:
- **Aprende** performance de cada cérebro por regime
- **Ajusta pesos** dinamicamente baseado no histórico
- **Detecta regimes** automaticamente (TREND_UP, TREND_DOWN, RANGE, HIGH_VOL)
- **Aplica RL** (Q-learning simples) para otimizar entrada/saída
- **Detecta degradação** de saúde (drawdown, perdas, desconexão)
- **Auto-pausa** em condições críticas

### Componentes V3

#### 1. MetaBrain (O Cérebro dos Cérebros)
```python
from src.brains.meta_brain import MetaBrain

meta_brain = MetaBrain(settings, db_path)
decision = meta_brain.evaluate(
    current_regime="TREND_UP",
    current_hour=14,
    current_volatility=1.5,
    brain_scores={"Elliott": 0.8, "Gann": 0.6},
)
# Output: weights {Elliott: 1.2x, Gann: 1.8x}, confidence=72%, allow_trading=True
```
Avalia performance histórica de cada cérebro e ajusta pesos dinamicamente.

#### 2. Regime Detector (Detecção Automática)
```python
from src.features.regime_detector import RegimeDetector

detector = RegimeDetector(settings, db_path)
regime_state = detector.detect(df, hour=14)
# Output: regime="TREND_UP", confidence=85%, volatility=1.8%, duration=47 candles
```
Detecta regimes com HMM (Gaussian) ou heurística (fallback). Rastreia transições.

#### 3. Reinforcement Learning (Q-Learning)
```python
from src.training.reinforcement import LightReinforcementLearner

rl_learner = LightReinforcementLearner(settings, db_path)
action = rl_learner.get_action(
    regime="TREND_UP",
    hour=14,
    volatility=1.5,
    trend=0.05,
    rsi=55,
    base_confidence=0.8
)
# Output: action="ENTER", confidence=68%
```
Q-learning simples (sem deep learning). Aprende quando não deve operar (SKIP).

#### 4. Knowledge Decay (Envelhecimento de Dados)
```python
from src.models.decay import KnowledgeDecayPolicy

policy = KnowledgeDecayPolicy(half_life_days=30)
decay = policy.combined_decay(
    timestamp="2024-01-15T14:30:00",
    knowledge_regime="TREND_UP",
    current_regime="TREND_UP",
    regime_duration=47,
    current_win_rate=0.55,
    previous_win_rate=0.50,
    current_volatility=1.5
)
# Output: decay_factor=0.95 (95% de valor; 5% decaido)
```
Dados antigos perdem valor com o tempo, especialmente se regime muda.

#### 4. Self-Diagnosis (Monitoramento de Saúde)
```python
from src.monitoring.self_diagnosis import SelfDiagnosisSystem

health_system = SelfDiagnosisSystem()
health = health_system.diagnose(
    recent_trades=[...],
    brain_performance={...},
    current_regime="TREND_UP",
    current_volatility=1.5,
    regime_confidence=0.85,
    data_staleness_minutes=0.5
)
# Output: status="GREEN" (score 0.85), position_size_factor=1.0
#         status="YELLOW" (score 0.58), position_size_factor=0.5
#         status="RED"    (score 0.22), position_size_factor=0.0 (PAUSE)
```
Monitora 6 dimensões: drawdown, loss rate, performance, regime, volatilidade, dados.

### Como usar V3

#### Habilitar em settings.py:
```python
meta_brain_enabled = True
regime_detector_enabled = True
rl_enabled = True
health_check_enabled = True
```

#### Fluxo no BossBrain:
```python
# 1. Detectar regime
regime = regime_detector.detect(df, hour)

# 2. MetaBrain avalia
meta_decision = meta_brain.evaluate(regime, hour, vol, brain_scores)
adjusted_scores = {b: brain_scores[b] * meta_decision.weight_adjustment[b] for b in brain_scores}

# 3. RL recomenda
rl_action = rl_learner.get_action(regime, hour, vol, trend, rsi, meta_decision.confidence)

# 4. Health check
health = health_system.diagnose(...)

# 5. Decisão final
if meta_decision.allow_trading and rl_action.action == "ENTER" and health.status != "RED":
    position_size = base_size * health.position_size_factor
    execute_trade(adjusted_scores, position_size)
```

### Dashboard V3
Novos endpoints:
- `GET /api/v3/meta-brain/status` → Decisão do MetaBrain (pesos, confiança, reasoning)
- `GET /api/v3/regime/current` → Regime atual, confiança, transições
- `GET /api/v3/rl-policy/action` → Ação RL com Q-values e entropy
- `GET /api/v3/health/status` → Status de saúde (GREEN/YELLOW/RED) + recomendações
- `GET /api/v3/brain-performance` → Win rates por cérebro × regime

### Banco de Dados V3
Novas tabelas:
- `brain_performance`: histórico de performance por cérebro × regime
- `meta_decisions`: log de decisões do MetaBrain
- `regime_transitions`: histórico de mudanças de regime
- `reinforcement_policy`: Q-table persistida
- `replay_priority`: priorização de experiências para aprendizado

### Validação V3
```bash
python VALIDATE_V3.py
```
Verifica se todos os módulos V3 estão implementados e funcionando.

### Documentação V3
- **V3_SUMMARY.md** - Resumo executivo (leia primeiro!)
- **V3_IMPLEMENTATION.md** - Detalhes técnicos
- **V3_QUICK_REFERENCE.md** - Guia rápido de uso
- **V3_ROADMAP.md** - Próximas fases e timeline

### Progresso V3
- ✅ **Fase 1 (Completo)**: Core modules (MetaBrain, RegimeDetector, RL, Decay, Health)
- ⏳ **Fase 2 (Próximo)**: Integração com BossBrain
- ⏳ **Fase 3**: Dashboard V3
- ⏳ **Fase 4**: Fine-tuning de parâmetros

### Performance Esperado
- Fase 2: +5-10% Sharpe vs V2
- Fase 3-4: +10-20% total vs V2

### Segurança V3
- ✅ Sem deep learning (interpretável)
- ✅ Health check automático (pause se RED)
- ✅ Posição reduzida se YELLOW
- ✅ Decay previne overfitting
- ✅ Aprende mais de perdas (não apenas ganhos)

### Zero Breaking Changes
- V3 é **100% aditivo**
- V2 funciona sem modificações
- Pode ativar/desativar em settings
- Database migrations são idempotentes

## V4 - Execução Profissional (NEW!)

### Modo de Operação
O sistema V4 oferece execução com múltiplas travas de segurança:

#### SIM (Paper Trading) - PADRÃO
```bash
# Padrão seguro para testes e validação
RUN_LIVE_SIM.bat
```
- Executa trades NO SIMULADOR
- Sem exposição de dinheiro real
- Testa pipeline completo de execução

#### REAL (Live Trading) - COM TRAVAS
```bash
# REQUIRES: ./data/LIVE_OK.txt criado manualmente
# REQUIRES: .env com LIVE_MODE=REAL
RUN_LIVE_REAL.bat
```

**ATIVAÇÃO DO MODO REAL (3 camadas de segurança):**

1. **Arquivo LIVE_OK.txt** (confirmação manual)
   ```bash
   mkdir ./data
   echo. > ./data/LIVE_OK.txt
   ```
   Este arquivo deve existir para habilitar modo REAL.

2. **Configuração .env**
   ```ini
   LIVE_MODE=REAL
   ENABLE_LIVE_TRADING=true
   LIVE_CONFIRM_KEY=sua_chave_secreta
   REQUIRE_LIVE_OK_FILE=true
   ```

3. **Checklist de Validação**
   - [ ] Testou em LIVE_SIM por pelo menos 8 horas
   - [ ] Verificou backtest com desempenho consistente
   - [ ] Confirmou conexão MT5 (status no terminal)
   - [ ] Revisou todos os limites de risco em .env
   - [ ] Criou ./data/LIVE_OK.txt
   - [ ] Executou RUN_HEALTHCHECK.bat sem erros

### Circuit Breakers & Limites

O sistema V4 implementa múltiplos níveis de proteção:

| Controle | Configuração | Ação |
|----------|--------------|------|
| **Perda Diária** | `DAILY_LOSS_LIMIT` | Para todas as operações |
| **Alvo Diário** | `DAILY_PROFIT_TARGET` | Para após atingir meta |
| **Max Trades/Dia** | `MAX_TRADES_PER_DAY` | Rejeita novas entries |
| **Max Trades/Hora** | `MAX_TRADES_PER_HOUR` | Evita overtrade |
| **Perdas Consecutivas** | `MAX_CONSEC_LOSSES` | Reduz tamanho (degrade) |
| **Volatilidade Alta** | `MAX_ATR_PCT` | Reduz exposição |
| **Divergência Cérebros** | `MAX_BRAIN_DIVERGENCE` | Reduz confiança |
| **Cooldown** | `COOLDOWN_SECONDS` | Espera entre trades |

### Degrade Automático

Após perdas consecutivas, o sistema reduz tamanho de posição automaticamente:

```
Nível 0: 1.0x tamanho normal (100%)
Nível 1: 0.5x tamanho reduzido (50%)
Nível 2: 0.25x muito reduzido (25%)
Nível 3: 0.125x mínimo (12.5%)
```

Recupera 1 nível por dia com bom desempenho.

### Operação Segura do Modo Real

**Antes de ativar LIVE_REAL:**

```bash
# 1. Validação do sistema
RUN_HEALTHCHECK.bat

# 2. Paper trading por 1 semana
RUN_LIVE_SIM.bat  # deixar rodando 8+ horas

# 3. Revisar logs
cat ./data/logs/app.log

# 4. Apenas se satisfeito, criar LIVE_OK.txt e rodar
RUN_LIVE_REAL.bat
```

### Monitoramento e Auditoria

O sistema V4 registra **TUDO**:

```
./data/db/trading.db
  ├─ order_events ......... Todos os eventos de ordem
  ├─ mt5_events ........... Conexão, erros MT5
  ├─ risk_events .......... Circuit breakers acionados
  ├─ audit_trail .......... Trilha completa de decisão
  ├─ position_state ....... Estado de posições
  └─ execution_results .... Resultado de execuções
```

**Analisar falhas:**
```bash
RUN_DIAG_REPLAY.bat  # Replay dos últimos 200 trades
```

### Controles Manuais

Arquivos de controle em `./data/`:

| Arquivo | Efeito | Como usar |
|---------|--------|-----------|
| `LIVE_OK.txt` | Habilita modo REAL | `echo . > ./data/LIVE_OK.txt` |
| `STOP.txt` | Para sistema completamente | `echo . > ./data/STOP.txt` |
| `PAUSE.txt` | Pausa, mas monitora | `echo . > ./data/PAUSE.txt` |
| `RESET_DAY.txt` | Zera contadores diários | `echo . > ./data/RESET_DAY.txt` |

Para reativar, delete o arquivo e reinicie.

### Exemplos de Configuração .env

**CONSERVADOR (recomendado para iniciantes):**
```ini
LIVE_MODE=SIM
DAILY_LOSS_LIMIT=100
MAX_TRADES_PER_DAY=3
MAX_TRADES_PER_HOUR=1
COOLDOWN_SECONDS=300
DEGRADE_STEPS=3
```

**MODERADO (após validação):**
```ini
LIVE_MODE=REAL
DAILY_LOSS_LIMIT=500
MAX_TRADES_PER_DAY=10
MAX_TRADES_PER_HOUR=2
COOLDOWN_SECONDS=180
DEGRADE_STEPS=2
```

**AGRESSIVO (não recomendado sem experiência):**
```ini
LIVE_MODE=REAL
DAILY_LOSS_LIMIT=2000
MAX_TRADES_PER_DAY=20
MAX_TRADES_PER_HOUR=4
COOLDOWN_SECONDS=60
DEGRADE_STEPS=1
```

## Estrutura
```
trading_brains_mt5/
  src/
    execution/ (NEW V4)
      ├─ execution_engine.py  - Orquestrador de execução
      ├─ fill_model.py        - Modelo realístico de fills
      ├─ order_router.py      - Router SIM/MT5
      ├─ position_tracker.py  - Estado de posições
      ├─ sl_tp_manager.py     - Gestão de SL/TP
      └─ risk_manager.py      - Circuitos de risco
    monitoring/
      ├─ self_diagnosis.py (V3)
      ├─ audit.py (NEW V4)    - Trilha de auditoria
      └─ replay_runner.py (NEW V4) - Replay de diagnóstico
    brains/
      meta_brain.py (V3)
    features/
      regime_detector.py (V3)
    training/
      reinforcement.py (V3)
    models/
      decay.py (V3)
    db/
      schema.py (updated: +6 V4 tables)
      repo.py (updated: +V4 queries)
  tests/
    test_v3_core.py
  data/
    LIVE_OK.txt (manual, habilita REAL mode)
    STOP.txt (opcional, para tudo)
    PAUSE.txt (opcional, pausa)
  RUN_LIVE_SIM.bat (NEW V4)
  RUN_LIVE_REAL.bat (NEW V4 - COM TRAVAS)
  RUN_DIAG_REPLAY.bat (NEW V4 - Diagnóstico)
  RUN_HEALTHCHECK.bat (NEW V4 - Verificação)
  .env.example (updated: +V4 settings)

---

# LEVEL 1 (L1): ROBUSTEZ ESTAT�STICA & CUSTOS REALISTAS

##  Objetivo
Implementar melhorias focadas em **anti-overfitting**, **custos realistas** e **filtros inteligentes** para evitar trading em janelas ruins.

##  Componentes L1

### 1. Walk-Forward Anti-Leak (Purge + Embargo)
**Problema**: Overfitting temporal - modelo treina em dados muito pr�ximos do per�odo de teste.

**Solu��o**: Remove per�odos cr�ticos de leakage.

