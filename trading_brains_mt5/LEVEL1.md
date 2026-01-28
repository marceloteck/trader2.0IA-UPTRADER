# LEVEL 1 (L1): ROBUSTEZ ESTATÍSTICA & CUSTOS REALISTAS

## 🎯 Objetivo
Implementar melhorias focadas em **anti-overfitting**, **custos realistas** e **filtros inteligentes** para evitar trading em janelas ruins.

## 📦 Componentes L1

### 1. Walk-Forward Anti-Leak (Purge + Embargo)
**Problema**: Overfitting temporal - modelo treina em dados muito próximos do período de teste.

**Solução**: Remove períodos críticos de leakage.

```python
# src/backtest/walk_forward.py
train, test = split_walk_forward(
    df,
    train_size=1000,
    test_size=250,
    purge_candles=50,      # Remove 50 candles antes da split
    embargo_candles=50     # Pula 50 candles no início do teste
)
```

**Configuração .env**:
```ini
WF_PURGE_CANDLES=50        # Remover esta quantidade antes da boundary
WF_EMBARGO_CANDLES=50      # Pular esta quantidade no início do teste
```

---

### 2. Modelo de Custos Realista (FIXO / POR_HORARIO / APRENDIDO)
**Problema**: Backtest usa custos fixos, mas spread/slippage variam por horário.

**Solução**: 3 modos de custo com adaptação por hora.

```python
# src/costs/cost_model.py
model = CostModel(
    mode="POR_HORARIO",                    # FIXO, POR_HORARIO, APRENDIDO
    spread_base=1.0,
    slippage_base=0.5,
    slippage_max=2.0
)

spread, slip, comm = model.get_costs(
    symbol="EURUSD",
    hour=14,               # Hora UTC
    volatility=1.5         # Fator volatilidade
)
```

**Modos**:

| Modo | Descrição | Uso |
|------|-----------|-----|
| **FIXO** | Valores .env imutáveis | Dev/teste rápido |
| **POR_HORARIO** | Tabela `data/config/spread_by_hour.json` | Análise realista |
| **APRENDIDO** | Estima de histórico (heurística) | Live advanced |

**Configuração .env**:
```ini
COST_MODE=FIXO                         # ou POR_HORARIO, APRENDIDO
COST_SPREAD_BASE=1.0
COST_SLIPPAGE_BASE=0.5
COST_SLIPPAGE_MAX=2.0
COST_COMMISSION=0.0
```

---

### 3. Filtro de Dias Ruins (Bad Day Filter)
**Problema**: Variância estatística causa dias ruins - continuar trading agrava perda.

**Solução**: Pausa automática se detectar padrão de perda.

```python
# src/live/bad_day_filter.py
filter = BadDayFilter(
    enabled=True,
    first_n_trades=5,              # Verificar nos primeiros 5 trades
    max_daily_loss=-100.0,         # Se pnl < -100, pausa
    min_winrate=0.4,               # Se win rate < 40%, pausa
    consecutive_losses_max=3       # Se 3 perdas seguidas, pausa
)

paused, reason = filter.check(trade_pnl=-50.0, timestamp=now)
if paused:
    print(f"Trading pausado: {reason}")
```

**Triggers de Pausa**:
- ✅ Primeiros N trades com perda > MAX_LOSS
- ✅ N perdas consecutivas
- ✅ Win rate abaixo do mínimo

**Configuração .env**:
```ini
BAD_DAY_ENABLED=true
BAD_DAY_FIRST_N_TRADES=5
BAD_DAY_MAX_LOSS=-100.0
BAD_DAY_MIN_WINRATE=0.4
BAD_DAY_CONSECUTIVE_MAX=3
```

---

### 4. Filtro de Horários (Time Filter)
**Problema**: Certos horários (abertura, fechamento) têm win rate pior.

**Solução**: Bloqueia janelas ruins automaticamente.

```python
# src/live/time_filter.py
filter = TimeFilter(
    enabled=True,
    blocked_windows=["09:00-09:15", "17:50-18:10"]  # Bloqueia
)

if filter.is_blocked(datetime.utcnow()):
    skip_trading = True
```

**Dois modos**:
- **Blacklist** (padrão): Bloqueia windows específicas
- **Whitelist**: Permite APENAS windows específicas

**Configuração .env**:
```ini
TIME_FILTER_ENABLED=false
TIME_FILTER_BLOCKED_WINDOWS=09:00-09:15,17:50-18:10
TIME_FILTER_ALLOW_ONLY=                              # Deixar vazio para blacklist
```

---

### 5. Labels Multi-Horizonte com Quality Score
**Problema**: Labels binários (WIN/LOSS) ignoram qualidade da trade.

**Solução**: Labels com MFE (max favorable) e MAE (max adverse) + quality score.

```python
# src/training/dataset.py
gen = LabelGenerator(
    horizons=[5, 10, 20],          # Avaliar em 3 horizontes
    mfe_weight=1.0,                # Peso para upside
    mae_weight=0.5                 # Penalidade para downside
)

labels = gen.generate_labels(trades, candles, symbol="EURUSD")

# Label por horizonte:
# tp1_hit: TP1 foi atingido?
# tp2_hit: TP2 foi atingido?
# mfe: Max favorable excursion (pips)
# mae: Max adverse excursion (pips)
# quality_score: α*MFE - β*MAE (métrica de qualidade)
```

**Uso em Treino**:
```python
# Treinar modelo supervisionado com labels multi-horizonte
supervised_model.fit(
    X=features,
    y={
        "prob_tp1": labels["tp1_hit"],
        "prob_tp2": labels["tp2_hit"],
        "expected_quality": labels["quality_score"]
    }
)
```

**Configuração .env**:
```ini
LABEL_HORIZONS=5,10,20
LABEL_MFE_WEIGHT=1.0
LABEL_MAE_WEIGHT=0.5
```

---

## 📊 Integração com Componentes Existentes

### Walk-Forward
Backtest agora usa purge/embargo automaticamente:
```bash
python -m src.main backtest --from 2024-01-01 --to 2024-06-01
```
Internamente chama `split_walk_forward(..., purge_candles=50, embargo_candles=50)`.

### Fill Model (V4)
Usa `CostModel` para spread/slippage dinâmicos durante simulação:
```python
from src.costs import CostModel

cost_model = CostModel(
    mode=settings.cost_mode,
    spread_base=settings.cost_spread_base,
    slippage_base=settings.cost_slippage_base
)

spread, slip = cost_model.get_costs(symbol, hour=now.hour)
```

### Live Trading
Filtros aplicados no loop principal:
```python
# src/live/runner.py (pseudocódigo)
bad_day_filter = BadDayFilter(...)
time_filter = TimeFilter(...)

while trading_active:
    if time_filter.is_blocked(now):
        continue  # Skip trading
    
    signal = meta_brain.decide(...)
    
    if signal.action != "HOLD":
        trade = execute(signal)
        paused, reason = bad_day_filter.check(trade.pnl)
        if paused:
            log_pause(reason)
```

### Treinamento
Modelo supervisionado treina com labels multi-horizonte:
```python
# src/models/supervised.py
label_gen = LabelGenerator(horizons=settings.label_horizons)
labels = label_gen.generate_labels(trades, candles)

# Treinar em 3 horizontes simultaneamente
for horizon in settings.label_horizons:
    model.train_horizon(labels, horizon)
```

---

## 🗄️ Banco de Dados (L1)

6 novas tabelas adicionadas a `src/db/schema.py`:

```sql
-- Splits de walk-forward com detalhes de purge/embargo
CREATE TABLE wf_splits (
    id, run_id, split_id,
    train_from, train_to,
    test_from, test_to,
    purge_candles, embargo_candles,
    created_at
);

-- Eventos de custo (spread, slippage por mode/hora)
CREATE TABLE cost_events (
    timestamp, symbol, mode,
    spread, slippage, commission,
    volatility, details
);

-- Eventos de pausa por bad day
CREATE TABLE bad_day_events (
    timestamp, reason,
    daily_pnl, trades_count,
    consecutive_losses, paused_until, details
);

-- Hits do time filter
CREATE TABLE time_filter_hits (
    timestamp, action,
    window
);

-- Labels multi-horizonte
CREATE TABLE labels (
    timestamp, symbol, side,
    entry_price, tp1, tp2, sl,
    horizon, tp1_hit, tp2_hit,
    mfe, mae, quality_score, details
);

-- Insights de reportes
CREATE TABLE report_insights (
    report_date, insight_type,
    subject, metric_name, metric_value, details
);
```

---

## 🧪 Testes L1

5 módulos de teste para validar componentes:

```bash
# Testar purge/embargo
pytest tests/test_walk_forward_purge_embargo.py -v

# Testar custos
pytest tests/test_cost_model.py -v

# Testar bad day filter
pytest tests/test_bad_day_filter.py -v

# Testar time filter
pytest tests/test_time_filter.py -v

# Testar label generation
pytest tests/test_labels_multi_horizon.py -v
```

---

## 📈 Exemplo: Configuração Completa L1

**.env** (exemplo recomendado):
```ini
# Walk-Forward Anti-Leak
WF_PURGE_CANDLES=50
WF_EMBARGO_CANDLES=50

# Custos Realistas
COST_MODE=POR_HORARIO
COST_SPREAD_BASE=1.0
COST_SLIPPAGE_BASE=0.5
COST_SLIPPAGE_MAX=2.0
COST_COMMISSION=0.0

# Bad Day Filter
BAD_DAY_ENABLED=true
BAD_DAY_FIRST_N_TRADES=5
BAD_DAY_MAX_LOSS=-100.0
BAD_DAY_MIN_WINRATE=0.40
BAD_DAY_CONSECUTIVE_MAX=3

# Time Filter
TIME_FILTER_ENABLED=false
TIME_FILTER_BLOCKED_WINDOWS=09:00-09:15,17:50-18:10
TIME_FILTER_ALLOW_ONLY=

# Label Generation
LABEL_HORIZONS=5,10,20
LABEL_MFE_WEIGHT=1.0
LABEL_MAE_WEIGHT=0.5
```

---

## 🔄 Fluxo Completo L1

```
1. BACKTEST
   ├─ Carrega dados
   ├─ Split com purge/embargo (anti-leak)
   ├─ Aplica CostModel (spread/slippage dinâmico)
   ├─ Gera labels multi-horizonte
   └─ Relatório com insights por regime/hora

2. TREINO
   ├─ Carrega labels (5/10/20 horizonte)
   ├─ Treina modelo supervisionado multi-horizonte
   ├─ Valida com quality scores
   └─ Salva modelo

3. LIVE SIM/REAL
   ├─ Antes de cada trade:
   │  ├─ Verifica TimeFilter (bloqueado?)
   │  ├─ Verifica BadDayFilter (pausa?)
   │  └─ Aplica CostModel ao fill
   ├─ Após cada trade:
   │  ├─ Atualiza BadDayFilter stats
   │  ├─ Registra cost_events
   │  └─ Gera labels para retraining
   └─ Relatório com sugestões de otimização
```

---

## ✅ Checklist de Implementação L1

- ✅ Walk-Forward purge/embargo (src/backtest/walk_forward.py)
- ✅ CostModel 3 modos (src/costs/cost_model.py)
- ✅ BadDayFilter (src/live/bad_day_filter.py)
- ✅ TimeFilter (src/live/time_filter.py)
- ✅ LabelGenerator multi-horizonte (src/training/dataset.py)
- ✅ Banco de dados L1 (src/db/schema.py)
- ✅ Settings L1 (src/config/settings.py)
- ✅ Testes L1 (tests/test_*.py)
- ⏳ Integração em fill_model.py
- ⏳ Integração em reports (regime/hora)
- ⏳ Integração em supervised.py (multi-horizonte)
- ⏳ Dashboard endpoints (filtros + performance)

---

## 🚀 Próximos Passos

**Fase 2 (L1 Continuation)**:
- Integrar CostModel em fill_model.py
- Relatórios por regime e hora
- Treinamento multi-horizonte completo
- Dashboard com status de filtros

**Fase 3 (L2 - Sugerido)**:
- Adaptação de parâmetros por regime
- Trailing stops dinâmicos
- Detecção de padrões de mercado (news, catalyst)

---

**V1-V5 Compatibilidade**: ✅ 100% backward compatible
**Breaking Changes**: ❌ Nenhuma
**Database Migration**: ✅ Automática (schema.py)
**Config Migration**: ✅ Defaults em settings.py
