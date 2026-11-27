"""The one number worth trending for each task in this service."""
from typing import Callable, Dict, Optional, Tuple


def _number(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _heart_rate(result: dict) -> Optional[float]:
    return _number(result.get("heart_rate_bpm"))


METRICS: Dict[str, Tuple[str, str, Callable[[dict], Optional[float]]]] = {
    "arrhythmia": ("Heart rate", "bpm", _heart_rate),
}
