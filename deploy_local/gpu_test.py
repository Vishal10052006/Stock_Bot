"""Optional CUDA smoke test; broker-free."""
from __future__ import annotations
import json
def main():
    r={'torch_installed':False,'cuda_available':False,'device':None}
    try:import torch
    except ImportError:print(json.dumps(r,indent=2));return 0
    r['torch_installed']=True;r['cuda_available']=bool(torch.cuda.is_available())
    if r['cuda_available']:
        r['device']=torch.cuda.get_device_name(0);x=torch.ones((8,8),device='cuda');y=x@x;torch.cuda.synchronize();r['matrix_check']=float(y.sum().item())
    print(json.dumps(r,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
