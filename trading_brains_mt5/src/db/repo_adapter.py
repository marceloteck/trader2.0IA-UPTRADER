from __future__ import annotations

from typing import Any, Dict, List

from . import repo


class RepoAdapter:
    """Adaptador para usar funções do repo com interfaces OO do motor V4."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert_order_event(self, event: Dict[str, Any]) -> None:
        repo.insert_order_event(self.db_path, event)

    def insert_execution_result(self, result: Dict[str, Any]) -> None:
        repo.insert_execution_result(self.db_path, result)

    def insert_risk_event(self, event: Dict[str, Any]) -> None:
        repo.insert_risk_event(self.db_path, event)

    def insert_audit_trail(self, trace: Dict[str, Any]) -> None:
        repo.insert_audit_trail(self.db_path, trace)

    def update_audit_trail_execution(self, run_id: str, sequence: int, execution_data: Dict) -> None:
        repo.update_audit_trail_execution(self.db_path, run_id, sequence, execution_data)

    def insert_position_state(self, position: Dict[str, Any]) -> None:
        repo.insert_position_state(self.db_path, position)

    def update_position_state(self, position: Dict[str, Any]) -> None:
        repo.update_position_state(self.db_path, position)

    def fetch_open_positions(self) -> List[Dict[str, Any]]:
        return repo.fetch_open_positions(self.db_path)

    def fetch_position_by_ticket(self, ticket: int) -> Dict[str, Any]:
        return repo.fetch_position_by_ticket(self.db_path, ticket)
