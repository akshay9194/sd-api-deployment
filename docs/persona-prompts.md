# Persona Image Generation Prompts

Quick reference for generating images via API calls.

## Base Prompts by Persona

### Female Personas

| Persona | Base Prompt |
|---------|-------------|
| **Scarlett** | `beautiful woman, 25 years old, athletic fit body, long wavy red hair, striking green eyes, full lips, high cheekbones, beauty mark on cheek, confident expression, fair skin` |
| **Emma** | `beautiful asian woman, 22 years old, petite body, long straight black hair, cute round face, big brown eyes, dimples, soft features, adorable smile, fair skin, youthful` |
| **Victoria** | `beautiful woman, 32 years old, tall elegant body, black hair in sleek bob, piercing blue eyes, sharp jawline, high cheekbones, commanding presence, sophisticated, powerful CEO aesthetic, fair skin, intense gaze` |
| **Lily** | `beautiful woman, 24 years old, natural beauty, wavy brown hair, warm hazel eyes, freckles, dimples, warm genuine smile, girl next door, medium skin tone, approachable` |
| **Isabella** | `beautiful latina woman, 26 years old, curvy dancer body, long curly dark brown hair, warm brown eyes, full lips, tan skin, passionate expression, Colombian beauty, sensual pose` |
| **Maya** | `beautiful african american woman, 24 years old, curvy body, long black braided hair, warm brown eyes, bright smile, trendy fashion, friendly expression, dark skin` |
| **Kira** | `beautiful succubus woman, supernatural beauty, curvy body, very long black wavy hair, glowing purple eyes, small demon horns, demon tail, pale skin, seductive expression, dark fantasy aesthetic` |

### Male Personas

| Persona | Base Prompt |
|---------|-------------|
| **Marcus** | `handsome man, 28 years old, athletic muscular body, short black hair with fade, warm brown eyes, strong jawline, tan skin, protective confident expression, firefighter physique, broad shoulders` |
| **Ryan** | `handsome man, 27 years old, lean athletic body, messy dark brown hair, intense blue eyes, stubble, tattoos on arms, bad boy aesthetic, leather jacket, smirk, dangerous charm` |
| **Alexander** | `handsome man, 31 years old, tall slim build, styled brown hair, warm green eyes, chiseled features, distinguished gentleman aesthetic, tailored suit, warm sophisticated smile, fair skin` |
| **Ethan** | `handsome man, 25 years old, average build, messy dirty blonde hair, warm brown eyes, boyish charm, friendly warm smile, casual hoodie style, approachable, light skin` |
| **Damien** | `handsome man, 30 years old, tall athletic build, short black hair slicked back, intense grey eyes, sharp jawline, CEO aesthetic, expensive suit, commanding presence, intimidating but attractive, fair skin` |
| **Lucian** | `handsome vampire man, ageless ethereal beauty, tall slim build, long silver hair, red eyes, pale skin, sharp features, fangs, gothic elegant clothing, dark romantic aesthetic, dangerous allure` |

## Quick API Test

```bash
# Test with Scarlett
curl -X POST "https://YOUR-POD-ID-8000.proxy.runpod.net/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "beautiful woman, 25 years old, athletic fit body, long wavy red hair, striking green eyes, full lips, high cheekbones, beauty mark on cheek, confident expression, fair skin, wearing casual dress, selfie angle, morning sunlight",
    "seed": 100001,
    "persona_id": "scarlett",
    "user_id": "test"
  }'
```

## Seed Ranges (For Face Consistency)

| Persona | Seed Range |
|---------|------------|
| Scarlett | 100000-100999 |
| Emma | 200000-200999 |
| Victoria | 300000-300999 |
| Lily | 400000-400999 |
| Isabella | 500000-500999 |
| Maya | 600000-600999 |
| Kira | 700000-700999 |
| Marcus | 800000-800999 |
| Ryan | 900000-900999 |
| Alexander | 1000000-1000999 |
| Ethan | 1100000-1100999 |
| Damien | 1200000-1200999 |
| Lucian | 1300000-1300999 |

## Scenario Modifiers

Add these to the base prompt for different scenarios:

```
# Morning selfie
, selfie angle, morning sunlight, cozy bedroom, just woke up

# Romantic evening
, elegant evening wear, romantic dinner setting, candlelight

# Casual at home  
, comfortable clothes, at home, relaxed pose, cozy

# Flirty
, flirty expression, playful pose, suggestive but tasteful

# Beach
, beach setting, swimwear, sunny day, summer vibes

# Workout
, gym clothes, fitness setting, active pose, athletic
```

## Running the Batch Generator

```bash
# Set your RunPod API URL
export SD_API_URL="https://YOUR-POD-ID-8000.proxy.runpod.net"

# Generate 10 images per persona (testing)
export IMAGES_PER_PERSONA=10
python scripts/generate-persona-images.py

# Full generation (100 per persona = 1,400 total)
export IMAGES_PER_PERSONA=100
python scripts/generate-persona-images.py
```

## Estimated Time

| Images/Persona | Total Images | Time @ 6s/img |
|----------------|--------------|---------------|
| 10 | 140 | ~14 min |
| 50 | 700 | ~70 min |
| 100 | 1,400 | ~2.3 hours |

---

## Full Body Image Generation

The standard generator creates **1024×1024** square images (great for selfies/portraits).  
For full body shots, use the dedicated **full body generator** with a **832×1216** tall aspect ratio.

### Key Differences from Portrait Generator

| Setting | Portrait | Full Body |
|---------|----------|-----------|
| Resolution | 1024×1024 | 832×1216 |
| Framing | Selfie / close-up | Head to toe |
| Prompt extras | Expression-focused | Pose + outfit + shoes |
| Seed offset | `seed_base + 0..999` | `seed_base + 5000..5999` |

### Running the Full Body Generator

```bash
# Set your RunPod API URL
export SD_API_URL="https://YOUR-POD-ID-8000.proxy.runpod.net"

# Generate 10 full body images per persona (testing)
export IMAGES_PER_PERSONA=10
python scripts/generate-fullbody-images.py

# Single persona only
export PERSONA=scarlett
python scripts/generate-fullbody-images.py

# Full run (50 per persona = 650 total)
export IMAGES_PER_PERSONA=50
python scripts/generate-fullbody-images.py
```

### Full Body Scenarios

| Scenario | Description |
|----------|-------------|
| standing_casual | Relaxed standing, urban street |
| fashion_pose | Editorial model pose, studio |
| walking | Walking toward camera, city |
| leaning_wall | Leaning on wall, cool pose |
| mirror_selfie | Full body mirror selfie |
| doorway | Standing in doorway |
| outdoor_nature | Park/garden, golden hour |
| beach_full | Standing on beach |
| gym_full | Athletic pose in gym |
| date_arrival | Dressed up at restaurant |
| staircase | Dramatic stair pose |
| balcony | City skyline background |
| bedroom_standing | Morning light, intimate |
| red_carpet | Glamorous event |
| cafe_standing | Outside cafe, casual |

### Full Body Prompt Tips

When crafting custom full body prompts, always include:
```
full body shot, head to toe, full length photo, showing feet, standing pose, wide framing
```

And add to negative prompt:
```
cropped, close up, portrait crop, face only, headshot, cut off legs, cut off feet
```
