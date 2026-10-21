from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from scripts.seed_database import seed


ROOT = Path(__file__).resolve().parents[2]


def test_event_and_incident_read_endpoints(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'api.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    with TestClient(create_app(url)) as client:
        payload = {
            "event_id": "EV-API-1",
            "event_type": "SUPPLIER_DELAY",
            "source_system": "integration_test",
            "entity_id": "PO-X7-1001",
            "timestamp": "2026-01-15T09:00:00Z",
            "payload": {"supplier_id": "SUP-A", "component_id": "MOTOR-X7", "order_id": "PO-X7-1001"},
            "idempotency_key": "api-delay-1",
        }
        created = client.post("/events", json=payload)
        assert created.status_code == 201
        incident_id = created.json()["incident_id"]

        duplicate = client.post("/events", json={**payload, "event_id": "EV-API-DUP"})
        assert duplicate.status_code == 201
        assert duplicate.json()["duplicate"] is True
        assert duplicate.json()["incident_id"] == incident_id

        incident = client.get(f"/incidents/{incident_id}")
        assert incident.status_code == 200
        assert incident.json()["component_id"] == "MOTOR-X7"
        assert client.get(f"/incidents/{incident_id}/status").json()["status"] == "NEW"
        assert client.get(f"/incidents/{incident_id}/report").json()["execution_plan"] is None


def test_api_rejects_unknown_supplier(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'api-invalid.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    with TestClient(create_app(url)) as client:
        response = client.post("/events", json={
            "event_type": "SUPPLIER_DELAY", "source_system": "test", "entity_id": "UNKNOWN",
            "timestamp": "2026-01-15T09:00:00Z", "payload": {"supplier_id": "UNKNOWN"},
            "idempotency_key": "unknown-supplier",
        })
        assert response.status_code == 422
        assert "unknown supplier_id" in response.json()["detail"]


def test_evaluation_endpoint_persists_measured_results(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'api-evaluation.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    with TestClient(create_app(url)) as client:
        event = client.post("/events", json={
            "event_type": "SUPPLIER_DELAY", "source_system": "evaluation_test", "entity_id": "PO-X7-1001",
            "timestamp": "2026-01-15T09:00:00Z",
            "payload": {"supplier_id": "SUP-A", "component_id": "MOTOR-X7", "order_id": "PO-X7-1001"},
            "idempotency_key": "evaluation-incident",
        })
        assert event.status_code == 201

        response = client.post("/evaluations/run")
        assert response.status_code == 201
        result = response.json()
        assert result["status"] == "COMPLETED"
        assert result["metrics"]["workflow_completion_rate"]["value_percent"] == 100.0
        assert result["metrics"]["reflection_issue_detection_rate"]["measured"] is False
        assert len(client.get("/evaluations").json()) == 1


def test_live_run_requires_model_credential_without_creating_fake_logs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    url = f"sqlite:///{tmp_path / 'api-live-run.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    with TestClient(create_app(url)) as client:
        created = client.post("/events", json={
            "event_type": "SUPPLIER_DELAY", "source_system": "run_test", "entity_id": "PO-X7-1001",
            "timestamp": "2026-01-15T09:00:00Z",
            "payload": {"supplier_id": "SUP-A", "component_id": "MOTOR-X7", "order_id": "PO-X7-1001"},
            "idempotency_key": "run-incident",
        })
        incident_id = created.json()["incident_id"]
        response = client.post(f"/incidents/{incident_id}/run")
        assert response.status_code == 503
        assert "API_KEY" in response.json()["detail"]
        assert client.get(f"/incidents/{incident_id}/workflow").json() == {
            "workflow_runs": [], "agent_runs": []
        }
