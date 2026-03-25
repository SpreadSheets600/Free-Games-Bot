from __future__ import annotations

import re
import hashlib
import logging
import email.utils
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import httpx

log = logging.getLogger(__name__)


@dataclass
class Giveaway:
    id: int
    title: str
    worth: str
    description: str
    instructions: str
    open_giveaway_url: str
    image: str
    thumbnail: str
    platforms: str
    type: str
    published_date: str
    end_date: str
    users: int
    status: str

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Giveaway":
        return cls(
            id=int(data.get("id")),
            title=data.get("title", ""),
            worth=data.get("worth", ""),
            description=data.get("description", ""),
            instructions=data.get("instructions", ""),
            open_giveaway_url=data.get("open_giveaway_url", ""),
            image=data.get("image", ""),
            thumbnail=data.get("thumbnail", ""),
            platforms=data.get("platforms", ""),
            type=data.get("type", ""),
            published_date=data.get("published_date", ""),
            end_date=data.get("end_date", ""),
            users=int(data.get("users", 0) or 0),
            status=data.get("status", ""),
        )


@dataclass
class FeedEntry:
    entry_key: str
    title: str
    url: str
    published: str
    feed_url: str
    summary: str


class GamerPowerClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": "FreeGamesBot/1.0"},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_giveaways(
        self,
        platform: Optional[str] = None,
        type_: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> List[Giveaway]:
        params: Dict[str, Any] = {}
        if platform:
            params["platform"] = platform
        if type_:
            params["type"] = type_
        if sort_by:
            params["sort-by"] = sort_by

        response = await self._client.get("/giveaways", params=params)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and data.get("status") == 201:
            return []
        if not isinstance(data, list):
            return []
        return [Giveaway.from_json(item) for item in data]

    async def fetch_giveaway(self, giveaway_id: int) -> Optional[Giveaway]:
        response = await self._client.get("/giveaway", params={"id": giveaway_id})
        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        return Giveaway.from_json(data)

    async def fetch_worth(
        self, platform: Optional[str] = None, type_: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if platform:
            params["platform"] = platform
        if type_:
            params["type"] = type_

        response = await self._client.get("/worth", params=params)
        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        return data if isinstance(data, dict) else None

    async def fetch_rss_feed(self, feed_url: str) -> List[FeedEntry]:
        response = await self._client.get(feed_url)
        response.raise_for_status()
        return self._parse_rss(response.text, feed_url)

    async def fetch_rss_feeds(self, feed_urls: Sequence[str]) -> List[FeedEntry]:
        entries: List[FeedEntry] = []
        for feed_url in feed_urls:
            try:
                entries.extend(await self.fetch_rss_feed(feed_url))
            except Exception:
                log.exception("Failed to fetch RSS feed %s", feed_url)
        return entries

    def match_feed_entries(
        self, entries: Sequence[FeedEntry], giveaways: Sequence[Giveaway]
    ) -> List[Giveaway]:
        matches: List[Giveaway] = []
        seen_ids: set[int] = set()
        indexed_by_title = {
            self._normalize_title(giveaway.title): giveaway for giveaway in giveaways
        }

        for entry in entries:
            giveaway_id = self._extract_giveaway_id(entry.url)
            matched = None
            if giveaway_id is not None:
                matched = next((g for g in giveaways if g.id == giveaway_id), None)

            if matched is None:
                matched = indexed_by_title.get(self._normalize_title(entry.title))

            if matched and matched.id not in seen_ids:
                seen_ids.add(matched.id)
                matches.append(matched)

        return matches

    def _parse_rss(self, xml_text: str, feed_url: str) -> List[FeedEntry]:
        root = ET.fromstring(xml_text)
        items = root.findall(".//item")
        entries: List[FeedEntry] = []

        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()

            if not title and not link and not guid:
                continue

            entry_key_source = guid or link or f"{feed_url}:{title}"
            entry_key = hashlib.sha1(entry_key_source.encode("utf-8")).hexdigest()
            entries.append(
                FeedEntry(
                    entry_key=entry_key,
                    title=title,
                    url=link or guid,
                    published=self._normalize_pubdate(pub_date),
                    feed_url=feed_url,
                    summary=re.sub(r"<[^>]+>", "", description).strip(),
                )
            )

        return entries

    def _extract_giveaway_id(self, url: str) -> Optional[int]:
        patterns = [
            r"[?&]id=(\d+)",
            r"/giveaway/(\d+)",
            r"/giveaway/[^/]+/(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return int(match.group(1))
        return None

    def _normalize_title(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _normalize_pubdate(self, value: str) -> str:
        if not value:
            return ""
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            return parsed.isoformat()
        except Exception:
            return value
