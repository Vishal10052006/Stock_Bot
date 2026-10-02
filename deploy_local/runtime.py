"""Detect local CPU/GPU resources."""
from __future__ import annotations
from dataclasses import asdict,dataclass
import json,os,platform,shutil,subprocess,sys
from pathlib import Path
@dataclass(frozen=True,slots=True)
class GPUInfo:
    available: bool
    devices: tuple[str,...]=()
    driver: str|None=None
    cuda_version: str|None=None
def detect_gpu()->GPUInfo:
    binary=shutil.which('nvidia-smi')
    if not binary:return GPUInfo(False)
    try:r=subprocess.run([binary,'--query-gpu=name,driver_version','--format=csv,noheader'],check=True,capture_output=True,text=True,timeout=5)
    except (OSError,subprocess.SubprocessError):return GPUInfo(False)
    devices=[];driver=None
    for line in r.stdout.splitlines():
        p=[x.strip() for x in line.split(',',1)]
        if p:devices.append(p[0])
        if len(p)==2 and driver is None:driver=p[1]
    cuda=None
    try:r=subprocess.run([binary,'--query-gpu=cuda_version','--format=csv,noheader'],check=True,capture_output=True,text=True,timeout=5);cuda=next((x.strip() for x in r.stdout.splitlines() if x.strip()),None)
    except (OSError,subprocess.SubprocessError):pass
    return GPUInfo(bool(devices),tuple(devices),driver,cuda)
def main()->int:
    root=Path(__file__).resolve().parents[1]; revision=None;git=shutil.which('git')
    if git:
        try:revision=subprocess.run([git,'-C',str(root),'rev-parse','HEAD'],check=True,capture_output=True,text=True,timeout=5).stdout.strip() or None
        except (OSError,subprocess.SubprocessError):pass
    print(json.dumps({'python':sys.version.split()[0],'platform':platform.platform(),'cpu_count':os.cpu_count() or 1,'git':revision,'gpu':asdict(detect_gpu())},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
