# ClearClause — hardening and evaluation report

**Assessment date:** 2026-09-26
**Scope:** local application code, live Google Cloud deployment, production-mode guardrails, and rubric readiness.
**Decision:** **A temporary public `run.app` demo is live by user choice.** Firebase sign-in, App Check enforcement, and Firestore quotas are configured to gate analysis. The sign-in success path still needs a real browser acceptance check; the user reported a sign-in failure, so the client initialization order was corrected and deployed. Cloud Armor/IP edge filtering is absent; do not treat this as a production launch or use sensitive legal documents before privacy/provider/legal review.

## Executive summary

ClearClause’s Vertex AI calls stay on the backend and use Application Default Credentials. Browser users never receive a Vertex key or service-account credential. The online request path now requires a verified Firebase Authentication account and App Check token, reserves per-user quota in a Firestore transaction before parsing an upload, and fails closed if authentication or quota protection is unavailable. Briefing and Q&A cost one quota unit; comparison costs two. Default caps are 8 units per rolling hour and 30 units per rolling 24 hours per account.

Additional safeguards include request-body limits before multipart parsing, existing per-PDF/page/text caps, CSP and other security headers, no-store API responses, a Vertex timeout, a one-switch GenAI shutdown, bounded Cloud Run scale/concurrency in a deployment template, and a `.dockerignore` that excludes local credentials and the virtual environment from the build context.

This project is deployed to Cloud Run as a limited online demo, not as a production legal service. The direct `run.app` endpoint lacks Cloud Armor and a controlled-domain HTTPS load-balancer edge. Privacy/provider terms, accessibility, authenticated end-to-end GenAI acceptance, and a successful sign-in retest remain open.

## Request and trust flow

1. The browser signs in through Firebase Authentication. The account must have a verified email.
2. For analysis, the browser refreshes its Firebase ID token and requests a Firebase App Check token using reCAPTCHA Enterprise.
3. ASGI middleware checks the request size and content type before FastAPI reads a multipart body. It verifies both tokens before letting an analysis request continue.
4. A Firestore transaction reserves weighted usage against the account’s rolling one-hour and 24-hour totals. Firestore stores timestamps and unit counts under a SHA-256-derived document key, not the Firebase UID or document content. If Firestore is unavailable, the app returns a temporary error without calling Vertex AI.
5. FastAPI reads each PDF within the existing byte, page, and extracted-text limits. PyMuPDF extracts text and page numbers in request memory/temp-file scope.
6. The backend sends bounded text to Gemini through Vertex AI using its attached Cloud Run service account and ADC. Citations are checked against exact source pages before display.
7. The browser renders generated text with DOM `textContent`; model output is not interpreted as HTML. Uploads and extracted text are not intentionally persisted by this app. Multipart parsing can spool uploads to ephemeral memory or disk, and document text is sent to Vertex AI.

## Changes made

### Security

- Added `app/security.py` with Firebase ID-token verification, verified-email enforcement, production App Check verification, pre-parser upload guards, security headers, and rate-limit backends.
- Cloud Run presence forces production mode. Startup rejects development auth, in-memory quota, missing Firebase configuration, missing App Check configuration, and invalid quota settings. Production App Check cannot be switched off through an environment override.
- Added rolling-hour and rolling-day account quotas. `/api/briefing` and `/api/answer` use one unit; `/api/compare` uses two. Quota checks occur before multipart parsing and Vertex calls. Quota service errors fail closed. A denied/invalid request may still consume a reserved unit; this intentionally makes repeated malformed requests costly to the caller.
- Added browser email/password sign-up and sign-in, email verification, password reset, and sign-out. The Firebase Web API key and app ID are public Firebase client configuration only; there is no Vertex API key in frontend configuration.
- Corrected the browser initialization order so Firebase App Check starts before Firebase Auth. Firebase's web guidance requires App Check initialization before accessing Firebase services; the prior order could cause Auth calls to be rejected when Auth enforcement was active.
- Improved Firebase sign-in error messages to show actionable setup guidance for common configuration and App Check failures, and the safe Firebase error code for otherwise unmapped failures.
- Added a bounded Vertex client timeout (`VERTEX_TIMEOUT_MS`) and an operator kill switch (`GENAI_ENABLED=false`).
- Added Content Security Policy, HSTS in production, `X-Content-Type-Options`, `X-Frame-Options`, referrer and permissions policies, no-store API responses, and same-origin resource policy.
- Added `.dockerignore` to prevent `.env`, `.venv`, tests, and local files from entering the container build context.
- Added `cloudrun-service.yaml` as a **placeholder template** with ingress restricted to a load balancer, zero minimum/three maximum instances, concurrency four, bounded CPU/memory, health probes, and production fail-closed environment settings.

### Code quality and evaluation

- Added `ruff.toml`, `requirements-dev.txt`, and focused tests for PDF parsing, citation grounding, weighted and rolling quotas, user scoping, early size checks, unauthenticated rejection, quota fail-closed behavior, security headers, and Cloud Run refusing development mode.
- Updated Cloud Build to run Ruff lint/format, pytest, and Python compilation before the container build. The configuration has not been run on Cloud Build and no trigger or deployment stage is configured.
- Updated README setup and deployment boundaries. The local server remains in explicit development mode; it is not a safe public deployment configuration.

## Verification results

The automated results below are the previously recorded local hardening baseline. The current deployment fix was built and deployed separately; no automated tests or sign-in with a user account were run in that deployment step.

| Check | Result | Scope |
|---|---|---|
| `pytest -q` | **16 passed** | Local/unit/API tests only; no live identity, Firestore, or Vertex integration. |
| `ruff check app tests` | **Passed** | Python lint. FastAPI’s declarative parameter defaults and long natural-language prompts are excluded from the corresponding style rules. |
| `ruff format --check app tests` | **Passed** | Python formatting. |
| `python -m compileall -q app tests` | **Passed** | Python syntax compilation. |
| `node --check app/static/app.js` | **Passed** | JavaScript syntax only, not browser behavior or Firebase integration. |
| Browser smoke check | **Passed** | Local page loads with updated tools; local development sign-in panel is hidden; no Vertex request made. |
| Cloud changes (historical baseline) | **None in that baseline** | The subsequent live deployment and configuration evidence are listed in the latest section below. |

## Six-criterion status

| Rubric criterion | Status after this work | Remaining evidence/work |
|---|---|---|
| **Problem Statement Alignment** | Core briefing, document Q&A, comparison, citations, and professional-question prompts remain implemented. | User research, checklists/export, broader document coverage, and a reviewed quality set. |
| **Code Quality** | Modular API/security/AI/PDF modules; Pydantic output validation; production configuration checks; local lint, format, compile, and test checks; Cloud Build checks are defined. | Configure/run Cloud Build trigger; dependency lock/SBOM, coverage report, type checking, peer review, and pinned immutable base image. |
| **Security** | Token and App Check validation, rolling distributed account quotas, fail-closed backend, upload bounds, security headers, no frontend Vertex credentials, runtime scaling template. | Cloud perimeter/IAM setup, live negative authorization tests, account-abuse and IP controls, dependency/image scan, privacy/legal review, and incident/deletion process. **Not production-ready.** |
| **Efficiency** | Flash-Lite model, bounded PDF/context/output, deterministic diff, request timeout, per-account units, scale/concurrency caps in template. | Measure p50/p95 latency and cost per task; set Vertex quotas; validate Firestore overhead; tune model, limits, and autoscaling with load tests. |
| **Testing** | 16 local tests plus syntax/lint/format and one local-browser smoke check. | Firebase/App Check real-token tests, Firestore transaction/concurrency tests, Vertex synthetic evaluation, end-to-end upload flows, load/abuse tests, CI. |
| **Accessibility** | Existing semantic/responsive UI, keyboard tabs, focus styles, status announcements; sign-in fields are labelled and status is announced. | WCAG 2.2 AA review, keyboard/screen-reader walkthrough, contrast and zoom/reflow audit, and Firebase error-state review. |

## Full public release prerequisites (the demo is already online)

The following are gates for a broader production release; they do not mean the currently configured synthetic-data demo is offline. The live deployment snapshot below records which cloud resources exist and what still needs real-browser acceptance.

1. **Choose the hosting/data region and public domain.** Confirm jurisdiction, residency, provider terms, Vertex availability, and legal/privacy requirements first. The template deliberately leaves the Cloud Run region as `REGION`.
2. **Set up Identity Platform/Firebase Authentication.** Enable email/password, email verification, password reset, email-enumeration protection, authorized domains, and account abuse protections. Register the Firebase Web app and populate `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, and `FIREBASE_APP_ID`. Restrict the Firebase API key to the deployed site’s HTTP referrers and only the Firebase Authentication APIs it needs. It is a public client key, not an authorization control.
3. **Set up Firebase App Check with reCAPTCHA Enterprise.** Register the web app, create/attach the Enterprise site key for the final domain, and set `FIREBASE_APP_CHECK_SITE_KEY`. Validate that App Check rejects tokens for other Firebase apps. Avoid disabling App Check to get around a failed setup.
4. **Create Firestore Native mode** in the reviewed region. Configure TTL on collection group `clearClauseRateLimits`, field `expiresAt`. Keep database client access closed; only the runtime service account should write rate documents. The app uses no user-document collection.
5. **Create a dedicated Cloud Run service account.** Grant only `roles/aiplatform.user` and `roles/datastore.user` in the required project/database scope. Basic App Check verification uses the Admin SDK; do not grant App Check administration. Do not create or mount service-account JSON keys. Verify the service identity can call the chosen Gemini model and Firestore.
6. **Enable the required APIs and quotas** for Vertex AI, Cloud Run, Cloud Build, Artifact Registry, Identity Platform/Firebase Auth, Firebase App Check, Firestore, Cloud Logging/Monitoring, reCAPTCHA Enterprise, and the external load balancer. Set conservative Vertex request/token quotas in addition to application quotas. Budget alerts notify but do not cap spend.
7. **Build an immutable image** with Cloud Build and scan it. Set the image digest in `cloudrun-service.yaml`, replace every placeholder, and apply to Cloud Run in the approved region. The manifest uses `internal-and-cloud-load-balancing` ingress and caps max instances/concurrency; don’t change ingress to direct public access.
8. **Put an HTTPS external Application Load Balancer and Cloud Armor in front.** Use a serverless NEG to the Cloud Run service. Configure Cloud Armor rate-based bans/thresholds by source IP (start conservatively, then tune for shared networks) and basic threat protections. Grant the load balancer path access to invoke the service, then prevent direct Cloud Run URL bypass through ingress. Public access to the website can be allowed through the load balancer; analysis endpoints still require the validated account and App Check tokens.
9. **Run staging security and quality checks** with synthetic PDFs and dedicated test accounts. Verify anonymous, expired, unverified, wrong-project, wrong-app, missing-App-Check, quota-exceeded, Firestore-down, oversized/chunked, malformed, and cross-origin requests are rejected before Vertex. Verify rolling quota concurrency and Firestore TTL behavior. Never use client documents for smoke tests.
10. **Go/no-go review.** Review privacy notice, AI provider terms/data handling, data residency, legal boundaries, accessibility, threat model, runbook, and rollback. Keep `GENAI_ENABLED=false` available as the emergency switch. Deploy only after all launch gates below have evidence.

## Release gates still open

- [x] Firebase email/password provider, deployed authorized host, and verified-email policy are configured. **Open:** retry the browser sign-in after the App Check initialization-order fix; end-to-end signup, verification, and password-reset acceptance are not evidenced here.
- [x] Firebase App Check/reCAPTCHA Enterprise is configured and Auth enforcement is enabled for the deployed host. **Open:** verify valid/invalid token behavior in a live browser and backend request.
- [x] Firestore database and quota TTL are configured. **Open:** verify transactional quotas under concurrency and service failure.
- [x] Dedicated runtime service account has only `roles/aiplatform.user` and `roles/datastore.user`; no service-account key was created.
- [ ] Vertex per-minute/token quotas, model/location approval evidence, and observed cost under synthetic use.
- [ ] HTTPS load balancer, Cloud Armor IP rate limiting, and private Cloud Run ingress; the current direct `run.app` service is intentionally temporary.
- [ ] Staging abuse, cross-user, prompt-injection, malformed-file, cost/load, and citation-evaluation suites pass.
- [ ] Dependency/container scans, privacy and provider terms review, accessibility audit, operations and incident plan complete.

## Known limitations and residual risks

- Public registration can still be abused with account farms. App Check and Cloud Armor raise the cost; they do not eliminate account or IP rotation. Add monitoring/abuse review and consider invite/allowlist onboarding during a pilot.
- Per-account quota is the hard application-level Vertex guard. The default 8/hour and 30/day weighted-unit values are starter settings and must be tuned using model pricing, per-task token use, and user testing. They are not a total project-spend cap.
- Firebase token revocation is not checked on every request (`check_revoked=False`) to avoid an extra account lookup on every analysis. A disabled/revoked account can retain access until its short-lived ID token expires (typically up to about one hour). Revisit if immediate revocation is a launch requirement.
- Limited-use App Check replay protection is not enabled; the Python verification path checks valid App Check tokens but does not consume them. A stolen valid ID/App Check token pair can be replayed until expiry, with the account quota limiting analysis volume. Revisit replay controls if the SDK support and latency tradeoff fit the pilot.
- Firestore, App Check, and Identity Platform resources are configured in the live project, and Cloud Run health/configuration checks pass. Actual Firebase sign-in, valid/invalid App Check token behavior, Firestore quota transaction behavior under load, and successful authenticated Gemini analysis still need live synthetic-data acceptance. Local mocks do not prove these integration paths.
- Uploaded legal text leaves the app process for Vertex AI and may be temporarily spooled during request parsing. No storage/retention UI or formal deletion workflow exists. Provider/region/retention terms and legal/privacy review remain a hard prerequisite for sensitive material.
- OCR, persistent user documents, user tenancy/ownership for stored documents, audit history, and legal-source updates are out of scope for this slice.

## Official implementation references checked

- [Firebase: Verify App Check tokens from a custom backend](https://firebase.google.com/docs/app-check/custom-resource-backend)
- [Firebase: Set up App Check with reCAPTCHA Enterprise for web](https://firebase.google.com/docs/app-check/web/recaptcha-enterprise-provider)
- [Firebase Admin Python: `app_check.verify_token`](https://firebase.google.com/docs/reference/admin/python/firebase_admin.app_check)
- [Firebase Authentication: Verify ID tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens)

## Public deployment readiness pass — 2026-09-26 (historical baseline)

**Current decision: still no-go for public traffic.** This pass prepared deployment artifacts and checked Google Cloud state using read-only commands. It did not enable APIs, create billable services, change IAM, deploy Cloud Run, or make a Vertex request.

### Project inventory

`gcloud config get-value project` returned `ai-legal-help`; `gcloud projects describe` returned lifecycle `ACTIVE`. Vertex AI, Cloud Run, Cloud Build, Artifact Registry, Identity Toolkit, IAM, Logging, Monitoring, and Secret Manager APIs were enabled. Firestore API was disabled. No Artifact Registry repository or Cloud Run service was listed. Only the default Compute Engine service account was listed; no dedicated ClearClause runtime identity was found. Firebase Console/App Check settings and public load-balancer/Cloud Armor policy were not verified as configured.

### Release-path changes

- Added `PUBLIC_DEPLOYMENT_RUNBOOK.md` with ordered region/domain decisions and Google Cloud deployment steps.
- Added `deployment/public-release-preflight.ps1` for read-only API, resource, template, and local-config checks. Manual identity, TTL, privacy, edge, and release evidence is explicitly reported as manual review.
- Changed Cloud Build image tag substitution to `BUILD_ID` so local-source builds do not depend on a Git commit. The deployment manifest now asks for an immutable Artifact Registry image digest.
- Clarified Cloud Run's public invocation boundary: invocation permission is only granted after `internal-and-cloud-load-balancing` ingress is in force; Firebase auth and App Check still gate analysis requests.
- Replaced `global` with an explicit Vertex endpoint-location placeholder in the public Cloud Run template; data location must be approved independently from the Cloud Run/Firestore region.
- Added the reCAPTCHA Enterprise endpoint to the CSP and strengthened the visible disclosure that legal-document content is sent to Vertex AI and may temporarily spool during upload parsing.
- Added a cost gate covering Vertex, load-balancer, Cloud Armor, and billable Firestore TTL activity; a monthly budget alert is not a spend cap.

### Remaining no-go gates

1. User approval of region, public domain/DNS, pilot audience, and accountable privacy/support contact.
2. Enable/configure Firebase Authentication and production App Check; populate production web-client values.
3. Enable Firestore API; create Native database in the approved region; activate TTL for `clearClauseRateLimits.expiresAt`.
4. Create the dedicated runtime identity and verify only necessary IAM; establish project/model quotas and spend guardrails.
5. Create Artifact Registry and run Cloud Build; scan the image and promote by immutable digest.
6. Deploy Cloud Run with restricted ingress; configure invoker access only behind a global HTTPS load balancer and Cloud Armor.
7. Complete synthetic staging auth/quota/abuse/citation/cost/load/accessibility/privacy and rollback evidence before a limited pilot.

The user confirmed that no public domain is available yet. This specifically blocks the planned managed-certificate HTTPS load balancer and Cloud Armor edge. A generated Cloud Run `run.app` hostname is a possible temporary staging endpoint, but it does not provide Cloud Armor, requires internet ingress, and the current application permits self-service account creation. Do not treat a direct `run.app` deployment as the full public security perimeter; use only a separately restricted synthetic-data staging configuration or wait until a controlled domain is available.

The user's existing budget alert is acknowledged. Alerts notify; they are not spend caps. This pass did not run tests or Cloud Build; the previously reported 16 local tests and lint/format checks predate these deployment-preparation edits. Current working details and plan status are in `context.md`, `implementation_plan.md`, and `execution_plan.md`.

The first read-only preflight returned 8 then 10 blockers before setup. That inventory has been superseded by the deployment update below.

## Live deployment assessment — 2026-09-26

- URL: [https://clearclause-api-ye2sfsdqnq-uc.a.run.app](https://clearclause-api-ye2sfsdqnq-uc.a.run.app). Cloud Run `us-central1`, ready revision `clearclause-api-00003-c9n`; public `run.app` ingress by explicit user choice.
- Vertex model is Gemini 3.5 Flash-Lite at `us` multi-region; Cloud Run and Firestore remain `us-central1`.
- Firebase email/password auth is enabled. Analysis requires a verified-email ID token, a valid App Check token bound to the Firebase Web app, and Firestore quota reservation. Firebase Auth's App Check enforcement is enabled.
- Browser API key is restricted by referrer and API allowlist. Vertex credentials remain on the server through the dedicated runtime service account. Runtime roles are only `roles/aiplatform.user` and `roles/datastore.user`.
- Firestore `(default)` is Native mode in `us-central1`, delete protection is enabled, and TTL on `clearClauseRateLimits.expiresAt` is `ACTIVE`.
- Cloud Run scale is capped at 3, concurrency 4, min 0. Health, landing-page, and `/api/config` smoke checks passed; `/api/config` reports production auth/App Check configuration. The deployment command also returned a project-number `run.app` alias; the configured Firebase and reCAPTCHA allowlists remain centered on the URL above, which is the URL to use for this demo.
- Updated read-only preflight reports **0 blocking checks and 4 manual sign-off items**: live Firebase/App Check acceptance, Cloud Armor edge limitation, privacy/legal readiness, and release verification.
- Container image was built and deployed by immutable digest `sha256:4c1220f16fc4053c0cf9127e5c7c360e8717852e6213e48bfb3180f7bc46e5a4`. The Docker-only build did not execute `cloudbuild.yaml` tests; no automated tests, user signup, or model-generation call was performed in this deployment turn.
- The user reported “The sign-in request could not be completed.” Code inspection found App Check was initialized after `getAuth()`. The order is fixed in the deployed client. Reload the demo and retry; if it still fails, share the Firebase error code shown by the updated page (never share a password).
- **Residual risk:** no Cloud Armor IP throttling. Public signup is self-service; Firebase Auth App Check and account-level quotas reduce misuse but do not replace edge-level abuse controls. Keep cohort small and monitor usage/cost. The user's ₹500/month alert is not a hard cap.
- **Open gates:** real authenticated synthetic-PDF GenAI acceptance check; auth/App Check/negative-token and quota-abuse verification; Vertex quotas/cost observation; dependency/image scan; privacy/provider/jurisdiction review; WCAG 2.2 AA and rollback/on-call evidence. Obtain a controlled domain before upgrading to the full external HTTPS load-balancer + Cloud Armor perimeter.
