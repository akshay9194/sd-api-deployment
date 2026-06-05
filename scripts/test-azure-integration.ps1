# Test Azure Blob Storage integration for persona images
# This script tests listing and accessing images from the Azure blob

$AzureStorageAccount = $env:AZURE_STORAGE_ACCOUNT ?? "sdxl"
$AzureStorageKey = $env:AZURE_STORAGE_KEY
if (-not $AzureStorageKey) { Write-Error "Set AZURE_STORAGE_KEY env var"; exit 1 }
$ContainerName = "personas"
$PersonaName = "scarlett"

function Get-BlobList {
    param($Prefix)
    
    $dateStr = [DateTime]::UtcNow.ToString("R")
    $version = "2021-06-08"
    
    $canonicalHeaders = "x-ms-date:$dateStr`nx-ms-version:$version"
    $canonicalResource = "/$AzureStorageAccount/$ContainerName`ncomp:list`nprefix:$Prefix`nrestype:container"
    $stringToSign = "GET`n`n`n`n`n`n`n`n`n`n`n`n$canonicalHeaders`n$canonicalResource"
    
    $key = [Convert]::FromBase64String($AzureStorageKey)
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = $key
    $signature = [Convert]::ToBase64String($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($stringToSign)))
    
    $uri = "https://$AzureStorageAccount.blob.core.windows.net/$ContainerName`?restype=container&comp=list&prefix=$([uri]::EscapeDataString($Prefix))"
    
    $headers = @{
        "x-ms-date" = $dateStr
        "x-ms-version" = $version
        "Authorization" = "SharedKey $($AzureStorageAccount):$signature"
    }
    
    try {
        $response = Invoke-RestMethod -Uri $uri -Headers $headers -Method GET
        return $response.EnumerationResults.Blobs.Blob.Name
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        return @()
    }
}

function Generate-SasToken {
    param($BlobName, $ExpiryMinutes = 60)
    
    $start = [DateTime]::UtcNow.AddMinutes(-5).ToString("yyyy-MM-ddTHH:mm:ssZ")
    $expiry = [DateTime]::UtcNow.AddMinutes($ExpiryMinutes).ToString("yyyy-MM-ddTHH:mm:ssZ")
    
    $stringToSign = "r`n$start`n$expiry`n/blob/$AzureStorageAccount/$ContainerName/$BlobName`n`n`nhttps`n2021-06-08`nb`n`n`n`n`n`n"
    
    $key = [Convert]::FromBase64String($AzureStorageKey)
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = $key
    $signature = [Convert]::ToBase64String($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($stringToSign)))
    
    $sasToken = "sv=2021-06-08&sr=b&sp=r&se=$([uri]::EscapeDataString($expiry))&st=$([uri]::EscapeDataString($start))&spr=https&sig=$([uri]::EscapeDataString($signature))"
    
    return $sasToken
}

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Testing Azure Blob Storage Integration" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

Write-Host "`nListing images for persona: $PersonaName" -ForegroundColor Yellow
$blobs = Get-BlobList -Prefix "$PersonaName/"

if ($blobs.Count -eq 0) {
    Write-Host "No images found!" -ForegroundColor Red
} else {
    Write-Host "Found $($blobs.Count) images:" -ForegroundColor Green
    $blobs | Select-Object -First 5 | ForEach-Object {
        Write-Host "  - $_" -ForegroundColor Gray
    }
    
    # Generate SAS URL for a random image
    $randomBlob = $blobs | Get-Random
    $sasToken = Generate-SasToken -BlobName $randomBlob
    $fullUrl = "https://$AzureStorageAccount.blob.core.windows.net/$ContainerName/$randomBlob`?$sasToken"
    
    Write-Host "`nSample SAS URL for: $randomBlob" -ForegroundColor Yellow
    Write-Host $fullUrl -ForegroundColor Cyan
    
    # Test if URL is accessible
    Write-Host "`nTesting URL accessibility..." -ForegroundColor Yellow
    try {
        $testResponse = Invoke-WebRequest -Uri $fullUrl -Method HEAD -TimeoutSec 10
        if ($testResponse.StatusCode -eq 200) {
            Write-Host "SUCCESS: Image is accessible!" -ForegroundColor Green
            Write-Host "Content-Type: $($testResponse.Headers['Content-Type'])" -ForegroundColor Gray
            Write-Host "Content-Length: $($testResponse.Headers['Content-Length']) bytes" -ForegroundColor Gray
        }
    } catch {
        Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n" + "=" * 60 -ForegroundColor Cyan
