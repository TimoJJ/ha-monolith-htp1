"""BEQ catalogue integration for Monoprice HTP-1.

Fetches the BEQ (Bass EQ) catalogue and provides search functionality
by movie title or TMDB ID. Mirrors the approach used in the Unfolded Circle
integration but adapted for Home Assistant's service architecture.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BEQ_DB_URL = "https://beqcatalogue.readthedocs.io/en/latest/database.json"
CACHE_TTL = 3600  # 1 hour

_beq_cache: list[dict] | None = None
_beq_cache_time: float = 0


async def async_fetch_catalogue(session: aiohttp.ClientSession) -> list[dict]:
    """Fetch the BEQ catalogue from the remote database, with in-memory caching."""
    global _beq_cache, _beq_cache_time  # noqa: PLW0603

    now = asyncio.get_event_loop().time()
    if _beq_cache is not None and (now - _beq_cache_time) < CACHE_TTL:
        return _beq_cache

    _LOGGER.info("Fetching BEQ catalogue from %s", BEQ_DB_URL)
    try:
        async with session.get(
            BEQ_DB_URL, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                _LOGGER.error("BEQ catalogue fetch failed: HTTP %d", resp.status)
                return _beq_cache or []
            data = await resp.json(content_type=None)
            if isinstance(data, list):
                _beq_cache = data
                _beq_cache_time = now
                _LOGGER.info("BEQ catalogue loaded: %d entries", len(data))
                return data
    except Exception as err:
        _LOGGER.error("BEQ catalogue fetch error: %s", err)
    return _beq_cache or []


def parse_tmdb_id(value: Any) -> int | None:
    """Extract a numeric TMDB ID from an int, string, or themoviedb.org URL."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
        match = re.search(r"/(?:movie|tv)/(\d+)", value)
        if match:
            return int(match.group(1))
    return None


def _extract_entry_tmdb_id(entry: dict) -> int | None:
    """Extract the TMDB ID stored in a catalogue entry."""
    raw = entry.get("theMovieDB") or entry.get("tmdbid") or entry.get("tmdb_id")
    if raw is None:
        return None
    return parse_tmdb_id(raw)


def _codec_matches(entry: dict, codec: str) -> bool:
    """Check if an entry's audioTypes contain the requested codec."""
    audio_types = entry.get("audioTypes", [])
    codec_lower = codec.lower()
    return any(codec_lower in at.lower() for at in audio_types)


def search_by_title(
    catalogue: list[dict],
    title: str,
    *,
    year: int | None = None,
    codec: str | None = None,
) -> list[dict]:
    """Search the BEQ catalogue by title (case-insensitive substring match)."""
    query = title.lower().strip()
    if not query:
        return []

    results = []
    for entry in catalogue:
        entry_title = entry.get("title", "").lower()
        if query not in entry_title:
            continue
        if year is not None and entry.get("year") != year:
            continue
        if codec and not _codec_matches(entry, codec):
            continue
        results.append(entry)

    return results


def search_by_tmdb_id(
    catalogue: list[dict],
    tmdb_id: int,
    *,
    codec: str | None = None,
) -> list[dict]:
    """Search the BEQ catalogue by TMDB ID."""
    results = []
    for entry in catalogue:
        entry_tmdb = _extract_entry_tmdb_id(entry)
        if entry_tmdb != tmdb_id:
            continue
        if codec and not _codec_matches(entry, codec):
            continue
        results.append(entry)
    return results


def best_match(results: list[dict]) -> dict | None:
    """Pick the best match from a list of search results.

    Prefers entries with more filters (usually higher-quality profiles).
    """
    if not results:
        return None
    return max(results, key=lambda e: len(e.get("filters", [])))


def prepare_filters(entry: dict) -> list[dict]:
    """Extract filters from a catalogue entry, stripping biquad data."""
    import copy

    filters = copy.deepcopy(entry.get("filters", []))
    for f in filters:
        f.pop("biquads", None)
    return filters
