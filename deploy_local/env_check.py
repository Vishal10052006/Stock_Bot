"""Check local .env permissions without printing its contents."""
from __future__ import annotations
import argparse,json,os,stat
from pathlib import Path

def check_env_file(path:Path)->dict:
    """Report only metadata and secret presence."""
    path=Path(path)
    if not path.is_file(): return {"status":"MISSING","exists":False,"path":str(path)}
    mode=stat.S_IMODE(path.stat().st_mode)
    open_access=bool(mode & (stat.S_IRGRP|stat.S_IWGRP|stat.S_IXGRP|stat.S_IROTH|stat.S_IWOTH|stat.S_IXOTH))
    return {"status":"WARN" if open_access else "PASS","exists":True,"mode":oct(mode),"world_or_group_access":open_access,"upstox_token_present":bool(os.getenv("UPSTOX_ACCESS_TOKEN","")),"path":str(path)}

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--path",type=Path,default=Path(".env"))
    result=check_env_file(parser.parse_args().path); print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__": raise SystemExit(main())
