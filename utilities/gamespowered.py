import aiohttp

BASE_URL = "https://www.gamerpower.com/api"
CONST_PLATFORMS = [
    "pc",
    "steam",
    "epic-games-store",
    "ubisoft",
    "gog",
    "itchio",
    "ps4",
    "ps5",
    "xbox-one",
    "xbox-series-xs",
    "switch",
    "android",
    "ios",
    "vr",
    "battlenet",
    "origin",
    "drm-free",
    "xbox-360",
]


async def get_giveaway(giveaway_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            BASE_URL + "/giveaway", params={"id": giveaway_id}
        ) as response:
            return await response.json()


async def get_all_giveaways(
    platform: str = None, type_: str = None, sort_by: str = None
):
    params = {}

    if platform:
        params["platform"] = platform
    if type_:
        params["type"] = type_
    if sort_by:
        params["sort-by"] = sort_by

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/giveaways", params=params) as response:
            return await response.json()


async def get_worth(platform: str = None, type_: str = None):
    params = {}

    if platform:
        params["platform"] = platform
    if type_:
        params["type"] = type_

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/worth", params=params) as response:
            return await response.json()


async def get_filtered_giveaways(platforms: list[str] = None, types: list[str] = None):
    params = {}

    if platforms:
        params["platform"] = ".".join(platforms)
    if types:
        params["type"] = ".".join(types)

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/filter", params=params) as response:
            return await response.json()
