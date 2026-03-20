from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    with patch("backend.main.get_db") as mock:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.cursor.return_value.fetchall.return_value = []
        mock.return_value = mock_conn
        yield mock


@pytest.fixture
def client():
    with patch("backend.main.get_db") as mock:
        mock_conn = MagicMock()
        mock.return_value = mock_conn
        from backend.main import app
        yield TestClient(app)


@pytest.fixture
def sample_url():
    return "https://www.amazon.in/dp/B09V3KXJPB"


@pytest.fixture
def sample_prices():
    return [1499.0, 1599.0, 1399.0, 1449.0, 1499.0, 1549.0]
