"""Configured public Indian research sources.

Verified public sources:
- RBI RSS listing exposes the Press Releases feed at rbi.org.in/pressreleases_rss.xml.
- PIB exposes its Press Releases RSS endpoint from its RSS directory.
"""
from research.providers.rss import RssResearchProvider

RBI_PRESS_RELEASES = "https://rbi.org.in/pressreleases_rss.xml"
PIB_PRESS_RELEASES = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1"


def rbi_provider() -> RssResearchProvider:
    return RssResearchProvider("rbi-rss", RBI_PRESS_RELEASES)


def pib_provider() -> RssResearchProvider:
    return RssResearchProvider("pib-rss", PIB_PRESS_RELEASES)
