"""Shared fixtures for backend API tests."""
import json
import os
import sys
from unittest.mock import MagicMock

import pytest

# Set env vars before importing app so pydantic-settings picks them up
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def make_response():
    """Return a factory that builds mock Anthropic API responses."""
    def _make(payload):
        text = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
        resp = MagicMock()
        resp.content = [MagicMock(text=text)]
        return resp
    return _make
