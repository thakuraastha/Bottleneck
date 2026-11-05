# Deploy Bottleneck from GitHub to Google Cloud Run

This deployment runs the dashboard, API, ADK agents, CrewAI crew, LangGraph supervisor, and A2A endpoint in a single public Cloud Run service. No process needs to run on the presentation laptop.

## One-time Google Cloud setup

1. Open **Google Cloud Console → Cloud Run** and select the project that will own the demo.
2. Choose **Deploy container → Continuously deploy from a repository**.
3. Connect GitHub and select `thakuraastha/Bottleneck`, branch `^main$`.
4. Select **Dockerfile** as the build type and `/Dockerfile` as the source location.
5. Use service name `bottleneck`, a nearby region (for example `asia-south1`), and allow unauthenticated access so the faculty can open the dashboard.

Cloud Run will use Cloud Build and Artifact Registry for builds from GitHub. Subsequent pushes to `main` create new revisions automatically.

## Required service settings

Expand **Containers, Networking, Security** and configure:

| Setting | Value | Reason |
|---|---:|---|
| Container port | `8080` | Matches Cloud Run's `PORT` and the Docker image |
| Memory | `2 GiB` | Allows the API and agent frameworks to run together |
| CPU | `2` | Reduces model orchestration latency |
| Request timeout | `300 seconds` | Leaves room for model-provider latency |
| Maximum instances | `1` | Prevents two instances from using separate temporary SQLite databases |
| Minimum instances | `1` for the live demo, otherwise `0` | Avoids a cold start during the presentation; setting `1` costs money while idle |
| Maximum concurrent requests | `20` | Allows dashboard polling while one workflow is active |
| Billing | **Instance-based** | Keeps CPU available for the background workflow after `/run` returns |

Do not set concurrency to `1`: the dashboard polls status and agent output while the workflow runs.

## Gemini secret

Store the key in **Secret Manager**, not as plain text in GitHub or the Docker image.

1. Create a secret named `bottleneck-gemini-api-key` with the Gemini API key as its value.
2. Grant the Cloud Run service identity **Secret Manager Secret Accessor** for that secret.
3. In the Cloud Run container settings, choose **Variables & Secrets → Reference a secret**.
4. Expose it as `GEMINI_API_KEY`, select `bottleneck-gemini-api-key`, and pin the current numeric secret version.

Add these non-secret environment variables:

```text
BOTTLENECK_ENVIRONMENT=production
BOTTLENECK_MODEL_STAGE_TIMEOUT_SECONDS=35
BOTTLENECK_MODEL_RETRY_ATTEMPTS=1
```

After the first deployment, copy the service URL and add it as:

```text
BOTTLENECK_CLOUD_DEPLOYMENT_URL=https://YOUR-SERVICE-URL
```

Redeploy that configuration as a new revision. The internal A2A endpoint automatically uses `127.0.0.1:$PORT/a2a`, so it does not depend on the public hostname.

## Verify before presenting

Open the Cloud Run URL and check:

1. `/health` returns `{"status":"ok"}`.
2. `/docs` opens the FastAPI documentation.
3. The dashboard Overview shows seeded incidents.
4. On **Incidents**, start one investigation.
5. On **Agents**, confirm cards move through running to completed and show ADK, CrewAI, and LangGraph outputs.
6. On **Recovery**, approve or reject a strategy.
7. On **Audit/Evaluation**, show the persisted evidence, callbacks, timing, token, and cost records.

## Presentation-day reset

Because the demo configuration uses temporary SQLite storage, deploy a new revision to start from a clean seeded database. In Cloud Run, open the service, choose **Edit & deploy new revision**, change the revision suffix (for example `faculty-demo-2`), and deploy. Do this before the presentation rather than during it.

## Durable production upgrade

The temporary database is deliberately restricted to one instance. To preserve approvals and audit history across revisions or scale beyond one instance, use a managed SQL database and set its SQLAlchemy connection string in `BOTTLENECK_DATABASE_URL`. Test the database migration and connection separately before changing the demo service.
