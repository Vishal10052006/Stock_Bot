"""Fail-closed local deployment preflight."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from deploy_local.runtime import detect_gpu
from execution.safety import IndependentSafetyGate, SafetyState

def build_report(require_market: bool = False) -> dict:
    """Validate repository layout, environment, compute and live lock."""
    root = Path(__file__).resolve().parents[1]
    failures = [
        f"missing repository path: {p}"
        for p in ("dashboard","trading","market","execution")
        if not (root/p).exists()
    ]
    if require_market:
        for name in ("UPSTOX_ACCESS_TOKEN","UPSTOX_INSTRUMENT_MAP"):
            if not os.getenv(name,"").strip():
                failures.append(f"missing environment variable: {name}")
    if os.getenv("STOCK_BOT_LIVE_BROKER_ENABLED","false").strip().lower()=="true":
        failures.append("STOCK_BOT_LIVE_BROKER_ENABLED must remain false")
    safety = IndependentSafetyGate().evaluate(SafetyState(live_execution_enabled=False))
    if safety.allowed:
        failures.append("live safety gate unexpectedly allowed execution")
    root_dir=Path(os.getenv("STOCK_BOT_RUNTIME_ROOT",".stock_bot_runtime"))
    root_dir.mkdir(parents=True,exist_ok=True)
    gpu=detect_gpu()
    return {
        "status":"PASS" if not failures else "BLOCKED",
        "failures":failures,
        "safety":{"allowed":safety.allowed,"block":safety.block.value,"reason":safety.reason},
        "compute":{"cpu_count":os.cpu_count() or 1,"gpu_available":gpu.available,"gpu_devices":gpu.devices,"gpu_driver":gpu.driver,"cuda_version":gpu.cuda_version},
        "runtime_root":str(root_dir.resolve()),
    }

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-market",action="store_true")
    args=parser.parse_args(argv)
    report=build_report(args.require_market)
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
