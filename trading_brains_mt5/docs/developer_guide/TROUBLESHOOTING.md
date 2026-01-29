# Troubleshooting — Trading Brains MT5

## 1) Sistema não opera no LIVE REAL
**Sintomas**
- `LIVE_MODE=REAL` mas o sistema fica em simulação

**Causas comuns**
- `ENABLE_LIVE_TRADING=false`
- `LIVE_CONFIRM_KEY` vazia ou `CHANGE_ME`
- Arquivo `LIVE_OK.txt` ausente quando `REQUIRE_LIVE_OK_FILE=true`

**Solução**
1. Atualize `.env` com valores válidos.
2. Crie `./data/LIVE_OK.txt`.
3. Reinicie o sistema.

## 2) Backtest com PnL irreal
**Sintomas**
- Resultados muito acima do esperado

**Causas comuns**
- Spreads/slippage não calibrados
- Janela de saída fixa sem custos reais

**Solução**
- Ajuste parâmetros do FillModel (`FILL_MODEL_*` no `.env`).
- Compare com trades reais ou replay.

## 3) Falha ao rodar testes
**Sintomas**
- `pytest` falha por dependências ausentes

**Solução**
1. Verifique `requirements.txt`.
2. Instale bibliotecas faltantes.
3. Rode novamente:
   ```bash
   pytest -q
   ```

## 4) Regimes inconsistentes
**Sintomas**
- Mudança frequente de regime

**Solução**
- Ajuste thresholds do detector de regime (ex.: ATR/vol).
- Considere aumentar a janela mínima de candles.

## 5) MT5 desconecta
**Solução**
- Verifique login no terminal MT5.
- Reinicie o terminal e o serviço do bot.
- Use `RUN_HEALTHCHECK.bat` para validar conexão.

