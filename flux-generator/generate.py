#!/usr/bin/env python3
"""
XinMate — Flux Batch Image Generator
======================================
Generates 500 images per persona (13 personas = 6,500 total).

Usage:
    python generate.py                          # All personas, all categories
    python generate.py --persona scarlett       # Single persona
    python generate.py --persona scarlett --category selfie  # Single combo
    python generate.py --dry-run                # Preview prompts, no generation
    python generate.py --skip-upload            # Generate locally, skip Azure
    python generate.py --workers 2              # Parallel workers (multi-GPU)

Output:
    /workspace/generated_images/{persona}/{category}/{nnnn}.png
    /workspace/manifests/{persona}_manifest.json

Environment:
    AZURE_STORAGE_ACCOUNT  (default: sdxl)
    AZURE_STORAGE_KEY      (required for upload)
    AZURE_CONTAINER_NAME   (default: personas)
    HF_TOKEN               (if model is gated)
"""

import argparse
import io
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Prevent CUDA OOM from memory fragmentation
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch

from config import (
    BASE_MODEL,
    LORA_REPO,
    LORA_WEIGHT_NAME,
    LORA_ADAPTER_NAME,
    INFERENCE_STEPS,
    GUIDANCE_SCALE,
    TORCH_DTYPE,
    CATEGORIES,
    PERSONAS,
    OUTPUT_DIR,
    MANIFEST_DIR,
)
from prompts import build_prompt, get_seed, get_dimensions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# MODEL LOADING
# ═══════════════════════════════════════════════════════════════

def load_pipeline(device: str = "cuda"):
    """Load Flux base model + LoRA weights with memory optimization."""
    from diffusers import AutoPipelineForText2Image

    dtype = torch.bfloat16 if TORCH_DTYPE == "bfloat16" else torch.float16

    logger.info(f"Loading base model: {BASE_MODEL}")
    pipe = AutoPipelineForText2Image.from_pretrained(
        BASE_MODEL,
        torch_dtype=dtype,
    )

    # Sequential CPU offload — moves individual layers to GPU as needed
    # Slower than model_cpu_offload but fits reliably in 24GB VRAM
    pipe.enable_sequential_cpu_offload()
    logger.info("Sequential CPU offload enabled (reliable 24GB VRAM mode)")

    logger.info(f"Loading LoRA: {LORA_REPO}")
    pipe.load_lora_weights(
        LORA_REPO,
        weight_name=LORA_WEIGHT_NAME,
        adapter_name=LORA_ADAPTER_NAME,
    )

    # Enable memory optimizations
    try:
        pipe.enable_xformers_memory_efficient_attention()
        logger.info("xformers enabled")
    except Exception:
        logger.info("xformers not available, using default attention")

    logger.info("Pipeline ready")
    return pipe


# ═══════════════════════════════════════════════════════════════
# GENERATION
# ═══════════════════════════════════════════════════════════════

def generate_single(
    pipe,
    prompt: str,
    negative_prompt: str,
    seed: int,
    width: int,
    height: int,
    device: str = "cuda",
) -> bytes:
    """Generate a single image and return PNG bytes."""
    # Use CPU generator — compatible with sequential CPU offload
    generator = torch.Generator(device="cpu").manual_seed(seed)

    # FLUX does not support negative_prompt — guidance_scale controls adherence
    result = pipe(
        prompt=prompt,
        guidance_scale=GUIDANCE_SCALE,
        num_inference_steps=INFERENCE_STEPS,
        width=width,
        height=height,
        generator=generator,
    )

    image = result.images[0]

    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)

    # Free VRAM between images to prevent fragmentation
    del result, image
    torch.cuda.empty_cache()

    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# MANIFEST (resume support + DB import)
# ═══════════════════════════════════════════════════════════════

def load_manifest(persona_name: str) -> dict:
    """Load existing manifest for resume support."""
    path = Path(MANIFEST_DIR) / f"{persona_name}_manifest.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"persona": persona_name, "generated_at": None, "images": []}


def save_manifest(persona_name: str, manifest: dict):
    """Save manifest after each image (crash-safe)."""
    path = Path(MANIFEST_DIR) / f"{persona_name}_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


def get_completed_keys(manifest: dict) -> set:
    """Get set of already-generated image keys for resume."""
    return {img["key"] for img in manifest.get("images", [])}


# ═══════════════════════════════════════════════════════════════
# MAIN BATCH LOOP
# ═══════════════════════════════════════════════════════════════

def run_batch(
    persona_ids: Optional[list] = None,
    category_filter: Optional[str] = None,
    skip_upload: bool = False,
    dry_run: bool = False,
    limit_per_category: int = 0,
):
    """Run batch generation for selected personas and categories."""

    # Determine which personas to generate
    if persona_ids:
        personas = {k: v for k, v in PERSONAS.items() if k in persona_ids}
        if not personas:
            logger.error(f"No matching personas: {persona_ids}")
            sys.exit(1)
    else:
        personas = PERSONAS

    # Determine categories
    if category_filter:
        if category_filter not in CATEGORIES:
            logger.error(f"Unknown category: {category_filter}. Options: {list(CATEGORIES.keys())}")
            sys.exit(1)
        categories = {category_filter: CATEGORIES[category_filter]}
    else:
        categories = CATEGORIES

    # Count total work
    total_images = 0
    for cat in categories.values():
        effective = min(cat["count"], limit_per_category) if limit_per_category > 0 else cat["count"]
        total_images += effective * len(personas)

    logger.info(f"═══════════════════════════════════════════════")
    logger.info(f"  XinMate Flux Batch Generator")
    logger.info(f"  Personas:   {len(personas)} ({', '.join(personas.keys())})")
    logger.info(f"  Categories: {len(categories)} ({', '.join(categories.keys())})")
    logger.info(f"  Total:      {total_images} images")
    logger.info(f"  Upload:     {'Azure Blob' if not skip_upload else 'LOCAL ONLY'}")
    logger.info(f"  Dry run:    {dry_run}")
    logger.info(f"═══════════════════════════════════════════════")

    if dry_run:
        _dry_run(personas, categories)
        return

    # Load model
    pipe = load_pipeline()

    # Optional Azure upload
    uploader = None
    if not skip_upload:
        try:
            from upload import upload_image
            uploader = upload_image
            logger.info("Azure upload enabled")
        except Exception as e:
            logger.warning(f"Azure upload disabled: {e}")

    # Generate
    global_start = time.time()
    global_done = 0

    for persona_id, persona in personas.items():
        logger.info(f"\n{'='*50}")
        logger.info(f"  PERSONA: {persona.name} ({persona_id})")
        logger.info(f"{'='*50}")

        manifest = load_manifest(persona_id)
        completed = get_completed_keys(manifest)

        for cat_name, cat_cfg in categories.items():
            count = cat_cfg["count"]
            if limit_per_category > 0:
                count = min(count, limit_per_category)
            width, height = get_dimensions(cat_name)

            logger.info(f"\n  Category: {cat_name} ({count} images, {width}×{height})")

            for i in range(count):
                key = f"{persona_id}/{cat_name}/{i:04d}"

                if key in completed:
                    global_done += 1
                    continue  # Resume: skip already done

                # Build prompt
                positive, negative, meta = build_prompt(persona, cat_name, i)
                seed = get_seed(persona, cat_name, i)

                # Generate
                t0 = time.time()
                try:
                    png_bytes = generate_single(
                        pipe, positive, negative, seed, width, height
                    )
                except torch.cuda.OutOfMemoryError:
                    logger.warning(f"  OOM on {key}, clearing cache and retrying...")
                    torch.cuda.empty_cache()
                    try:
                        png_bytes = generate_single(
                            pipe, positive, negative, seed, width, height
                        )
                    except Exception as e:
                        logger.error(f"  FAILED {key} (retry): {e}")
                        continue
                except Exception as e:
                    logger.error(f"  FAILED {key}: {e}")
                    continue

                gen_time = time.time() - t0

                # Save locally
                local_path = Path(OUTPUT_DIR) / f"{key}.png"
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(png_bytes)

                # Upload to Azure
                blob_url = ""
                if uploader:
                    try:
                        blob_url = uploader(png_bytes, persona.name, cat_name, i)
                    except Exception as e:
                        logger.warning(f"  Upload failed {key}: {e}")
                        blob_url = ""

                # Update manifest
                manifest["images"].append({
                    "key": key,
                    "url": blob_url or str(local_path),
                    "category": meta["category"],
                    "mood": meta["mood"],
                    "scenario": meta["scenario"],
                    "tags": meta["tags"],
                    "isNsfw": meta["isNsfw"],
                    "seed": seed,
                    "prompt": positive,
                    "width": width,
                    "height": height,
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                })
                save_manifest(persona_id, manifest)

                global_done += 1
                remaining = total_images - global_done
                elapsed = time.time() - global_start
                avg_per_img = elapsed / global_done if global_done > 0 else 0
                eta_sec = remaining * avg_per_img

                logger.info(
                    f"  [{global_done}/{total_images}] {key} "
                    f"seed={seed} {gen_time:.1f}s "
                    f"ETA: {_fmt_time(eta_sec)}"
                )

    elapsed_total = time.time() - global_start
    logger.info(f"\n{'='*50}")
    logger.info(f"  COMPLETE: {global_done}/{total_images} images")
    logger.info(f"  Time:     {_fmt_time(elapsed_total)}")
    logger.info(f"  Avg:      {elapsed_total/max(global_done,1):.1f}s per image")
    logger.info(f"{'='*50}")


def _dry_run(personas, categories):
    """Preview prompts without generating."""
    for persona_id, persona in personas.items():
        for cat_name, cat_cfg in categories.items():
            positive, negative, meta = build_prompt(persona, cat_name, 0)
            seed = get_seed(persona, cat_name, 0)
            w, h = get_dimensions(cat_name)
            print(f"\n{'─'*60}")
            print(f"Persona:  {persona.name} | Category: {cat_name}")
            print(f"Size:     {w}×{h} | Seed: {seed}")
            print(f"Prompt:   {positive[:200]}...")
            print(f"Negative: {negative[:120]}...")
            print(f"Meta:     {meta}")


def _fmt_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="XinMate Flux Batch Image Generator")
    parser.add_argument("--persona", type=str, help="Generate for single persona (e.g., ananya)")
    parser.add_argument("--category", type=str, help="Generate single category (e.g., selfie)")
    parser.add_argument("--limit", type=int, default=0, help="Max images per category (0 = all). Use --limit 5 for testing")
    parser.add_argument("--skip-upload", action="store_true", help="Skip Azure upload, save locally only")
    parser.add_argument("--dry-run", action="store_true", help="Preview prompts without generating")
    parser.add_argument("--list-personas", action="store_true", help="List all persona IDs")

    args = parser.parse_args()

    if args.list_personas:
        for pid, p in PERSONAS.items():
            print(f"  {pid:15s}  {p.name:12s}  {p.gender:6s}  age={p.age}")
        return

    persona_ids = [args.persona] if args.persona else None

    run_batch(
        persona_ids=persona_ids,
        category_filter=args.category,
        skip_upload=args.skip_upload,
        dry_run=args.dry_run,
        limit_per_category=args.limit,
    )


if __name__ == "__main__":
    main()
