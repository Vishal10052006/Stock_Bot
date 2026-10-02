"""Validate local operator snapshot freshness and authority."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
def check_snapshot(path:Path,max_age_seconds=120.0):
    if not Path(path).is_file():return {'status':'DOWN','reason':'snapshot missing'}
    try:payload=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):return {'status':'BLOCKED','reason':'snapshot malformed'}
    if not isinstance(payload,dict) or payload.get('authority')!='OBSERVATION_ONLY':return {'status':'BLOCKED','reason':'snapshot authority invalid'}
    age=time.time()-Path(path).stat().st_mtime
    if age>max_age_seconds:return {'status':'STALE','reason':f'snapshot age {age:.1f}s exceeds limit'}
    return {'status':'PASS','reason':'operator snapshot is fresh','age_seconds':age}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--max-age-seconds',type=float,default=120.0);a=p.parse_args();r=check_snapshot(a.snapshot,a.max_age_seconds);print(json.dumps(r,indent=2,sort_keys=True));return 0 if r['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
