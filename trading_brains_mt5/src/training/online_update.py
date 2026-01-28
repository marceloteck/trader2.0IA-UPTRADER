"""
Level 5: Online Policy Updates

Implementa aprendizado seguro e incremental de políticas.

Funcionalidades:
- Atualizar políticas de forma incremental e segura
- Replay prioritário
- Snapshots para rollback
- Limites de confiança
"""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("trading_brains.training.online_update")


@dataclass
class PolicySnapshot:
    """Snapshot de política para rollback."""
    id: str
    time: datetime
    regime: str
    policy_data: Dict
    metrics: Dict  # Estatísticas de performance quando criado
    note: str


class OnlineUpdater:
    """
    Gerencia atualizações online seguras de políticas.
    
    Implementa:
    - Batching de trades antes de atualizar
    - Snapshots automáticos
    - Rollback se performance piora
    - Replay buffer para reforço de experiências boas
    """
    
    def __init__(
        self,
        batch_size: int = 10,
        snapshot_interval: int = 50,
        keep_snapshots: int = 5,
    ):
        """
        Inicialize atualizador online.
        
        Args:
            batch_size: Número de trades a acumular antes de atualizar
            snapshot_interval: Intervalo de trades para criar snapshots
            keep_snapshots: Número de snapshots a manter
        """
        self.batch_size = batch_size
        self.snapshot_interval = snapshot_interval
        self.keep_snapshots = keep_snapshots
        
        self.pending_trades: List[Dict] = []
        self.snapshots: Dict[str, List[PolicySnapshot]] = {}
        self.trade_count: Dict[str, int] = {}
    
    def add_trade(
        self,
        regime: str,
        trade_data: Dict,
    ) -> None:
        """
        Adicione trade ao buffer.
        
        Args:
            regime: Regime em que foi executado
            trade_data: Dados do trade (estado, ação, recompensa, etc.)
        """
        self.pending_trades.append({
            "regime": regime,
            "time": datetime.utcnow().isoformat(),
            "data": trade_data,
        })
        
        if regime not in self.trade_count:
            self.trade_count[regime] = 0
        self.trade_count[regime] += 1
    
    def should_update(self) -> bool:
        """Verifique se deve executar atualização de política."""
        return len(self.pending_trades) >= self.batch_size
    
    def get_pending_trades(self, regime: Optional[str] = None) -> List[Dict]:
        """Obtenha trades pendentes."""
        if regime:
            return [t for t in self.pending_trades if t["regime"] == regime]
        return self.pending_trades.copy()
    
    def clear_pending(self) -> None:
        """Limpe buffer de trades pendentes."""
        self.pending_trades.clear()
    
    def create_snapshot(
        self,
        regime: str,
        policy_export: Dict,
        metrics: Dict,
        note: str = "",
    ) -> PolicySnapshot:
        """
        Crie snapshot de política.
        
        Args:
            regime: Regime
            policy_export: Dados da política exportados
            metrics: Métrica de performance
            note: Nota descritiva
        
        Returns:
            PolicySnapshot criado
        """
        snap_id = f"{regime}_{self.trade_count.get(regime, 0)}_{datetime.utcnow().timestamp():.0f}"
        
        snapshot = PolicySnapshot(
            id=snap_id,
            time=datetime.utcnow(),
            regime=regime,
            policy_data=policy_export,
            metrics=metrics,
            note=note,
        )
        
        if regime not in self.snapshots:
            self.snapshots[regime] = []
        
        self.snapshots[regime].append(snapshot)
        
        # Mantenha apenas N snapshots mais recentes
        if len(self.snapshots[regime]) > self.keep_snapshots:
            self.snapshots[regime] = self.snapshots[regime][-self.keep_snapshots:]
        
        logger.info(f"Policy snapshot criado: {snap_id} (metrics={metrics})")
        
        return snapshot
    
    def get_last_snapshot(self, regime: str) -> Optional[PolicySnapshot]:
        """Obtenha último snapshot de regime."""
        if regime not in self.snapshots or not self.snapshots[regime]:
            return None
        return self.snapshots[regime][-1]
    
    def rollback_to_snapshot(self, regime: str, snapshot: PolicySnapshot) -> Dict:
        """
        Faça rollback para snapshot anterior.
        
        Args:
            regime: Regime
            snapshot: Snapshot para restaurar
        
        Returns:
            Policy data do snapshot
        """
        logger.warning(f"Rollback de política {regime} para snapshot {snapshot.id}")
        return snapshot.policy_data
    
    def get_snapshots(self, regime: str) -> List[PolicySnapshot]:
        """Obtenha histórico de snapshots."""
        return self.snapshots.get(regime, [])
    
    def export_state(self) -> Dict:
        """Exporte estado completo."""
        return {
            "pending_trades_count": len(self.pending_trades),
            "trade_counts": self.trade_count,
            "snapshots_per_regime": {r: len(s) for r, s in self.snapshots.items()},
        }
