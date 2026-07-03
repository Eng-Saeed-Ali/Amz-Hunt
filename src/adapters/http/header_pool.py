"""HTTP header pool — browser-realistic header rotation for curl_cffi."""

from __future__ import annotations

import random
from typing import Literal

# Ordered list of impersonate profiles matching curl_cffi's supported targets
IMPERSONATE_PROFILES: list[Literal["chrome124", "chrome120", "firefox120", "safari17_0", "edge101"]] = [
    "chrome124",
    "chrome120",
    "firefox120",
    "safari17_0",
    "edge101",
]

# User-Agent strings matching the impersonate profiles above
USER_AGENTS: dict[str, str] = {
    "chrome124": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "chrome120": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "firefox120": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
        "Gecko/20100101 Firefox/120.0"
    ),
    "safari17_0": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.2 Safari/605.1.15"
    ),
    "edge101": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.53"
    ),
}

# Accept-Language variants for Egypt/US/Arabic locales
ACCEPT_LANGUAGES: list[str] = [
    "en-EG,en;q=0.9,ar-EG;q=0.8,ar;q=0.7,en-US;q=0.6",
    "ar-EG,ar;q=0.9,en;q=0.8,en-US;q=0.7",
    "en-US,en;q=0.9,ar;q=0.5",
    "en-GB,en;q=0.9,ar;q=0.6",
    "en,ar;q=0.8",
]

# Referrer pool — common Amazon Egypt entry points
REFERRERS: list[str] = [
    "https://www.amazon.eg/",
    "https://www.amazon.eg/gp/goldbox",
    "https://www.amazon.eg/gp/browse.html",
    "https://www.amazon.eg/s",
    "https://www.amazon.eg/gp/yourstore",
]

# Sec-Ch-UA (Client Hints) per profile
SEC_CH_UA: dict[str, str] = {
    "chrome124": '"Google Chrome";v="124", "Chromium";v="124", "Not-A.Brand";v="99"',
    "chrome120": '"Google Chrome";v="120", "Chromium";v="120", "Not-A.Brand";v="99"',
    "firefox120": '"Firefox";v="120"',
    "safari17_0": '"Safari";v="17", "Apple";v="17"',
    "edge101": '"Microsoft Edge";v="101", "Chromium";v="101", "Not;A=Brand";v="99"',
}

# Sec-Ch-UA-Mobile
SEC_CH_UA_MOBILE: dict[str, str] = {
    "chrome124": "?0",
    "chrome120": "?0",
    "firefox120": "?0",
    "safari17_0": "?0",
    "edge101": "?0",
}

# Sec-Ch-UA-Platform
SEC_CH_UA_PLATFORM: dict[str, str] = {
    "chrome124": '"Windows"',
    "chrome120": '"Windows"',
    "firefox120": '"Windows"',
    "safari17_0": '"macOS"',
    "edge101": '"Windows"',
}

# Internal rotation index (shuffled at startup for unpredictability)
_rotation_index: int = 0
_shuffled_profiles: list[str] = []


def _shuffle_profiles() -> None:
    """Shuffle the impersonate profile order for rotation unpredictability."""
    global _shuffled_profiles
    _shuffled_profiles = IMPERSONATE_PROFILES.copy()
    random.shuffle(_shuffled_profiles)


# Initialize shuffled order on module load
_shuffle_profiles()


def get_headers(impersonate: str = "chrome124") -> dict[str, str]:
    """Return a complete realistic browser header dict for the given profile.

    Args:
        impersonate: curl_cffi impersonate target (e.g., "chrome124", "firefox120").

    Returns:
        Dict of HTTP headers including User-Agent, Accept-Language, Sec-Ch-Ua,
        Sec-Fetch-*, and other browser-realistic headers.
    """
    # Validate profile, fallback to chrome124
    if impersonate not in IMPERSONATE_PROFILES:
        impersonate = "chrome124"

    ua = USER_AGENTS.get(impersonate, USER_AGENTS["chrome124"])
    accept_lang = random.choice(ACCEPT_LANGUAGES)
    referrer = random.choice(REFERRERS)
    sec_ch_ua = SEC_CH_UA.get(impersonate, SEC_CH_UA["chrome124"])
    sec_ch_ua_mobile = SEC_CH_UA_MOBILE.get(impersonate, "?0")
    sec_ch_ua_platform = SEC_CH_UA_PLATFORM.get(impersonate, '"Windows"')

    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": accept_lang,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": sec_ch_ua,
        "Sec-Ch-Ua-Mobile": sec_ch_ua_mobile,
        "Sec-Ch-Ua-Platform": sec_ch_ua_platform,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Referer": referrer,
        "Connection": "keep-alive",
    }


def rotate_headers() -> tuple[dict[str, str], str]:
    """Rotate to the next header profile and return (headers, profile).

    Returns:
        Tuple of (complete header dict, impersonate profile string).
    """
    global _rotation_index
    profile = _shuffled_profiles[_rotation_index]
    _rotation_index = (_rotation_index + 1) % len(_shuffled_profiles)
    return get_headers(profile), profile


def reset_rotation() -> None:
    """Reset the header rotation (reshuffles profile order)."""
    global _rotation_index
    _rotation_index = 0
    _shuffle_profiles()