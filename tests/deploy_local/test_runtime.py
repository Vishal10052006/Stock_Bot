from __future__ import annotations
import json
from deploy_local.doctor import build_report
from deploy_local.health import check_snapshot

def test_doctor_is_fail_closed_for_live():
    report=build_report(False)
    assert report["status"]=="PASS"
    assert report["safety"]["allowed"] is False
    assert report["safety"]["block"]=="LIVE_LOCKED"

def test_health_accepts_fresh_observation_snapshot(tmp_path):
    path=tmp_path/"snapshot.json"
    path.write_text(json.dumps({"authority":"OBSERVATION_ONLY"}),encoding="utf-8")
    assert check_snapshot(path,120)["status"]=="PASS"
