from pathlib import Path
import tempfile
import unittest

from trading.runtime_pipeline import TradingResearchRuntime


class RuntimeDashboardJournalTests(unittest.TestCase):
    def test_runtime_can_persist_monitoring_to_shared_dashboard_journal(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "monitoring.jsonl"
            runtime = TradingResearchRuntime(monitoring_journal_path=str(path))
            self.assertIsNotNone(runtime.monitoring.pipeline.engine.journal)
            self.assertEqual(runtime.monitoring.pipeline.engine.journal.path, path)


if __name__ == "__main__":
    unittest.main()
