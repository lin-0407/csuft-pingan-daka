$dir = $PSScriptRoot
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
if (Test-Path (Join-Path $dir 'proxy_backup.json')) {
  $b = Get-Content (Join-Path $dir 'proxy_backup.json') -Raw | ConvertFrom-Json
  Set-ItemProperty $key -Name ProxyEnable -Value $b.ProxyEnable
  if ($b.ProxyServer)   { Set-ItemProperty $key -Name ProxyServer   -Value $b.ProxyServer }
  if ($b.ProxyOverride) { Set-ItemProperty $key -Name ProxyOverride -Value $b.ProxyOverride }
  Write-Output ('proxy restored: enable=' + $b.ProxyEnable + ' server=' + $b.ProxyServer)
}
if (Test-Path (Join-Path $dir 'mitmdump.pid')) {
  $procId = [int](Get-Content (Join-Path $dir 'mitmdump.pid'))
  try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Output ('mitmdump stopped: ' + $procId) } catch { Write-Output ('mitmdump not running: ' + $procId) }
}
