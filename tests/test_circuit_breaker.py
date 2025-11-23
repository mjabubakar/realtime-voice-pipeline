import asyncio

import pytest


@pytest.mark.asyncio
async def test_circuit_breaker_closed_success(circuit_breaker):
    """Test circuit breaker in closed state with success"""

    async def success_func():
        return "success"

    result = await circuit_breaker.call(success_func())

    assert result == "success"
    assert circuit_breaker.state.value == "closed"
    assert circuit_breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures(circuit_breaker):
    """Test circuit breaker opens after threshold failures"""

    async def failing_func():
        raise Exception("Service error")

    # Trigger failures to open circuit
    for _ in range(circuit_breaker.failure_threshold):
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_func())

    assert circuit_breaker.state.value == "open"
    assert circuit_breaker.failure_count == circuit_breaker.failure_threshold


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open(circuit_breaker):
    """Test circuit breaker blocks requests when open"""
    from datetime import datetime

    from app.utils.circuit_breaker import CircuitBreakerOpenException, CircuitState

    # Force circuit open
    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.last_failure_time = datetime.now()

    # Create a simple async function that returns an awaitable
    async def some_func():
        await asyncio.sleep(0)
        return "result"

    # The circuit breaker call method expects an awaitable
    # Pass the coroutine itself (the result of calling some_func())
    with pytest.raises(CircuitBreakerOpenException):
        # Create the coroutine and pass it to call
        coro = some_func()
        await circuit_breaker.call(coro)


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery(circuit_breaker):
    """Test circuit breaker recovery through half-open state"""
    from datetime import datetime, timedelta

    from app.utils.circuit_breaker import CircuitState

    # Set circuit to open with old failure time
    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=100)

    async def success_func():
        return "success"

    # First call should transition to half-open
    await circuit_breaker.call(success_func())
    assert circuit_breaker.state == CircuitState.HALF_OPEN

    # Enough successes should close circuit
    for _ in range(circuit_breaker.success_threshold - 1):
        await circuit_breaker.call(success_func())

    assert circuit_breaker.state == CircuitState.CLOSED


def test_circuit_breaker_status(circuit_breaker):
    """Test circuit breaker status reporting"""
    status = circuit_breaker.get_status()

    assert "name" in status
    assert "state" in status
    assert "failure_count" in status
    assert status["name"] == "Test"


def test_circuit_breaker_manual_reset(circuit_breaker):
    """Test manual circuit breaker reset"""
    from app.utils.circuit_breaker import CircuitState

    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.failure_count = 10

    circuit_breaker.reset()

    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_fails(circuit_breaker):
    """Test circuit reopens on failure in half-open state"""
    from datetime import datetime, timedelta

    from app.utils.circuit_breaker import CircuitState

    circuit_breaker.state = CircuitState.OPEN
    circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=100)

    async def success_func():
        return "success"

    async def failing_func():
        raise Exception("Still failing")

    # Transition to half-open
    await circuit_breaker.call(success_func())
    assert circuit_breaker.state == CircuitState.HALF_OPEN

    # Failure should reopen circuit
    with pytest.raises(Exception):
        await circuit_breaker.call(failing_func())

    assert circuit_breaker.state == CircuitState.OPEN
