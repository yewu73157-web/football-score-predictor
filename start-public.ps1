$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project

$env:FOOTBALL_HOST = "0.0.0.0"
$env:FOOTBALL_PORT = "8765"
$env:FOOTBALL_DEBUG = "0"

$listen = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if (-not $listen) {
  Start-Process -FilePath python -ArgumentList "app.py" -WorkingDirectory $project -WindowStyle Hidden
  Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "正在创建公网访问地址..."
Write-Host "保持这个窗口打开，公网地址才会持续有效。"
Write-Host ""

ssh `
  -o StrictHostKeyChecking=no `
  -o UserKnownHostsFile=NUL `
  -o ServerAliveInterval=30 `
  -R 80:localhost:8765 `
  nokey@localhost.run
