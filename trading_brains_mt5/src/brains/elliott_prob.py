from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional

import pandas as pd
import numpy as np

from .brain_interface import Brain, BrainSignal, Context


@dataclass
class ElliottCandidate:
    """Uma possível contagem de ondas Elliott"""
    wave_count: int
    direction: str  # BUY ou SELL
    confidence: float
    impulse_range: tuple
    correction_range: tuple
    projection: float
    invalidation: float
    reasons: List[str]

    @property
    def score(self) -> float:
        return self.confidence


class ElliottProbBrain(Brain):
    """
    Detecta padrões de ondas Elliott probabilisticamente.
    Gera 2-4 contagens candidatas com scores independentes.
    Usa como FILTRO: aumenta score se converge com outros cérebros.
    """
    id = "elliott_prob"
    name = "Elliott Probabilistic"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        """
        Detecta estrutura Elliott e gera contagens candidatas.
        Retorna o sinal mais provável ou None.
        """
        if data is None or data.empty or len(data) < 50:
            return None

        # Extrair pivôs (swing highs/lows)
        pivots = self._extract_pivots(data, lookback=5)
        if len(pivots) < 5:
            return None

        # Gerar candidatos
        candidates = self._generate_candidates(pivots, data)
        if not candidates:
            return None

        # Selecionar o melhor
        best = max(candidates, key=lambda c: c.confidence)

        # Montar sinal
        direction = best.direction
        if direction == "BUY":
            entry = float(data.iloc[-1]["close"])
            sl = best.invalidation
            tp1 = best.projection
            tp2 = best.projection * 1.5
        else:
            entry = float(data.iloc[-1]["close"])
            sl = best.invalidation
            tp1 = best.projection
            tp2 = best.projection * 0.5

        return BrainSignal(
            brain_id=self.id,
            action=direction,
            entry=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            reasons=best.reasons,
            metadata={
                "wave_count": best.wave_count,
                "confidence": best.confidence,
                "candidates_count": len(candidates),
                "invalidation": best.invalidation,
                "projection": best.projection,
                "candidates": [asdict(c) for c in candidates],
            },
        )

    def score(self, signal: BrainSignal, context: Context) -> float:
        """Score baseado na confiança do candidato Elliott e convergência."""
        confidence = float(signal.metadata.get("confidence", 0.0))
        candidates = float(signal.metadata.get("candidates_count", 1))
        # Mais candidatos = mais confluência = score maior
        confluence_bonus = min(candidates * 15, 30)
        base_score = confidence * 70
        return min(base_score + confluence_bonus, 95.0)

    @staticmethod
    def _extract_pivots(data: pd.DataFrame, lookback: int = 5) -> List[dict]:
        """Extrai swing highs e swing lows (pivôs)."""
        pivots = []
        for i in range(lookback, len(data) - lookback):
            # Swing high
            if (data.iloc[i]["high"] > data.iloc[i - lookback : i]["high"].max() and
                data.iloc[i]["high"] > data.iloc[i + 1 : i + lookback + 1]["high"].max()):
                pivots.append({
                    "type": "high",
                    "price": float(data.iloc[i]["high"]),
                    "index": i,
                })
            # Swing low
            if (data.iloc[i]["low"] < data.iloc[i - lookback : i]["low"].min() and
                data.iloc[i]["low"] < data.iloc[i + 1 : i + lookback + 1]["low"].min()):
                pivots.append({
                    "type": "low",
                    "price": float(data.iloc[i]["low"]),
                    "index": i,
                })
        return sorted(pivots, key=lambda p: p["index"])

    def _generate_candidates(self, pivots: List[dict], data: pd.DataFrame) -> List[ElliottCandidate]:
        """Gera múltiplos candidatos de contagem Elliott."""
        candidates = []

        if len(pivots) < 5:
            return candidates

        # Padrão 1: Impulso de 5 ondas (3 para cima, 2 para baixo = BUY)
        if pivots[-5]["type"] == "low" and pivots[-4]["type"] == "high" and \
           pivots[-3]["type"] == "low" and pivots[-2]["type"] == "high" and \
           pivots[-1]["type"] == "low":
            wave1_range = pivots[-4]["price"] - pivots[-5]["price"]
            wave3_range = pivots[-2]["price"] - pivots[-3]["price"]
            
            if wave3_range > wave1_range * 0.618:
                projection = pivots[-2]["price"] + wave3_range * 1.618
                invalidation = pivots[-1]["price"]
                confidence = 0.7
                candidates.append(ElliottCandidate(
                    wave_count=5,
                    direction="BUY",
                    confidence=confidence,
                    impulse_range=(pivots[-5]["price"], pivots[-2]["price"]),
                    correction_range=(pivots[-2]["price"], pivots[-1]["price"]),
                    projection=projection,
                    invalidation=invalidation,
                    reasons=["Impulso de 5 ondas detectado", f"Wave 3 > Wave 1 * 0.618"],
                ))

        # Padrão 2: Impulso de 5 ondas (3 para baixo, 2 para cima = SELL)
        if pivots[-5]["type"] == "high" and pivots[-4]["type"] == "low" and \
           pivots[-3]["type"] == "high" and pivots[-2]["type"] == "low" and \
           pivots[-1]["type"] == "high":
            wave1_range = pivots[-5]["price"] - pivots[-4]["price"]
            wave3_range = pivots[-3]["price"] - pivots[-2]["price"]
            
            if wave3_range > wave1_range * 0.618:
                projection = pivots[-2]["price"] - wave3_range * 1.618
                invalidation = pivots[-1]["price"]
                confidence = 0.7
                candidates.append(ElliottCandidate(
                    wave_count=5,
                    direction="SELL",
                    confidence=confidence,
                    impulse_range=(pivots[-5]["price"], pivots[-2]["price"]),
                    correction_range=(pivots[-2]["price"], pivots[-1]["price"]),
                    projection=projection,
                    invalidation=invalidation,
                    reasons=["Impulso de 5 ondas (down) detectado"],
                ))

        # Padrão 3: Correção A-B-C (BUY setup after ABC correction)
        if len(pivots) >= 6:
            recent_5 = pivots[-5:]
            if recent_5[0]["type"] == "high" and recent_5[1]["type"] == "low" and \
               recent_5[2]["type"] == "high" and recent_5[3]["type"] == "low" and \
               recent_5[4]["type"] == "high":
                wave_a = recent_5[0]["price"] - recent_5[1]["price"]
                wave_c = recent_5[2]["price"] - recent_5[3]["price"]
                
                if abs(wave_c - wave_a) / wave_a < 0.2:
                    projection = recent_5[4]["price"] + (recent_5[0]["price"] - recent_5[1]["price"])
                    invalidation = recent_5[3]["price"]
                    confidence = 0.6
                    candidates.append(ElliottCandidate(
                        wave_count=3,
                        direction="BUY",
                        confidence=confidence,
                        impulse_range=(recent_5[1]["price"], recent_5[4]["price"]),
                        correction_range=(recent_5[0]["price"], recent_5[3]["price"]),
                        projection=projection,
                        invalidation=invalidation,
                        reasons=["Correção ABC completa"],
                    ))

        # Padrão 4: Divergência
        if len(pivots) >= 3:
            highs = [p["price"] for p in pivots if p["type"] == "high"]
            if len(highs) >= 2:
                last_high = highs[-1]
                prev_high = highs[-2]
                
                if last_high < prev_high * 0.98:
                    invalidation = last_high
                    lows = [p["price"] for p in pivots if p["type"] == "low"]
                    projection = min(lows) if lows else last_high * 0.9
                    confidence = 0.55
                    candidates.append(ElliottCandidate(
                        wave_count=0,
                        direction="SELL",
                        confidence=confidence,
                        impulse_range=(prev_high, last_high),
                        correction_range=(projection, last_high),
                        projection=projection,
                        invalidation=invalidation,
                        reasons=["Divergência bearish"],
                    ))

        return candidates
