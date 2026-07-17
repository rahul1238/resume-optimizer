# Production environment

Configure backend secrets in the hosting provider's environment settings. Never
commit production values or pass them as Docker build arguments.

## API variables

| Variable | Secret | Production value |
| --- | --- | --- |
| `APP_ENV` | No | `production` |
| `CORS_ALLOWED_ORIGINS` | No | JSON list containing the Firebase Hosting URL |
| `FIREBASE_PROJECT_ID` | No | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Yes | Complete service-account JSON on one line |
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `R2_ENDPOINT_URL` | No | S3-compatible storage endpoint |
| `R2_ACCESS_KEY_ID` | Yes | Storage access key ID |
| `R2_SECRET_ACCESS_KEY` | Yes | Storage secret access key |
| `R2_BUCKET_NAME` | No | Resume object bucket |

The API refuses to start in production when a required value is missing, the
Firebase credential JSON is malformed, or CORS contains a wildcard, localhost,
or a non-HTTPS origin. `FIREBASE_SERVICE_ACCOUNT_PATH` remains available as a
local alternative to the JSON secret.

## Web variables

The `NEXT_PUBLIC_*` Firebase values are intentionally public Firebase client
configuration. Set them as build-time variables for the Next.js application,
along with `NEXT_PUBLIC_API_BASE_URL` pointing to the deployed HTTPS API URL.

Use [the web environment example](../../apps/web/.env.local.example) as the
complete frontend checklist. Firebase Security Rules and backend ID-token
verification provide access control; the public web API key is not a secret.

Continue with the [Render API deployment](render.md) after preparing these
values, then configure [Firebase Hosting](firebase-hosting.md) for the web app.
