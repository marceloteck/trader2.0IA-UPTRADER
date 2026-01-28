"""Test version module."""

from src.version import (
    VERSION,
    get_build_info,
    mask_sensitive_config,
    get_git_commit
)


def test_version():
    """Test version string."""
    assert VERSION == "5.0.0"


def test_build_info():
    """Test build info generation."""
    build = get_build_info()
    
    assert build.version == "5.0.0"
    assert build.python_version is not None
    assert build.platform is not None
    assert build.build_date is not None


def test_git_commit():
    """Test git commit extraction."""
    commit = get_git_commit()
    # May be None if not in git repo
    if commit:
        assert len(commit) == 8  # 8-char hash


def test_mask_sensitive():
    """Test masking of sensitive data."""
    config = {
        "symbol": "EURUSD",
        "api_key": "secret123",
        "password": "pass456",
        "live_confirm_key": "key789"
    }
    
    masked = mask_sensitive_config(config)
    
    assert masked["symbol"] == "EURUSD"
    assert masked["api_key"] == "***MASKED***"
    assert masked["password"] == "***MASKED***"
    assert masked["live_confirm_key"] == "***MASKED***"
