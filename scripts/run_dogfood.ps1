# Orqis dogfood harness — preflight + Tier A (+ Tier B if CURSOR_API_KEY set).
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "==> preflight"
python scripts/preflight.py

Write-Host "==> Tier A: pipeline runaway"
pytest tests/test_pipeline_runaway.py -v

if ($env:CURSOR_API_KEY) {
    Write-Host "==> Tier B: agent IDE flow"
    pytest tests/test_agent_ide_flow.py -v
} else {
    Write-Host "SKIP Tier B: CURSOR_API_KEY not set"
}
