"""Configured public Indian research sources."""
from research.providers.rss import RssResearchProvider

RBI_PRESS_RELEASES = "https://www.rbi.org.in/Scripts/rss.aspx"
PIB_PRESS_RELEASES = "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1"


def rbi_provider() -> RssResearchProvider:
    return RssResearchProvider("rbi-rss", RBI_PRESS_RELEASES)


def pib_provider() -> RssResearchProvider:
    return RssResearchProvider("pib-rss", PIB_PRESS_RELEASES)
