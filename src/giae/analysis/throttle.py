"""API rate limiting and retry logic for GIAE.

Provides a throttled HTTP wrapper that limits concurrent API calls
and retries on HTTP 429 (Too Many Requests) with exponential backoff.
Uses only Python stdlib.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
from http.client import HTTPResponse
from typing import Any

logger = logging.getLogger(__name__)

# Module-level semaphore — shared across all threads and API clients
_api_semaphore: threading.Semaphore | None = None
_lock = threading.Lock()


def configure_throttle(max_concurrent: int = 3) -> None:
    """
    Set the global API concurrency limit.

    Call once at startup (e.g. in Interpreter.__post_init__).
    Safe to call multiple times — last call wins.

    Args:
        max_concurrent: Max number of simultaneous API calls.
    """
    global _api_semaphore
    with _lock:
        _api_semaphore = threading.Semaphore(max_concurrent)
        logger.debug("API throttle configured: max_concurrent=%d", max_concurrent)


def throttled_urlopen(
    request: urllib.request.Request | str,
    timeout: int = 30,
    max_retries: int = 3,
    data: bytes | None = None,
) -> HTTPResponse:
    """
    Drop-in replacement for urllib.request.urlopen with:
    - Semaphore-based concurrency limiting
    - Exponential backoff on HTTP 429
    - Configurable retry count

    Args:
        request: URL string or Request object.
        timeout: HTTP timeout in seconds.
        max_retries: Number of retries on 429 responses.
        data: Optional POST data.

    Returns:
        HTTPResponse object.

    Raises:
        urllib.error.HTTPError: On non-429 HTTP errors after all retries.
        urllib.error.URLError: On network errors.
    """
    global _api_semaphore

    # Lazy-init with a sensible default if configure_throttle wasn't called
    if _api_semaphore is None:
        configure_throttle(3)
    sem = _api_semaphore  # type: ignore[assignment]

    last_error: Exception | None = None

    for attempt in range(max_retries):
        with sem:
            try:
                if data is not None:
                    return urllib.request.urlopen(request, data=data, timeout=timeout)
                return urllib.request.urlopen(request, timeout=timeout)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    # Rate limited — back off
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = min(float(retry_after), 60.0)
                        except ValueError:
                            wait = min(2 ** attempt * 2.0, 30.0)
                    else:
                        wait = min(2 ** attempt * 2.0, 30.0)

                    logger.warning(
                        "API rate limited (429). Retrying in %.1fs (attempt %d/%d)",
                        wait, attempt + 1, max_retries,
                    )
                    last_error = e
                    time.sleep(wait)
                    continue
                raise
            except urllib.error.URLError as e:
                # Network error — retry once with backoff
                if attempt < max_retries - 1:
                    wait = min(2 ** attempt * 1.0, 10.0)
                    logger.debug(
                        "Network error: %s. Retrying in %.1fs (attempt %d/%d)",
                        e.reason, wait, attempt + 1, max_retries,
                    )
                    last_error = e
                    time.sleep(wait)
                    continue
                raise

    # All retries exhausted
    if last_error:
        raise last_error
    raise urllib.error.URLError("All retries exhausted")
