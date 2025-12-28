def get_game_platform(platforms: str) -> str | None:
    platforms_mapping = {
        "epic-games-store": ["Epic Games", "https://s6.imgcdn.dev/Yl5JYi.png"],
        "steam": ["Steam", "https://s6.imgcdn.dev/Yl5o5H.jpg"],
        "gog": ["GOG", "https://s6.imgcdn.dev/YlKwmM.webp"],
    }

    platform_list = platforms.split(", ")

    for item in platform_list:
        item_lower = item.lower()
        if item_lower in platforms_mapping:
            return platforms_mapping[item_lower][1]

    return None


get_game_platform("epic-games-store")
