from __future__ import annotations

import os

from scripts.runtime_config import configure_platform_environment


def test_cloud_run_uses_runtime_port_for_internal_a2a(monkeypatch) -> None:
    monkeypatch.setenv("K_SERVICE", "bottleneck")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.delenv("BOTTLENECK_DATABASE_URL", raising=False)
    monkeypatch.delenv("BOTTLENECK_A2A_SUPPLIER_URL", raising=False)

    configure_platform_environment()

    assert os.environ["BOTTLENECK_DATABASE_URL"] == "sqlite:////tmp/bottleneck.db"
    assert os.environ["BOTTLENECK_A2A_SUPPLIER_URL"] == "http://127.0.0.1:8080/a2a"


def test_cloud_run_preserves_managed_database_and_a2a_overrides(monkeypatch) -> None:
    monkeypatch.setenv("K_SERVICE", "bottleneck")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("BOTTLENECK_DATABASE_URL", "postgresql+psycopg://managed")
    monkeypatch.setenv("BOTTLENECK_A2A_SUPPLIER_URL", "https://agents.example/a2a")

    configure_platform_environment()

    assert os.environ["BOTTLENECK_DATABASE_URL"] == "postgresql+psycopg://managed"
    assert os.environ["BOTTLENECK_A2A_SUPPLIER_URL"] == "https://agents.example/a2a"
