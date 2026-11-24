import io

import neurokit2 as nk
import numpy as np
from fastapi.testclient import TestClient

from app.arrhythmia import model as m
from app.main import app

client = TestClient(app)


class FakeSession:
    """ONNX stand-in: calls every beat 'N' with high confidence (or the class forced by `cls`)."""

    def __init__(self, cls=0):
        self.cls = cls

    def run(self, names, feed):
        n = feed["beat"].shape[0]
        assert feed["beat"].shape[1:] == (1, 256) and feed["rr"].shape == (n, 4)
        logits = np.full((n, 5), -4.0, dtype=np.float32)
        logits[:, self.cls] = 6.0
        return [logits]


def _install(monkeypatch, cls=0):
    monkeypatch.setattr(m, "_session", FakeSession(cls))
    monkeypatch.setattr(m, "_rr_mean", np.zeros(4, dtype=np.float32))
    monkeypatch.setattr(m, "_rr_std", np.ones(4, dtype=np.float32))


def _csv(seconds=20, fs=360, hr=70, header=None, with_time=False):
    sig = nk.ecg_simulate(duration=seconds, sampling_rate=fs, heart_rate=hr, noise=0.01, random_state=1)
    lines = []
    if header:
        lines.append(header)
    for i, v in enumerate(sig):
        lines.append(f"{i / fs:.4f},{v:.5f}" if with_time else f"{v:.5f}")
    return "\n".join(lines).encode()


def _upload(data: bytes, name="ecg.csv"):
    return client.post("/uploads", files={"file": (name, io.BytesIO(data))})


def _predict(data: bytes, **extra):
    url = _upload(data).json()["file_url"]
    return client.post("/arrhythmia/predict", json={"file_url": url, **extra})


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_roundtrip_and_empty_rejected():
    assert _upload(b"1,2,3").json()["file_url"].endswith(".csv")
    assert _upload(b"").status_code == 400


def test_predict_without_weights_returns_fallback(monkeypatch):
    monkeypatch.setattr(m, "_model_available", lambda: False)
    monkeypatch.setattr(m, "_session", None)
    r = _predict(_csv())
    assert r.status_code == 200 and "weights not found" in r.json()["summary"]


def test_non_numeric_file_rejected():
    r = _predict(b"hello this is not an ecg\nat all")
    assert r.status_code == 422 and "detail" in r.json()


def test_binary_file_rejected():
    assert _predict(bytes(range(256)) * 10).status_code == 422


def test_normal_signal_gives_beats_and_rate(monkeypatch):
    _install(monkeypatch)
    j = _predict(_csv(hr=70)).json()
    assert j["rhythm_type"] == "Normal Sinus Rhythm"
    assert len(j["beats"]) >= 20 and all(b["class"] == "N" for b in j["beats"])
    assert 62 <= j["heart_rate_bpm"] <= 78
    assert j["signal_fs"] == 360 and abs(j["duration_sec"] - 20) < 0.1
    assert 0 < len(j["signal"]) <= 12000
    assert j["beat_summary"]["N"] == len(j["beats"])


def test_header_row_and_time_column_are_handled(monkeypatch):
    _install(monkeypatch)
    j = _predict(_csv(header="time,ECG", with_time=True)).json()
    assert len(j["beats"]) >= 20


def test_sampling_rate_parameter_resamples(monkeypatch):
    _install(monkeypatch)
    j = _predict(_csv(fs=250, hr=60), sampling_rate=250).json()
    assert abs(j["duration_sec"] - 20) < 0.2 and 15 <= len(j["beats"]) <= 25


def test_too_short_signal_rejected(monkeypatch):
    _install(monkeypatch)
    assert _predict(_csv(seconds=1)).status_code == 422


def test_short_signal_warns(monkeypatch):
    _install(monkeypatch)
    j = _predict(_csv(seconds=6)).json()
    assert j["warnings"] and "10" in j["warnings"][0]


def test_ventricular_class_is_flagged(monkeypatch):
    _install(monkeypatch, cls=2)  # every beat 'V'
    j = _predict(_csv(hr=80)).json()
    assert j["beat_summary"]["V"] == len(j["beats"]) and len(j["flagged_beats"]) == len(j["beats"])


def test_samples_listed_and_served():
    names = client.get("/arrhythmia/samples").json()["samples"]
    assert "sinus_rhythm" in names and "ventricular_ectopy" in names
    r = client.get("/arrhythmia/samples/sinus_rhythm")
    assert r.status_code == 200 and len(r.text.splitlines()) == 7200
    assert client.get("/arrhythmia/samples/nope").status_code == 404
