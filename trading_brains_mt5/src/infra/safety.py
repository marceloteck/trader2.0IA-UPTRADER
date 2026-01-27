from __future__ import annotations

import os


class SafetyError(RuntimeError):
    pass


def assert_live_trading_enabled(enable_live: bool, confirm_key: str) -> None:
    if not enable_live:
        raise SafetyError("ENABLE_LIVE_TRADING is false. Live trading disabled.")
    if confirm_key.strip() == "" or confirm_key == "CHANGE_ME":
        raise SafetyError("LIVE_CONFIRM_KEY is not set. Refusing to trade live.")


def stop_file_exists(base_path: str = "./data") -> bool:
    return os.path.exists(os.path.join(base_path, "STOP.txt"))
