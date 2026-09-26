# ClearClause — execution plan

**Goal:** Deliver a safe, judge-ready GenAI MVP with visible evidence for Code Quality, Security, Efficiency, Testing, Accessibility, and Problem Statement Alignment.

**Assumptions:** Four-week sprint; 4–6 person team; English-only pilot; one selected jurisdiction; authenticated users; synthetic or explicitly authorized test documents. Companion implementation plan is the architecture source of truth.

**Status notice (2026-09-26):** Sections 1–14 preserve earlier planning and delivery snapshots; some statements there predate the live deployment. Section 15 below is the latest execution status and supersedes older “not deployed” or “not configured” statements.

## 1. Delivery rules

- Build one complete flow first: upload → process → AI explanation/Q&A → cited comparison → reviewed checklist/export → deletion.
- Make GenAI central through clause understanding, grounded chat, semantic diffs, checklists, and professional-preparation briefs—not a generic chatbot.
- Every generated factual claim is cited or explicitly marked unsupported. Failed citation validation means abstention.
- Treat document text as untrusted. Any function call is read-only and backend-authorized.
- Use a small Google Cloud service set, one region, weekly deployable builds, synthetic demo data, and a budget cap.
- Do not add legal corpus or jurisdiction-specific answers before source governance and professional review.

## 2. Owners

| Role | Ownership |
|---|---|
| Product/demo lead | Scope, user research, plain-language copy, rubric matrix, demo and success measures. |
| Frontend/accessibility engineer | Web UI, authentication client, upload/status, citations, comparison, checklist/export. |
| Backend/platform engineer | Cloud Run API, token verification, authorization, SQL, storage, Pub/Sub, deletion and quotas. |
| AI/document engineer | Document AI, chunk/provenance pipeline, Vertex AI, retrieval, structured output and evaluations. |
| Quality/security owner | Threat model, suites, prompt-injection cases, CI gates and release checklist. |

Roles may be combined, but another person reviews IAM, security-sensitive code, prompts, and schemas.

## 3. Four-week schedule

### Week 0 — Align and de-risk (1–2 days)

Select user, launch jurisdiction, document types, authorized demo data, retention, region, budget, and legal-boundary reviewer. If jurisdiction remains undecided, limit responses to supplied documents. Create dev/staging projects, billing alerts, APIs, least-privilege identities, repo, threat model, data-flow map, and synthetic evaluation corpus with answer keys.

**Deliver:** product brief, user journey, rubric evidence matrix, architecture/data lifecycle, evaluation corpus, decision log.

**Gate:** No personal legal document used before privacy/terms review; billing alerts and synthetic corpus exist before live model calls.

### Week 1 — Secure foundation and ingestion

Set up monorepo, shared typed contracts, lint/type checks, migrations, CI, and Terraform. Configure Identity Platform and server-side token verification. Deploy separate Cloud Run web/API/worker services and identities. Configure private Cloud Storage and lifecycle rules. Implement scoped short-lived upload, checksum/type validation, completion callback, Pub/Sub, idempotency/retry/dead-letter logic, Document AI OCR, page provenance, and accessible status UI.

**Deliver:** Authenticated user uploads a synthetic file and sees READY, NEEDS_REVIEW, or FAILED with a useful explanation.

**Gate:** Anonymous and cross-user tests fail safely; duplicate events do not duplicate chunks; no raw text or signed URL in logs; staging deletion removes source and stored chunks.

### Week 2 — Core GenAI and grounding

Add Cloud SQL with pgvector and full-text search. Chunk by page/section and embed with Vertex AI. Enforce user/document retrieval filters. Implement Gemini clause taxonomy, summary, Q&A, explicit obligation extraction, and professional question preparation. Require structured outputs, untrusted-document handling, bounded context, citation/quote validation, and abstention. Add golden and prompt-injection evaluations; record model/prompt/parser versions.

**Deliver:** AI briefing and question answering on digital and scanned synthetic PDFs, exact source links, uncertainty, and a deliberate abstention.

**Gate:** Every displayed citation resolves to a source span; unsupported output is not stated as fact. If quality misses the gate, narrow to extraction-only answers.

### Week 3 — Comparison and refinement

Implement deterministic section alignment and exact text diff. Have Gemini explain only changed excerpts, neutrally, citing both versions. Add user-selected comparison lenses, editable checklist, professional-preparation brief, and cited export. Complete keyboard operation, focus/status announcements, screen-reader labels, contrast, zoom/reflow, and non-color diff labels. Add quotas, token/output limits, Cloud Run caps, and cost/latency instrumentation. Run moderated walkthroughs with five users where possible, including an assistive-technology and low legal-literacy user.

**Deliver:** version comparison, user-editable action list, accessible export, user-feedback log, accessibility notes, initial cost/latency results.

**Gate:** Model explanation matches deterministic diff; vague dates require verification; critical/serious accessibility blockers are fixed.

### Week 4 — Release candidate and judging

Freeze features. Run unit, integration, end-to-end, GenAI quality, security/dependency/image, abuse, accessibility, and load suites in staging. Verify deletion, retention, queue replay, dead-letter recovery, rollback, log redaction, IAM, bucket privacy, SQL row-level security, and budget alerts. Prepare demo account, two synthetic contract versions, concise architecture/threat/evaluation packet, user guide, and runbook.

**Deliver:** release candidate; six-dimension evidence matrix; scorecard; demo script; known limits; go/no-go record.

**Gate:** No critical/high security issue; zero cross-user failures; citation checks pass; AI abstains when unsupported; deletion works; accessibility review complete; cost alerts active.

## 4. Post-MVP invited pilot (2–4 weeks)

1. Qualified local legal reviewers check product boundaries, examples, privacy notice, jurisdiction, deadline wording, retention and consent.
2. Review provider terms, data location, deletion, backups, incident procedure, and privacy obligations.
3. Expand reviewed evaluation cases across layouts, scans, tables, ambiguities, and adversarial instructions; measure omissions and false positives.
4. Test backlog/replay, database restore, model/processor outage, quotas, rate limits, and deletion reconciliation.
5. Name on-call/support owners, severity levels, escalation, model rollback, and incident response.
6. Invite a small cohort, review issues/quality daily, and expand only while gates remain green.

External legal information is a separate milestone: official-source inventory, jurisdiction/version metadata, update monitoring, professional review, citation tests, and separate launch approval.

## 5. Definition of done

| Workstream | Done when |
|---|---|
| Product/content | Every main view explains evidence, uncertainty, limitations, and user next step in plain language. |
| Frontend | Upload, answer, source navigation, compare, checklist/export, and delete work with keyboard, screen reader, zoom, and readable errors. |
| API/domain | Every read/write checks ownership; inputs and model outputs validate; retries and quotas are safe. |
| Ingestion | Async, idempotent pipeline preserves page/section provenance, quality status, and retry visibility. |
| GenAI | Clause understanding, grounded Q&A, semantic comparison, and checklist produce schema-valid, cited output or abstain. |
| Infrastructure | Terraform reproduces environment; identities are least privilege; storage private; alerts and rollback configured. |
| Quality/security | Results tie to exact release candidate; each gate has named reviewer/signoff. |
| Demo | Clean run shows meaningful GenAI, exact evidence, abstention, comparison, privacy/deletion and rubric proof. |

## 6. Rubric evidence packet

| Dimension | Demonstrate | Evidence |
|---|---|---|
| Problem alignment | Ask about termination; see simple answer, cited clause/page, uncertainty, next question; compare revised file. | Demo and user-task completion notes. |
| GenAI value | Clause understanding, grounded conversation, semantic change explanation, checklist, professional brief. | Versioned model/prompt/evaluation report, citations, abstention. |
| Security | Private bucket, upload expiry/scope, least privilege, SQL filters, deletion, negative access test. | Threat model, tenant-isolation results, redacted logs. |
| Testing | Functional, adversarial, model and failure scenarios. | CI and quality scorecard with failures. |
| Accessibility | Keyboard upload, citation, compare, delete; announced status; readable text diff. | WCAG 2.2 AA checklist and manual review. |
| Efficiency | Async queue, bounded context, diff-first comparison, token and scaling limits. | Staging p95 latency and cost per task. |
| Code quality | Typed modules, shared schemas, Terraform, CI, migrations, runbook. | Repo map, checks, architecture decisions, dependency scan. |

Report measured values from the build; do not claim targets were achieved based only on the plan.

## 7. Test cases and gates

Cover born-digital/scanned files, tables, split-page clauses, term changes, ambiguous dates, contradictions, missing evidence, poor OCR, unsupported language, corrupt/encrypted files, and embedded prompt injection. Also test expired/revoked tokens, guessed IDs, duplicate storage events, stale generations, downstream outage, rate limits, and deletion during processing.

Proposed pilot gates:

- 100% of displayed citations resolve technically to exact source.
- ≥95% citation correctness on professionally reviewed pack; zero ungrounded high-consequence claims in that set.
- Zero cross-user access in authz suite.
- ≥90% ambiguous, missing, unreadable, or conflicting cases warn or abstain.
- No critical/serious automated accessibility finding; manual core-flow review completed.
- Staging p95 and cost/task meet a target declared before release.
- No high-severity exploitable dependency/image/security finding open.

If a gate fails, narrow the feature or delay launch. Do not quietly lower the threshold.

## 8. Release and operations

1. PR checks run formatting, lint/type, unit, migration/schema, secret/dependency, and synthetic prompt evaluation.
2. Cloud Build creates immutable Artifact Registry image digest.
3. Deploy same digest to staging and run integration, smoke, security, accessibility, and quality suites.
4. Product, security, accessibility, and legal-boundary owners record decisions.
5. Promote approved digest. Keep Cloud Run revision rollback and separate prompt/model rollback.
6. Monitor errors, queue age, extraction failures, answer latency, token use, cost, deletion backlog, and abuse.
7. Use incident severity and support procedures; restrict content access during debugging.

References: [Cloud Build to Cloud Run](https://docs.cloud.google.com/build/docs/deploying-builds/deploy-cloud-run), [Cloud Run autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling), [Pub/Sub dead letters](https://docs.cloud.google.com/pubsub/docs/handling-failures), [Cloud Monitoring alerts](https://docs.cloud.google.com/monitoring/alerts).

## 9. Risk register

| Risk | Mitigation / trigger |
|---|---|
| GenAI invents duty or date | Exact source validation, reviewed set, no deadline computation; unsupported high-consequence claim blocks release. |
| OCR misses key passage | Page count/quality checks, original preview, warning and retry; do not imply complete extraction. |
| Cross-user access | API checks, SQL row security, private storage and negative tests; confirmed failure stops pilot. |
| Prompt injection | Untrusted-source boundary, no privileged tools, schema validation and adversarial evaluation. |
| User mistakes output for advice | Neutral language, source-first UI, professional-preparation next step, reviewer signoff. |
| Stale or mismatched law | No law corpus in MVP; future official-source and jurisdiction/version governance. |
| PII enters telemetry | Content-free allowlist, redaction, restricted access, log scan. |
| Cost spike | Quotas, token caps, queue/instance caps, budget alert, generation kill switch. |
| Preview service changes | Adapter boundary, OCR fallback, evaluation before upgrade. |
| Accessibility barrier | Weekly user review; unresolved critical barrier blocks release. |

## 10. Five-to-seven-minute demo

1. Introduce a user comparing two synthetic service agreements.
2. Upload version one; show private asynchronous processing.
3. Ask when either party may terminate; show Gemini explanation, exact quote/page, and citation navigation.
4. Ask something absent; show abstention and a suggested professional question.
5. Compare version two; show exact changed words and neutral Gemini explanation citing both files.
6. Generate/edit a checklist and flag a vague date for verification.
7. Export a professional-preparation brief and delete both files.
8. Close with measured evaluation, tenant-isolation result, accessibility notes, p95/cost, and known limits.

Have a recording/screenshots as fallback and label it. Never demo with a real person’s legal document.

## 11. Go/no-go checklist

- [ ] Scope is information/navigation, not professional advice.
- [ ] Jurisdiction/data terms reviewed, or answers restricted to supplied documents.
- [ ] Test/demo data is synthetic or authorized.
- [ ] Authentication, ownership, SQL filters/RLS, private storage, and deletion verified.
- [ ] Gemini output schema and citations validated; unsupported cases abstain.
- [ ] Prompt-injection and cross-user suites pass.
- [ ] OCR gaps and failed jobs visible and recoverable.
- [ ] Keyboard/screen-reader review covers upload, answer, citations, comparison, export, deletion.
- [ ] Staging evidence supports latency, cost, quota, and alert choices.
- [ ] No high-severity security issue; rollback and incident owners named.
- [ ] Demo and evidence packet correspond to the same release candidate.

**Success condition:** A reviewer sees useful GenAI over document structure, can verify every generated statement against source text, sees honest abstention where evidence is missing, and can inspect evidence for every supplied rubric dimension.

## 12. Live execution snapshot (2026-09-26)

This section records implementation state alongside the planned schedule. The original four-week plan remains the target sequence; elapsed time does not mean a gate has passed.

### Started: local GenAI vertical slice

**Created in `D:\AI_legal_help`:** FastAPI starter API, minimal accessible browser UI, Google Gen AI SDK Vertex adapter using ADC, PDF text extraction with page mapping, briefing/Q&A/version comparison endpoints, structured response models, exact source-quote validation, citation-failure abstention, deterministic paragraph diff, input bounds, Dockerfile, Cloud Build image definition, and local setup README.

**Done:** Python 3.13 virtual environment and dependencies installed; FastAPI server started at `http://127.0.0.1:8000`; health endpoint returned `status=ok` and `genai_configured=true`; home page returned HTTP 200 with all three workflows. A minimal synthetic Vertex Q&A succeeded. A synthetic briefing first found and reproduced a structured-schema rejection (`too many states`); the Gemini schema was simplified while server-side Pydantic bounds remain, after which briefings succeeded on Gemini 2.5 Flash and the updated Gemini 3.5 Flash-Lite model with citations matching the synthetic page. Browser briefing and Q&A submissions returned HTTP 200. One later response failed JSON parsing (`json_invalid`); the app now labels this as invalid JSON, caps briefings at six short points, raises the output allowance, and logs only finish reason and parser position if it recurs. Current server was restarted with these changes.

**Not yet done:** a user-uploaded synthetic PDF through the browser end-to-end, full evaluation, test suite, security review, accessibility review, or Cloud Run deployment. The synthetic direct model calls are diagnostics, not a quality evaluation. The `cloudbuild.yaml` builds an image only; it does not deploy.

### Prototype operating guardrails

- Text-based PDFs only; 12 MiB max, 40 pages max, and 100,000 extracted characters max. Scanned-PDF OCR is a later phase.
- The app is local-only and has no user login, authorization, multi-tenant controls, or persistent deletion/retention flow. It must not be exposed publicly.
- Use synthetic or authorized data until Identity Platform, ownership checks, private storage, and privacy review are implemented.
- Vertex AI model calls use project ADC; Google AI Studio API is not used. The current `$300` Cloud Free Trial credit may cover eligible Vertex AI usage if the billing account is an eligible trial and within the 90-day/credit limit. The actual project billing-account status and remaining credit have not been checked.
- The user confirmed budget alerts are set; alert setup is considered complete. Alerts do not cap or automatically stop spend.

### Next work blocks and gates

1. **Setup/readiness:** Check billing account trial/status and remaining credit, then retry the UI with a synthetic PDF. Model requests consume billable usage. Record exact model, region, cost, and failures. No production privacy data.
2. **Quality/security:** Add versioned synthetic cases, test citations/abstention/prompt injection and IDOR once auth exists; implement accessibility checks and manual review; collect rubric evidence rather than claim targets.
3. **Identity/storage:** Choose jurisdiction and region; configure Identity Platform; establish ownership model; add private Cloud Storage upload and deletion design. Gate: negative cross-user access review before multi-user storage.
4. **Async processing:** Add Pub/Sub idempotency/dead-letter handling and Document AI OCR, expose low-quality extraction status, then benchmark.
5. **Grounded retrieval:** Add Cloud SQL/pgvector only after identity filters/RLS, migrations, and citation anchors are ready.
6. **Authenticated Cloud Run:** Build and deploy separate API/worker/web identities with minimal roles, scaling bounds, content-free logs, staged promotion, and rollback. Keep unauthenticated access disabled.

Update this snapshot and `context.md` after each work block, recording actual cloud mutations, checked evidence, and unresolved gate items.

### Security and rubric hardening update (2026-09-26)

**Completed in the local app:** Firebase verified-email authentication path and browser sign-in UI; Firebase App Check/reCAPTCHA Enterprise verification path required in production; Firestore transactional rolling one-hour and 24-hour account quotas (briefing/answer 1 unit, compare 2; defaults 8/hour and 30/day); fail-closed behavior if auth/App Check/Firestore fails; request body limits before multipart parsing; CSP/security headers; Vertex timeout and operator kill switch; `.dockerignore`; production Cloud Run template with load-balancer-only ingress, scale/concurrency bounds, health probes; README and security/evaluation report.

**Verified locally:** 16 automated tests pass; Ruff lint and format checks pass; Python compilation and JavaScript syntax checks pass; local browser page smoke check passes. Tests do not call Vertex or live Google Identity/Firestore/App Check resources.

**No cloud mutation:** no Google API enablement, Firebase/Identity Platform setup, Firestore database, TTL policy, IAM grant, Cloud Armor policy, load balancer, Cloud Run deploy, budget change, or Vertex generation was made during this hardening block.

**Current gate:** Not approved for public deployment. Configure Identity Platform, App Check/reCAPTCHA Enterprise, Firestore Native/TTL, least-privilege runtime service account, Vertex hard quotas, and HTTPS load balancer + Cloud Armor. Then run live integration/abuse/cost/load checks and accessibility/privacy review. See `security_evaluation_report.md` for step-by-step sequence and go/no-go list. Preserve the original four-week schedule as the target plan; this snapshot records code achieved only.

## 13. Public deployment execution sequence (2026-09-26)

This release sequence supersedes the earlier generic “deploy Cloud Run” step with the actual project state and a public-edge design. It prepares a staging pilot; it does not authorize a production launch.

1. **Decision gate:** choose approved Firestore/Cloud Run region, controlled DNS domain, privacy/support owner, and invited-pilot scope. Record billing state, model availability, and Vertex quotas.
2. **Read-only preflight:** run `deployment/public-release-preflight.ps1`; clear every automated `BLOCK` and complete its manual Firebase, Firestore TTL, IAM, domain/Cloud Armor, privacy, and release items.
3. **Provision identity and quota protection:** enable required APIs; configure Firebase email verification and App Check; create Firestore Native mode and `expiresAt` TTL; create the dedicated runtime identity with only Vertex AI and Datastore roles.
4. **Build artifact:** create the regional Artifact Registry repository; run the Cloud Build check/build pipeline; inspect vulnerability results and deploy only an immutable image digest.
5. **Deploy behind the edge:** apply the reviewed Cloud Run template with private/load-balancer-only ingress and caps; configure the minimal invocation permission required by the external load balancer; create managed HTTPS, DNS, serverless NEG, and Cloud Armor. Never use open direct `run.app` ingress.
6. **Stage and review:** test auth/App Check failures, distributed quota concurrency, Firestore outage, upload abuse, prompt injection, citation grounding/abstention, logs, cost, accessibility, privacy language, and rollback using synthetic documents.
7. **Launch decision:** pilot only after each gate has evidence and named operational owners. Keep `GENAI_ENABLED=false` ready for immediate analysis shutdown.

**Current verified blockers:** Firestore API is disabled; no Firestore database, Artifact Registry repository, Cloud Run service, dedicated runtime service account, HTTPS load balancer, or Cloud Armor policy was found. Region and production Firebase/App Check values remain unset. The user confirmed that no public domain is available yet, so the planned HTTPS/Cloud Armor edge cannot be completed. A generated `run.app` route is only a restricted staging option and is not equivalent to the public release path. No cloud mutation was made during this readiness pass. `PUBLIC_DEPLOYMENT_RUNBOOK.md` has exact commands and the preflight script is read-only.

## 14. Live deployment snapshot (2026-09-26)

**User choices:** Cloud Run/Firestore in `us-central1`; Gemini 3.5 Flash-Lite via Vertex `us` multi-region; temporary public Cloud Run `run.app` URL with application protections, accepting no Cloud Armor IP edge until a controlled domain is available.

**Completed:** APIs enabled; Firebase Web app/Identity Platform email-password configured; reCAPTCHA Enterprise key registered with App Check and Authentication enforcement; Firestore Native database/delete protection and active quota TTL; runtime service account with only Vertex and Datastore roles; Artifact Registry image built by immutable digest; Cloud Run service deployed with verified-email auth, required App Check, Firestore quotas, 0–3 instances, concurrency 4, and 90-second timeout. URL: https://clearclause-api-ye2sfsdqnq-uc.a.run.app.

**Evidence:** `/` returned 200, `/api/health` returned `ok`, `/api/config` confirmed production auth/App Check values, Firestore TTL reported ACTIVE, and runtime IAM contained only the two expected roles. The Docker-only build did not run `cloudbuild.yaml` test steps. No user signup, model generation, automated test, abuse, performance, or accessibility evaluation was run in this turn.

**Remaining gates:** real synthetic-PDF GenAI acceptance; negative-token and quota-abuse checks; model quota/cost monitoring; image/dependency scan; privacy/provider/jurisdiction review; WCAG 2.2 AA, rollback, and operational ownership. Direct `run.app` has no Cloud Armor IP filtering; keep the pilot small and documents synthetic/authorized. Move to a controlled-domain HTTPS load balancer + Cloud Armor before a broader public launch.

## 15. Browser demo stabilization and GitHub preparation (2026-09-26)

### Completed

- Corrected the Firebase browser setup order: App Check now initializes before Firebase Auth, as required when Auth App Check enforcement is enabled.
- Improved sign-in error messages so common Firebase configuration and App Check errors have useful guidance; unexpected failures surface the sanitized Firebase error code.
- Built and deployed image digest `sha256:4c1220f16fc4053c0cf9127e5c7c360e8717852e6213e48bfb3180f7bc46e5a4`. Cloud Run revision `clearclause-api-00003-c9n` now serves 100% traffic. The configured demo URL, `/`, `/api/health`, and `/api/config` were checked.
- Prepared the repository for `https://github.com/yashwaghh/AI_Legal_help.git`: improved public README, added a security policy, tightened `.gitignore`, and excluded the private context log and live deployment YAML snapshot.

### Acceptance still needed

- Retry sign-in in the browser after a fresh reload. Firebase sign-in was not performed by the deployment operator, so this fix still needs confirmation in the browser.
- After successful email verification, run briefing, grounded Q&A, and comparison using only synthetic or otherwise authorized PDFs. Capture model/citation acceptance evidence and user-visible errors.
- A successful temporary demo does not close Cloud Armor, privacy/provider, data-residency, WCAG 2.2 AA, abuse/load, cost, or rollback gates for a broader public launch.
