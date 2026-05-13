param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."),
    [string]$Company = "Your Company",
    [string]$InputDir = "data/finance_exports",
    [string]$OutputDir = "output",
    [string]$InputGlob = "*.csv"
)

Set-Location $ProjectRoot

if (Test-Path ".venv\Scripts\python.exe") {
    $python = ".venv\Scripts\python.exe"
} else {
    $python = "python"
}

& $python -m src.cfo_agent.main --company $Company --input-dir $InputDir --input-glob $InputGlob --output-dir $OutputDir
if ($LASTEXITCODE -ne 0) {
    throw "Monthly CFO report generation failed."
}

Write-Output "Monthly CFO report generation completed successfully."
