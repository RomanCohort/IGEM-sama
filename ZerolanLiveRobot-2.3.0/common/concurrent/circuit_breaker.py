"""Thread-safe Circuit Breaker for external service calls.

Protects the system from cascading failures when external services (LLM, TTS,
ASR, Milvus) become unresponsive. Implements the classic three-state pattern:

  CLOSED (healthy) -> OPEN (failing, reject fast) -> HALF_OPEN (probing) -> CLOSED

Usage:
    cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)

    if cb.allow():
        try:
            result = external_service.call()
            cb.record_success()
        except Exception:
            cb.record_failure()
            # handle failure
    else:
        # circuit is open, use fallback
        result = fallback_response()
"""

import threading
import time
from typing import Optional

from loguru import logger


class CircuitBreaker:
    """Thread-safe circuit breaker for protecting external service calls.

    Args:
        failure_threshold: Number of consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait before transitioning from OPEN to HALF_OPEN.
        name: Optional name for logging.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "unnamed",
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._name = name

        self._state = self.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_allowed: int = 0  # tracks probe requests in HALF_OPEN

        # Metrics
        self._total_calls: int = 0
        self._rejected_calls: int = 0

        self._lock = threading.Lock()

    def allow(self) -> bool:
        """Check if a request should be attempted.

        Returns:
            True if the request should proceed, False if the circuit is open
            and the request should be rejected fast.
        """
        with self._lock:
            self._total_calls += 1

            if self._state == self.CLOSED:
                return True

            if self._state == self.OPEN:
                # Check if enough time has passed to try again
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self._recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_allowed = 0
                    logger.info(f"CircuitBreaker[{self._name}]: OPEN -> HALF_OPEN")
                    # Allow one probe request
                    self._half_open_allowed += 1
                    return True
                self._rejected_calls += 1
                return False

            if self._state == self.HALF_OPEN:
                # Allow limited probe requests
                if self._half_open_allowed < 1:
                    self._half_open_allowed += 1
                    return True
                self._rejected_calls += 1
                return False

            return False

    def record_success(self):
        """Record a successful call. Transitions HALF_OPEN -> CLOSED."""
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._state = self.CLOSED
                self._failure_count = 0
                logger.info(f"CircuitBreaker[{self._name}]: HALF_OPEN -> CLOSED (service recovered)")

    def record_failure(self):
        """Record a failed call. May transition CLOSED -> OPEN or HALF_OPEN -> OPEN."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                logger.warning(f"CircuitBreaker[{self._name}]: HALF_OPEN -> OPEN (probe failed)")

            elif self._state == self.CLOSED:
                if self._failure_count >= self._failure_threshold:
                    self._state = self.OPEN
                    logger.warning(
                        f"CircuitBreaker[{self._name}]: CLOSED -> OPEN "
                        f"({self._failure_count} consecutive failures)"
                    )

    @property
    def state(self) -> str:
        """Current circuit state."""
        with self._lock:
            return self._state

    @property
    def stats(self) -> dict:
        """Return current metrics."""
        with self._lock:
            return {
                "name": self._name,
                "state": self._state,
                "failure_count": self._failure_count,
                "total_calls": self._total_calls,
                "rejected_calls": self._rejected_calls,
            }
