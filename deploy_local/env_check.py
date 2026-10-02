"""Check local .env permissions without printing secret values."""
from __future__ import annotations
import argparse,json,os,stat
from pathlib import Path
def check_env_file(path:Path):
    if not Path(path).is_file():return {'status':'MISSING','exists':False,'path':str(path)}
    mode=stat.S_IMODE(Path(path).stat().st_mode);open_access=bool(mode&(stat.S_IRGRP|stat.S_IWGRP|stat.S_IXGRP|stat.S_IROTH|stat.S_IWOTH|stat.S_IXOTH))
    return {'status':'WARN' if open_access else 'PASS','mode':oct(mode),'world_or_group_access':open_access,'upstox_token_present':bool(os.getenv('UPSTOX_ACCESS_TOKEN','')),'path':str(path)}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--path',type=Path,default=Path('.env'));r=check_env_file(p.parse_args().path);print(json.dumps(r,indent=2,sort_keys=True));return 0 if r['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
