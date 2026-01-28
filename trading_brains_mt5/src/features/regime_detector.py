"""
Regime Detector: Detecção automática de regimes de mercado
Implementa HMM (Hidden Markov Model) ou fallback estatístico.

V3: Aprende padrões de transição entre regimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging
import json

import pandas as pd
import numpy as np

from ..db import repo
from ..config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class RegimeState:
    """Estado atual do regime"""
    regime: str
    confidence: float  # 0-1
    duration_candles: int  # Há quantas velas neste regime?
    volatility: float
    trend_direction: float  # -1 (DOWN), 0 (RANGE), +1 (UP)
    regime_started_at: str  # ISO timestamp
    metadata: Dict = None


class RegimeDetector:
    """
    Detecta regimes de mercado automaticamente.
    
    Regimes:
    - TREND_UP: preço subindo, volatilidade baixa-média
    - TREND_DOWN: preço descendo, volatilidade baixa-média  
    - RANGE: preço oscilando, volatilidade baixa
    - HIGH_VOL: volatilidade alta (incerteza)
    - BREAKOUT: transição rápida
    
    Usa HMM if disponível (hmmlearn), senão usa heurística com MAs e volatilidade.
    """

    def __init__(self, settings: Settings, db_path: str):
        self.settings = settings
        self.db_path = db_path
        
        # Estado anterior (para detectar mudanças)
        self.previous_regime: Optional[RegimeState] = None
        self.current_regime: Optional[RegimeState] = None
        
        # Cache de features para HMM
        self.feature_history: List[np.ndarray] = []
        self.regime_history: List[str] = []
        
        # Tentar importar hmmlearn
        self.use_hmm = False
        try:
            from hmmlearn import hmm
            self.hmm = hmm
            self.use_hmm = True
            logger.info("HMM disponível para regime detection")
        except ImportError:
            logger.info("hmmlearn não disponível, usando fallback heurístico")
        
        # Parâmetros
        self.MIN_REGIME_DURATION = 3  # Mínimo de velas para validar regime
        self.CONFIDENCE_THRESHOLD = 0.6
        
        # Carregar histórico anterior
        self._load_regime_history()

    def detect(
        self,
        df: pd.DataFrame,  # últimas N velas (mínimo 50)
        hour: int,
    ) -> RegimeState:
        """
        Detecta regime atual baseado em dados OHLCV.
        
        Args:
            df: DataFrame com open, high, low, close, volume
            hour: hora do dia
        
        Returns:
            RegimeState com regime atual, confiança, duração, etc
        """
        
        if len(df) < 10:
            logger.warning("Dados insuficientes para regime detection")
            return RegimeState(
                regime="UNKNOWN",
                confidence=0.1,
                duration_candles=0,
                volatility=0.0,
                trend_direction=0.0,
                regime_started_at=datetime.utcnow().isoformat(),
            )
        
        # Calcular features
        features = self._extract_features(df)
        
        # Detectar regime
        if self.use_hmm and len(self.feature_history) > 50:
            regime, confidence = self._hmm_predict(features)
        else:
            regime, confidence = self._heuristic_predict(features, df)
        
        # Calcular duração do regime
        duration = self._calculate_regime_duration(regime)
        
        # Criar estado
        state = RegimeState(
            regime=regime,
            confidence=confidence,
            duration_candles=duration,
            volatility=features.get("volatility", 0.0),
            trend_direction=features.get("trend_direction", 0.0),
            regime_started_at=datetime.utcnow().isoformat(),
            metadata={
                "hour": hour,
                "atr_pct": features.get("atr_pct", 0.0),
                "rsi": features.get("rsi", 50),
                "ma_slope": features.get("ma_slope", 0.0),
            }
        )
        
        # Detectar mudança de regime
        if self.current_regime and self.current_regime.regime != regime:
            self._log_regime_transition(self.current_regime, state)
        
        # Atualizar histórico
        self.previous_regime = self.current_regime
        self.current_regime = state
        self.feature_history.append(np.array(list(features.values())))
        self.regime_history.append(regime)
        
        # Limpar histórico antigo (manter últimas 1000)
        if len(self.feature_history) > 1000:
            self.feature_history = self.feature_history[-1000:]
            self.regime_history = self.regime_history[-1000:]
        
        return state

    def _extract_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Extrai features para detecção de regime"""
        
        features = {}
        
        # Trend: diferença entre MA curta e longa
        ma_short = df["close"].rolling(10).mean().iloc[-1]
        ma_long = df["close"].rolling(50).mean().iloc[-1]
        features["ma_diff"] = ma_short - ma_long
        features["ma_slope"] = (ma_short - df["close"].rolling(20).mean().iloc[-1]) / ma_short
        
        # Volatilidade: ATR percentual
        high_low = df["high"] - df["low"]
        tr = high_low.copy()
        tr = tr.rolling(14).mean()
        atr = tr.iloc[-1]
        atr_pct = (atr / df["close"].iloc[-1]) * 100
        features["volatility"] = atr_pct
        features["atr_pct"] = atr_pct
        
        # RSI: overbought/oversold
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        features["rsi"] = rsi.iloc[-1]
        
        # Trend direction: preço vs MA (normalize)
        current_price = df["close"].iloc[-1]
        ma_medium = df["close"].rolling(20).mean().iloc[-1]
        if ma_medium > 0:
            trend_pct = (current_price - ma_medium) / ma_medium
            features["trend_direction"] = np.clip(trend_pct, -1, 1)
        else:
            features["trend_direction"] = 0.0
        
        # Volatilidade histórica (std de retornos)
        returns = df["close"].pct_change().dropna()
        features["volatility_std"] = returns.std() * 100
        
        # Range-bound detector: se preço oscila muito dentro da vela
        features["range_ratio"] = (df["high"] - df["low"]).iloc[-1] / (abs(df["close"].iloc[-1] - df["open"].iloc[-1]) + 1e-10)
        
        return features

    def _heuristic_predict(self, features: Dict, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Fallback heurístico para detectar regime.
        Não usa ML, apenas regras estatísticas.
        """
        
        atr_pct = features.get("atr_pct", 0)
        trend_dir = features.get("trend_direction", 0)
        ma_slope = features.get("ma_slope", 0)
        rsi = features.get("rsi", 50)
        vol_std = features.get("volatility_std", 0)
        
        # Detectar por volatilidade primeiro
        if atr_pct > 3.0 or vol_std > 3.0:
            # Alta volatilidade
            regime = "HIGH_VOL"
            confidence = 0.8 if atr_pct > 4.0 else 0.6
        
        elif abs(trend_dir) < 0.02:
            # Preço oscilando, sem tendência
            regime = "RANGE"
            confidence = 0.7
        
        elif trend_dir > 0.03:
            # Tendência de alta
            regime = "TREND_UP"
            confidence = 0.75 if ma_slope > 0.001 else 0.6
        
        elif trend_dir < -0.03:
            # Tendência de baixa
            regime = "TREND_DOWN"
            confidence = 0.75 if ma_slope < -0.001 else 0.6
        
        else:
            # Undefined
            regime = "RANGE"
            confidence = 0.5
        
        # Ajustar confiança por RSI extremos
        if rsi > 75 or rsi < 25:
            confidence = min(1.0, confidence + 0.1)
        
        return regime, confidence

    def _hmm_predict(self, features: Dict) -> Tuple[str, float]:
        """
        Usa HMM para detectar regime (se disponível).
        Implementação simplificada.
        """
        
        try:
            if len(self.feature_history) < 20:
                # Insuficiente para treinar HMM
                return "UNKNOWN", 0.5
            
            # Treinar HMM com histórico recente
            X = np.array(self.feature_history[-200:])
            
            # Usar GaussianHMM com 4 estados (TREND_UP, TREND_DOWN, RANGE, HIGH_VOL)
            model = self.hmm.GaussianHMM(n_components=4, covariance_type="full", n_iter=1000)
            model.fit(X)
            
            # Predizer estado atual
            hidden_state = model.predict(X[-1:].reshape(1, -1))[0]
            score = np.max(model.score_samples(X[-1:].reshape(1, -1))[1])
            
            # Mapear hidden state para regime
            regime_map = {
                0: "TREND_UP",
                1: "TREND_DOWN",
                2: "RANGE",
                3: "HIGH_VOL",
            }
            regime = regime_map.get(hidden_state, "UNKNOWN")
            confidence = np.clip(score / 50, 0, 1)  # Normalize score
            
            return regime, confidence
        
        except Exception as e:
            logger.warning(f"HMM prediction error: {e}, falling back to heuristic")
            return "UNKNOWN", 0.3

    def _calculate_regime_duration(self, current_regime: str) -> int:
        """Calcula há quantas velas estamos no regime atual"""
        
        if not self.current_regime or self.current_regime.regime != current_regime:
            return 0
        
        return self.current_regime.duration_candles + 1

    def _log_regime_transition(self, from_regime: RegimeState, to_regime: RegimeState) -> None:
        """Registra transição de regime no DB para análise"""
        
        try:
            repo.insert_regime_transition(
                self.db_path,
                from_regime=from_regime.regime,
                to_regime=to_regime.regime,
                from_duration=from_regime.duration_candles,
                from_volatility=from_regime.volatility,
                to_volatility=to_regime.volatility,
                timestamp=datetime.utcnow().isoformat(),
            )
            
            logger.info(
                f"Regime transition: {from_regime.regime} → {to_regime.regime} "
                f"(duration: {from_regime.duration_candles} candles)"
            )
        except Exception as e:
            logger.warning(f"Erro ao logar transição de regime: {e}")

    def _load_regime_history(self) -> None:
        """Carrega histórico anterior de regimes"""
        try:
            history = repo.fetch_regime_history(self.db_path, limit=100)
            
            for entry in history:
                regime = entry.get("to_regime", "UNKNOWN")
                self.regime_history.append(regime)
            
            logger.info(f"Carregado histórico de {len(history)} transições de regime")
        except Exception as e:
            logger.warning(f"Erro ao carregar regime history: {e}")

    def get_regime_transition_probability(self, from_regime: str, to_regime: str) -> float:
        """
        Calcula probabilidade histórica de transição entre regimes.
        Usada para prever mudanças futuras.
        """
        
        if not self.regime_history or len(self.regime_history) < 2:
            return 0.1  # Prior uniforme
        
        # Contar transições
        transitions = sum(
            1 for i in range(len(self.regime_history) - 1)
            if self.regime_history[i] == from_regime and self.regime_history[i + 1] == to_regime
        )
        
        occurrences = sum(1 for r in self.regime_history if r == from_regime)
        
        if occurrences == 0:
            return 0.1
        
        return transitions / occurrences

    def predict_regime_change(self) -> Optional[Tuple[str, float]]:
        """
        Prediz próxima mudança de regime.
        Retorna (novo_regime, confiança) ou None se sem mudança prevista.
        """
        
        if not self.current_regime:
            return None
        
        # Verificar se há sinais de transição
        current = self.current_regime
        
        # Se duração é longa e volatilidade alta, provável mudança
        if current.duration_candles > 50 and current.volatility > 2.5:
            # Calcular probabilidades de transição
            transition_probs = {}
            for regime in ["TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOL"]:
                if regime != current.regime:
                    prob = self.get_regime_transition_probability(current.regime, regime)
                    transition_probs[regime] = prob
            
            if transition_probs:
                next_regime = max(transition_probs, key=transition_probs.get)
                confidence = transition_probs[next_regime]
                return (next_regime, confidence)
        
        return None
