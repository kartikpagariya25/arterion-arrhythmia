# Downloads trained ONNX weights from the latest GitHub Release into backend/app/arrhythmia/weights/
$ErrorActionPreference = "Stop"
$repo = "kartikpagariya25/arterion-arrhythmia"
$dest = Join-Path $PSScriptRoot "..\backend\app\arrhythmia\weights"
New-Item -ItemType Directory -Force $dest | Out-Null
foreach ($f in "model.onnx", "feature_stats.json") {
  Write-Host "Downloading $f ..."
  Invoke-WebRequest "https://github.com/$repo/releases/latest/download/$f" -OutFile (Join-Path $dest $f)
}
Write-Host "Done."
