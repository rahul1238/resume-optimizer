# Local Jenkins CI/CD

The root `Jenkinsfile` verifies every build. A successful build of `main` then
deploys that exact commit to Render, waits for it to become live, rebuilds the
web app with production browser configuration, and deploys it to Firebase
Hosting. Other branches stop after CI and do not read deployment credentials.

Jenkins itself is free; Docker Desktop performs the container builds and Docker
Scout performs the vulnerability gate.

## Prerequisites

Install Jenkins LTS on the development machine and make these commands available
to the Jenkins service user:

- `git`
- Node.js 22 LTS and `npm`
- `docker`, with Docker Desktop running
- `docker scout`

The pipeline adds the standard Apple Silicon Homebrew and `/usr/local/bin` paths.
If a command is installed elsewhere, add that directory under **Manage Jenkins >
System > Global properties > Environment variables**.

Install only the suggested Jenkins plugins during initial setup, plus
**Pipeline**, **Git**, and **Credentials Binding** if they are not already
present. No paid Jenkins plugin or hosted Jenkins service is required.

## Add deployment credentials

Open **Manage Jenkins > Credentials > System > Global credentials** and create
these credentials with the exact IDs shown:

| ID | Kind | Value |
| --- | --- | --- |
| `render-api-key` | Secret text | Render API key from **Account Settings > API Keys** |
| `render-service-id` | Secret text | API service ID beginning with `srv-` |
| `firebase-service-account` | Secret file | Dedicated Firebase deployer service-account JSON |
| `web-production-env` | Secret file | Production Next.js public configuration |

Grant the deployer service account only **Firebase Hosting Admin**
(`roles/firebasehosting.admin`) and **API Keys Viewer**
(`roles/serviceusage.apiKeysViewer`). Do not reuse the API runtime service
account. The production environment file must contain:

```dotenv
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=project-id.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=project-id.firebasestorage.app
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
NEXT_PUBLIC_FIREBASE_APP_ID=...
NEXT_PUBLIC_API_BASE_URL=https://resume-optimizer-api.onrender.com
```

These `NEXT_PUBLIC_*` values are browser configuration, not server secrets. The
credential-file binding keeps environment-specific values out of the repository
and removes the temporary copy after each build.

## Create the job

1. Select **New Item**, enter `resume-optimizer`, and choose **Pipeline**.
2. Under **Pipeline**, select **Pipeline script from SCM**.
3. Choose **Git**, enter the repository URL, and add GitHub credentials only if
   the repository is private.
4. Set the branch to `*/main` and the script path to `Jenkinsfile`.
5. Save and select **Build Now**.

The pipeline checks out a clean workspace, tests its deployment helper, runs all
API tests in the same Tectonic-enabled Linux runtime used by production, lints
and exports the web app, builds the production API image for Linux AMD64, and
fails on critical or high Docker Scout findings. Placeholder public Firebase
values are used only for the CI build.

On `main`, Jenkins asks Render to deploy `GIT_COMMIT` and polls until the deploy
is live. Only then does it build with `web-production-env` and authenticate the
Firebase CLI through `GOOGLE_APPLICATION_CREDENTIALS`. Any API or Hosting
failure fails the Jenkins build.

For automatic builds, configure a GitHub webhook after the Jenkins job works
manually. Do not expose a Jenkins instance running on a personal machine directly
to the public internet; that is a separate hardening step.
