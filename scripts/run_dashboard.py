#!/usr/bin/env python3
from __future__ import annotations
import os
from dashboard.contracts import DashboardConfig
from dashboard.server import serve
def main():
    serve(DashboardConfig(
        host=os.getenv("STOCK_BOT_DASHBOARD_HOST","127.0.0.1"),
        port=int(os.getenv("STOCK_BOT_DASHBOARD_PORT","8765")),
        journal_path=os.getenv("STOCK_BOT_MONITORING_JOURNAL","data/monitoring/dashboard.jsonl"),
        environment=os.getenv("STOCK_BOT_ENVIRONMENT","RESEARCH/PAPER")))
if __name__=="__main__": main()
