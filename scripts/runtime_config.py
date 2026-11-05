from __future__ import annotations

import os


def configure_platform_environment() -> None:
    """Translate hosting metadata into the application's portable settings."""
    port = os.getenv("PORT", "8000")
    if os.getenv("K_SERVICE"):
        # Cloud Run's writable filesystem is ephemeral. A managed database URL
        # can override this for durable deployments.
        os.environ.setdefault("BOTTLENECK_DATABASE_URL", "sqlite:////tmp/bottleneck.db")
        os.environ.setdefault(
            "BOTTLENECK_A2A_SUPPLIER_URL",
            f"http://127.0.0.1:{port}/a2a",
        )

    if os.getenv("RENDER_EXTERNAL_URL"):
        external_url = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
        os.environ.setdefault("BOTTLENECK_A2A_SUPPLIER_URL", f"{external_url}/a2a")
        os.environ.setdefault("BOTTLENECK_CLOUD_DEPLOYMENT_URL", external_url)

    if os.getenv("VERCEL"):
        os.environ.setdefault("BOTTLENECK_DATABASE_URL", "sqlite:////tmp/bottleneck.db")
        vercel_host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
        if vercel_host:
            cloud_url = f"https://{vercel_host}"
            os.environ.setdefault("BOTTLENECK_A2A_SUPPLIER_URL", f"{cloud_url}/a2a")
            os.environ.setdefault("BOTTLENECK_CLOUD_DEPLOYMENT_URL", cloud_url)
