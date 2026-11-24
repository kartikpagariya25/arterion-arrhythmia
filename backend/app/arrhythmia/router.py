import os

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..accounts.deps import optional_user
from ..accounts.history import record_analysis
from .model import predict

router = APIRouter(prefix="/arrhythmia", tags=["arrhythmia"])
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")


class PredictRequest(BaseModel):
    file_url: str
    sampling_rate: int = Field(360, ge=50, le=2000, description="Hz of the uploaded signal (MIT-BIH is 360)")


@router.post("/predict")
def predict_arrhythmia(req: PredictRequest, response: Response, user=Depends(optional_user)):
    result = predict(req.file_url, req.sampling_rate)
    record_analysis(user, "arrhythmia", req.file_url, result, response)
    return result


def _sample_names():
    return sorted(f[:-4] for f in os.listdir(SAMPLES_DIR) if f.endswith(".csv"))


@router.get("/samples")
def list_samples():
    return {"samples": _sample_names()}


@router.get("/samples/{name}", response_class=PlainTextResponse)
def get_sample(name: str):
    if name not in _sample_names():
        raise HTTPException(status_code=404, detail="Unknown sample.")
    with open(os.path.join(SAMPLES_DIR, name + ".csv"), encoding="utf-8") as f:
        return f.read()
