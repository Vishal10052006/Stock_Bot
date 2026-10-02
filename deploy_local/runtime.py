"""Detect local CPU/GPU runtime without contacting a broker."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json, os, platform, shutil, subprocess, sys
from pathlib import Path

@dataclass(frozen=True, slots=True)
class GPUInfo:
    """Detected NVIDIA GPU metadata."""
    available: bool
    devices: tuple[str, ...] = ()
    driver: str | None = None
    cuda_version: str | None = None

def detect_gpu() -> GPUInfo:
    """Use nvidia-smi when installed and fail closed otherwise."""
    binary = shutil.which("nvidia-smi")
    if not binary:
        return GPUInfo(False)
    try:
        result = subprocess.run(
            [binary, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            check=True, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return GPUInfo(False)
    devices, driver = [], None
    for line in result.stdout.splitlines():
        parts = [item.strip() for item in line.split(",", 1)]
        if parts:
            devices.append(parts[0])
        if len(parts) == 2 and driver is None:
            driver = parts[1]
    cuda_version = None
    try:
        result = subprocess.run(
            [binary, "--query-gpu=cuda_version", "--format=csv,noheader"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        cuda_version = next((line.strip() for line in result.stdout.splitlines() if line.strip()), None)
    except (OSError, subprocess.SubprocessError):
        pass
    return GPUInfo(bool(devices), tuple(devices), driver, cuda_version)

def main() -> int:
    """Print local runtime information."""
    root = Path(__file__).resolve().parents[1]
    git = shutil.which("git")
    revision = None
    if git:
        try:
            revision = subprocess.run(
                [git, "-C", str(root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, timeout=5,
            ).stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            pass
    print(json.dumps({
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count() or 1,
        "git": revision,
        "gpu": asdict(detect_gpu()),
    }, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
