# Firebase Hosting deployment

The web application is exported as static HTML, CSS, and JavaScript into
`apps/web/out`. Firebase Hosting serves those files directly; this setup does
not provision Cloud Functions, Cloud Run, or Firebase App Hosting.

## Prepare Firebase

1. Keep the Firebase project on the Spark plan.
2. In **Authentication > Settings > Authorized domains**, add the Hosting
   domains (`project-id.web.app` and `project-id.firebaseapp.com`).
3. Set the frontend variables from `apps/web/.env.local.example` in the Jenkins
   build environment. Set `NEXT_PUBLIC_API_BASE_URL` to the Render HTTPS URL.

All `NEXT_PUBLIC_*` values are embedded into the browser bundle at build time.
The Firebase web configuration is public by design; the Jenkins credential used
to deploy Hosting must remain secret.

## Build and verify

From the repository root:

```bash
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run build
```

The build must produce `apps/web/out/index.html`, `login.html`, and
`dashboard.html`. Deploy only Hosting from the repository root:

```bash
firebase deploy --only hosting --project your-firebase-project-id
```

Jenkins invokes Firebase CLI `15.24.0` explicitly, so deployments do not depend
on a globally installed version. It authenticates with Application Default
Credentials from its `firebase-service-account` secret-file credential;
interactive login and legacy `FIREBASE_TOKEN` credentials are not used.

Firebase Hosting on Spark includes no-cost usage quotas and stops
serving after those quotas are exhausted. Do not link a billing account, because
that automatically upgrades the project from Spark to the Blaze plan.

Configure the credentials in [local Jenkins CI/CD](jenkins.md) before running a
`main` build.
