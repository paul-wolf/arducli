"""Fetches and caches ArduPilot parameter metadata from the ParameterRepository."""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

BASE_URL = "https://raw.githubusercontent.com/ArduPilot/ParameterRepository/main"
CACHE_DIR = Path.home() / ".arducli" / "param_meta"
MAX_AGE_DAYS = 60

# MAV_TYPE int → ParameterRepository vehicle prefix
_VEHICLE_MAP = {
    1: "Plane",  # FIXED_WING
    2: "Copter",  # QUADROTOR
    13: "Copter",  # HEXAROTOR
    14: "Copter",  # OCTOROTOR
    15: "Copter",  # TRICOPTER
    10: "Rover",  # GROUND_ROVER
    11: "Rover",  # SURFACE_BOAT
    12: "Sub",  # SUBMARINE
}

_KNOWN_VERSIONS = {
    "Copter": ["4.7", "4.6", "4.5", "4.4", "4.3", "4.2", "4.1", "4.0"],
    "Plane": ["4.7", "4.6", "4.5", "4.4", "4.3", "4.2", "4.1", "4.0"],
    "Rover": ["4.6", "4.5", "4.4", "4.3", "4.2", "4.1", "4.0"],
    "Sub": ["4.5", "4.4", "4.3", "4.2", "4.1", "4.0"],
}


@dataclass
class ParamMeta:
    display_name: str = ""
    description: str = ""
    units: str = ""
    values: dict = field(default_factory=dict)  # enum: {"0": "Disabled", …}
    bitmask: dict = field(default_factory=dict)  # bits: {"0": "GPS", …}
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    increment: Optional[float] = None
    read_only: bool = False
    reboot_required: bool = False
    user_level: str = ""


def _parse_major_minor(version_str: str) -> str:
    m = re.search(r"(\d+)\.(\d+)", version_str or "")
    return f"{m.group(1)}.{m.group(2)}" if m else ""


def _resolve_version(vehicle: str, requested: str) -> str:
    known = _KNOWN_VERSIONS.get(vehicle, [])
    if not known:
        return "4.5"
    if requested in known:
        return requested
    try:
        target = tuple(int(x) for x in requested.split("."))
        candidates = sorted(
            (tuple(int(x) for x in v.split(".")), v) for v in known if tuple(int(x) for x in v.split(".")) <= target
        )
        if candidates:
            return candidates[-1][1]
    except (ValueError, TypeError):
        pass
    return known[0]


def _parse_raw(data: dict) -> dict[str, dict]:
    """Parse apm.pdef.json into a flat {param_name: field_dict}."""
    out = {}
    for group in data.values():
        if not isinstance(group, dict):
            continue
        for name, pd in group.items():
            if not name or not isinstance(pd, dict):
                continue

            range_min = range_max = None
            rv = pd.get("Range")
            if rv:
                try:
                    if isinstance(rv, dict):
                        range_min, range_max = float(rv["low"]), float(rv["high"])
                    elif isinstance(rv, str):
                        lo, hi = rv.split()[:2]
                        range_min, range_max = float(lo), float(hi)
                except (ValueError, TypeError, KeyError):
                    pass

            def _bool(v):
                return v if isinstance(v, bool) else str(v).lower() == "true"

            out[name] = {
                "display_name": pd.get("DisplayName", ""),
                "description": pd.get("Description", ""),
                "units": pd.get("Units", ""),
                "values": pd.get("Values") or {},
                "bitmask": pd.get("Bitmask") or {},
                "range_min": range_min,
                "range_max": range_max,
                "increment": float(pd["Increment"]) if "Increment" in pd else None,
                "read_only": _bool(pd.get("ReadOnly", False)),
                "reboot_required": _bool(pd.get("RebootRequired", False)),
                "user_level": pd.get("User", ""),
            }
    return out


class ParameterMetadataService:
    def __init__(self):
        self._meta: dict[str, ParamMeta] = {}
        self._loaded = False
        self._vehicle = ""
        self._version = ""

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self, vehicle_type_int: int, firmware_version: str = "") -> bool:
        """Load metadata for the given MAV_TYPE + firmware version string.

        Fetches the primary version for the FC firmware, then merges the previous
        version as a fallback so parameters dropped from newer docs are still found.
        Returns True on success.
        """
        vehicle = _VEHICLE_MAP.get(vehicle_type_int, "Copter")
        mm = _parse_major_minor(firmware_version)
        version = _resolve_version(vehicle, mm) if mm else _KNOWN_VERSIONS.get(vehicle, ["4.5"])[0]

        self._vehicle = vehicle
        self._version = version

        primary = self._fetch_version(vehicle, version)
        if primary is None:
            return False

        # Merge previous version as fallback: newer definitions win, older fill gaps.
        # This handles parameters removed from newer ParameterRepository docs (e.g. ARMING_CHECK).
        known = _KNOWN_VERSIONS.get(vehicle, [])
        idx = known.index(version) if version in known else -1
        if idx >= 0 and idx + 1 < len(known):
            fallback = self._fetch_version(vehicle, known[idx + 1])
            if fallback:
                merged = {**fallback, **primary}
            else:
                merged = primary
        else:
            merged = primary

        self._meta = {k: ParamMeta(**v) for k, v in merged.items()}
        self._loaded = True
        return True

    def _fetch_version(self, vehicle: str, version: str) -> Optional[dict]:
        """Return parsed metadata dict for one vehicle+version, using cache when fresh."""
        cache_file = CACHE_DIR / f"{vehicle}-{version}.json"

        # Fresh cache → load from disk
        if cache_file.exists():
            age = (time.time() - cache_file.stat().st_mtime) / 86400
            if age < MAX_AGE_DAYS:
                try:
                    return json.loads(cache_file.read_text())
                except Exception:
                    pass  # corrupt — fall through to fetch

        # Fetch from GitHub
        url = f"{BASE_URL}/{vehicle}-{version}/apm.pdef.json"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            parsed = _parse_raw(resp.json())
        except Exception as e:
            print(f"[param-meta] fetch {url} failed: {e}")
            # Stale cache is better than nothing
            if cache_file.exists():
                try:
                    return json.loads(cache_file.read_text())
                except Exception:
                    pass
            return None

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            cache_file.write_text(json.dumps(parsed))
        except Exception:
            pass
        return parsed

    def get(self, param_name: str) -> Optional[ParamMeta]:
        return self._meta.get(param_name.upper())

    def is_loaded(self) -> bool:
        return self._loaded

    def vehicle(self) -> str:
        return self._vehicle

    def version(self) -> str:
        return self._version
