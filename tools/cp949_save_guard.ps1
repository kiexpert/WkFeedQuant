# cp949_save_guard.ps1
# Pre-commit guard for CP949 encoding mismatches.
#
# Project policy (per CLAUDE.md "Encoding (MANDATORY)"): repository text
# files are UTF-8 by default. CP949 checks remain available only for export
# or compatibility gates, never as the default.
#
# This script is invoked by the codex pre-commit hook with -Path <abs file>.
# It performs a non-blocking check: if a file decodes cleanly as UTF-8 it
# passes; if not, it emits a warning but exits 0 so the commit proceeds.
# Binary files (.png/.jpg/.zip/.exe/...) are skipped.

param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

if (-not (Test-Path -LiteralPath $Path)) {
    exit 0
}

$ext = [System.IO.Path]::GetExtension($Path).ToLowerInvariant()
$binaryExts = @(
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
    '.mp4', '.mp3', '.wav', '.ogg', '.flac',
    '.zip', '.7z', '.tar', '.gz', '.rar',
    '.pdf', '.exe', '.dll', '.so', '.dylib',
    '.pyc', '.pyd', '.whl',
    '.ttf', '.otf', '.woff', '.woff2'
)
if ($binaryExts -contains $ext) {
    exit 0
}

try {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
} catch {
    exit 0
}
if ($bytes.Length -eq 0) { exit 0 }

# UTF-8 strict decode test — if it fails, file is not valid UTF-8.
try {
    $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
    [void]$utf8.GetString($bytes)
} catch {
    Write-Warning ("[cp949-save-guard] Non-UTF-8 bytes detected in: {0}" -f $Path)
}

exit 0
