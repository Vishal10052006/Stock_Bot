"""Optional local CUDA smoke test; never contacts a broker."""
from __future__ import annotations
import json

def main()->int:
    """Report CUDA visibility and execute a tiny local test when available."""
    result={"torch_installed":False,"cuda_available":False,"device":None}
    try:
        import torch
    except ImportError:
        print(json.dumps(result,indent=2,sort_keys=True)); return 0
    result["torch_installed"]=True
    result["cuda_available"]=bool(torch.cuda.is_available())
    if result["cuda_available"]:
        result["device"]=torch.cuda.get_device_name(0)
        x=torch.ones((8,8),device="cuda"); y=x@x; torch.cuda.synchronize()
        result["matrix_check"]=float(y.sum().item())
    print(json.dumps(result,indent=2,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
