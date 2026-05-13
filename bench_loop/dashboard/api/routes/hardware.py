"""Hardware detection endpoint."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter

from bench_loop.hardware import detect_hardware

router = APIRouter()


@router.get("/hardware")
async def get_hardware():
    hw = detect_hardware()
    if isinstance(hw, dict):
        data = dict(hw)
    elif hasattr(hw, "to_dict"):
        data = hw.to_dict()
    else:
        data = {k: getattr(hw, k) for k in dir(hw) if not k.startswith("_")}
    # Normalize legacy field names expected by the UI.
    if "cpu_model" not in data and "cpu" in data:
        data["cpu_model"] = data["cpu"]
    if "memory_total_mb" not in data and "system_memory_gb" in data:
        data["memory_total_mb"] = round(float(data["system_memory_gb"]) * 1024)
    if "gpu" in data and not isinstance(data["gpu"], dict):
        data["gpu"] = {
            "model": data["gpu"] or "",
            "vendor": "",
            "vram_total_mb": int((data.get("gpu_memory_gb") or 0) * 1024) or None,
        }
    usage = shutil.disk_usage(Path.home())
    data["disk_total_gb"] = round(usage.total / (1024**3), 1)
    data["disk_free_gb"] = round(usage.free / (1024**3), 1)
    return data
