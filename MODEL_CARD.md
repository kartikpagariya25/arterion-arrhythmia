# Model card: Arterion ECG Monitor

> Research prototype, not a medical device. Do not use for diagnosis or treatment decisions.

## Task
Beat-by-beat arrhythmia classification for single-lead ECG, plus rule-based rhythm alerts.

## Model
CardioNet, a 1D residual CNN (498 k parameters) over a 256-sample beat window plus four R-R features, exported to ONNX.

## Input and output
- **Input:** a single-lead ECG as CSV/text (sampling rate 360 Hz by default; a header row and a time column are tolerated).
- **Output:** a class per beat (N, S, V, F, Q), counts, heart rate, rhythm alerts and a decimated signal for plotting.

## Training and evaluation data
MIT-BIH Arrhythmia Database (PhysioNet): DS1 records for training, the disjoint DS2 records (49,692 beats) for testing.

## Results
- Accuracy 0.900, macro-F1 0.411 on inter-patient DS2.
- Ventricular ectopy: sensitivity 0.943, PPV 0.825.
- Supraventricular: sensitivity 0.238. Fusion: sensitivity 0.028. These classes are poor.

Numbers in `training/artifacts/metrics.json` match the published weights.

## Limitations
- Supraventricular and fusion beats are mostly missed.
- Rhythm alerts (VT, bigeminy, trigeminy, AFib-like irregularity, tachy/bradycardia) are hand-written rules and have not been validated against annotated rhythm episodes.
- Trained on one database with two-lead recordings reduced to one lead; other devices, sampling rates and noise levels may behave differently.

## Intended use
Research, teaching and prototyping. Not for diagnosis, triage or any clinical decision, and not validated for any clinical setting.

## Licence and data terms
Code: MIT. MIT-BIH is distributed under the Open Data Commons Attribution License.
