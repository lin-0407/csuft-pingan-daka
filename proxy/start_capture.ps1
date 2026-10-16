$ErrorActionPreference = 'Stop'
$dir = $PSScriptRoot
$cert = Join-Path $env:USERPROFILE '.mitmproxy\mitmproxy-ca-cert.cer'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'

$cur = Get-ItemProperty $key
@{
  ProxyEnable   = $cur.ProxyEnable
  ProxyServer   = $cur.ProxyServer
  ProxyOverride = $cur.ProxyOverride
  AutoConfigURL = $cur.AutoConfigURL
} | ConvertTo-Json | Set-Content (Join-Path $dir 'proxy_backup.json') -Encoding UTF8
Write-Output ("backup: enable=" + $cur.ProxyEnable + " server=" + $cur.ProxyServer)

$hasCa = Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -match 'mitmproxy' }
if (-not $hasCa) {
  $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'CurrentUser')
  $store.Open('ReadWrite')
  $certObj = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cert)
  $store.Add($certObj)
  $store.Close()
  Write-Output 'CA: added via X509Store to CurrentUser\Root'
} else {
  Write-Output ('CA: already trusted -> ' + $hasCa.Subject)
}

# work around Start-Process env-dictionary bug with case-duplicate vars
foreach ($n in @('no_proxy', 'https_proxy', 'http_proxy')) {
  if (Test-Path ('Env:' + $n)) { Remove-Item ('Env:' + $n) -ErrorAction SilentlyContinue }
}

$addon = Join-Path $dir 'csuft_addon.py'
$argList = @(
  '-m', 'upstream:http://127.0.0.1:7892',
  '-p', '8866',
  '-s', ('"' + $addon + '"'),
  '--set', 'allow_hosts=simp\.csuft\.edu\.cn',
  '--set', 'flow_detail=1',
  '-w', ('"' + (Join-Path $dir 'flows.dump') + '"')
)
$proc = Start-Process -FilePath 'C:\Python314\Scripts\mitmdump.exe' -ArgumentList $argList -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dir 'mitmdump.out.log') -RedirectStandardError (Join-Path $dir 'mitmdump.err.log')
$proc.Id | Set-Content (Join-Path $dir 'mitmdump.pid')
Start-Sleep -Seconds 4
Write-Output ('mitmdump pid=' + $proc.Id + ' exited=' + $proc.HasExited)

Set-ItemProperty $key -Name ProxyEnable -Value 1
Set-ItemProperty $key -Name ProxyServer -Value '127.0.0.1:8866'
Write-Output ('system proxy now: ' + (Get-ItemProperty $key).ProxyServer)

Write-Output '--- listening ---'
(Get-NetTCPConnection -LocalPort 8866 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 3 | Out-String)
Write-Output '--- mitmdump.err.log ---'
Get-Content (Join-Path $dir 'mitmdump.err.log') -ErrorAction SilentlyContinue | Select-Object -First 15
