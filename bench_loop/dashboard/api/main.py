"""BenchLoop API — FastAPI backend for local LLM benchmarking."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Canonical bench-loop lives in the live workspace, NOT in this backup tree.
# The old relative-path resolver picked up the stale `workspace.pre-symlink-backup-...`
# copy which had a different RunConfig schema and the LT-XX task IDs. Override.
_default_bench_loop = "/Users/aurora/.ocplatform/workspace/bench-loop"
bench_loop_root = Path(os.environ.get("BENCH_LOOP_DIR", _default_bench_loop)).resolve()
if not (bench_loop_root / "bench_loop").is_dir():
    # Fall back to the historical relative path if the canonical one is missing.
    bench_loop_root = (Path(__file__).resolve().parent.parent.parent / "bench-loop").resolve()
if str(bench_loop_root) not in sys.path:
    sys.path.insert(0, str(bench_loop_root))
print(f"[bench-loop-api] using bench_loop from: {bench_loop_root}", flush=True)

# Ensure api package root is importable for routes
api_root = Path(__file__).resolve().parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routes import benchmark, chat, hardware, health, models

app = FastAPI(title="BenchLoop", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(benchmark.router, prefix="/api")
app.include_router(hardware.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# Serve the bundled UI (built React SPA) at /
_ui_dir = Path(__file__).resolve().parent.parent / "ui"
if _ui_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_ui_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # Serve specific static files when they exist, else fall back to index.html.
        candidate = _ui_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_ui_dir / "index.html")
