# ClearClause public deployment runbook

**Purpose:** record the live Google Cloud pilot, its repeatable configuration, and its remaining launch gates. The user explicitly approved the temporary generated `run.app` URL and accepted that Cloud Armor IP filtering is absent until a controlled domain is available.

## Live deployment — 2026-09-26

| Item | Current state |
|---|---|
| Public URL | [https://clearclause-api-ye2sfsdqnq-uc.a.run.app](https://clearclause-api-ye2sfsdqnq-uc.a.run.app) |
| Cloud Run | `clearclause-api`, `us-central1`, revision `clearclause-api-00005-9wj`, public `run.app` ingress |
| Model | Gemini 3.5 Flash-Lite on Vertex `us` multi-region endpoint |
| Database | Firestore Native `(default)`, `us-central1`, delete protection enabled; quota TTL `ACTIVE` |
| Identity | Firebase email/password enabled; analysis requires verified email; Firebase Auth App Check enforcement enabled |
| Abuse controls | reCAPTCHA Enterprise App Check (site key restricted to deployed hostname), backend token verification, Firestore rolling per-user quota (8 hourly/30 daily weighted units) |
| Cloud Run limits | 0 minimum / 3 maximum instances, concurrency 4, 1 vCPU, 1 GiB RAM |
| Runtime identity | `clearclause-runtime@ai-legal-help.iam.gserviceaccount.com`, roles `aiplatform.user` and `datastore.user` only |
| Artifact | `us-central1-docker.pkg.dev/ai-legal-help/clearclause/clearclause-api@sha256:3da3918b1362e40e818044d31dcbd17461be7f69b10d9c5ca36b82c5e871bbba` |
| Smoke check | `/` returned 200; `/api/health` returned `ok`; `/api/config` confirms production Firebase/App Check config |
| Residual risk | No Cloud Armor or IP-level edge throttling; user accepted this temporary route. Keep a small pilot and synthetic/authorized PDFs until privacy/provider/legal review is complete. |

The current revision also fixes a confirmed Firebase referrer-policy conflict and invalid Firestore quota serialization. The restricted browser key requires the allowed origin, so responses now use `strict-origin-when-cross-origin`. Quota events use map records instead of unsupported nested arrays. Health/config checks do not prove the sign-in success path; a fresh browser sign-in and synthetic-document flow still need confirmation.

The Firebase Web API key and reCAPTCHA site key are public client values, constrained to the deployed host and required APIs; neither grants Vertex access. Vertex uses the Cloud Run service account and ADC. No service-account key was created. Cloud Build `6b259e17-65fe-475c-819b-0e1f7d78099f` passed the configured lint, format, coverage, test and image-build steps before this deployment. Local evidence: 40 tests, 80.33% Python statement coverage. Live developer-ADC diagnostics passed all three synthetic Vertex workflows and Firestore quota writes; they are distinct from authenticated browser acceptance. See `EVALUATION_UPDATE.md` for scope and remaining gates.

## Pre-provisioning baseline — 2026-09-26

Read-only `gcloud` inventory was run against project `ai-legal-help`.

| Item | Observed state |
|---|---|
| Selected gcloud project | `ai-legal-help` |
| Project lifecycle | `ACTIVE` |
| Public domain | User confirmed none is available currently |
| Enabled relevant APIs | Vertex AI, Cloud Run, Cloud Build, Artifact Registry, Identity Toolkit, IAM, Logging, Monitoring, Secret Manager |
| Required APIs still missing | Firestore, Firebase management, Firebase App Check, reCAPTCHA Enterprise, Compute/load balancing |
| Firestore API | Disabled; a Firestore database could not be listed until the API is enabled |
| Artifact Registry repositories | None listed |
| Cloud Run services | None listed |
| Service accounts | Only the default Compute Engine account was listed; no dedicated ClearClause runtime account |
| HTTPS load balancer / Cloud Armor | None listed |
| Cloud changes in this readiness pass | None |

This inventory is a historical point-in-time check from before the deployment. The live state is listed above.

The 10-blocker result above is historical, from before setup. APIs, Firebase, Firestore, Artifact Registry, runtime IAM, image build, and Cloud Run have since been provisioned. Do not rerun the database/account creation commands below against this existing project. Use them only as a reference for a separate environment.

## Remaining decisions and limits

1. **Data/residency approval:** Cloud Run and Firestore are in `us-central1`; Gemini inference uses Google's `us` multi-region endpoint. Confirm this US processing boundary and provider terms before handling sensitive legal documents.
2. **Full edge protection:** the current generated `run.app` endpoint is public without Cloud Armor IP filtering. A domain under your control is needed for the planned external HTTPS load balancer and managed certificate.
3. **Privacy and pilot owner:** identify the organization/contact that owns the privacy notice, support mailbox, retention statement, and incident response. Current notice is a prototype disclosure, not a reviewed privacy policy.
4. **Pilot audience:** sign-up is currently self-service. Start with a small known cohort and monitor abuse, quota denials, Cloud Run requests, Vertex usage, and billing.

## Workflow

```text
Browser
  ├─ Firebase Authentication (verified email)
  ├─ Firebase App Check / reCAPTCHA Enterprise
  └─ Firebase Authentication + reCAPTCHA Enterprise App Check
            └─ HTTPS Cloud Run run.app (public ingress; max 3 instances)
                     ├─ Firestore: hashed per-user quota events, TTL cleanup
                     └─ Vertex AI Gemini 3.5 Flash-Lite (`us` multi-region)
```

The browser never receives Vertex credentials. The application checks Firebase ID and App Check tokens, then reserves the user's Firestore quota before reading the multipart PDF. PDFs are bounded by request size, page count, and extracted text. The server calls Vertex AI through the Cloud Run service account and validates response structure and source citations before displaying a result. The user selected direct `run.app` publication for now; Cloud Armor/IP throttling is not present, so per-user quotas are the current analysis limit, not a network-edge defense.

## Current no-domain public path and future edge upgrade

This route is now live by user choice. Cloud Run ingress is `all`; anonymous users can load the UI, but analysis requires a verified Firebase account, valid App Check token, and available Firestore quota. Firebase Authentication also enforces App Check. Cloud Armor and IP rate limiting are absent. Keep access to a small cohort and documents synthetic or explicitly authorized. For a stronger public edge, obtain a controlled domain, place the service behind an external HTTPS load balancer with Cloud Armor, then change ingress to `internal-and-cloud-load-balancing` and verify direct `run.app` requests are blocked.

## Setup reference and current service operations

### 1. Run the read-only preflight

From PowerShell:

```powershell
cd D:\AI_legal_help
$env:GOOGLE_CLOUD_PROJECT = 'ai-legal-help'
$env:CLEARCLAUSE_REGION = 'us-central1'
$env:CLEARCLAUSE_VERTEX_LOCATION = 'us'
.\deployment\public-release-preflight.ps1 -ExposureMode runapp
```

The preflight reports missing APIs/resources and required browser configuration without enabling services or creating resources. It intentionally does not print Firebase values or account email addresses.

### 2. Enable only the required APIs

Already completed for `ai-legal-help`. The command below is retained as a reference for another project.

After region, domain, billing, and IAM ownership are confirmed, a project administrator can enable the APIs below. This is a cloud mutation; this runbook does not run it.

```powershell
gcloud services enable `
  aiplatform.googleapis.com `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  firestore.googleapis.com `
  identitytoolkit.googleapis.com `
  firebase.googleapis.com `
  firebaseappcheck.googleapis.com `
  recaptchaenterprise.googleapis.com `
  compute.googleapis.com `
  logging.googleapis.com `
  monitoring.googleapis.com `
  --project=ai-legal-help
```

Confirm exact API needs against the chosen Firebase and Cloud Armor setup; avoid enabling unrelated products. Check the current billing account and Vertex quota in Console. The budget alerts the user configured are notifications, not a hard spend cap.

### 3. Configure Firebase Authentication and App Check

Already configured for the live `run.app` host: email/password, verified-email analysis gate, Firebase Web app, API-key restrictions, reCAPTCHA Enterprise site key, 1-hour App Check token TTL, and App Check enforcement for Firebase Authentication.

In Firebase Console for `ai-legal-help`:

1. Enable Identity Platform / Firebase Authentication email and password.
2. Require verified email for analysis; configure password reset, authorized domains, email-enumeration protection, and account abuse controls.
3. Register the production Firebase Web app. Restrict its public API key to the production host and required Firebase APIs; this key is not a Vertex credential.
4. Create a reCAPTCHA Enterprise **web score key** for the production domain. Register it with Firebase App Check for this Web app. Never add `localhost` to the production key.
5. Monitor App Check metrics and confirm real browser tokens verify on the backend before enabling enforcement for the pilot.
6. Record the Firebase web API key, auth domain, app ID, and reCAPTCHA site key for the Cloud Run web configuration. These are client values; do not store Admin SDK private keys.

### 4. Create Firestore and quota cleanup

Already completed: Native `(default)` database in `us-central1` with delete protection; TTL is `ACTIVE` for `clearClauseRateLimits.expiresAt`.

After the region is approved, create Firestore Native mode in the selected region. This location is difficult to change later:

```powershell
gcloud firestore databases create `
  --database='(default)' `
  --location='<approved-region>' `
  --type=firestore-native `
  --delete-protection `
  --project=ai-legal-help
```

The app's quota records use collection group `clearClauseRateLimits` and timestamp field `expiresAt`. Configure TTL and wait for it to become active:

```powershell
gcloud firestore fields ttls update expiresAt `
  --collection-group=clearClauseRateLimits `
  --enable-ttl `
  --project=ai-legal-help
```

The app only writes hashed account keys and short-lived quota events. No user document or extracted legal text belongs in this database. Keep client-side Firestore rules closed; the server uses its runtime identity.

### 5. Create the dedicated runtime identity

Already completed. The runtime identity has only `roles/aiplatform.user` and `roles/datastore.user`; do not rerun the create command.

```powershell
gcloud iam service-accounts create clearclause-runtime `
  --display-name="ClearClause Cloud Run runtime" `
  --project=ai-legal-help

gcloud projects add-iam-policy-binding ai-legal-help `
  --member="serviceAccount:clearclause-runtime@ai-legal-help.iam.gserviceaccount.com" `
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding ai-legal-help `
  --member="serviceAccount:clearclause-runtime@ai-legal-help.iam.gserviceaccount.com" `
  --role="roles/datastore.user"
```

Review the project IAM policy and organization constraints before granting. Do not grant Owner/Editor, do not use the default Compute Engine account for the app, and do not create a JSON key. The runtime gets Vertex AI access and Firestore quota access only.

### 6. Create the image repository and build

Already completed: image digest shown in the live deployment table. The deployed image was built with a Docker-only Cloud Build command; it did not run the separate `cloudbuild.yaml` lint/test steps. Future candidates should use the checked pipeline and be deployed by immutable digest.

```powershell
gcloud artifacts repositories create clearclause `
  --repository-format=docker `
  --location='<approved-region>' `
  --project=ai-legal-help

cd D:\AI_legal_help
gcloud builds submit . `
  --config=cloudbuild.yaml `
  --region='<approved-region>' `
  --project=ai-legal-help `
  --substitutions="_REGION=<approved-region>,_REPOSITORY=clearclause"
```

`cloudbuild.yaml` uses Cloud Build's unique `BUILD_ID`, so a local source upload does not depend on a Git commit. The pipeline runs the configured lint, formatting, unit-test, and compile checks before building. A build is not a deployment. Confirm the build identity has only the build and Artifact Registry permissions it needs; scan the published image and resolve its immutable `sha256` digest before deployment. Deploy by digest, not a mutable `latest` tag.

### 7. Configure Cloud Run and production web values

The active service is deployed with the `run.app` ingress the user selected. The live `cloudrun-service.yaml` is a local-only snapshot and is excluded from Git because it contains project-specific Firebase browser configuration. For an existing service, export a local copy for review before using `services replace`:

```powershell
gcloud run services describe clearclause-api `
  --region=us-central1 `
  --project=ai-legal-help `
  --format=export | Set-Content -Encoding utf8 .\cloudrun-service.yaml
```

Keep this generated file local; do not commit it. When preparing a new deployment, review every project-specific field:

- `PROJECT_ID`, `REGION`, runtime service-account email, and Artifact Registry image digest.
- `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_APP_ID`, and `FIREBASE_APP_CHECK_SITE_KEY` from the production Firebase Web/App Check setup.
- Set `GOOGLE_CLOUD_LOCATION` to the approved Vertex endpoint location. The live demo uses `us`; confirm model availability and residency needs before changing it.

Keep `AUTH_MODE=firebase`, `RATE_LIMIT_BACKEND=firestore`, `APP_CHECK_REQUIRED=true`, `GENAI_ENABLED=true`, the selected ingress, instance/concurrency caps, and request limits. The temporary public mode uses ingress `all`; the full edge mode must change to `internal-and-cloud-load-balancing`. Do not put Firebase Admin credentials or Vertex keys in the manifest. The server obtains Google credentials through the attached service account and ADC.

Deploy the reviewed manifest:

```powershell
gcloud run services replace .\cloudrun-service.yaml `
  --project=ai-legal-help `
  --region='<approved-region>'
```

The external load balancer must invoke the backend. Only after confirming Cloud Run ingress is restricted to the load balancer, allow unauthenticated invocation at the Cloud Run IAM layer so the edge can serve the public page. The app still requires Firebase ID and App Check tokens for analysis routes:

```powershell
gcloud run services add-iam-policy-binding clearclause-api `
  --member=allUsers `
  --role=roles/run.invoker `
  --project=ai-legal-help `
  --region='<approved-region>'
```

This public invocation grant is safe only with the restricted ingress above and the Firebase/App Check application checks. If organization policy prevents the binding, resolve that policy with the project administrator; do not open direct internet ingress as a workaround.

### 8. Put the public domain behind HTTPS and Cloud Armor

Create a global external Application Load Balancer with a regional serverless NEG targeting `clearclause-api`. Attach a Google-managed TLS certificate for the controlled domain, reserve a global IPv4 address, add DNS records, and route the HTTPS frontend to the backend service. Attach a Cloud Armor security policy to that backend service. Do not add a direct Cloud Run domain mapping.

Start Cloud Armor rate rules in **preview** and examine real request logs before enforcement. Tune an IP-based throttle for the analysis paths for expected shared-network traffic. Cloud Armor limits are approximate and are intended for abuse/availability protection; rely on Firestore's account quota for the app's actual per-user limit. Apply rule priorities carefully so a higher-priority allow rule cannot bypass throttling.

### 9. Staging release gates

Use only synthetic PDFs and dedicated test identities. Keep the Vertex kill switch available (`GENAI_ENABLED=false`). Do not send real legal or client documents in staging.

- HTTPS certificate is active; every browser request uses HTTPS; correct DNS and security headers are present.
- The app home page and public Firebase config load through the load balancer. External requests to the Cloud Run `run.app` URL fail because ingress is load-balancer-only.
- Missing, expired, unverified, wrong-project, wrong-app, and missing App Check tokens fail closed before Vertex.
- Firestore quota reservations are atomic under concurrent requests, limits are enforced across instances, and Firestore failure blocks model calls.
- Vertex has a project quota and a bounded budget/alerting plan. Confirm model, region, quota, latency, and cost using synthetic content.
- Test oversized/chunked requests, malformed/encrypted/large PDFs, prompt injection, citation mismatches, cross-origin behavior, and safe error paths.
- Review service logs to confirm no prompts, extracted text, answers, file contents, or credentials are recorded.
- Complete privacy/provider-terms/legal review, WCAG 2.2 AA evaluation, dependency/image scan, rollback practice, and operational ownership.

### 10. Go / no-go

Public pilot may start only after every release gate is evidenced in `security_evaluation_report.md`. Limit the first cohort; keep monitoring, rollback, quota tuning, support, and incident response owners named. If a citation or authorization gate fails, disable GenAI and stop onboarding until corrected.

## Cost gate and trial-credit limits

Do not treat the existing monthly budget alert or the $300 trial credit as a spend cap. Vertex AI generation is usage-billed, the external load balancer and Cloud Armor Standard have their own charges, and Firestore TTL deletion operations are not included in the Firestore free quota. The exact monthly total depends on region, service configuration, traffic, document size, model tokens, and TTL activity; estimate it with the current pricing pages/calculator before provisioning, then watch actual billing. Keep the account quotas, Cloud Armor abuse throttle, low Cloud Run max-instance setting, Vertex quotas, and `GENAI_ENABLED=false` shutdown switch in place.

References: [Vertex AI generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), [Cloud Load Balancing pricing](https://cloud.google.com/load-balancing/pricing), [Cloud Armor pricing](https://cloud.google.com/vpc/network-pricing#cloud_armor), and [Firestore pricing/TTL charges](https://cloud.google.com/firestore/pricing).

## Official Google references

- [Cloud Run ingress controls](https://docs.cloud.google.com/run/docs/securing/ingress)
- [External Application Load Balancer for a serverless app](https://docs.cloud.google.com/load-balancing/docs/https/setting-up-https-serverless)
- [Cloud Armor rate limiting](https://docs.cloud.google.com/armor/docs/configure-rate-limiting) and [rate-limit behavior](https://docs.cloud.google.com/armor/docs/rate-limiting-overview)
- [Create Firestore databases](https://cloud.google.com/firestore/docs/manage-databases) and [TTL configuration](https://docs.cloud.google.com/firestore/native/docs/ttl)
- [Firebase App Check with reCAPTCHA Enterprise](https://firebase.google.com/docs/app-check/web/recaptcha-enterprise-provider)
- [Build container images with Cloud Build](https://docs.cloud.google.com/build/docs/building/build-containers)
- [Cloud Run public invocation](https://docs.cloud.google.com/run/docs/authenticating/public)
