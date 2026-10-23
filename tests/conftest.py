import pytest
from fastapi.testclient import TestClient

from fulvo.app import app


@pytest.fixture
def client():
    """Cliente HTTP de prueba, creado de nuevo para cada test."""
    return TestClient(app)
