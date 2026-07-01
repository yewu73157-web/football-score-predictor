$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project

$env:FOOTBALL_HOST = "0.0.0.0"
$env:FOOTBALL_PORT = "8765"
$env:FOOTBALL_DEBUG = "0"

$ip = Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {
    $_.IPAddress -notlike "127.*" -and
    $_.IPAddress -notlike "169.254.*" -and
    $_.InterfaceAlias -notmatch "Kuaijiasu|vEthernet|Loopback"
  } |
  Select-Object -First 1 -ExpandProperty IPAddress

Write-Host ""
Write-Host "足球比分预测服务已准备启动"
Write-Host "电脑访问: http://127.0.0.1:8765/"
if ($ip) {
  Write-Host "手机访问: http://$ip`:8765/"
  Write-Host "手机和电脑需要连接同一个 Wi-Fi。"
} else {
  Write-Host "未自动识别局域网 IP，请运行 ipconfig 查看 IPv4 地址。"
}
Write-Host ""
Write-Host "如果手机打不开，请允许 Windows 防火墙放行 Python。"
Write-Host ""

python app.py
