# Render API deployment

The root `render.yaml` defines one Docker web service in Render's Singapore
region. It uses the Free instance type and does not create a database, disk,
worker, or other billable resource.

## Create the service

1. Push the repository and open the Render Dashboard.
2. Select **New > Blueprint** and connect this repository.
3. Keep the detected Blueprint path as `render.yaml`.
4. Enter every value marked **Prompted** using the
   [environment checklist](environment.md).
5. Review that the workspace is **Hobby** and the instance type is **Free**.
6. For strict zero spend, do not attach a payment method; Render suspends free
   services or builds when included usage is exhausted instead of charging.
7. Apply the Blueprint and wait for `/api/v1/health/` to report success.

For `CORS_ALLOWED_ORIGINS`, enter a JSON list containing the deployed Firebase
Hosting origin, for example `["https://project-id.web.app"]`. Paste the complete
Firebase service-account file contents into `FIREBASE_SERVICE_ACCOUNT_JSON`.

## Free-tier behavior

Render Free web services spin down after 15 minutes without inbound traffic and
can take about a minute to wake. The filesystem is ephemeral, which is safe for
this API because durable resume data is stored in Firestore and object storage.
Do not add synthetic keep-alive requests: they consume the workspace's included
instance hours and bandwidth without removing the Free tier's other limits.

Automatic Render deploys are disabled in the Blueprint. The initial Blueprint
creation performs the first deploy. Subsequent `main` deployments are triggered
through Render's API only after Jenkins tests and image checks pass. Jenkins
sends the exact Git commit SHA and polls its deployment until it reaches `live`;
a failed, canceled, unknown, or timed-out deployment fails the pipeline.

Create a Render API key under **Account Settings > API Keys**, then add it and
the service ID to Jenkins as described in [local Jenkins CI/CD](jenkins.md).
Render API keys can access the workspaces available to their owner, so never put
the key in the repository or a frontend environment file.
