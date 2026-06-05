# XinMate — Flux Batch Image Generator

Production-grade batch image generator for XinMate persona images. Runs on RunPod GPU, generates 500 images per persona (10 personas = 5,000 total), uploads to Azure Blob Storage, and saves metadata for PostgreSQL import. Designed for Indian market.

## Architecture

```
RunPod GPU Pod (A100 / 4090)
        │
        ▼
  Flux.1-dev + LoRA
        │
        ▼
  Prompt Generator
  (10 personas × 5 categories × 100 each)
        │
        ▼
  PNG Image (1024×1024 or 832×1216)
        │
   ┌────┴────┐
   ▼         ▼
Local      Azure Blob
Save       Upload
   │         │
   ▼         ▼
Manifest   personas/{name}/{category}/{nnnn}.png
JSON
   │
   ▼
PostgreSQL Import
(PersonaImage table)
```

## Quick Start (RunPod)

### 1. Create Pod

| Setting | Value |
|---------|-------|
| **GPU** | A100 40GB (recommended) or RTX 4090 |
| **Template** | RunPod PyTorch 2.x |
| **Volume** | 100GB+ Network Volume at `/workspace` |
| **Container Disk** | 20GB |

### 2. Set Environment Variables

In RunPod Pod settings → Environment Variables:

```
AZURE_STORAGE_ACCOUNT=sdxl
AZURE_STORAGE_KEY=<your-azure-storage-key>
AZURE_CONTAINER_NAME=personas
HF_TOKEN=<your-huggingface-token>
```

### 3. Run

```bash
# SSH into pod, then:
cd /workspace
git clone https://github.com/akshay9194/sd-api-deployment.git
cd sd-api-deployment/flux-generator
pip install -r requirements.txt

# Generate all personas
python generate.py

# Or single persona
python generate.py --persona scarlett

# Or single category
python generate.py --persona scarlett --category selfie

# Preview prompts without generating
python generate.py --dry-run

# Skip Azure upload (local only)
python generate.py --skip-upload
```

## Output Structure

### Local Files
```
/workspace/generated_images/
├── scarlett/
│   ├── selfie/
│   │   ├── 0000.png
│   │   ├── 0001.png
│   │   └── ... (100 images)
│   ├── portrait/
│   ├── full_body/
│   ├── lifestyle/
│   └── fashion/
├── emma/
├── victoria/
└── ... (13 personas)
```

### Azure Blob Storage
```
https://sdxl.blob.core.windows.net/personas/
├── scarlett/selfie/0000.png
├── scarlett/portrait/0000.png
├── emma/selfie/0000.png
└── ...
```

### Manifest JSON
```
/workspace/manifests/scarlett_manifest.json
```

```json
{
  "persona": "scarlett",
  "generated_at": "2026-06-06T...",
  "images": [
    {
      "key": "scarlett/selfie/0000",
      "url": "https://sdxl.blob.core.windows.net/personas/scarlett/selfie/0000.png",
      "category": "SELFIE",
      "mood": "smiling warmly",
      "scenario": "mirror selfie in bedroom, casual",
      "tags": ["athletic", "confident", "fitness", "selfie", "smiling"],
      "isNsfw": false,
      "seed": 100000,
      "prompt": "beautiful woman, 25 years old, ...",
      "width": 1024,
      "height": 1024,
      "generatedAt": "2026-06-06T..."
    }
  ]
}
```

## Database Import

After generation, import manifests into XinMate's PostgreSQL:

```bash
DATABASE_URL='postgresql://xinmate:password@host:5432/xinmate' \
python import_to_db.py

# Single persona
python import_to_db.py --persona scarlett

# Preview without inserting
python import_to_db.py --dry-run
```

This populates the `PersonaImage` table which the app's `PersonaImageService` uses to serve images to users.

## Categories

| Category | Count | Dimensions | DB Category |
|----------|-------|------------|-------------|
| Selfie | 100 | 1024×1024 | SELFIE |
| Portrait | 100 | 1024×1024 | PORTRAIT |
| Full Body | 100 | 832×1216 | FULL_BODY |
| Lifestyle | 100 | 1024×1024 | CANDID |
| Fashion | 100 | 1024×1024 | MOOD |

## Personas (10 — Indian Market)

### Female (6)
| ID | Name | Age | Archetype | Seed Range |
|----|------|-----|-----------|------------|
| ananya | Ananya | 22 | Desi girl next door — college crush | 100000+ |
| riya | Riya | 26 | Bold Mumbai city girl — glamorous | 200000+ |
| meera | Meera | 24 | South Indian beauty — graceful, traditional | 300000+ |
| zara | Zara | 21 | Edgy Gen-Z influencer — Instagram aesthetic | 400000+ |
| priya | Priya | 29 | Corporate queen — sophisticated, premium | 500000+ |
| aisha | Aisha | 25 | Exotic mixed beauty — mysterious, alluring | 600000+ |

### Male (4)
| ID | Name | Age | Archetype | Seed Range |
|----|------|-----|-----------|------------|
| arjun | Arjun | 28 | Protective alpha — strong, reliable | 700000+ |
| kabir | Kabir | 26 | Brooding artist — soulful musician, intense | 800000+ |
| vivaan | Vivaan | 32 | Rich gentleman — old money, sophisticated | 900000+ |
| rehan | Rehan | 24 | Boy next door — sweet, funny, relatable | 1000000+ |

## Resume Support

The generator saves a manifest after every image. If interrupted (spot instance preemption, crash, etc.), just re-run the same command — it skips already-generated images automatically.

## Time Estimates

| GPU | Speed | 500 images | 5,000 images |
|-----|-------|------------|--------------|
| A100 40GB | ~8s/img | ~1.1 hours | ~11 hours |
| RTX 4090 | ~15s/img | ~2.1 hours | ~21 hours |
| 2× A100 | ~8s/img | ~0.6 hours | ~5.5 hours |

## Customization

### Add new categories

Edit `config.py` → `CATEGORIES` dict. Add matching scenarios in `CATEGORY_SCENARIOS`.

### Change model

Edit `config.py`:
```python
BASE_MODEL = "black-forest-labs/FLUX.1-dev"
LORA_REPO = "your/lora-repo"
LORA_WEIGHT_NAME = "lora.safetensors"
```

### Adjust quality

Edit `config.py`:
```python
INFERENCE_STEPS = 28    # More = better quality, slower
GUIDANCE_SCALE = 7.0    # Higher = more prompt adherence
```
