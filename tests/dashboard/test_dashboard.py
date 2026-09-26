from pathlib import Path
import json, threading, time, unittest
from urllib.request import urlopen
from dashboard.contracts import DashboardConfig
from dashboard.service import DashboardService
from dashboard.server import DashboardServer

class DashboardTests(unittest.TestCase):
    def test_empty_dashboard_is_explicit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p=DashboardService.from_environment(DashboardConfig(journal_path=str(Path(d)/"e.jsonl"))).overview()
        self.assertEqual(p["summary"]["registered_agents"],7)
        self.assertEqual(p["summary"]["events"],0)
        self.assertEqual(p["live_trading"],"LOCKED")
        self.assertTrue(all(a["status"] in {"WAITING","LOCKED"} for a in p["agents"]))

    def test_event_updates_agent_state(self):
        import tempfile
        from monitoring.journal import MonitoringEvent, MonitoringJournal
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"events.jsonl"; j=MonitoringJournal(path)
            j.append(MonitoringEvent.create(event_type="HEALTH",source="analysis_bot",payload={"message":"ok"},severity="HEALTHY",correlation_id="RUN-1",timestamp="2026-09-26T10:45:00+00:00"))
            p=DashboardService.from_environment(DashboardConfig(journal_path=str(path))).overview()
        a=next(x for x in p["agents"] if x["agent_id"]=="AG-02")
        self.assertEqual(a["status"],"ACTIVE"); self.assertEqual(a["event_count"],1)

    def test_api_smoke(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cfg=DashboardConfig(host="127.0.0.1",port=18765,journal_path=str(Path(d)/"e.jsonl"))
            s=DashboardServer(cfg); t=threading.Thread(target=s.serve_forever,daemon=True); t.start()
            try:
                time.sleep(.05)
                with urlopen("http://127.0.0.1:18765/api/overview",timeout=2) as r: body=json.loads(r.read())
                self.assertEqual(body["summary"]["registered_agents"],7)
            finally:
                s.shutdown(); s.server_close()

if __name__=="__main__":
    unittest.main()
