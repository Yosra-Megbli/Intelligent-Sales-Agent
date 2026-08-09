# Builds the ZIP that actually gets sent to the client.
#
# P0 finding this fixes ("Secrets dans ZIP"): backend/.env holds real
# secrets (GROQ_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET,
# DATABASE_URL credentials...) and is correctly excluded from git via
# .gitignore - but .gitignore only protects `git` operations. A manual
# "Send to > Compressed folder" on the project root, or any other raw
# folder-to-zip tool, does NOT know about .gitignore and would happily
# include backend/.env verbatim. `git log` for this repo confirms .env was
# never committed (no history leak), but nothing previously stopped it
# from leaking via a *manual* zip at delivery time - that gap is what this
# script closes.
#
# How: `git archive` only ever includes files tracked by git at the given
# ref - an untracked, gitignored file like backend/.env physically cannot
# end up in its output, by construction (not by a hand-maintained exclude
# list that can go stale). A second, explicit scan of the archive contents
# runs afterwards anyway, as defense-in-depth against a future mistake
# (e.g. someone `git add -f`-ing a secret file despite .gitignore).
#
# Usage:
#   powershell -File scripts/package_client_delivery.ps1
#   powershell -File scripts/package_client_delivery.ps1 -Ref my-branch -OutFile dist/custom-name.zip

param(
    [string]$Ref = "HEAD",
    [string]$OutFile = "dist/sophie-client-delivery.zip"
)

$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
    throw "Not inside a git repository - run this from the project (or a clone of it)."
}
Set-Location $repoRoot

$outDir = Split-Path -Parent $OutFile
if ($outDir -and -not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}
if (Test-Path $OutFile) {
    Remove-Item -Force $OutFile
}

Write-Host "Building client archive from ref '$Ref' (tracked files only) -> $OutFile"
git archive --format=zip --output $OutFile $Ref
if ($LASTEXITCODE -ne 0) {
    throw "git archive failed (exit $LASTEXITCODE) - is '$Ref' a valid ref, and does it have anything committed?"
}

# --- Defense-in-depth: scan the archive we just built, don't just trust
#     "git archive should be safe by construction" -----------------------
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $OutFile))
try {
    $entryNames = $zip.Entries | ForEach-Object { $_.FullName }
} finally {
    $zip.Dispose()
}

$forbiddenPatterns = @(
    '(^|/)\.env$',
    '(^|/)\.env\.[^/]*local[^/]*$',
    '\.pem$',
    '\.key$',
    '(^|/)id_rsa$',
    '(^|/)credentials\.json$'
)

$offenders = $entryNames | Where-Object {
    $name = $_
    $forbiddenPatterns | Where-Object { $name -match $_ }
}

if ($offenders) {
    Remove-Item -Force $OutFile
    Write-Host "REFUSED: the archive would have contained secret-shaped file(s):" -ForegroundColor Red
    $offenders | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "The archive was deleted. This should be impossible via 'git archive' unless" -ForegroundColor Red
    Write-Host "one of these files was force-added to git (git add -f) despite .gitignore -" -ForegroundColor Red
    Write-Host "check 'git ls-files' for it and remove it from the repository first." -ForegroundColor Red
    exit 1
}

Write-Host ("OK: {0} files archived, no secret-shaped filenames found." -f $entryNames.Count) -ForegroundColor Green
Write-Host "Reminder: this only checks FILENAMES. Before sending $OutFile to the client," -ForegroundColor Yellow
Write-Host "also confirm backend/.env.example (not .env) is what's inside, and that no" -ForegroundColor Yellow
Write-Host "committed file contains a real secret value pasted into a comment or doc." -ForegroundColor Yellow
