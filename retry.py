"""Shared retry / backoff utility used by all API clients."""
import logging
import random
import time
from functools import wraps
from typing import Callable, Iterable, Type

log = logging.getLogger(__name__)


def with_backoff(
    *,
    retries: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Iterable[Type[Exception]] = (Exception,),
    retryable_status: Iterable[int] = (429, 500, 502, 503, 504),
) -> Callable:
    """
    Decorator: retry with exponential backoff + jitter on transient failures.

    Retries when:
    - The raised exception type is in `exceptions`
    - The exception has a `.status_code` or `.resp.status` attribute whose
      value is in `retryable_status`

    Non-retryable errors (e.g. 400 Bad Request, 401 Unauthorized, 403 Forbidden)
    are re-raised immediately without consuming retry budget.
    """
    exc_tuple = tuple(exceptions)

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except exc_tuple as exc:
                    status = _extract_status(exc)

                    # Non-retryable HTTP error — fail fast
                    if status is not None and status not in retryable_status:
                        raise

                    attempt += 1
                    if attempt > retries:
                        log.error(
                            "[retry] %s: giving up after %d attempts (last error: %s)",
                            fn.__name__, retries, exc,
                        )
                        raise

                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay += random.uniform(0, delay * 0.2)   # ±20 % jitter

                    log.warning(
                        "[retry] %s: attempt %d/%d failed (%s). Retrying in %.1fs …",
                        fn.__name__, attempt, retries, exc, delay,
                    )
                    time.sleep(delay)

        return wrapper
    return decorator


def _extract_status(exc: Exception) -> int | None:
    """Pull HTTP status code from various exception shapes."""
    # googleapiclient.errors.HttpError  → exc.resp.status
    resp = getattr(exc, "resp", None)
    if resp is not None:
        return int(getattr(resp, "status", 0)) or None

    # openai SDK → exc.status_code
    code = getattr(exc, "status_code", None)
    if code is not None:
        return int(code)

    # smtplib — no numeric status exposed, always retry
    return None
