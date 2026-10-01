# Restarts the Jarvis desk. Stops listeners on the desk ports, then starts them again.
$ErrorActionPreference = "Continue"
$Root = "D:\Cursor\Jarvis"

function Test-DeskProcess([string]$Name, [string]$CommandLine) {
    $blob = "$Name $CommandLine"
    return $blob -match 'uvicorn.*app\.main:app|next\\dist\\bin\\next|hermes_cli|hermes\.cmd|gateway run|ollama(\.exe)?\s+serve'
}

function Stop-DeskPort([int]$Port) {
    $owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($procId in $owners) {
        if (-not $procId -or $procId -eq 0) { continue }
        $current = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
        if (-not $current) { continue }
        $killId = $procId
        $parentId = $current.ParentProcessId
        while ($parentId -and $parentId -ne 0) {
            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$parentId" -ErrorAction SilentlyContinue
            if (-not $parent) { break }
            if (-not (Test-DeskProcess $parent.Name $parent.CommandLine)) { break }
            $killId = $parentId
            $parentId = $parent.ParentProcessId
        }
        if (Test-DeskProcess $current.Name $current.CommandLine) {
            & taskkill.exe /PID $killId /T /F 2>$null | Out-Null
        }
    }
}

foreach ($port in 3000, 8000, 8642, 11434) {
    Stop-DeskPort $port
}
Start-Sleep -Seconds 1

$python = Join-Path $Root ".venv\Scripts\python.exe"
Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "app.main:app",
    "--app-dir", "backend",
    "--host", "127.0.0.1",
    "--port", "8000"
) -WorkingDirectory $Root -WindowStyle Hidden

$npm = "C:\Program Files\nodejs\npm.cmd"
Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/c", "`"$npm`" run dev") -WorkingDirectory (Join-Path $Root "frontend") -WindowStyle Hidden

$hermes = "C:\Users\asus\AppData\Local\hermes\bin\hermes.cmd"
if (Test-Path $hermes) {
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/c", "`"$hermes`" gateway run") -WorkingDirectory $Root -WindowStyle Hidden
} else {
    $hermesPython = "C:\Users\asus\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
    Start-Process -FilePath $hermesPython -ArgumentList @("-m", "hermes_cli.main", "gateway", "run") -WorkingDirectory $Root -WindowStyle Hidden
}

$ollama = "C:\Users\asus\AppData\Local\Programs\Ollama\ollama.exe"
Start-Process -FilePath $ollama -ArgumentList @("serve") -WindowStyle Hidden

Write-Output "Restarted API :8000, HUD :3000, Hermes :8642, and Ollama :11434. Open http://localhost:3000"
exit 0
