# ClearClause

ClearClause is a GenAI legal-information assistant that turns a user-provided PDF into a plain-language briefing, answers questions grounded in that document, and compares two document versions. It is an early demo and does not provide legal advice or replace a qualified legal professional.

**Try the live demo:** [ClearClause on Cloud Run](https://clearclause-api-ye2sfsdqnq-uc.a.run.app)

## What the demo can do

- Explain a text-based legal PDF in plain language, with page-level source citations.
- Answer questions using the supplied document and say when its text does not support an answer.
- Compare two versions using a deterministic text diff, then summarize relevant changes.
- Check cited page numbers and quoted source text before showing AI findings.
- Generate structured findings, obligations, risks, and next-step prompts for discussion with a legal professional.
- Download the current summary, source quotations and questions as a text file.

The browser sends PDFs to the ClearClause backend for extraction and analysis. The backend calls Gemini through Vertex AI using Google Cloud Application Default Credentials; Vertex credentials are never sent to the browser. The demo accepts text-based PDFs up to 12 MiB and 40 pages. It does not provide OCR for scanned documents.

## Try the demo safely

1. Open the demo link and create an account or sign in.
2. Verify the email address using the link Firebase sends you, then sign in again.
3. Choose **Understand**, **Ask a question**, or **Compare versions** and upload a text-based PDF.
4. Review each finding alongside its document citation. Treat the result as an aid for understanding, not as a legal conclusion.

The demo uses Firebase Authentication, verified-email checks, reCAPTCHA Enterprise App Check, Firebase Auth App Check enforcement, and Firestore-backed weighted per-account quotas (8 analysis units/hour and 30/day; a comparison uses 2 units). App Check and Firebase quotas protect application endpoints; Cloud Armor and a custom-domain load-balancer edge are not configured.

**Privacy boundary:** Uploaded PDFs and extracted text are sent to Vertex AI for analysis. The app does not intentionally retain documents, but multipart uploads may temporarily spool to Cloud Run memory or disk. Use synthetic, public, or explicitly authorized documents only until privacy terms, data-processing conditions, retention behavior, and legal review are complete. The demo is not a production legal service.

## Run locally (Windows PowerShell)

Requirements: Python 3.13, Google Cloud CLI, a Google Cloud project with Vertex AI enabled and billing configured, and permission to call the selected model.

```powershell
git clone https://github.com/yashwaghh/AI_Legal_help.git
cd AI_Legal_help
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
$env:GOOGLE_CLOUD_PROJECT = 'YOUR_GOOGLE_CLOUD_PROJECT'
$env:GOOGLE_CLOUD_LOCATION = 'us'
$env:GOOGLE_GENAI_USE_VERTEXAI = 'true'
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GOOGLE_CLOUD_PROJECT
python -m uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000. The example environment uses local development auth and an in-memory limiter; it is for a trusted development machine only. Do not use those settings on a public deployment. Configure Firebase Authentication, App Check, Firestore quotas, and production environment variables before enabling public access. See [`PUBLIC_DEPLOYMENT_RUNBOOK.md`](PUBLIC_DEPLOYMENT_RUNBOOK.md).

## Checks

The latest improvement pass has 40 passing tests and 80.33% Python statement coverage, with a 75% CI floor. See [the evaluation update](EVALUATION_UPDATE.md) for changes across all six criteria and verification limits. GitHub Actions checks pushes to `main` and pull requests.

Run the same code-quality and test commands used by the Cloud Build pipeline:

```powershell
python -m ruff check app tests
python -m ruff format --check app tests
python -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=75
python -m compileall -q app tests
```

`cloudbuild.yaml` runs these checks before building the container image. It builds an image only; it does not deploy it. Connect the GitHub repository to Cloud Build to run this pipeline on pushes or pull requests. Keep deployment as a separately reviewed promotion step.

## Google Cloud deployment outline

The demo architecture uses Cloud Run and Firestore in `us-central1`, with Gemini on Vertex AI's `us` multi-region endpoint. A deployment needs a dedicated Cloud Run runtime service account with least-privilege access to Vertex AI and Firestore, Firebase Authentication and App Check configuration, and project billing/API enablement. Do not create or commit a service-account JSON key. Prefer attached service identities and Workload Identity Federation for CI.

For the current project-specific resource inventory, Firebase settings, rollout steps, and residual risks, see [`PUBLIC_DEPLOYMENT_RUNBOOK.md`](PUBLIC_DEPLOYMENT_RUNBOOK.md) and [`security_evaluation_report.md`](security_evaluation_report.md). The local `cloudrun-service.yaml` is a deployment snapshot that may contain project-specific browser configuration; it is deliberately excluded from Git. Recreate deployment configuration from reviewed environment variables and the runbook instead of copying a local snapshot into a public repository.

## Evaluation criteria and evidence

| Criterion | Evidence in this repository |
| --- | --- |
| Code quality | Small FastAPI modules, typed request/response schemas, bounded input sizes, Ruff checks in Cloud Build |
| Security | Server-side Vertex access, Firebase ID-token and App Check verification, Firestore quotas, request limits, security headers, safe DOM rendering, and an explicit legal-information boundary |
| Efficiency | File/page/text limits, request timeout, weighted quotas, bounded Cloud Run instances and concurrency, deterministic diff before Gemini comparison |
| Testing | API, document extraction, and security test suites; Cloud Build runs pytest and compile checks |
| Accessibility | Semantic HTML, labeled controls, keyboard-operable tabs, status announcements, responsive layout, and visible source citations |
| Problem alignment | Plain-language PDF briefing, source-grounded Q&A, two-version comparison, citation checking, and preparation prompts for a legal professional |

These controls reduce risk but do not establish legal, privacy, security, or regulatory compliance. See the security report for known gaps and deployment evidence.

## Repository layout

- `app/` — FastAPI routes, PDF extraction, Vertex AI adapter, schemas, security, and browser UI.
- `tests/` — API, document, and security tests.
- `implementation_plan.md` — product and architecture plan aligned to the evaluation criteria.
- `execution_plan.md` — delivery phases, evidence, and acceptance gates.
- `PUBLIC_DEPLOYMENT_RUNBOOK.md` — operational setup and public-demo rollout instructions.
- `security_evaluation_report.md` — security decisions, evidence, and residual risks.
- `deployment/public-release-preflight.ps1` — read-only local and Google Cloud preflight.

## Legal-information notice

ClearClause explains text supplied by a user. It can miss context, misread clauses, or produce incomplete summaries. It does not know the user's complete facts or jurisdiction, does not determine legal rights, and does not create a lawyer-client relationship. For decisions, deadlines, disputes, or significant obligations, consult a qualified legal professional.
