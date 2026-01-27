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

## Estrutura
```
trading_brains_mt5/
  src/
  data/
  tests/
  *.bat
```
