# Generate RAW Dataset for Face Training
# Generates 300-500 base images and uploads to Azure Blob Storage
#
# Usage: .\generate-raw-dataset.ps1 -FolderName "raw-dataset-v1" -Count 300

param(
    [string]$FolderName = "raw-dataset-$(Get-Date -Format 'yyyyMMdd')",
    [int]$Count = 100,
    [int]$BatchSize = 4,
    [string]$PodUrl = "https://3d9i9swfej3mkm-8000.proxy.runpod.net"
)

# Azure Configuration
$AzureStorageAccount = $env:AZURE_STORAGE_ACCOUNT ?? "sdxl"
$AzureStorageKey = $env:AZURE_STORAGE_KEY
if (-not $AzureStorageKey) { Write-Error "Set AZURE_STORAGE_KEY env var"; exit 1 }
$ContainerName = "personas"

# Generation Settings (matching ComfyUI workflow)
$BasePrompt = @"
RAW photo, realistic woman of South Asian descent,
raised in the United States,
with subtle Southern European features,
youthful facial structure, smooth skin with natural texture,
even warm complexion with light golden undertone,
lean facial structure, refined jawline,
thick dark brown hair with soft natural waves, center part,
neutral expression,
soft indoor window light, 50mm lens
"@

$NegativePrompt = @"
makeup, heavy makeup, exaggerated features,
cartoon, anime, deformed face, bad anatomy,
extra fingers, distorted eyes,
model face, influencer look, stock photo, perfect symmetry,
beauty editorial, generic face, nordic features, slavic features, pale skin,
western european stock face,round face, wide jaw, soft cheeks,
beauty editorial, stock photo,
european model, nordic features,round face, wide jaw, heavy cheeks,
nordic features, pale skin,
beauty editorial, stock model face,
teenage, childlike face,
pale skin, porcelain skin,
nordic features, slavic features,
short hair, bangs,
editorial model, stock photo face
"@

$GenerationSettings = @{
    cfg_scale = 3.6
    steps = 22
    sampler = "DPM++ 2M Karras"
    batch_size = 1
    seed = random
}

# ═══════════════════════════════════════════════════════════════
# Azure Blob Upload Function
# ═══════════════════════════════════════════════════════════════

function Upload-ToAzureBlob {
    param(
        [byte[]]$ImageBytes,
        [string]$BlobName
    )
    
    $dateStr = [DateTime]::UtcNow.ToString("R")
    $version = "2021-06-08"
    $contentLength = $ImageBytes.Length
    $contentType = "image/png"
    
    # Build signature
    $canonicalHeaders = "x-ms-blob-type:BlockBlob`nx-ms-date:$dateStr`nx-ms-version:$version"
    $canonicalResource = "/$AzureStorageAccount/$ContainerName/$BlobName"
    $stringToSign = "PUT`n`n`n$contentLength`n`n$contentType`n`n`n`n`n`n`n$canonicalHeaders`n$canonicalResource"
    
    $key = [Convert]::FromBase64String($AzureStorageKey)
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = $key
    $signature = [Convert]::ToBase64String($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($stringToSign)))
    
    $uri = "https://$AzureStorageAccount.blob.core.windows.net/$ContainerName/$BlobName"
    
    $headers = @{
        "x-ms-date" = $dateStr
        "x-ms-version" = $version
        "x-ms-blob-type" = "BlockBlob"
        "Authorization" = "SharedKey $($AzureStorageAccount):$signature"
        "Content-Type" = $contentType
    }
    
    try {
        $response = Invoke-RestMethod -Uri $uri -Headers $headers -Method PUT -Body $ImageBytes
        return $true
    } catch {
        Write-Host "  Upload failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# ═══════════════════════════════════════════════════════════════
# Generate Single Image
# ═══════════════════════════════════════════════════════════════

function Generate-Image {
    param([int]$Index)
    
    $body = @{
        prompt = $BasePrompt
        negative_prompt = $NegativePrompt
        steps = $GenerationSettings.steps
        cfg_scale = $GenerationSettings.cfg_scale
        width = $GenerationSettings.width
        height = $GenerationSettings.height
        seed = -1  # Random seed
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Method Post -Uri "$PodUrl/generate" -Body $body -ContentType "application/json" -TimeoutSec 120
        
        if ($response.success) {
            return @{
                success = $true
                image_url = $response.image_url
                seed = $response.seed_used
                hash = $response.image_hash
            }
        } else {
            return @{ success = $false; error = $response.error }
        }
    } catch {
        return @{ success = $false; error = $_.Exception.Message }
    }
}

# ═══════════════════════════════════════════════════════════════
# Download Image from Pod
# ═══════════════════════════════════════════════════════════════

function Download-Image {
    param([string]$ImagePath)
    
    $fullUrl = "$PodUrl$ImagePath"
    
    try {
        $response = Invoke-WebRequest -Uri $fullUrl -TimeoutSec 30
        return $response.Content
    } catch {
        Write-Host "  Download failed: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# ═══════════════════════════════════════════════════════════════
# Main Execution
# ═══════════════════════════════════════════════════════════════

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "RAW Dataset Generator" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Pod URL:     $PodUrl" -ForegroundColor Gray
Write-Host "  Folder:      $ContainerName/$FolderName/" -ForegroundColor Gray
Write-Host "  Target:      $Count images" -ForegroundColor Gray
Write-Host "  Resolution:  $($GenerationSettings.width)x$($GenerationSettings.height)" -ForegroundColor Gray
Write-Host "  Steps:       $($GenerationSettings.steps)" -ForegroundColor Gray
Write-Host "  CFG:         $($GenerationSettings.cfg_scale)" -ForegroundColor Gray
Write-Host ""

# Test API connectivity
Write-Host "Testing API connectivity..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$PodUrl/health" -TimeoutSec 10
    if ($health.status -eq "healthy") {
        Write-Host "  API is healthy!" -ForegroundColor Green
        Write-Host "  ComfyUI: $($health.comfyui_status)" -ForegroundColor Gray
    } else {
        Write-Host "  API returned unhealthy status!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "  Failed to connect to API: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting generation..." -ForegroundColor Yellow
Write-Host "-" * 70 -ForegroundColor Gray

$successful = 0
$failed = 0
$startTime = Get-Date

for ($i = 1; $i -le $Count; $i++) {
    $progress = [math]::Round(($i / $Count) * 100)
    $elapsed = (Get-Date) - $startTime
    $rate = if ($successful -gt 0) { $elapsed.TotalSeconds / $successful } else { 0 }
    $eta = if ($rate -gt 0) { [TimeSpan]::FromSeconds($rate * ($Count - $i)) } else { [TimeSpan]::Zero }
    
    Write-Host "`r[$progress%] Image $i/$Count | Success: $successful | Failed: $failed | ETA: $($eta.ToString('hh\:mm\:ss'))   " -NoNewline -ForegroundColor Cyan
    
    # Generate image
    $result = Generate-Image -Index $i
    
    if ($result.success) {
        # Download image
        $imageBytes = Download-Image -ImagePath $result.image_url
        
        if ($imageBytes) {
            # Upload to Azure
            $blobName = "$FolderName/img_$($i.ToString('D4'))_seed$($result.seed).png"
            $uploaded = Upload-ToAzureBlob -ImageBytes $imageBytes -BlobName $blobName
            
            if ($uploaded) {
                $successful++
            } else {
                $failed++
            }
        } else {
            $failed++
        }
    } else {
        $failed++
        Write-Host ""
        Write-Host "  Error on image $i : $($result.error)" -ForegroundColor Red
    }
    
    # Small delay to avoid overwhelming the API
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Generation Complete!" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Results:" -ForegroundColor Yellow
Write-Host "  Successful: $successful" -ForegroundColor Green
Write-Host "  Failed:     $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Gray" })
Write-Host "  Total time: $((Get-Date) - $startTime)" -ForegroundColor Gray
Write-Host ""
Write-Host "Images saved to:" -ForegroundColor Yellow
Write-Host "  https://$AzureStorageAccount.blob.core.windows.net/$ContainerName/$FolderName/" -ForegroundColor Cyan
Write-Host ""
