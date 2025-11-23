import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit is open"""


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_duration: int = 60,
        success_threshold: int = 2,
        name: str = "Service",
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Failures before opening circuit
            timeout_duration: Seconds before attempting recovery
            success_threshold: Successes needed to close circuit from half-open
            name: Service name for logging
        """
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration
        self.success_threshold = success_threshold
        self.name = name

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

        logger.info(
            f"Circuit breaker initialized for {name}: "
            f"threshold={failure_threshold}, timeout={timeout_duration}s"
        )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Async function to call
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenException: If circuit is open
        """
        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker is OPEN for {self.name}. "
                    f"Retry after {self._time_until_retry():.0f}s"
                )

        try:
            # Execute the function
            result = await func

            # Record success
            self._on_success()

            return result

        except Exception:
            # Record failure
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.debug(
                f"Circuit breaker {self.name}: Success in HALF_OPEN "
                f"({self.success_count}/{self.success_threshold})"
            )

            # If enough successes, close the circuit
            if self.success_count >= self.success_threshold:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0

        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        logger.warning(
            f"Circuit breaker {self.name}: Failure recorded "
            f"({self.failure_count}/{self.failure_threshold})"
        )

        if self.state == CircuitState.HALF_OPEN:
            # Single failure in half-open state reopens circuit
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN")
            self.state = CircuitState.OPEN
            self.success_count = 0

        elif self.state == CircuitState.CLOSED:
            # Too many failures, open the circuit
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker {self.name}: CLOSED -> OPEN "
                    f"(threshold reached: {self.failure_count})"
                )
                self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True

        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.timeout_duration

    def _time_until_retry(self) -> float:
        """Calculate seconds until retry is allowed"""
        if self.last_failure_time is None:
            return 0

        time_since_failure = datetime.now() - self.last_failure_time
        remaining = self.timeout_duration - time_since_failure.total_seconds()
        return max(0, remaining)

    def reset(self):
        """Manually reset circuit breaker"""
        logger.info(f"Circuit breaker {self.name}: Manual reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "time_until_retry": self._time_until_retry() if self.state == CircuitState.OPEN else 0,
        }


class MultiServiceCircuitBreaker:
    """
    Manage circuit breakers for multiple services
    """

    def __init__(self):
        self.breakers = {}

    def get_or_create(
        self, service_name: str, failure_threshold: int = 5, timeout_duration: int = 60
    ) -> CircuitBreaker:
        """
        Get existing or create new circuit breaker for service

        Args:
            service_name: Service identifier
            failure_threshold: Failures before opening
            timeout_duration: Timeout in seconds

        Returns:
            Circuit breaker instance
        """
        if service_name not in self.breakers:
            self.breakers[service_name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                timeout_duration=timeout_duration,
                name=service_name,
            )

        return self.breakers[service_name]

    def get_all_status(self) -> dict:
        """Get status of all circuit breakers"""
        return {name: breaker.get_status() for name, breaker in self.breakers.items()}

    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            breaker.reset()


# Global circuit breaker manager
circuit_breaker_manager = MultiServiceCircuitBreaker()
