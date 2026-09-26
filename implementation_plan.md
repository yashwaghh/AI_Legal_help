# ClearClause — implementation plan

**Purpose:** A Google Cloud based GenAI solution that helps people understand, compare, and navigate legal documents while remaining an information assistant rather than a substitute for professional legal advice.

**Rubric:** The supplied screenshot lists Code Quality, Security, Efficiency, Testing, Accessibility, and Problem Statement Alignment. These are treated as scoring dimensions; the written request defines the task.

**Latest implemented release (2026-09-26):** Revision `clearclause-api-00005-9wj` is live. It fixes Firebase's referrer conflict and Firestore quota serialization, reuses valid auth tokens/cached schemas, bounds browser requests, validates PDF signatures before upload, detects short contract changes, discloses partial analysis, and exports cited summaries/questions as text. Accessibility handling and CI/coverage gates were expanded. Evidence: 40 passing local tests and 80.33% Python statement coverage; successful Cloud Build; live HTTP checks and separate synthetic Vertex/Firestore diagnostics. Full authenticated browser acceptance and broader production gates remain open. `EVALUATION_UPDATE.md` is the current six-criterion release record; later planning sections preserve historical checkpoints.

## 1. Product proposal

ClearClause is a document-centered legal information workspace for individuals, freelancers, and small organizations. Users upload an agreement, ask questions in plain language, understand key clauses, compare versions, prepare a checklist, and create questions for a legal professional. GenAI is a central capability: it classifies and explains clauses, answers questions over selected sources, describes meaningful changes, and turns cited findings into editable outputs.

### MVP workflows

1. **AI briefing:** Plain-language overview; parties, explicit dates, payment, renewal, termination, and responsibilities; every point has a page and supporting excerpt.
2. **Grounded Q&A:** Ask a natural-language question over the selected document set. Return a concise answer, citations, uncertainty, and an abstention when evidence is absent, ambiguous, or conflicting.
3. **Semantic comparison:** Align two versions and compute exact text differences deterministically. Gemini explains changes neutrally with citations from both versions. Users can choose a lens such as payment, confidentiality, termination, or all changes.
4. **Action checklist:** Extract proposed obligations and explicit dates into user-editable tasks, each linked to its source. The user confirms tasks. Do not calculate legal deadlines or invent dates.
5. **Professional-preparation brief:** Create a user-editable summary of facts, unresolved questions, and cited passages for a legal professional. Do not generate a filing or binding legal instrument.

Start with English-language PDFs and a narrow pilot document set selected with users. Add DOCX only after provenance and extraction quality are reliable. MVP answers use the supplied documents only. Do not infer jurisdiction or present a jurisdiction-specific conclusion. No advice on whether to sign, sue, settle, or disclose; no enforceability opinions, outcome predictions, signing, filing, sending, or automatic source edits. No attorney-client privilege claim.

## 2. Rubric-to-evidence plan

| Dimension | Build evidence |
|---|---|
| Problem Statement Alignment | Demo simplification, cited Q&A, comparison, obligations, next steps, and professional preparation on real user tasks. |
| Code Quality | Typed API contracts, modular domain logic, validated model output, migrations, lint/type checks, review, reproducible builds, runbooks. |
| Security | Threat model, least-privilege IAM, user-isolation tests, private storage, deletion proof, prompt-injection evaluation, redacted logs. |
| Testing | Unit, integration, end-to-end, model, security, accessibility, and performance suites with versioned reports and release gates. |
| Accessibility | Target WCAG 2.2 AA from upload through export; automated checks plus keyboard and screen-reader reviews. |
| Efficiency | Async processing, bounded retrieval/output, quotas, cost-per-task instrumentation, Cloud Run caps, latency measurements. |

Targets below are proposals to validate, not achieved results or promises of legal accuracy.

## 3. Google Cloud architecture

Select one region after checking pilot jurisdiction, residency, service/model availability, processor support, quotas, and budget. Preview components must have a fallback.

    Browser → Cloud Run web app → Cloud Run API
                 Identity Platform token → API verifies identity and document authorization
    Browser → short-lived upload URL → private Cloud Storage
    Cloud Storage object event → Pub/Sub → Cloud Run ingestion worker
                                            ├── Document AI OCR/layout
                                            ├── Vertex AI embeddings
                                            └── Cloud SQL PostgreSQL + pgvector
    Cloud Run API ↔ Cloud SQL filtered retrieval
    Cloud Run API ↔ Vertex AI Gemini structured, grounded generation
    Cloud Build → Artifact Registry → Cloud Run web, API, worker
    IAM / Cloud KMS / Secret Manager / Sensitive Data Protection / Cloud Audit Logs
    Cloud Logging / Monitoring / Error Reporting / Trace

| Layer | Google Cloud service | Purpose and safeguards |
|---|---|---|
| Web, API, worker | Cloud Run | Separate stateless services. Use distinct runtime identities, configured concurrency and maximum instances, and asynchronous ingestion rather than long browser requests. |
| Authentication | Identity Platform | Email or federated login. API verifies token issuer, audience, signature, expiry, and subject. Authentication is not authorization: check ownership for every document, answer, export, retry, and delete. |
| Files | Cloud Storage | Private raw and derived storage, uniform bucket-level access, public access prevention, lifecycle cleanup. API creates short-lived signed uploads scoped to one opaque object key after type, size, ownership, and quota checks. |
| Queue | Cloud Storage notifications and Pub/Sub | Decouple upload from OCR/embedding. Assume at-least-once, delayed, or reordered delivery: object generation, idempotency, bounded retry, visible status, dead-letter topic. |
| Parsing | Document AI | Enterprise Document OCR for scanned PDFs. Pilot Layout Parser for structure-aware chunks only after confirming current availability, region/language support, and preview status. Fallback: OCR plus deterministic page/heading chunking. |
| Data and retrieval | Cloud SQL for PostgreSQL with pgvector and full-text search | Store user/document metadata, chunks, citations, embeddings, and state. Use hybrid search. Always filter by authenticated owner/workspace and chosen document IDs; add row-level security as defense in depth. |
| GenAI | Vertex AI Gemini | Clause classification, plain-language explanation, grounded Q&A, change explanation, obligation extraction, and professional-preparation brief. Choose model through evaluation, version settings, require structured output. |
| Embeddings | Vertex AI text embeddings | Semantic retrieval for document chunks and questions; lexical search complements exact clause numbers and phrases. Store model/version metadata. |
| Security | IAM, Secret Manager, Cloud KMS, Sensitive Data Protection, Cloud Audit Logs | Least privilege and separate identities. Prefer workload identity/application default credentials over downloaded keys. CMEK only where the specific service supports it and region/rotation requirements are reviewed. DLP may inspect/redact telemetry but never substitutes for authorization. |
| CI/CD | Cloud Build, Artifact Registry | PR checks, immutable image digests, dependency/image scanning, staging then approved promotion; Terraform and reviewed IAM changes. |
| Operations | Cloud Logging, Monitoring, Error Reporting, Trace | Log request IDs, status, service/model version, latency, token count only. Never log prompts, answers, legal text, extracted clauses, or signed URLs. Alert on error rate, queue age, processing/model failures, SQL saturation, deletion backlog, and budget. |
| Later, if justified | Cloud Armor/load balancer; BigQuery | Edge protection for a larger public launch. BigQuery only for minimized pseudonymous events; never raw documents or prompts. Avoid services added only to increase service count. |

References for the design: [Document AI extraction and layout](https://docs.cloud.google.com/document-ai/docs/extracting-overview), [Document AI OCR](https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr), [Cloud SQL vectors](https://docs.cloud.google.com/sql/docs/postgres/generate-manage-vector-embeddings), [Vertex AI embeddings](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings), [Vertex AI function calling and structured output](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling), [Identity Platform](https://docs.cloud.google.com/identity-platform/docs/concepts-authentication), [Cloud Storage signed URLs](https://docs.cloud.google.com/storage/docs/access-control/signed-urls), [Pub/Sub failure handling](https://docs.cloud.google.com/pubsub/docs/handling-failures), and [Cloud Run autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling).

## 4. GenAI design

### Capabilities

- **Clause understanding:** Gemini classifies passages into a narrow taxonomy: payment, term, renewal, termination, confidentiality, liability, dispute resolution, data use, and other. Extract candidate parties, amounts, explicit dates, conditions, and duties with provenance and uncertainty.
- **Plain-language explanation:** Simplify clause language while preserving exceptions, conditions, defined terms, and the original beside the paraphrase.
- **Document Q&A:** Answer in conversational language using only retrieved evidence. Return a citation for each claim, explain what is missing, and abstain when unsupported.
- **Semantic diff explanation:** First align sections and calculate exact changed words deterministically. Gemini explains only those excerpts; cite both sides and use neutral labels such as changed, added, removed, or needs review.
- **User-directed lens:** Let the user request “compare payment terms” or “show dates and renewal changes.” Do not produce a hidden generic legal risk score.
- **Actionable outputs:** Convert supported duties into editable checklist candidates and prepare neutral questions for a professional. The user confirms or discards them.
- **Bounded function calling:** Optional read-only tools: find a clause, fetch an authorized section, or compare two authorized documents. Backend rechecks authorization for every call. No tool can sign, send, file, or modify a source document.

### Grounding pipeline

1. API validates the user and access to every selected document.
2. Vertex AI embeds the question. Cloud SQL performs owner/document-filtered vector plus lexical retrieval and returns a small set of page/section chunks with extraction confidence.
3. Gemini receives only the question, task instructions, and selected excerpts. Document content is explicitly untrusted data and cannot override system rules.
4. Gemini returns a strict structured object: answer, status, citations, uncertainties, suggested questions.
5. Server validates schema and confirms citation document, page, and exact quote span against canonical extracted text. If validation fails, remove the unsupported claim or abstain.
6. UI distinguishes quoted legal text from generated paraphrase and opens the cited page/section.

Use task-specific prompt templates, bounded retrieved context, output/token caps, and versioned model/prompt/schema/chunking configurations. Model confidence is never treated as evidence.

Example response fields: answer; status (supported, partial, insufficient_evidence, conflicting); citation list (document ID, page, section, exact quote); uncertainties; suggested questions. Server, not Gemini, resolves citations and decides whether a claim is displayable.

## 5. Data workflow, storage, and API

### Upload and processing

1. User signs in and accepts a plain-language notice explaining processing, retention, deletion, and limitations.
2. API checks auth, workspace ownership, quota, size/type; creates opaque document ID and a short-lived single-object upload.
3. Browser uploads directly to private Cloud Storage.
4. Pub/Sub triggers worker; worker verifies generation, checksum, MIME signature, size, supported format, and idempotency key.
5. Document AI extracts text/layout. Preserve page boundaries, headings, tables, order, and confidence; chunk by section/page with stable provenance.
6. Vertex AI creates embeddings; worker stores chunks, metadata, vectors, and status in Cloud SQL.
7. UI shows READY, NEEDS_REVIEW, or FAILED, with safe reason and retry. Incomplete OCR must be visible before Q&A.

Set configurable initial file/page limits, then validate against processor quotas and cost. Reject encrypted/unsupported files and warn on unreadable pages or unsupported language.

### Core entities

| Entity | Key fields | Constraint |
|---|---|---|
| User/workspace | Auth subject, user/workspace ID, role, locale | Store minimum account data. Client-supplied ID never proves ownership. |
| Document | Opaque ID, owner/workspace, object key, hash, type, page count, status, quality, retention/deletion times | Check ownership for every operation; no content in logs or object names. |
| Chunk | Chunk/document/owner IDs, page range, heading path, text, embedding, confidence | Mandatory owner/document filters, SQL row security, stable citation anchors. |
| Finding | Neutral kind, summary, source IDs, quote spans, uncertainty, user-reviewed status | Every finding resolves to accessible evidence; no unsupported legal risk score. |
| Conversation | ID, selected docs, timestamp | Persist only if user opts in; avoid prompt/answer body retention by default. |
| Deletion job | Resource IDs, state, attempts, completion time | Idempotently cover original, OCR, chunks/vectors, exports, caches, scheduled jobs. |

API surface: POST upload intent; POST upload completion; GET document status; POST grounded answer; POST comparison with optional lens; POST checklist/export; DELETE document/account. Version schemas, limit request sizes/rates, validate AI output, and authorize each operation.

## 6. Legal safety and security

At onboarding, upload, answer, comparison, and export, explain that this is general information based on supplied documents, not legal advice or a lawyer-client relationship. A footer disclaimer alone is insufficient.

| Threat | Control |
|---|---|
| Cross-user access | API authorization and SQL owner filters/RLS; opaque IDs; negative isolation tests for retrieval, APIs, tools, and exports. |
| Stolen upload URL | Private storage, short expiry, one-object scope, checksum/type/size validation; never log URL. |
| Malformed file | Signature checks, parser resource limits/sandbox, size/page limit, safe failure and scanning policy. |
| Prompt injection | Source text treated as untrusted; separated instructions; no privileged tools; strict schema; adversarial evaluation and server-checked citations. |
| PII in logs | Content-free allowlisted structured logs, redaction, restricted access, test log scans. |
| Duplicate events | Idempotency by object generation, bounded retries, dead-letter topic and replay procedure. |
| Incomplete deletion | Delete originals, derived OCR, chunks/vectors, exports, caches, and backups per declared retention; reconciliation and visible completion. |
| Cost/abuse | Per-user quotas, upload/query limits, token caps, Cloud Run max, budget alerts and generation kill switch. |

Separate dev/staging/production projects. Give each service a minimal identity; no owner/editor roles or static service-account keys. Use private buckets with uniform bucket-level access, Secret Manager for secrets, encryption in transit/at rest, Cloud Audit Logs, and KMS CMEK only after product/region support review. Proposed pilot retention is 30 days, subject to counsel/privacy review, with immediate user deletion control.

Do not claim GDPR, CCPA, DPDP, HIPAA, attorney-client confidentiality, or another compliance based solely on a Cloud control. Choose a launch jurisdiction and review provider terms, residency, consent, retention, deletion, and incident obligations with qualified counsel. Add external legal sources only in a separate phase using official primary sources with jurisdiction, effective date, version, update date, and professional review; otherwise ask or abstain.

## 7. Code quality and repo

    apps/web/                 React and TypeScript interface
    services/api/             Authentication, authorization, orchestration
    services/ingestion/       Pub/Sub worker, parsing, chunking, embeddings
    packages/contracts/       Shared typed API and citation schemas
    packages/domain/          Comparison, checklist, access rules
    infra/terraform/          Cloud resources and IAM
    evals/                    Golden docs, model and adversarial cases
    docs/                     Architecture, threat model, runbooks, data map

Keep deterministic domain logic separate from handlers and model adapters. Runtime-validate all API and model boundaries; version database migrations. Require lint/format, type checks, static analysis, secret/dependency and container scans, PR review, and reproducible builds. Use synthetic fixtures and mocked services locally. Never commit real legal documents, prompts from users, or secrets.

## 8. Testing and release gates

Evaluation set covers born-digital and scanned PDFs, tables, page-split clauses, changed terms, explicit/ambiguous dates, contradictions, missing evidence, low OCR, unsupported language, corrupt/encrypted files, and malicious embedded instructions.

| Layer | Examples and proposed gate |
|---|---|
| Unit | Authz, state transitions, section diff, extraction, provenance, citation validator, deletion. Target ≥80% coverage in critical domain/security modules. |
| Integration | SQL filters/RLS, Storage upload, Pub/Sub duplicate/retry/dead-letter, Document AI/Vertex adapters. Duplicate events do not duplicate records; failures remain visible/retryable. |
| End-to-end | Sign-in, upload, cited answer, compare, export, delete; complete with keyboard/screen reader; unauthorized access denied. |
| GenAI quality | Evidence support, citation correctness/coverage, omissions, abstention, neutral comparisons, prompt injection. All citation links resolve; proposed ≥95% reviewer citation correctness and zero ungrounded high-consequence claims on curated set. If missed, narrow feature or abstain. |
| Security | IDOR, token validation, tenant isolation, upload abuse, prompt injection, rate limits, log scan, dependency/image issues. Zero cross-user access failures; no high-severity exploitable issue open for pilot. |
| Performance/cost | Concurrent uploads, queue backlog, scanned files, p95 answer/processing latency, SQL saturation, token use. Declare target after staging run; budget caps/alerts active. |
| Accessibility | Automated scan, keyboard, focus, screen reader, zoom/reflow, contrast, non-color labels. Target WCAG 2.2 AA; resolve critical/serious findings and record manual review. |

Keep evaluation reports versioned with dataset, model, prompt, parser, scores, failure examples, reviewer, and release decision. These are operational gates, not a legal accuracy guarantee.

## 9. Efficiency, accessibility, and success
Process uploads asynchronously. Use bounded hybrid top-k retrieval, token/output caps, and diff-first comparisons that send only changed text to Gemini. Generate reports on demand. Reuse embeddings only per user and immutable document; do not expose cross-tenant deduplication. Choose cheaper/faster models for simple tasks only if evaluation passes. Cap Cloud Run scaling/concurrency to protect SQL and budget; measure cost per page, document, and question. Do not invoke services just to inflate the cloud-service count.

Target [WCAG 2.2 AA](https://www.w3.org/TR/WCAG22/): semantic headings/controls, keyboard operation, visible focus, announced status/errors, screen-reader labels, reflow/zoom, contrast, non-color diff labels, and readable explanations. Show the original clause beside generated text. Review with assistive technology and low legal/digital literacy. Translate only after language-specific OCR, retrieval, output, and professional review.

Proposed pilot measures: ≥80% of moderated users locate the clause and explain its source; ≥90% complete upload-to-cited-answer without facilitation; ≥95% citation correctness and 100% technical citation resolution; zero cross-tenant defects; ≥90% ambiguous/missing/conflicting cases are flagged or abstain; no critical accessibility blocker. Measure task completion, citation opens, p95 latency, processing failures, deletion completion, cost/task, and helpfulness. Analytics never contains legal text or questions.

## 10. Decisions before production

1. Choose launch jurisdiction, users, and agreement categories.
2. Review data terms, residency, privacy notice, retention, deletion, consent, and incident response.
3. Verify regional model/processor support and Layout Parser preview status; retain fallback.
4. Check file limits, quotas, scanning policy, and cost on synthetic representative documents.
5. Decide account requirement; private authenticated workspaces are recommended for legal documents.
6. Name quality reviewer, security owner, support contact, and deletion/incident owner.
7. Approve official-source corpus and updating before adding legal-information retrieval beyond uploads.

## 11. Technical references

- [Document AI extraction overview](https://docs.cloud.google.com/document-ai/docs/extracting-overview)
- [Document AI Enterprise OCR](https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr)
- [Vertex AI function calling and structured output](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling)
- [Vertex AI text embeddings](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings)
- [Cloud SQL embeddings and pgvector](https://docs.cloud.google.com/sql/docs/postgres/generate-manage-vector-embeddings)
- [Identity Platform authentication](https://docs.cloud.google.com/identity-platform/docs/concepts-authentication)
- [Cloud Storage signed URLs](https://docs.cloud.google.com/storage/docs/access-control/signed-urls)
- [Uniform bucket-level access](https://docs.cloud.google.com/storage/docs/uniform-bucket-level-access)
- [Cloud Storage Pub/Sub notifications](https://docs.cloud.google.com/storage/docs/pubsub-notifications)
- [Pub/Sub dead-letter topics](https://docs.cloud.google.com/pubsub/docs/handling-failures)
- [Cloud Run autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling)
- [Cloud Build deployment to Cloud Run](https://docs.cloud.google.com/build/docs/deploying-builds/deploy-cloud-run)
- [Sensitive Data Protection](https://cloud.google.com/security/products/dlp)
- [Cloud KMS CMEK practices](https://docs.cloud.google.com/kms/docs/cmek-recommended-practices)
- [Secret Manager best practices](https://docs.cloud.google.com/secret-manager/docs/best-practices)
- [Cloud Monitoring alerting](https://docs.cloud.google.com/monitoring/alerts)
- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)

Features, model names, preview status, quotas, pricing, regions, and processing terms change. Recheck official documentation before implementation and launch.

## 13. Public-pilot release readiness update (2026-09-26)

The runnable slice now has a production authentication/App Check path, shared Firestore quotas, upload bounds, Vertex AI generation and citation checks, and a Cloud Run template. A deployment runbook and read-only preflight script now describe the handoff from the current project state. Cloud Build uses its unique `BUILD_ID` for local-source submissions instead of assuming a Git commit exists. The response CSP explicitly allows the reCAPTCHA Enterprise API endpoint used by the web App Check flow. The user-facing document warning states that files and extracted text are sent to Vertex AI, explains temporary upload spooling, and directs pilot users to synthetic/non-sensitive files until privacy terms are reviewed.

These changes prepare the release path; they do **not** make the project production-ready by themselves. A read-only inventory found no Cloud Run service, Artifact Registry repository, Firestore database, dedicated runtime identity, or external load balancer, and found the Firestore API disabled. Public launch still depends on the approved region and controlled domain, Firebase/App Check configuration, Firestore, least-privilege IAM, Cloud Armor, reviewed privacy terms, and live staging evidence. See `PUBLIC_DEPLOYMENT_RUNBOOK.md` and `security_evaluation_report.md` for actual state and release gates.

The user has confirmed there is no controlled public domain yet. A generated `run.app` URL is suitable only for separately configured, restricted synthetic-data staging: it does not apply Cloud Armor and requires broader Cloud Run ingress. The current self-service sign-up flow further means that URL must not be casually shared. The implementation plan keeps the Cloud Armor-backed public topology as the target and treats no-domain staging as an isolated interim option.

## 12. Earlier implementation baseline and Vertex AI decision (2026-09-26)

This section records an earlier planning checkpoint. Its “not deployed” and “not configured” statements are historical and are superseded by the live deployment snapshots below and in `security_evaluation_report.md`.

The initial code slice is in `D:\AI_legal_help`; it was not deployed at this earlier checkpoint. The prototype uses the Google Gen AI Python SDK with the Vertex AI backend and ADC, not the Gemini API in Google AI Studio. The default model and location are configurable starter settings (`gemini-3.5-flash-lite`, `global`); the current demo uses Gemini 3.5 Flash-Lite on Vertex AI's `us` multi-region endpoint.

The first local workflow includes a plain-language PDF briefing, document-grounded Q&A, and two-document comparison. It extracts selectable text from bounded PDFs, sends excerpts through the server to Gemini, requests structured responses, validates quotes against exact page text, and withholds output on citation failures. Gemini's constrained-output schema omits size constraints that caused a `too many states` rejection; Pydantic still enforces those limits after generation. If Gemini output fails runtime validation, the API returns a safe `insufficient_evidence` abstention and logs only field paths/error types. One browser response had the Pydantic error type `json_invalid`, meaning the returned text was not valid JSON; its exact upstream cause was not recorded. The briefing prompt/output were bounded more tightly, output allowance was raised, and the app now records only completion reason plus parser position if malformed JSON recurs. A minimal synthetic Vertex Q&A call and synthetic briefing calls on Gemini 2.5 Flash and Gemini 3.5 Flash-Lite succeeded; browser briefing and Q&A requests also returned 200. These are diagnostics, not the full evaluation suite. Comparison starts with a deterministic text diff. The browser UI presents citations and legal-information boundaries. It does not persist documents by design, but the server sends user-selected document text to Vertex AI to fulfill each operation.

The starter app runs locally by default. A fail-closed production security path has since been added in code: Firebase Authentication with verified email, Firebase App Check, Firestore transactional rolling account quotas, upload bounds, security headers, a Vertex timeout/kill switch, and a Cloud Run template. These controls are not active in the local development mode, and the required Google Cloud services, IAM, Cloud Armor/load balancer, quota settings, and live integration checks have not yet been configured. Do not deploy publicly or use confidential/client legal documents until the gates in `security_evaluation_report.md` are met. See `context.md` for the current working log.

The user confirmed budget-alert setup for the project: INR 500/month with project scope and 50/80/100% current-spend thresholds. No further alert work is in scope. Google's Free Trial currently provides a $300 welcome credit for up to 90 days on eligible Google Cloud services, and its terms explicitly exclude Gemini API in Google AI Studio costs. The current implementation calls Vertex AI, not that AI Studio API. Whether this project's billing account is a Free Trial or paid account and its remaining credit still needs checking in Cloud Billing. A budget alert is a notification, not a spend cap. Gemini 2.5 Flash is scheduled to retire on 2026-10-20, so the starter now defaults to Gemini 3.5 Flash-Lite, which has global availability and is listed as GA through at least July 2027. Verify current model pricing and account eligibility before increasing usage; OCR, data services, and hosting add costs.

Current code and cloud state must not be represented as passing any planned quality, security, legal, accessibility, or performance gate until evaluated. The hardening milestone has 16 local tests passing plus lint, format, compilation, and JavaScript syntax checks; live Identity Platform, App Check, Firestore transaction, Cloud Armor, Vertex-quality, load, and accessibility tests remain. See `security_evaluation_report.md` for evidence, open gates, and production setup sequence.

## Deployed MVP status (2026-09-26)

The live thin slice is at https://clearclause-api-ye2sfsdqnq-uc.a.run.app. Cloud Run and Firestore are in `us-central1`; Gemini 3.5 Flash-Lite uses the Vertex AI `us` multi-region endpoint. Firebase verified-email sign-in, App Check, Firestore weighted quotas, and citation/output validation are deployed. Persistent user document storage, OCR, async ingestion, retrieval, and professional-preparation export remain future work. This temporary public `run.app` route has no Cloud Armor IP filtering; the full public edge and privacy/accessibility release gates remain open.

## 13. Browser demo stabilization and repository readiness (2026-09-26)

- Fixed Firebase client initialization so App Check starts before Firebase Auth. This is required when Firebase Auth App Check enforcement is enabled. Added actionable UI messages for common Firebase configuration/App Check errors and an error code for otherwise unmapped Firebase errors.
- Built and deployed immutable image `sha256:4c1220f16fc4053c0cf9127e5c7c360e8717852e6213e48bfb3180f7bc46e5a4`; Cloud Run revision `clearclause-api-00003-c9n` serves 100% traffic. Health and API configuration checks pass. The browser sign-in success path and authenticated Vertex analysis have not yet been confirmed with a real demo account.
- Updated the project for the user-provided GitHub repository: repo-facing README, security policy, credential/local-state ignore rules, and a repository cleanliness review. The live Cloud Run YAML snapshot and private working context remain local-only.
- Next acceptance: user reloads the linked browser demo and retries sign-in, completes email verification, and—using a synthetic PDF only—runs briefing, Q&A, and comparison. If Firebase sign-in still fails, capture the sanitized `auth/...` error code; never share a password or a real legal document.
- Remaining broader-release gates: measured Gemini quality/citations, negative App Check and quota-abuse tests, dependency/image scan, cost observation, privacy/provider/jurisdiction review, WCAG 2.2 AA, controlled-domain Cloud Armor edge, and rollback/operations readiness.
