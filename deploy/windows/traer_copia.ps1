<#
 Trae al computador la última copia cifrada del servidor y verifica su integridad.
 Uso:  powershell -NoProfile -ExecutionPolicy Bypass -File traer_copia.ps1
 Requiere la llave dedicada (por defecto $HOME\.ssh\respaldo_dh), que en el servidor solo puede pedir
 la última copia (ver docs/respaldo_en_mi_pc.md). Las copias ya vienen cifradas: sin BACKUP_PASSPHRASE no se abren.
#>
param(
    [string]$Destino  = "D:\Respaldos\DH-Control",
    [string]$Llave    = "$HOME\.ssh\respaldo_dh",
    [string]$Servidor = "control@31.97.136.172",
    [int]$Conservar   = 30
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$ssh = @("-i", $Llave, "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", $Servidor)

$nombre = (& ssh @ssh name).Trim()
if (-not $nombre -or $LASTEXITCODE -ne 0) { throw "No se pudo obtener el nombre de la última copia." }
$final = Join-Path $Destino $nombre
if (Test-Path $final) { Write-Host "Ya tienes la copia más reciente: $nombre"; exit 0 }

$sha = ((& ssh @ssh sha).Trim()).ToLower()
$parcial = "$final.parcial"
# cmd /c redirige en binario (PowerShell 5 dañaría el archivo)
cmd /c "ssh -i `"$Llave`" -o BatchMode=yes -o IdentitiesOnly=yes $Servidor latest > `"$parcial`""
if ($LASTEXITCODE -ne 0) { Remove-Item $parcial -ErrorAction SilentlyContinue; throw "Falló la descarga." }

$local = (Get-FileHash $parcial -Algorithm SHA256).Hash.ToLower()
if ($local -ne $sha) { Remove-Item $parcial; throw "La huella no coincide: descarga corrupta, se descartó." }
Rename-Item $parcial $nombre
Write-Host "Copia guardada y verificada: $final"

# Conserva solo las últimas $Conservar copias
Get-ChildItem $Destino -Filter "control-*.gpg" | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $Conservar | Remove-Item -Force
