"""
XinMate — Live Generation Monitor Dashboard
=============================================
Lightweight FastAPI server that shows real-time generation progress.
Reads manifest files and shows stats, latest images, ETA.

Runs alongside generate.py on the same pod.
Access at: https://YOUR-POD-ID-8080.proxy.runpod.net

Usage:
    python monitor.py &          # Start in background
    python generate.py           # Run generator normally
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="XinMate Image Generator Monitor")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/workspace/generated_images"))
MANIFEST_DIR = Path(os.getenv("MANIFEST_DIR", "/workspace/manifests"))

# ── Config (must match generate.py) ─────────────────────────
PERSONAS = {
    "ananya": {"name": "Ananya", "gender": "F", "target": 500},
    "riya": {"name": "Riya", "gender": "F", "target": 500},
    "meera": {"name": "Meera", "gender": "F", "target": 500},
    "zara": {"name": "Zara", "gender": "F", "target": 500},
    "priya": {"name": "Priya", "gender": "F", "target": 500},
    "aisha": {"name": "Aisha", "gender": "F", "target": 500},
    "arjun": {"name": "Arjun", "gender": "M", "target": 500},
    "kabir": {"name": "Kabir", "gender": "M", "target": 500},
    "vivaan": {"name": "Vivaan", "gender": "M", "target": 500},
    "rehan": {"name": "Rehan", "gender": "M", "target": 500},
}
TOTAL_TARGET = sum(p["target"] for p in PERSONAS.values())
CATEGORIES = ["selfie", "portrait", "full_body", "lifestyle", "fashion"]


def read_manifests() -> Dict:
    """Read all manifest files and compute stats."""
    stats = {}
    total_done = 0
    latest_images = []

    for pid, pinfo in PERSONAS.items():
        manifest_path = MANIFEST_DIR / f"{pid}_manifest.json"
        count = 0
        cat_counts = {c: 0 for c in CATEGORIES}
        last_time = None

        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                images = manifest.get("images", [])
                count = len(images)

                for img in images:
                    key = img.get("key", "")
                    for c in CATEGORIES:
                        if f"/{c}/" in key:
                            cat_counts[c] += 1
                            break

                # Last 3 images for this persona
                for img in images[-3:]:
                    latest_images.append({
                        "persona": pinfo["name"],
                        "key": img.get("key", ""),
                        "category": img.get("category", ""),
                        "mood": img.get("mood", ""),
                        "time": img.get("generatedAt", ""),
                    })

                if images:
                    last_time = images[-1].get("generatedAt", "")
            except Exception:
                pass

        stats[pid] = {
            "name": pinfo["name"],
            "gender": pinfo["gender"],
            "done": count,
            "target": pinfo["target"],
            "pct": round(count / pinfo["target"] * 100, 1) if pinfo["target"] > 0 else 0,
            "categories": cat_counts,
            "lastTime": last_time,
        }
        total_done += count

    # Sort latest images by time (newest first)
    latest_images.sort(key=lambda x: x.get("time", ""), reverse=True)

    return {
        "totalDone": total_done,
        "totalTarget": TOTAL_TARGET,
        "totalPct": round(total_done / TOTAL_TARGET * 100, 1) if TOTAL_TARGET > 0 else 0,
        "personas": stats,
        "latestImages": latest_images[:12],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── API Endpoints ────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    return JSONResponse(read_manifests())


@app.get("/api/preview/{persona}/{category}/{number}")
async def get_preview(persona: str, category: str, number: int):
    """Serve a generated image for preview."""
    path = OUTPUT_DIR / persona / category / f"{number:04d}.png"
    if path.exists():
        return FileResponse(path, media_type="image/png")
    return JSONResponse({"error": "not found"}, status_code=404)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


# ── Dashboard HTML ───────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XinMate — Image Generator Monitor</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #e0e0e0; }

.header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px 30px; border-bottom: 1px solid #333; }
.header h1 { font-size: 22px; color: #fff; }
.header .subtitle { font-size: 13px; color: #888; margin-top: 4px; }

.stats-bar { display: flex; gap: 20px; padding: 20px 30px; background: #161616; border-bottom: 1px solid #222; flex-wrap: wrap; }
.stat-card { background: #1e1e1e; border-radius: 10px; padding: 16px 24px; min-width: 160px; }
.stat-card .label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
.stat-card .value { font-size: 28px; font-weight: 700; color: #fff; margin-top: 4px; }
.stat-card .value.green { color: #4ade80; }
.stat-card .value.blue { color: #60a5fa; }
.stat-card .value.amber { color: #fbbf24; }

.progress-outer { width: 100%; height: 8px; background: #333; border-radius: 4px; margin-top: 8px; }
.progress-inner { height: 100%; border-radius: 4px; background: linear-gradient(90deg, #4ade80, #22d3ee); transition: width 0.5s; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; padding: 20px 30px; }
.persona-card { background: #1a1a1a; border-radius: 12px; padding: 16px; border: 1px solid #2a2a2a; }
.persona-card .name { font-size: 16px; font-weight: 600; color: #fff; }
.persona-card .gender { font-size: 11px; color: #888; margin-left: 8px; }
.persona-card .count { font-size: 13px; color: #aaa; margin-top: 6px; }
.persona-card .cats { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.cat-tag { font-size: 10px; padding: 3px 8px; border-radius: 6px; background: #2a2a2a; color: #ccc; }
.cat-tag.done { background: #166534; color: #4ade80; }

.section-title { padding: 20px 30px 10px; font-size: 16px; color: #888; }

.latest-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; padding: 0 30px 30px; }
.latest-card { background: #1a1a1a; border-radius: 8px; padding: 10px; border: 1px solid #2a2a2a; }
.latest-card .meta { font-size: 11px; color: #888; }
.latest-card .persona-name { font-size: 13px; font-weight: 600; color: #ddd; }

.refresh-note { text-align: center; padding: 10px; font-size: 11px; color: #555; }
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.status-dot.running { background: #4ade80; animation: pulse 1.5s infinite; }
.status-dot.idle { background: #555; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
</head>
<body>

<div class="header">
    <h1>🎨 XinMate Image Generator</h1>
    <div class="subtitle">Flux Batch Generation Monitor — <span id="timestamp">loading...</span></div>
</div>

<div class="stats-bar">
    <div class="stat-card">
        <div class="label">Status</div>
        <div class="value" id="status"><span class="status-dot idle"></span>Loading</div>
    </div>
    <div class="stat-card">
        <div class="label">Progress</div>
        <div class="value green" id="progress">0 / 0</div>
        <div class="progress-outer"><div class="progress-inner" id="progress-bar" style="width:0%"></div></div>
    </div>
    <div class="stat-card">
        <div class="label">Completion</div>
        <div class="value blue" id="pct">0%</div>
    </div>
    <div class="stat-card">
        <div class="label">Personas Done</div>
        <div class="value amber" id="personas-done">0 / 10</div>
    </div>
</div>

<div class="section-title">Personas</div>
<div class="grid" id="persona-grid"></div>

<div class="section-title">Latest Generated</div>
<div class="latest-grid" id="latest-grid"></div>

<div class="refresh-note">Auto-refreshes every 5 seconds</div>

<script>
async function refresh() {
    try {
        const res = await fetch('/api/stats');
        const d = await res.json();

        document.getElementById('timestamp').textContent = new Date(d.timestamp + 'Z').toLocaleString();
        document.getElementById('progress').textContent = d.totalDone + ' / ' + d.totalTarget;
        document.getElementById('pct').textContent = d.totalPct + '%';
        document.getElementById('progress-bar').style.width = d.totalPct + '%';

        const isRunning = d.totalDone > 0 && d.totalDone < d.totalTarget;
        const statusEl = document.getElementById('status');
        if (d.totalDone >= d.totalTarget) {
            statusEl.innerHTML = '<span class="status-dot" style="background:#4ade80"></span>Complete';
        } else if (isRunning) {
            statusEl.innerHTML = '<span class="status-dot running"></span>Generating';
        } else {
            statusEl.innerHTML = '<span class="status-dot idle"></span>Idle';
        }

        let personasDone = 0;
        let gridHtml = '';
        for (const [pid, p] of Object.entries(d.personas)) {
            if (p.done >= p.target) personasDone++;
            const pPct = Math.round(p.done / p.target * 100);
            let catsHtml = '';
            for (const [cat, cnt] of Object.entries(p.categories)) {
                const isDone = cnt >= 100;
                catsHtml += '<span class="cat-tag ' + (isDone ? 'done' : '') + '">' + cat + ': ' + cnt + '</span>';
            }
            gridHtml += '<div class="persona-card">' +
                '<span class="name">' + p.name + '</span>' +
                '<span class="gender">(' + p.gender + ')</span>' +
                '<div class="count">' + p.done + ' / ' + p.target + ' (' + pPct + '%)</div>' +
                '<div class="progress-outer"><div class="progress-inner" style="width:' + pPct + '%"></div></div>' +
                '<div class="cats">' + catsHtml + '</div>' +
                '</div>';
        }
        document.getElementById('persona-grid').innerHTML = gridHtml;
        document.getElementById('personas-done').textContent = personasDone + ' / 10';

        let latestHtml = '';
        for (const img of d.latestImages) {
            const parts = img.key.split('/');
            const previewUrl = '/api/preview/' + parts[0] + '/' + parts[1] + '/' + parseInt(parts[2]);
            latestHtml += '<div class="latest-card">' +
                '<div class="persona-name">' + img.persona + '</div>' +
                '<div class="meta">' + img.category + ' · ' + img.mood + '</div>' +
                '<div class="meta">' + (img.time ? new Date(img.time).toLocaleTimeString() : '') + '</div>' +
                '</div>';
        }
        document.getElementById('latest-grid').innerHTML = latestHtml;

    } catch (e) {
        console.error('Refresh failed:', e);
    }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("=" * 50)
    print("  XinMate Generation Monitor")
    print("  http://localhost:8080")
    print("  On RunPod: https://YOUR-POD-ID-8080.proxy.runpod.net")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
