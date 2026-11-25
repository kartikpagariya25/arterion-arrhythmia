import csv
import io
import json
import os

import numpy as np

from ..common import InvalidInput, fetch_bytes
from .preprocess import (
    CLASSES, SAMPLING_RATE, bandpass_filter, compute_rr_features, detect_r_peaks,
    extract_beat_window, normalize_beat, resample_to_target,
)
from .rhythm_rules import detect_alerts

WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")
MODEL_PATH = os.path.join(WEIGHTS_DIR, "model.onnx")
STATS_PATH = os.path.join(WEIGHTS_DIR, "feature_stats.json")

MIN_SECONDS = 2.0       # below this there are too few beats to say anything
WARN_SECONDS = 10.0     # below this rhythm rules (bigeminy, AFib...) are unreliable
MAX_PLOT_POINTS = 12000
TIME_HEADERS = ("time", "sample", "index", "t", "seconds", "sec", "ms")

RHYTHM_DESCRIPTIONS = {
    "VT": "Ventricular Tachycardia",
    "AFIB": "Atrial Fibrillation",
    "BIGEMINY": "Ventricular Bigeminy",
    "TRIGEMINY": "Ventricular Trigeminy",
    "TACHY": "Sinus Tachycardia",
    "BRADY": "Sinus Bradycardia",
}

_session = None
_rr_mean = None
_rr_std = None


def _model_available() -> bool:
    return os.path.exists(MODEL_PATH) and os.path.exists(STATS_PATH)


def load_model():
    global _session, _rr_mean, _rr_std
    if _session is None and _model_available():
        import onnxruntime as ort

        _session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
        with open(STATS_PATH) as f:
            stats = json.load(f)
        _rr_mean = np.array(stats["rr_mean"], dtype=np.float32)
        _rr_std = np.array(stats["rr_std"], dtype=np.float32)
    return _session


def parse_signal(raw: bytes) -> np.ndarray:
    """Read one ECG lead from CSV/plain text: optional header row, optional time/index column."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidInput("This endpoint needs an ECG as a CSV/text file of numbers.")
    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]
    if not rows:
        raise InvalidInput("The file is empty.")

    def numeric(row):
        try:
            [float(c) for c in row]
            return True
        except ValueError:
            return False

    header = None
    if not numeric(rows[0]):
        header, rows = [c.strip().lower() for c in rows[0]], rows[1:]
    col = 0
    if header and len(header) > 1:
        candidates = [i for i, h in enumerate(header) if h not in TIME_HEADERS and not h.startswith(("time", "sample"))]
        col = candidates[0] if candidates else len(header) - 1
    values = []
    for r in rows:
        try:
            values.append(float(r[col]))
        except (ValueError, IndexError):
            raise InvalidInput("The file is not a numeric ECG signal (found non-numeric values).")
    sig = np.asarray(values, dtype=np.float64)
    if not np.isfinite(sig).all():
        raise InvalidInput("The signal contains NaN or infinite values.")
    return sig


def _classify_beats(cleaned_signal, r_peaks):
    beats, rrs, valid_peaks = [], [], []
    for i, r in enumerate(r_peaks):
        window = extract_beat_window(cleaned_signal, r)
        if window is None:
            continue
        beats.append(normalize_beat(window))
        rrs.append(compute_rr_features(r_peaks, i))
        valid_peaks.append(r)
    if not beats:
        return []

    beats = np.array(beats, dtype=np.float32)[:, None, :]
    rrs = (np.array(rrs, dtype=np.float32) - _rr_mean) / (_rr_std + 1e-8)
    logits = _session.run(["logits"], {"beat": beats, "rr": rrs})[0]
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    probs = e / e.sum(axis=1, keepdims=True)
    return [
        {"time_sec": round(float(r) / SAMPLING_RATE, 3), "class": CLASSES[int(p.argmax())], "confidence": round(float(p.max()), 4)}
        for r, p in zip(valid_peaks, probs)
    ]


def _overall_rhythm(alerts, beat_summary):
    critical = [a for a in alerts if a["severity"] == "critical"]
    warning = [a for a in alerts if a["severity"] == "warning"]
    if critical:
        return RHYTHM_DESCRIPTIONS.get(critical[0]["type"], critical[0]["type"])
    if warning:
        return RHYTHM_DESCRIPTIONS.get(warning[0]["type"], warning[0]["type"])
    if beat_summary.get("V", 0) > 0 or beat_summary.get("S", 0) > 0:
        return "Normal Sinus Rhythm with Isolated Ectopic Beats"
    return "Normal Sinus Rhythm"


def _summary_text(rhythm_type, beat_summary, alerts):
    total = sum(beat_summary.values())
    if not alerts and total - beat_summary.get("N", 0) == 0:
        return f"Normal sinus rhythm across {total} analyzed beats. No abnormalities detected."
    parts = [f"{rhythm_type} pattern detected."]
    if beat_summary.get("V", 0):
        parts.append(f"{beat_summary['V']} ventricular ectopic beat(s).")
    if beat_summary.get("S", 0):
        parts.append(f"{beat_summary['S']} supraventricular ectopic beat(s).")
    if alerts:
        parts.append(f"{len(alerts)} rhythm-level alert(s) flagged for review.")
    return " ".join(parts)


def _decimate_for_plot(sig: np.ndarray):
    step = max(1, int(np.ceil(len(sig) / MAX_PLOT_POINTS)))
    return [round(float(v), 4) for v in sig[::step]], step


def predict(file_url: str, sampling_rate: int = SAMPLING_RATE) -> dict:
    signal = parse_signal(fetch_bytes(file_url))
    if len(signal) / sampling_rate < MIN_SECONDS:
        raise InvalidInput(
            f"The signal is only {len(signal) / sampling_rate:.1f} s long; at least {MIN_SECONDS:.0f} s is needed."
        )
    load_model()
    if _session is None:
        return {
            "rhythm_type": "unknown", "flagged_beats": [], "beats": [],
            "summary": "Arrhythmia model weights not found, so training has not been completed.", "confidence": 0.0,
        }

    cleaned = bandpass_filter(resample_to_target(signal, sampling_rate, SAMPLING_RATE), SAMPLING_RATE)
    duration = len(cleaned) / SAMPLING_RATE
    warnings = []
    if duration < WARN_SECONDS:
        warnings.append(f"Only {duration:.1f} s of signal: at least 10 s is recommended for reliable rhythm analysis.")

    plot, step = _decimate_for_plot(cleaned)
    base = {"signal": plot, "signal_fs": SAMPLING_RATE / step, "duration_sec": round(duration, 2), "warnings": warnings}
    if step == 1:
        base["signal_fs"] = SAMPLING_RATE

    beats = _classify_beats(cleaned, detect_r_peaks(cleaned, SAMPLING_RATE))
    if not beats:
        return {**base, "rhythm_type": "Undetermined", "beats": [], "flagged_beats": [], "beat_summary": {},
                "summary": "Unable to detect valid beats in the provided signal.", "confidence": 0.0}

    beat_summary = {c: 0 for c in CLASSES}
    for b in beats:
        beat_summary[b["class"]] += 1
    alerts = detect_alerts([{"time": b["time_sec"], "class": b["class"]} for b in beats])
    rhythm_type = _overall_rhythm(alerts, beat_summary)
    times = np.array([b["time_sec"] for b in beats])
    hr = round(float(60.0 / np.median(np.diff(times))), 1) if len(times) > 2 else None

    return {
        **base,
        "rhythm_type": rhythm_type,
        "heart_rate_bpm": hr,
        "beats": beats,
        "flagged_beats": [b for b in beats if b["class"] != "N"],
        "beat_summary": beat_summary,
        "rhythm_alerts": alerts,
        "summary": _summary_text(rhythm_type, beat_summary, alerts),
        "confidence": round(float(np.mean([b["confidence"] for b in beats])), 4),
    }
