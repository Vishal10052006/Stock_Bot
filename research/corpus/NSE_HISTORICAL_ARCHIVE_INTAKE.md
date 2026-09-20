# NSE Historical Archive Intake

The official NSE Corporate Filings — Announcements surface provides a custom
date range and CSV download. NSE rows expose broadcast time and exchange
received/dissemination timestamps. Those source timestamps are used as the
Research Bot causal fields. Archive retrieval time is separate provenance.

Official source: https://www.nseindia.com/companies-listing/corporate-filings-announcements

The intake client requires all three point-in-time timestamps. Rows without
source-native received or dissemination timestamps are rejected rather than
repaired. NSE timestamps are interpreted in the Asia/Kolkata timezone.

Example:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from research.corpus.nse_archive import NSEHistoricalArchiveClient

ist = ZoneInfo("Asia/Kolkata")
client = NSEHistoricalArchiveClient()
path = client.download_csv(
    start=datetime(2026, 1, 1, tzinfo=ist),
    end=datetime(2026, 9, 15, tzinfo=ist),
    output_path="data/research_archive/nse_announcements_2026.csv",
)
records = client.parse_csv(path, archived_at=datetime.now(ist))
```

Do not commit raw archives unless their licensing and repository-size policy
permit it. Prefer storing retrieval metadata and a checksum alongside the
local archive.