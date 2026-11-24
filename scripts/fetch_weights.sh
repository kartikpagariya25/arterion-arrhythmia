#!/usr/bin/env bash
# Downloads trained ONNX weights from the latest GitHub Release into backend/app/arrhythmia/weights/
set -euo pipefail
REPO="kartikpagariya25/arterion-arrhythmia"
DEST="$(dirname "$0")/../backend/app/arrhythmia/weights"
mkdir -p "$DEST"
for f in model.onnx feature_stats.json; do
  echo "Downloading $f ..."
  curl -fL --retry 3 -o "$DEST/$f" "https://github.com/$REPO/releases/latest/download/$f"
done
echo "Done."
