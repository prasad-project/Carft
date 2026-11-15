from app.connectors.api_sources import Arxiv, DevTo, GitHub, HackerNews, HuggingFace
from app.connectors.base import Connector, RawItem
from app.connectors.feeds import GoogleNews, Lobsters, ScienceDaily, TechCrunch
from app.connectors.social import Reddit, XTwitter

ALL_CONNECTORS: list[Connector] = [
    HackerNews(), GitHub(), DevTo(), Arxiv(), HuggingFace(), Lobsters(),
    ScienceDaily(), TechCrunch(), GoogleNews(), Reddit(), XTwitter(),
]
BY_KEY = {c.key: c for c in ALL_CONNECTORS}
__all__ = ["ALL_CONNECTORS", "BY_KEY", "Connector", "RawItem"]
