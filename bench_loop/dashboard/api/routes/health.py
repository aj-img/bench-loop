"""Health check endpoint."""
from __future__ import annotations

from fastapi import APIRouter

import bench_loop
from bench_loop.hardware import detect_hardware

router = APIRouter()


def _hw_field(hw, attr: str, default=None):
    if isinstance(hw, dict):
        return hw.get(attr, default)
    return getattr(hw, attr, default)


@router.get("/health")
async def health():
    hw = detect_hardware()
    cpu = _hw_field(hw, "cpu") or _hw_field(hw, "cpu_model") or ""
    gpu = _hw_field(hw, "gpu")
    if isinstance(gpu, dict):
        gpu = gpu.get("model", "")
    elif gpu is None or gpu == "":
        # fall back to nested object access
        nested = _hw_field(hw, "gpu")
        if hasattr(nested, "model"):
            gpu = nested.model
    mem_gb = _hw_field(hw, "system_memory_gb")
    if mem_gb is None:
        mem_mb = _hw_field(hw, "memory_total_mb")
        mem_gb = round(mem_mb / 1024, 1) if mem_mb else 0
    return {
        "status": "ok",
        "version": bench_loop.__version__,
        "hardware": {
            "cpu": cpu,
            "gpu": gpu or "",
            "memory_gb": mem_gb,
        },
    }
