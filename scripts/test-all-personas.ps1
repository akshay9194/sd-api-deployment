param(
    [string]$ApiUrl = "https://wbnoh3d4yojy7b-8000.proxy.runpod.net",
    [int]$ImagesPerCategory = 10,
    [string]$ContainerName = "personas"
)

# ═══════════════════════════════════════════════════════════════
# AZURE BLOB STORAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════
$AzureStorageAccount = $env:AZURE_STORAGE_ACCOUNT ?? "sdxl"
$AzureStorageKey = $env:AZURE_STORAGE_KEY
if (-not $AzureStorageKey) { Write-Error "Set AZURE_STORAGE_KEY env var"; exit 1 }

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

    $headers = @{
        "x-ms-blob-type" = "BlockBlob"
        "x-ms-date" = $date
        "x-ms-version" = $version
        "Authorization" = "SharedKey ${StorageAccount}:$signature"
        "Content-Type" = $contentType
    }

    $uri = "https://$StorageAccount.blob.core.windows.net/$Container/$BlobName"
    try {
        Invoke-WebRequest -Uri $uri -Method Put -Headers $headers -Body $ImageData -UseBasicParsing | Out-Null
        return $true
    } catch {
        return $false
    }
}

# ═══════════════════════════════════════════════════════════════
# GLOBAL NEGATIVE PROMPT
# ═══════════════════════════════════════════════════════════════
$GLOBAL_NEGATIVE = @"
celebrity, famous person, influencer, model,
real person, known face,
teen, teenage, young-looking, child, minor,
anime, illustration, painting, cgi, 3d render,
beauty filter, plastic skin,
distorted anatomy, extra limbs, extra fingers
"@ -replace "`r`n"," " -replace "`n"," "

# ═══════════════════════════════════════════════════════════════
# ROLEPLAY SCENARIOS (Fantasy, Historical, Themed)
# ═══════════════════════════════════════════════════════════════
$SCENARIOS = @{
    "fantasy_princess" = "wearing elegant medieval princess gown, castle throne room setting, regal graceful pose, cinematic fantasy lighting"
    "nurse_medical" = "wearing professional nurse scrubs uniform, modern hospital setting, caring compassionate expression"
    "teacher_classroom" = "wearing smart professional blouse and pencil skirt, classroom setting, intelligent confident pose"
    "maid_french" = "wearing classic French maid costume, elegant mansion interior, playful flirty pose"
    "secretary_office" = "wearing fitted business suit with glasses, modern office setting, professional seductive pose"
    "warrior_fantasy" = "wearing fantasy leather armor, medieval battlefield setting, fierce warrior stance"
    "vampire_gothic" = "wearing elegant Victorian gothic dress, dark castle setting, mysterious seductive expression"
    "cheerleader_sports" = "wearing cheerleader uniform, stadium setting, energetic spirited pose"
    "pilot_aviation" = "wearing pilot uniform with cap, airplane cockpit setting, confident professional pose"
    "dancer_burlesque" = "wearing glamorous showgirl costume with feathers, vintage cabaret stage, elegant dance pose"
}

# Male roleplay scenarios
$MALE_SCENARIOS = @{
    "knight_medieval" = "wearing full knight armor, medieval castle setting, noble heroic stance"
    "doctor_medical" = "wearing doctor white coat with stethoscope, modern hospital setting, caring professional expression"
    "professor_academic" = "wearing tweed blazer with glasses, university library setting, intellectual confident pose"
    "butler_formal" = "wearing formal butler tailcoat uniform, elegant mansion interior, dignified refined pose"
    "ceo_executive" = "wearing expensive three-piece suit, executive boardroom setting, powerful commanding presence"
    "warrior_viking" = "wearing Viking warrior armor with fur cape, Nordic battlefield setting, fierce battle stance"
    "vampire_lord" = "wearing elegant Victorian gothic coat, dark castle throne room, mysterious aristocratic presence"
    "firefighter_hero" = "wearing firefighter gear with helmet, fire station setting, heroic protective stance"
    "pilot_captain" = "wearing airline captain uniform with cap, airplane cockpit setting, confident authoritative pose"
    "rockstar_musician" = "wearing leather jacket with band shirt, concert stage setting, charismatic performer pose"
}

# ═══════════════════════════════════════════════════════════════
# ALL 13 PERSONAS WITH IDENTITY FEATURES
# ═══════════════════════════════════════════════════════════════
$personas = @{
    # FEMALE PERSONAS
    "scarlett" = @{
        baseSeed = 100000
        identity = "female, long naturally wavy ginger red hair, green eyes, light fair skin with faint freckles, fit toned body"
    }
    "emma" = @{
        baseSeed = 200000
        identity = "female, East Asian Korean woman, long straight black hair, dark brown eyes, pale porcelain skin, petite slim body"
    }
    "victoria" = @{
        baseSeed = 300000
        identity = "female, short black bob haircut, piercing ice blue eyes, pale fair skin, tall elegant figure"
    }
    "lily" = @{
        baseSeed = 400000
        identity = "female, shoulder length wavy chestnut brown hair, warm hazel green eyes, freckles, olive skin, natural body"
    }
    "isabella" = @{
        baseSeed = 500000
        identity = "female, Colombian Latina woman, very long curly dark brown hair, warm brown eyes, golden caramel tan skin, curvy hourglass figure"
    }
    "maya" = @{
        baseSeed = 600000
        identity = "female, African American Black woman, long black box braids, warm dark brown eyes, rich dark brown ebony skin, curvy voluptuous body"
    }
    "kira" = @{
        baseSeed = 700000
        identity = "female, very long wavy black hair with purple highlights, pale skin, dark eye makeup, curvy alternative gothic style"
    }
    # MALE PERSONAS
    "marcus" = @{
        baseSeed = 800000
        identity = "male, short black hair with clean fade, warm brown eyes, strong square jawline, light stubble, mixed race tan brown skin, athletic muscular build"
    }
    "ryan" = @{
        baseSeed = 900000
        identity = "male, messy medium dark brown hair, intense piercing blue eyes, sharp features, light stubble, arm tattoos, light skin, lean athletic body"
    }
    "alexander" = @{
        baseSeed = 1000000
        identity = "male, neatly styled medium brown hair, warm green eyes, chiseled cheekbones, clean shaven, fair skin, tall refined build"
    }
    "ethan" = @{
        baseSeed = 1100000
        identity = "male, messy dirty blonde hair, warm friendly brown eyes, boyish charming face, light stubble, light skin with slight tan, average athletic build"
    }
    "damien" = @{
        baseSeed = 1200000
        identity = "male, short black hair slicked back, intense piercing grey eyes, strong sharp jawline, clean shaven, fair pale skin, tall muscular build"
    }
    "lucian" = @{
        baseSeed = 1300000
        identity = "male, long flowing platinum silver white hair, striking pale grey eyes, sharp aristocratic features, very pale white skin, tall slim elegant build"
    }
}

# Male-specific scenarios
$MALE_SCENARIOS = @{
    "beach_swim" = "wearing swim trunks, sunlit beach environment, golden hour light, confident masculine pose"
    "gym_workout" = "wearing tank top and shorts, gym environment, muscular fitness pose"
    "casual_street" = "wearing fitted t-shirt and jeans, urban street setting, confident walking pose"
    "formal_suit" = "wearing tailored suit jacket open collar, evening setting, sophisticated pose"
    "athletic_run" = "wearing running outfit, outdoor park trail, athletic jogging pose"
    "pool_summer" = "wearing swim shorts, luxury poolside setting, relaxed summer vibes"
    "home_casual" = "wearing casual henley shirt, cozy home interior, relaxed intimate setting"
    "outdoor_hike" = "wearing outdoor athletic wear, mountain trail setting, adventurous pose"
    "evening_smart" = "wearing smart casual blazer, city night lights, refined masculine presence"
    "fitness_boxing" = "wearing boxing shorts, gym boxing ring, powerful athletic stance"
}

# ═══════════════════════════════════════════════════════════════
# BASE PROMPT
# ═══════════════════════════════════════════════════════════════
$BASE_PROMPT = @"
photorealistic lifestyle photograph of a clearly adult person, 25+ years old,
fully mature body, natural human proportions,
subtle skin texture with visible pores,
shot on professional camera, shallow depth of field,
soft natural lighting, RAW photo look, ultra-high detail
"@ -replace "`r`n"," " -replace "`n"," "

# ═══════════════════════════════════════════════════════════════
# START GENERATION
# ═══════════════════════════════════════════════════════════════
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " XinMate Roleplay Image Generator" -ForegroundColor Cyan
Write-Host " 13 Personas × 10 Scenarios = 130 Images" -ForegroundColor Cyan
Write-Host " Container: $ContainerName" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$totalCount = 0
$successCount = 0

foreach ($persona in $personas.GetEnumerator() | Sort-Object Key) {
    $name = $persona.Key
    $baseSeed = $persona.Value.baseSeed
    $identity = $persona.Value.identity
    
    # Determine if male or female for scenario selection
    $isMale = $identity -match "^male"
    $scenarioSet = if ($isMale) { $MALE_SCENARIOS } else { $SCENARIOS }

    Write-Host "═══════════════════════════════════════" -ForegroundColor Magenta
    Write-Host "  PERSONA: $($name.ToUpper())" -ForegroundColor Magenta
    Write-Host "═══════════════════════════════════════" -ForegroundColor Magenta

    $scenarioIndex = 0
    foreach ($scenario in $scenarioSet.GetEnumerator()) {
        $scenarioName = $scenario.Key
        $scenarioDesc = $scenario.Value
        $seed = $baseSeed + ($scenarioIndex * 1000) + (Get-Random -Minimum 1 -Maximum 999)
        $scenarioIndex++
        
        $prompt = "$BASE_PROMPT, $identity, $scenarioDesc"
        
        Write-Host "  [$scenarioName] " -ForegroundColor Cyan -NoNewline

        $body = @{
            prompt = $prompt
            negative_prompt = $GLOBAL_NEGATIVE
            seed = $seed
            persona_id = "$name-$scenarioName"
            steps = 32
            cfg_scale = 6.0
            width = 1024
            height = 1280
        } | ConvertTo-Json

        try {
            $response = Invoke-RestMethod `
                -Uri "$ApiUrl/generate" `
                -Method Post `
                -Body $body `
                -ContentType "application/json" `
                -TimeoutSec 300

            $totalCount++

            if ($response.success) {
                $imageUrl = "$ApiUrl$($response.image_url)"
                try {
                    $img = Invoke-WebRequest -Uri $imageUrl -UseBasicParsing
                    $blobName = "$name/${scenarioName}_$seed.png"
                    $uploaded = Upload-ToAzureBlob `
                        -ImageData $img.Content `
                        -BlobName $blobName `
                        -StorageAccount $AzureStorageAccount `
                        -StorageKey $AzureStorageKey `
                        -Container $ContainerName

                    if ($uploaded) {
                        Write-Host "OK → Azure OK" -ForegroundColor Green
                        $successCount++
                    } else {
                        Write-Host "OK → Azure FAILED" -ForegroundColor Yellow
                    }
                } catch {
                    Write-Host "OK → Download FAILED" -ForegroundColor Yellow
                }
            } else {
                Write-Host "FAILED" -ForegroundColor Red
            }
        } catch {
            $totalCount++
            Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
        }

        Start-Sleep -Seconds 1
    }
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " GENERATION COMPLETE" -ForegroundColor Cyan
Write-Host " Total: $totalCount | Success: $successCount" -ForegroundColor Cyan
Write-Host " Azure: https://$AzureStorageAccount.blob.core.windows.net/$ContainerName/" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
