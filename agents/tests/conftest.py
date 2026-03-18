"""Shared fixtures for ChaosGuard agent tests."""

import uuid

import pytest


@pytest.fixture
def scan_id():
    """A deterministic scan UUID for reproducible tests."""
    return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def experiment_id():
    """A deterministic experiment UUID for reproducible tests."""
    return "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def sample_experiment_config():
    """A valid experiment plan dict within default safety limits."""
    return {
        "faults": [
            {
                "target_service": "api",
                "fault_type": "network_delay",
                "params": {"delay_ms": 500, "jitter_ms": 100},
            },
            {
                "target_service": "db",
                "fault_type": "cpu_stress",
                "params": {"duration_s": 30, "cores": 2},
            },
        ],
        "total_duration_s": 120,
    }


@pytest.fixture
def oversized_experiment_config():
    """An experiment plan that exceeds the default blast-radius limit."""
    return {
        "faults": [
            {"target_service": f"svc-{i}", "fault_type": "network_delay", "params": {}}
            for i in range(5)
        ],
        "total_duration_s": 600,
    }


@pytest.fixture
def mock_redis(mocker):
    """A mocked Redis client that behaves synchronously for unit tests."""
    mock = mocker.MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    return mock


@pytest.fixture
def mock_docker_client(mocker):
    """A mocked Docker client."""
    client = mocker.MagicMock()
    container = mocker.MagicMock()
    container.id = "abc123def456"
    container.status = "running"
    client.containers.get.return_value = container
    client.containers.run.return_value = container
    return client
