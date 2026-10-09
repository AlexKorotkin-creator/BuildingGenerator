param([string]$Out = "$PSScriptRoot/logs/cpu_watch.csv")

New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null

function Get-Proc($names) {
  foreach ($n in $names) {
    $p = Get-Process -Name $n -ErrorAction SilentlyContinue | Sort-Object WorkingSet64 -Descending | Select-Object -First 1
    if ($p) { return $p }
  }
  return $null
}

"time,houdini_cores,ue_cores,houdini_ws_gb,ue_ws_gb" | Out-File -FilePath $Out -Encoding utf8

$hPrev = $null; $uPrev = $null; $tPrev = (Get-Date).ToUniversalTime()
while ($true) {
  Start-Sleep -Milliseconds 2000
  $h = Get-Proc @('houdini','houdinifx','houdinicore')
  $u = Get-Proc @('UnrealEditor','UE4Editor','UnrealEditor-Win64-DebugGame')
  $tNow = (Get-Date).ToUniversalTime()
  $dt = ($tNow - $tPrev).TotalSeconds
  if ($dt -le 0) { $dt = 2 }

  $hc = 0.0; $uc = 0.0; $hg = 0.0; $ug = 0.0
  if ($h) {
    $hg = [math]::Round($h.WorkingSet64 / 1GB, 1)
    $cur = $h.TotalProcessorTime.TotalSeconds
    if ($hPrev -ne $null) { $hc = [math]::Round(($cur - $hPrev) / $dt, 2) }
    $hPrev = $cur
  } else { $hPrev = $null }
  if ($u) {
    $ug = [math]::Round($u.WorkingSet64 / 1GB, 1)
    $cur = $u.TotalProcessorTime.TotalSeconds
    if ($uPrev -ne $null) { $uc = [math]::Round(($cur - $uPrev) / $dt, 2) }
    $uPrev = $cur
  } else { $uPrev = $null }

  $tPrev = $tNow
  "{0},{1},{2},{3},{4}" -f $tNow.ToString("HH:mm:ss"), $hc, $uc, $hg, $ug | Out-File -FilePath $Out -Append -Encoding utf8
}
