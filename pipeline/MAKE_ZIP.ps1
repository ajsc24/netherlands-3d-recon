# Run on Windows to create drone_recon_linux.zip for transfer
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$zip = Join-Path (Split-Path $here -Parent) "drone_recon_linux.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $here -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Created: $zip"
Write-Host "Also copy your .mp4 separately to input/video.mp4 on Linux"
