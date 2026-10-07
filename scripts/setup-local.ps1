$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$postgresBin = 'C:\Program Files\PostgreSQL\18\bin'
$localDir = Join-Path $projectRoot '.local'
$dataDir = Join-Path $localDir 'postgres-data'
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}
if (-not (Test-Path (Join-Path $projectRoot 'backend\.env'))) {
    $password = New-Secret
    $jwtSecret = New-Secret
    [IO.File]::WriteAllText((Join-Path $projectRoot 'backend\.env'), "DATABASE_URL=postgresql+psycopg://lifelens:$password@127.0.0.1:55432/lifelens`nJWT_SECRET=$jwtSecret`nFRONTEND_ORIGIN=http://localhost:5173`nACCESS_TOKEN_MINUTES=30`n")
}
$envContents = Get-Content (Join-Path $projectRoot 'backend\.env') -Raw
$password = [regex]::Match($envContents, 'postgresql\+psycopg://lifelens:([^@]+)@127\.0\.0\.1:55432/lifelens').Groups[1].Value
if (-not $password) { throw 'Existing .env uses another database. Configure that database manually; no existing configuration was changed.' }
if (-not (Test-Path (Join-Path $dataDir 'PG_VERSION'))) {
    $pwFile = Join-Path $localDir 'init-password'
    [IO.File]::WriteAllText($pwFile, $password)
    try {
        & "$postgresBin\initdb.exe" -D $dataDir -U lifelens -A scram-sha-256 --pwfile=$pwFile --encoding=UTF8 --locale=C
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL initialization failed' }
    } finally { Remove-Item -LiteralPath $pwFile -ErrorAction SilentlyContinue }
}
& "$postgresBin\pg_ctl.exe" status -D $dataDir
if ($LASTEXITCODE -ne 0) {
    $pgStart = Start-Process -FilePath "$postgresBin\pg_ctl.exe" -ArgumentList @('start', '-D', "`"$dataDir`"", '-l', "`"$(Join-Path $localDir 'postgres.log')`"", '-o', '"-p 55432 -h 127.0.0.1"', '-w') -WindowStyle Hidden -PassThru
    $pgStart.WaitForExit()
    if ($pgStart.ExitCode -ne 0) { throw 'PostgreSQL startup failed; see .local/postgres.log' }
}
$env:PGPASSWORD = $password
try {
    $exists = & "$postgresBin\psql.exe" -h 127.0.0.1 -p 55432 -U lifelens -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='lifelens'"
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL connection failed' }
    if ("$exists".Trim() -ne '1') {
        & "$postgresBin\createdb.exe" -h 127.0.0.1 -p 55432 -U lifelens lifelens
        if ($LASTEXITCODE -ne 0) { throw 'Database creation failed' }
    }
} finally { Remove-Item Env:\PGPASSWORD }
if (-not (Test-Path (Join-Path $projectRoot 'frontend\.env'))) {
    Copy-Item (Join-Path $projectRoot 'frontend\.env.example') (Join-Path $projectRoot 'frontend\.env')
}
Write-Host 'Local PostgreSQL ready on 127.0.0.1:55432. Run migrations and seed from backend/.'
