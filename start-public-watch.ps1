$ErrorActionPreference = "Continue"

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project

$env:FOOTBALL_HOST = "0.0.0.0"
$env:FOOTBALL_PORT = "8765"
$env:FOOTBALL_DEBUG = "0"

function Ensure-App {
  $listen = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
  if (-not $listen) {
    Start-Process -FilePath python -ArgumentList "app.py" -WorkingDirectory $project -WindowStyle Hidden
    Start-Sleep -Seconds 3
  }
}

function Extract-Url($path) {
  if (-not (Test-Path $path)) { return $null }
  $text = Get-Content $path -Raw -ErrorAction SilentlyContinue
  $matches = [regex]::Matches($text, "https://[a-zA-Z0-9.-]+")
  if ($matches.Count -eq 0) { return $null }
  return $matches[$matches.Count - 1].Value
}

Write-Host ""
Write-Host "公网隧道守护模式已启动。"
Write-Host "说明：这是临时公网地址，断线后会自动重连，但地址可能变化。"
Write-Host "真正固定地址需要云部署或 Cloudflare Tunnel 绑定域名。"
Write-Host ""

while ($true) {
  Ensure-App
  $log = Join-Path $project "public-tunnel-watch.log"
  Remove-Item $log -Force -ErrorAction SilentlyContinue

  $process = Start-Process `
    -FilePath "C:\Windows\System32\OpenSSH\ssh.exe" `
    -ArgumentList @(
      "-o", "StrictHostKeyChecking=no",
      "-o", "UserKnownHostsFile=NUL",
      "-o", "ServerAliveInterval=30",
      "-R", "80:localhost:8765",
      "nokey@localhost.run"
    ) `
    -RedirectStandardOutput $log `
    -RedirectStandardError $log `
    -WindowStyle Hidden `
    -PassThru

  $url = $null
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $url = Extract-Url $log
    if ($url) { break }
  }

  if ($url) {
    Set-Content -Path (Join-Path $project "current-public-url.txt") -Value $url -Encoding UTF8
    Write-Host "当前公网地址: $url"
  } else {
    Write-Host "未获取到公网地址，准备重试。"
  }

  while (-not $process.HasExited) {
    Start-Sleep -Seconds 10
  }

  Write-Host "公网隧道已断开，5 秒后自动重连。"
  Start-Sleep -Seconds 5
}
