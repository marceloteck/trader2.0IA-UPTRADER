"""
Version info and build metadata.

Tracks:
- Version string
- Build timestamp
- Python version
- Platform
- Git commit (if available)
- Config snapshot (masked)
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional


VERSION = "5.0.0"
BUILD_DATE = datetime.utcnow().isoformat()


@dataclass
class BuildInfo:
    """Build metadata."""
    version: str
    build_date: str
    python_version: str
    platform: str
    git_commit: Optional[str] = None
    config_snapshot: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)


def get_git_commit() -> Optional[str]:
    """Get current git commit hash."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return commit[:8]
    except Exception:
        return None


def get_build_info(config_snapshot: Optional[Dict[str, Any]] = None) -> BuildInfo:
    """Get complete build info."""
    return BuildInfo(
        version=VERSION,
        build_date=BUILD_DATE,
        python_version=platform.python_version(),
        platform=platform.platform(),
        git_commit=get_git_commit(),
        config_snapshot=config_snapshot
    )


def mask_sensitive_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive keys in config snapshot."""
    sensitive_keys = [
        "api_key",
        "api_secret",
        "password",
        "token",
        "live_confirm_key",
        "secret",
        "credential"
    ]
    
    masked = config.copy()
    for key in sensitive_keys:
        for config_key in list(masked.keys()):
            if any(sens in config_key.lower() for sens in sensitive_keys):
                masked[config_key] = "***MASKED***"
    return masked
