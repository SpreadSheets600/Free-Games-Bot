from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class Giveaway:
    id: int
    title: str
    worth: str
    description: str
    instructions: str
    open_giveaway_url: str
    image: str
    platforms: str
    type: str
    published_date: str
    end_date: str

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
            platforms=data.get("platforms", ""),
            type=data.get("type", ""),
            published_date=data.get("published_date", ""),
            end_date=data.get("end_date", ""),
        )


class GamerPowerClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=15.0)

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

        return data if isinstance(data, dict) else None
