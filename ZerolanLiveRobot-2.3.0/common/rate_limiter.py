"""Anti-Spam Rate Limiter for IGEM-sama.

Prevents a single viewer from flooding the bot with messages.
Two levels of protection:
  - Per-user rate limit: max N messages per M seconds
  - Global rate limit: max total messages per second
"""

import threading
import time
from collections import defaultdict, deque
from typing import Optional

from loguru import logger


class RateLimiter:
    """Per-user + global rate limiter for danmaku processing.

    Usage:
        limiter = RateLimiter(per_user_limit=3, per_user_window=10, global_limit=2)
        if limiter.allow(uid="123"):
            # process the message
        else:
            # skip this message
    """

    def __init__(
        self,
        per_user_limit: int = 3,
        per_user_window: int = 10,
        global_limit: int = 2,
        global_window: float = 1.0,
    ):
        """
        Args:
            per_user_limit: Max messages a single user can send in the window.
            per_user_window: Time window in seconds for per-user limit.
            global_limit: Max messages processed globally per global_window seconds.
            global_window: Time window in seconds for global limit.
        """
        self._per_user_limit = per_user_limit
        self._per_user_window = per_user_window
        self._global_limit = global_limit
        self._global_window = global_window

        # uid -> deque of timestamps
        self._user_timestamps: dict[str, deque] = defaultdict(deque)
        # Global timestamp deque
        self._global_timestamps: deque = deque()

        # Thread safety lock
        self._lock = threading.Lock()

        # Stats
        self._rejected_count: int = 0

    def allow(self, uid: str = "") -> bool:
        """Check if a message from *uid* should be processed.

        Returns True if the message is allowed, False if rate-limited.
        Thread-safe.
        """
        with self._lock:
            now = time.time()

            # Check global rate limit
            self._cleanup(self._global_timestamps, self._global_window)
            if len(self._global_timestamps) >= self._global_limit:
                self._rejected_count += 1
                logger.debug(f"Global rate limit hit (rejected #{self._rejected_count})")
                return False

            # Check per-user rate limit
            if uid:
                self._cleanup(self._user_timestamps[uid], self._per_user_window)
                if len(self._user_timestamps[uid]) >= self._per_user_limit:
                    self._rejected_count += 1
                    logger.debug(f"User {uid} rate limited (rejected #{self._rejected_count})")
                    return False
                self._user_timestamps[uid].append(now)

            self._global_timestamps.append(now)
            return True

    def _cleanup(self, dq: deque, window: float):
        """Remove timestamps older than *window* seconds."""
        now = time.time()
        while dq and now - dq[0] > window:
            dq.popleft()

    @property
    def rejected_count(self) -> int:
        return self._rejected_count

    def reset(self):
        """Clear all rate limiting state. Thread-safe."""
        with self._lock:
            self._user_timestamps.clear()
            self._global_timestamps.clear()
            self._rejected_count = 0
