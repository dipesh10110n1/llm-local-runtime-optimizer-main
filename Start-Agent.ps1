<# Start the local model and Orbit interface from any PowerShell directory. #>
[CmdletBinding()]
param(
    [ValidateSet("qwen2.5-0.5b-instruct-q4_k_m.gguf", "qwen2.5-1.5b-instruct-q4_k_m.gguf", "qwen2.5-3b-instruct-q4_k_m.gguf")]
    [string]$Model = "qwen2.5-0.5b-instruct-q4_k_m.gguf",
    [int]$Threads = 4,
    [int]$ContextSize = 1024
)
$projectRoot = $PSScriptRoot; $python = Join-Path $projectRoot ".venv\Scripts\python.exe"; $modelPath = Join-Path $projectRoot "models\$Model"
if (-not (Test-Path -LiteralPath $python)) { throw "Project virtual environment not found: $python" }
if (-not (Test-Path -LiteralPath $modelPath)) { throw "Model not found: $modelPath" }
if (-not (Get-Command llama-server -ErrorAction SilentlyContinue)) { throw "llama-server is not installed or not on PATH." }
$listening = $false
try { $listening = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:9931/health).StatusCode -eq 200 } catch { }
if (-not $listening) {
    Write-Host "Starting local model: $Model" -ForegroundColor Cyan
    # ArgumentList is deliberately one quoted string: the project path contains spaces.
    $serverArguments = '-m "{0}" --host 127.0.0.1 --port 9931 -t {1} -c {2} -ngl 0' -f $modelPath, $Threads, $ContextSize
    $serverProcess = Start-Process -FilePath "llama-server" -ArgumentList $serverArguments -WindowStyle Hidden -PassThru
    $deadline = (Get-Date).AddSeconds(90)
    do { Start-Sleep -Milliseconds 700; try { $listening = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:9931/health).StatusCode -eq 200 } catch { $listening = $false } } until ($listening -or (Get-Date) -gt $deadline)
    if (-not $listening) { throw "The local model did not become ready within 90 seconds." }
    $modelId = $Model -replace '-instruct-q4_k_m\.gguf$', '-q4_k_m'
    $runtimeState = @{ model_id = $modelId; model_file = "models/$Model"; threads = $Threads; context_size = $ContextSize; gpu_layers = 0; pid = $serverProcess.Id }
    $runtimeState | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot "runtime\active_runtime.json") -Encoding utf8
}
elseif (-not (Test-Path -LiteralPath (Join-Path $projectRoot "runtime\active_runtime.json"))) {
    # Adopt only a matching local server so Orbit can safely switch it later.
    $matchingServer = Get-CimInstance Win32_Process | Where-Object { $_.Name -like "llama-server*" -and $_.CommandLine -like "*$Model*" } | Select-Object -First 1
    if ($matchingServer) {
        $modelId = $Model -replace '-instruct-q4_k_m\.gguf$', '-q4_k_m'
        @{ model_id = $modelId; model_file = "models/$Model"; threads = $Threads; context_size = $ContextSize; gpu_layers = 0; pid = $matchingServer.ProcessId } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot "runtime\active_runtime.json") -Encoding utf8
    }
}
Set-Location $projectRoot
Write-Host "Orbit is ready at http://127.0.0.1:8502" -ForegroundColor Green
& $python -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8502
