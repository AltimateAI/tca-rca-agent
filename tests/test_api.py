"""Tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient
from tca_api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_root_endpoint():
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "endpoints" in data


def test_analyze_endpoint():
    """Test RCA analysis endpoint."""
    response = client.post(
        "/api/rca/analyze",
        json={
            "issue_id": "test-123",
            "sentry_org": "test-org"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "analysis_id" in data
    assert data["status"] == "analyzing"


def test_analyze_endpoint_validation():
    """Test that analyze endpoint validates input."""
    # Missing required field
    response = client.post(
        "/api/rca/analyze",
        json={"sentry_org": "test-org"}
    )

    assert response.status_code == 422  # Validation error


def test_history_endpoint():
    """Test history retrieval."""
    response = client.get("/api/rca/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_stats_endpoint():
    """Test stats endpoint."""
    response = client.get("/api/rca/stats")
    assert response.status_code == 200

    data = response.json()
    assert "total_patterns" in data
    assert "total_antipatterns" in data
