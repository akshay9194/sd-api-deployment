# Persona Variant Generator - 10 SFW images per persona
# Usage: .\generate-persona-variants.ps1 -ApiUrl "https://YOUR-POD-8000.proxy.runpod.net"
#
# Generates varied images: different poses, settings, outfits, activities

param(
    [string]$ApiUrl = "https://1an705ff1fij4z-8000.proxy.runpod.net",
    [string]$ContainerName = "personas"
)

# ═══════════════════════════════════════════════════════════════
# AZURE BLOB STORAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════
$AzureStorageAccount = $env:AZURE_STORAGE_ACCOUNT ?? "sdxl"
$AzureStorageKey = $env:AZURE_STORAGE_KEY
if (-not $AzureStorageKey) { Write-Error "Set AZURE_STORAGE_KEY env var"; exit 1 }

# ═══════════════════════════════════════════════════════════════
# AZURE BLOB UPLOAD FUNCTION
# ═══════════════════════════════════════════════════════════════
function Upload-ToAzureBlob {
    param(
        [byte[]]$ImageData,
        [string]$BlobName,
        [string]$StorageAccount,
        [string]$StorageKey,
        [string]$Container
    )
    
    $date = [DateTime]::UtcNow.ToString("R")
    $version = "2020-10-02"
    $contentLength = $ImageData.Length
    $contentType = "image/png"
    
    $canonicalizedHeaders = "x-ms-blob-type:BlockBlob`nx-ms-date:$date`nx-ms-version:$version"
    $canonicalizedResource = "/$StorageAccount/$Container/$BlobName"
    $stringToSign = "PUT`n`n`n$contentLength`n`n$contentType`n`n`n`n`n`n`n$canonicalizedHeaders`n$canonicalizedResource"
    
    $keyBytes = [Convert]::FromBase64String($StorageKey)
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = $keyBytes
    $signatureBytes = $hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($stringToSign))
    $signature = [Convert]::ToBase64String($signatureBytes)
    
    $authHeader = "SharedKey ${StorageAccount}:$signature"
    $uri = "https://$StorageAccount.blob.core.windows.net/$Container/$BlobName"
    $headers = @{
        "x-ms-blob-type" = "BlockBlob"
        "x-ms-date" = $date
        "x-ms-version" = $version
        "Authorization" = $authHeader
        "Content-Type" = $contentType
    }
    
    try {
        $response = Invoke-WebRequest -Uri $uri -Method Put -Headers $headers -Body $ImageData -UseBasicParsing
        return $response.StatusCode -eq 201
    } catch {
        return $false
    }
}

# ═══════════════════════════════════════════════════════════════
# BASE PROMPT (Photorealistic Foundation)
# ═══════════════════════════════════════════════════════════════
$BASE_PROMPT = @"
photorealistic photograph of a clearly adult person, 25+ years old,
fully mature facial structure, natural human proportions,
subtle skin texture with visible pores,
slight facial asymmetry, realistic eye moisture and reflections,
shot on professional camera, shallow depth of field,
soft natural lighting with realistic shadows,
RAW photo look, ultra-high detail
"@ -replace "`r`n", " " -replace "`n", " "

# ═══════════════════════════════════════════════════════════════
# SCENARIO TEMPLATES (10 per persona)
# ═══════════════════════════════════════════════════════════════
$scenarios = @(
    @{
        name = "portrait_closeup"
        desc = "close-up portrait, head and shoulders, indoor natural window light, relaxed expression, casual setting"
        seedOffset = 0
    },
    @{
        name = "full_body_casual"
        desc = "full body shot, standing relaxed pose, wearing casual everyday clothes, urban street background, natural daylight"
        seedOffset = 1000
    },
    @{
        name = "outdoor_nature"
        desc = "three-quarter shot, outdoor park setting, trees and greenery background, warm afternoon sunlight, genuine smile"
        seedOffset = 2000
    },
    @{
        name = "cafe_lifestyle"
        desc = "sitting at a cafe table, holding coffee cup, cozy cafe interior, warm ambient lighting, thoughtful expression"
        seedOffset = 3000
    },
    @{
        name = "formal_portrait"
        desc = "professional headshot, wearing smart business attire, clean studio background, confident composed expression"
        seedOffset = 4000
    },
    @{
        name = "athletic_fitness"
        desc = "athletic wear, gym or outdoor fitness setting, active healthy lifestyle, energetic confident pose, bright lighting"
        seedOffset = 5000
    },
    @{
        name = "evening_elegant"
        desc = "elegant evening wear, sophisticated setting, warm ambient lighting, refined composed expression, classy atmosphere"
        seedOffset = 6000
    },
    @{
        name = "beach_summer"
        desc = "beach setting, summer casual wear, ocean background, golden hour sunset lighting, relaxed happy expression"
        seedOffset = 7000
    },
    @{
        name = "home_cozy"
        desc = "cozy home interior, comfortable loungewear, sitting on sofa, warm lamp lighting, relaxed intimate atmosphere"
        seedOffset = 8000
    },
    @{
        name = "profile_artistic"
        desc = "side profile view, artistic portrait, dramatic side lighting, contemplative expression, moody atmosphere"
        seedOffset = 9000
    }
)

# ═══════════════════════════════════════════════════════════════
# PERSONA DEFINITIONS (Identity Features Only)
# ═══════════════════════════════════════════════════════════════
$personas = @{
    "scarlett" = @{
        identity = "female, long naturally wavy ginger red hair, green eyes, light fair skin with faint freckles"
        baseSeed = 100001
    }
    "emma" = @{
        identity = "female, East Asian Korean woman, long straight black hair, dark brown eyes, soft oval face, pale porcelain skin"
        baseSeed = 200001
    }
    "victoria" = @{
        identity = "female, short black bob haircut, piercing ice blue eyes, sharp defined jawline, high cheekbones, pale fair skin"
        baseSeed = 300001
    }
    "lily" = @{
        identity = "female, shoulder length wavy chestnut brown hair, warm hazel green eyes, freckles across nose, dimples, olive skin"
        baseSeed = 400001
    }
    "isabella" = @{
        identity = "female, Colombian Latina woman, very long curly dark brown hair, warm brown eyes, full lips, golden caramel tan skin"
        baseSeed = 500001
    }
    "maya" = @{
        identity = "female, African American Black woman, long black box braids, warm dark brown eyes, rich dark brown ebony skin"
        baseSeed = 600001
    }
    "kira" = @{
        identity = "female, very long wavy black hair with purple highlights, pale skin, dark eye makeup, alternative gothic style"
        baseSeed = 700001
    }
    "marcus" = @{
        identity = "male, short black hair with clean fade, warm brown eyes, strong square jawline, light stubble, mixed race tan brown skin"
        baseSeed = 800001
    }
    "ryan" = @{
        identity = "male, messy medium dark brown hair, intense piercing blue eyes, sharp features, light stubble, arm tattoos, light skin"
        baseSeed = 900001
    }
    "alexander" = @{
        identity = "male, neatly styled medium brown hair, warm green eyes, chiseled cheekbones, clean shaven, fair skin"
        baseSeed = 1000001
    }
    "ethan" = @{
        identity = "male, messy dirty blonde hair, warm friendly brown eyes, boyish charming face, light stubble, light skin with slight tan"
        baseSeed = 1100001
    }
    "damien" = @{
        identity = "male, short black hair slicked back, intense piercing grey eyes, strong sharp jawline, clean shaven, fair pale skin"
        baseSeed = 1200001
    }
    "lucian" = @{
        identity = "male, long flowing platinum silver white hair, striking pale grey eyes, sharp aristocratic features, very pale white skin"
        baseSeed = 1300001
    }
}

# ═══════════════════════════════════════════════════════════════
# MAIN GENERATION LOOP
# ═══════════════════════════════════════════════════════════════

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  XinMate Persona Variant Generator" -ForegroundColor Cyan
Write-Host "  10 Scenarios x 13 Personas = 130 Images" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "API: $ApiUrl"
Write-Host "Azure: $AzureStorageAccount/$ContainerName"
Write-Host ""

# Check API health
Write-Host "Checking API health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get
    Write-Host "API Status: $($health.status) | ComfyUI: $($health.comfyui)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Cannot connect to API" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting batch generation..." -ForegroundColor Yellow
Write-Host ""

$totalImages = 0
$successCount = 0
$failCount = 0
$startTime = Get-Date

foreach ($persona in $personas.GetEnumerator() | Sort-Object Key) {
    $name = $persona.Key
    $data = $persona.Value
    
    Write-Host "═══════════════════════════════════════" -ForegroundColor Magenta
    Write-Host "  PERSONA: $($name.ToUpper())" -ForegroundColor Magenta
    Write-Host "═══════════════════════════════════════" -ForegroundColor Magenta
    
    foreach ($scenario in $scenarios) {
        $totalImages++
        $scenarioName = $scenario.name
        $seed = $data.baseSeed + $scenario.seedOffset
        
        # Build full prompt: BASE + IDENTITY + SCENARIO
        $fullPrompt = "$BASE_PROMPT, $($data.identity), $($scenario.desc)"
        
        Write-Host "  [$scenarioName] " -ForegroundColor Cyan -NoNewline
        Write-Host "Generating (seed: $seed)..." -NoNewline
        
        $body = @{
            prompt = $fullPrompt
            seed = $seed
            persona_id = $name
            steps = 32
            cfg_scale = 6.0
            width = 1024
            height = 1024
        } | ConvertTo-Json
        
        try {
            $response = Invoke-RestMethod -Uri "$ApiUrl/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 300
            
            if ($response.success) {
                Write-Host " OK" -ForegroundColor Green -NoNewline
                
                $imageUrl = "$ApiUrl$($response.image_url)"
                
                # Download and upload to Azure
                try {
                    $imageData = Invoke-WebRequest -Uri $imageUrl -UseBasicParsing
                    $imageBytes = $imageData.Content
                    
                    # Blob name: persona/scenario_seed.png
                    $blobName = "$name/${scenarioName}_$seed.png"
                    
                    Write-Host " -> Azure..." -ForegroundColor Yellow -NoNewline
                    $uploaded = Upload-ToAzureBlob -ImageData $imageBytes -BlobName $blobName -StorageAccount $AzureStorageAccount -StorageKey $AzureStorageKey -Container $ContainerName
                    
                    if ($uploaded) {
                        Write-Host " Done" -ForegroundColor Green
                        $successCount++
                    } else {
                        Write-Host " Upload Failed" -ForegroundColor Red
                        $failCount++
                    }
                } catch {
                    Write-Host " Download Failed" -ForegroundColor Red
                    $failCount++
                }
            } else {
                Write-Host " FAILED: $($response.error)" -ForegroundColor Red
                $failCount++
            }
        } catch {
            Write-Host " ERROR: $($_.Exception.Message)" -ForegroundColor Red
            $failCount++
        }
        
        # Small delay between requests
        Start-Sleep -Seconds 1
    }
    
    Write-Host ""
}

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GENERATION COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total Images: $totalImages"
Write-Host "Success: $successCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host "Duration: $($duration.ToString('hh\:mm\:ss'))"
Write-Host ""
Write-Host "Azure Container: https://$AzureStorageAccount.blob.core.windows.net/$ContainerName/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Folder structure:" -ForegroundColor Yellow
Write-Host "  personas/"
Write-Host "    {persona_name}/"
Write-Host "      portrait_closeup_{seed}.png"
Write-Host "      full_body_casual_{seed}.png"
Write-Host "      outdoor_nature_{seed}.png"
Write-Host "      cafe_lifestyle_{seed}.png"
Write-Host "      formal_portrait_{seed}.png"
Write-Host "      athletic_fitness_{seed}.png"
Write-Host "      evening_elegant_{seed}.png"
Write-Host "      beach_summer_{seed}.png"
Write-Host "      home_cozy_{seed}.png"
Write-Host "      profile_artistic_{seed}.png"
