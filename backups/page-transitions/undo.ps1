$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$sourceFile = Join-Path $PSScriptRoot 'app.js.before'
$targetFile = Join-Path $projectRoot 'src/app.js'
Copy-Item -LiteralPath $sourceFile -Destination $targetFile -Force
Write-Output 'Page transition changes reverted. Refresh the browser.'
