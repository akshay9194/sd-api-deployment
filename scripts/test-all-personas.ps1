# Production Persona Generator - BASE + DELTA Prompt System
# Usage: .\test-all-personas.ps1 -ApiUrl "https://YOUR-POD-8000.proxy.runpod.net"
#
# Prompt Structure:
# - BASE_PROMPT: Shared photorealistic foundation
# - PERSONA_DELTA: Individual characteristics only
# - GLOBAL_NEGATIVE: Applied server-side automatically

param(
    [string]$ApiUrl = "https://1an705ff1fij4z-8000.proxy.runpod.net"
)

# ═══════════════════════════════════════════════════════════════
# BASE PROMPT (Shared Across All Personas)
# ═══════════════════════════════════════════════════════════════
$BASE_PROMPT = @"
photorealistic portrait photograph of a clearly adult person, 25+ years old,
fully mature facial structure, natural human proportions,
subtle skin texture with visible pores,
slight facial asymmetry, realistic eye moisture and reflections,
shot on professional camera, shallow depth of field,
soft natural lighting with realistic shadows,
indoor or environmental setting,
unposed candid moment, documentary photography style,
RAW photo look, ultra-high detail
"@ -replace "`r`n", " " -replace "`n", " "

# ═══════════════════════════════════════════════════════════════
# PERSONA DELTAS (Individual Characteristics Only)
# ═══════════════════════════════════════════════════════════════
$personas = @{
    # ========== FEMALE PERSONAS ==========
    "scarlett" = @{
        delta = "female, long naturally wavy ginger red hair, green eyes, light fair skin with faint freckles, soft golden hour window light, calm confident expression"
        seed = 100001
    }
    "emma" = @{
        delta = "female, East Asian Korean woman, long straight black hair, dark brown eyes, soft oval face shape, pale porcelain skin, neutral daylight window lighting, gentle relaxed expression"
        seed = 200001
    }
    "victoria" = @{
        delta = "female, short black bob haircut, piercing ice blue eyes, sharp defined jawline, high cheekbones, pale fair skin, professional studio lighting, intense confident gaze, elegant sophisticated presence"
        seed = 300001
    }
    "lily" = @{
        delta = "female, shoulder length wavy chestnut brown hair, warm hazel green eyes, cute freckles across nose, dimples, medium olive skin tone, warm natural window light, genuine warm smile, approachable friendly"
        seed = 400001
    }
    "isabella" = @{
        delta = "female, Colombian Latina woman, very long curly dark brown hair, expressive warm brown eyes, full lips, golden caramel tan skin, warm sunset lighting, passionate confident expression"
        seed = 500001
    }
    "maya" = @{
        delta = "female, African American Black woman, long black box braids hairstyle, warm dark brown eyes, bright genuine smile, rich dark brown ebony skin, natural daylight, vibrant confident energy"
        seed = 600001
    }
    "kira" = @{
        delta = "female, very long wavy black hair with subtle purple highlights, pale skin, dark eye makeup, moody artistic lighting, mysterious contemplative expression, alternative gothic aesthetic"
        seed = 700001
    }
    
    # ========== MALE PERSONAS ==========
    "marcus" = @{
        delta = "male, short black hair with clean fade haircut, warm brown eyes, strong square jawline, light stubble beard, mixed race tan brown skin, soft studio lighting with subtle contrast, calm confident masculine presence"
        seed = 800001
    }
    "ryan" = @{
        delta = "male, messy medium dark brown hair, intense piercing blue eyes, sharp facial features, light stubble, visible arm tattoos, light skin, moody dramatic lighting, edgy confident expression"
        seed = 900001
    }
    "alexander" = @{
        delta = "male, neatly styled medium brown hair, warm green eyes, chiseled cheekbones, clean shaven, fair skin, elegant warm lighting, sophisticated charming smile, refined gentleman presence"
        seed = 1000001
    }
    "ethan" = @{
        delta = "male, messy dirty blonde hair, warm friendly brown eyes, boyish charming face, light stubble, light skin with slight tan, soft natural lighting, genuine warm smile, approachable friendly presence"
        seed = 1100001
    }
    "damien" = @{
        delta = "male, short black hair slicked back, intense piercing grey eyes, strong sharp jawline, clean shaven, fair pale skin, dramatic high contrast lighting, commanding confident expression, powerful presence"
        seed = 1200001
    }
    "lucian" = @{
        delta = "male, long flowing platinum silver white hair, striking pale grey eyes, sharp aristocratic features, very pale white skin, moody candlelit atmosphere, dark romantic mysterious expression, elegant gothic aesthetic"
        seed = 1300001
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  XinMate Persona Generator (v2.0)" -ForegroundColor Cyan
Write-Host "  BASE + DELTA Prompt System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "API: $ApiUrl"
Write-Host "Personas: $($personas.Count)"
Write-Host "Settings: steps=32, cfg=6.0, dpmpp_2m_karras"
Write-Host ""

# Check health first
Write-Host "Checking API health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get
    Write-Host "API Status: $($health.status) | ComfyUI: $($health.comfyui)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Cannot connect to API" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "BASE PROMPT (shared):" -ForegroundColor DarkGray
Write-Host $BASE_PROMPT.Substring(0, 80) + "..." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Starting generation..." -ForegroundColor Yellow
Write-Host ""

$results = @()

foreach ($persona in $personas.GetEnumerator()) {
    $name = $persona.Key
    $data = $persona.Value
    
    # Combine BASE + DELTA
    $fullPrompt = "$BASE_PROMPT, $($data.delta)"
    
    Write-Host "[$name] " -ForegroundColor Cyan -NoNewline
    Write-Host "Generating..." -NoNewline
    
    $body = @{
        prompt = $fullPrompt
        seed = $data.seed
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
            Write-Host " - $($response.image_url)" -ForegroundColor DarkGray
            $results += @{
                persona = $name
                success = $true
                url = "$ApiUrl$($response.image_url)"
                seed = $response.seed_used
            }
        } else {
            Write-Host " FAILED - $($response.error)" -ForegroundColor Red
            $results += @{ persona = $name; success = $false; error = $response.error }
        }
    } catch {
        Write-Host " ERROR - $($_.Exception.Message)" -ForegroundColor Red
        $results += @{ persona = $name; success = $false; error = $_.Exception.Message }
    }
    
    # Small delay between requests
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RESULTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$successCount = ($results | Where-Object { $_.success }).Count
Write-Host "Success: $successCount / $($results.Count)" -ForegroundColor $(if ($successCount -eq $results.Count) { "Green" } else { "Yellow" })
Write-Host ""

Write-Host "Image URLs:" -ForegroundColor Yellow
foreach ($r in $results | Where-Object { $_.success }) {
    Write-Host "  $($r.persona): $($r.url)"
}

Write-Host ""
Write-Host "Done! Open the URLs above in your browser to view images." -ForegroundColor Green
