# Guia do Desenvolvedor — Trading Brains MT5

Este guia descreve a arquitetura, os principais fluxos e como operar/testar o sistema.

## 1) Arquitetura resumida

### Fluxo principal
1. **Dados**: candles do MT5 (`src/mt5/`).
2. **Features**: indicadores, regimes, liquidez (`src/features/`).
3. **Cérebros**: detecção de padrões (Wyckoff, Elliott, Gann, Liquidity etc) (`src/brains/`).
4. **BossBrain**: agrega sinais e faz filtros de confluência, risco/retorno e gates (`src/brains/brain_hub.py`).
5. **Execução V4**: risco, roteamento e SL/TP (`src/execution/`).
6. **Persistência**: banco SQLite + logs (`src/db/`).

### Componentes críticos
- **Regimes**: `src/features/regime_detector.py` e `src/features/regime_change.py`
- **Risco**: `src/execution/risk_manager.py`
- **Execução**: `src/execution/execution_engine.py`
- **Backtest**: `src/backtest/engine.py`

## 2) Execução: SIM vs REAL

### Live sim
```bash
python -m src.main live-sim
```

### Live real
```bash
python -m src.main live-real
```

**Travas obrigatórias para LIVE REAL**
- `ENABLE_LIVE_TRADING=true`
- `LIVE_CONFIRM_KEY` válida
- `LIVE_OK.txt` presente (se `REQUIRE_LIVE_OK_FILE=true`)

## 3) Backtest (mais realista)
```bash
python -m src.main backtest --from 2024-01-01 --to 2024-06-01
```

O backtest utiliza o mesmo modelo de fills (slippage/spread) do motor V4, reduzindo divergência de execução.

## 4) Testes
```bash
pytest -q
```

### Testes principais
- `tests/test_backtest_engine.py`
- `tests/test_regime_change_detection.py`
- `tests/test_sl_tp_manager_v4.py`

## 5) Estrutura de pastas
```
src/
  brains/                # Estratégias (cérebros)
  features/              # Features e regimes
  execution/             # Motor V4 (risco, roteamento, SL/TP)
  backtest/              # Backtest e relatórios
  training/              # Treinos supervisionados/RL
  db/                    # Repo SQLite
docs/
  developer_guide/       # Documentação para desenvolvedores
```

## 6) Checklist rápido de operação
- [ ] `.env` configurado
- [ ] MT5 conectado
- [ ] Banco inicializado
- [ ] Rodou `healthcheck`
- [ ] Testes essenciais passando

