#!/usr/bin/env python3
"""
XinMate — Import Manifests into PostgreSQL
============================================
Reads manifest JSON files and inserts PersonaImage records.

Usage:
    python import_to_db.py                      # Import all manifests
    python import_to_db.py --persona scarlett    # Single persona
    python import_to_db.py --dry-run             # Preview SQL without executing

Requires:
    DATABASE_URL env var (PostgreSQL connection string)
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MANIFEST_DIR = os.getenv("MANIFEST_DIR", "/workspace/manifests")


def get_db_connection():
    """Connect to PostgreSQL using DATABASE_URL."""
    try:
        import psycopg2
    except ImportError:
        logger.error("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    return psycopg2.connect(db_url)


def get_persona_id_map(conn) -> dict:
    """Map persona names (lowercase) to their DB UUIDs."""
    cur = conn.cursor()
    cur.execute('SELECT id, LOWER(name) FROM "Persona"')
    mapping = {name: pid for pid, name in cur.fetchall()}
    cur.close()
    return mapping


def import_manifest(conn, manifest_path: Path, persona_id_map: dict, dry_run: bool = False):
    """Import a single manifest file into PersonaImage table."""
    with open(manifest_path) as f:
        manifest = json.load(f)

    persona_name = manifest["persona"]
    db_persona_id = persona_id_map.get(persona_name.lower())

    if not db_persona_id:
        logger.warning(f"Persona '{persona_name}' not found in DB, skipping")
        return 0

    images = manifest.get("images", [])
    if not images:
        logger.info(f"No images in manifest for {persona_name}")
        return 0

    cur = conn.cursor()
    inserted = 0

    for img in images:
        image_id = str(uuid.uuid4())

        sql = """
            INSERT INTO "PersonaImage" (
                id, "personaId", url, category, mood, scenario,
                tags, "isNsfw", width, height, seed, "promptUsed",
                "isActive", "viewCount", "sentCount", "createdAt"
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
        """

        values = (
            image_id,
            db_persona_id,
            img["url"],
            img["category"],     # SELFIE, PORTRAIT, FULL_BODY, CANDID, MOOD
            img.get("mood"),
            img.get("scenario"),
            img.get("tags", []),
            img.get("isNsfw", False),
            img.get("width", 1024),
            img.get("height", 1024),
            img.get("seed"),
            img.get("prompt"),
            True,                # isActive
            0,                   # viewCount
            0,                   # sentCount
            img.get("generatedAt", datetime.utcnow().isoformat()),
        )

        if dry_run:
            logger.info(f"  [DRY] INSERT {img['key']} → {img['category']}")
        else:
            cur.execute(sql, values)

        inserted += 1

    if not dry_run:
        conn.commit()

    cur.close()
    logger.info(f"  {persona_name}: {inserted} images imported")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Import manifests into PostgreSQL")
    parser.add_argument("--persona", type=str, help="Import single persona manifest")
    parser.add_argument("--manifest-dir", type=str, default=MANIFEST_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Preview without inserting")
    args = parser.parse_args()

    manifest_dir = Path(args.manifest_dir)
    if not manifest_dir.exists():
        logger.error(f"Manifest dir not found: {manifest_dir}")
        sys.exit(1)

    # Find manifest files
    if args.persona:
        files = [manifest_dir / f"{args.persona}_manifest.json"]
        if not files[0].exists():
            logger.error(f"Manifest not found: {files[0]}")
            sys.exit(1)
    else:
        files = sorted(manifest_dir.glob("*_manifest.json"))

    if not files:
        logger.error("No manifest files found")
        sys.exit(1)

    logger.info(f"Found {len(files)} manifest(s)")

    conn = get_db_connection()
    persona_id_map = get_persona_id_map(conn)
    logger.info(f"DB personas: {list(persona_id_map.keys())}")

    total = 0
    for f in files:
        logger.info(f"Processing: {f.name}")
        total += import_manifest(conn, f, persona_id_map, dry_run=args.dry_run)

    conn.close()
    logger.info(f"\nTotal imported: {total} images")


if __name__ == "__main__":
    main()
