"""SDK version update notification (internal, dev mode only)."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any

from .version import __version__

SDK_NAME = "python"
CACHE_FILE = Path.home() / ".muxi" / "sdk-versions.json"
TWELVE_HOURS = timedelta(hours=12)

_has_checked_version = False


def _notifications_disabled() -> bool:
    """Check if version notifications are disabled."""
    return os.environ.get("MUXI_SDK_VERSION_NOTIFICATION") == "0"


def _load_cache() -> Dict[str, Any]:
    """Load version cache from disk."""
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    """Save version cache to disk."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass


def _was_notified_recently() -> bool:
    """Check if user was notified within the last 12 hours."""
    try:
        cache = _load_cache()
        entry = cache.get(SDK_NAME)
        if not entry or not entry.get("last_notified"):
            return False
        
        last_notified = datetime.fromisoformat(entry["last_notified"])
        return datetime.now() - last_notified < TWELVE_HOURS
    except Exception:
        return False


def _update_latest_version(latest: str) -> None:
    """Update cache with latest known version."""
    try:
        cache = _load_cache()
        entry = cache.get(SDK_NAME, {})
        cache[SDK_NAME] = {
            **entry,
            "current": __version__,
            "latest": latest,
        }
        _save_cache(cache)
    except Exception:
        pass


def _mark_notified() -> None:
    """Mark that user was notified."""
    try:
        cache = _load_cache()
        if SDK_NAME in cache:
            cache[SDK_NAME]["last_notified"] = datetime.now().isoformat()
            _save_cache(cache)
    except Exception:
        pass


def _is_newer_version(latest: str, current: str) -> bool:
    """Compare version strings."""
    try:
        # Handle semver-like or date-based versions
        return latest > current
    except Exception:
        return False


def check_for_updates(headers: Dict[str, str]) -> None:
    """Check response headers for SDK update notification.
    
    Args:
        headers: Response headers dict (case-insensitive keys supported)
    """
    global _has_checked_version
    
    # Only check once per process
    if _has_checked_version:
        return
    _has_checked_version = True
    
    # Dev mode only
    if _notifications_disabled():
        return
    
    # Get header (case-insensitive)
    latest = None
    for key, value in headers.items():
        if key.lower() == "x-muxi-sdk-latest":
            latest = value
            break
    
    if not latest:
        return  # Old server, no header
    
    # Only proceed if newer
    if not _is_newer_version(latest, __version__):
        return
    
    # Always update cache
    _update_latest_version(latest)
    
    # Notify if 12 hours passed
    if not _was_notified_recently():
        print(f"[muxi] SDK update available: {latest} (current: {__version__})")
        print("[muxi] Run: pip install --upgrade muxi")
        _mark_notified()
