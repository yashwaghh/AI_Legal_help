# ClearClause evaluation improvement report

Date: 2026-09-26. The supplied screenshot is the evaluator baseline, not a new score. A fresh evaluation is needed to measure score changes.

| Criterion | Baseline | Implemented improvement | Evidence and limit |
| --- | ---: | --- | --- |
| Code Quality | 88 | Content-safe Python logging, cached schemas, shared authentication state rendering, bounded document labels, GitHub CI and corrected Cloud Build uploads | Ruff lint/format and JavaScript syntax pass; CI uses no cloud credentials |
| Security | 92 | Corrected Firebase referrer conflict and Firestore quota records; clear displayed results on user changes and withhold responses for previous sessions | Firebase configuration read returned 403 without referrer and 200 with the allowed origin; live Firestore round-trip passed for isolated synthetic identity |
| Efficiency | 82 | Reuse valid identity/App Check tokens, cache model schemas, preflight PDF sizes/signatures, prevent overlapping analyses, bound browser wait, retain identical-document model skip | Synthetic Vertex tasks returned supported results: briefing 10.98s, Q&A 1.65s, comparison 1.94s; a single diagnostic sample, not a benchmark |
| Testing | 80 | Expanded 16 tests to 40; coverage and 75% minimum gate; GitHub push/PR checks; fixed Cloud Build exclusions | 40 local tests passed; 80.33% Python statement coverage; test-and-build pipeline runs before deployment |
| Accessibility | 90 | Darker secondary text, larger result text, visible upload focus, 44px button targets, reduced motion, busy/alert announcements, result focus and mobile wrapping | Page assertions and browser checks; full WCAG and screen-reader audit remains open |
| Problem Statement Alignment | 95 | Download summary with quotations/questions, detect short amounts/dates and case changes, disclose bounded analysis, improve email-verification recovery | Tests cover short changes, absent evidence, malformed generation, citation refusal, and the three HTTP workflows |

## Deployment defects repaired

1. **Firebase referrer conflict:** the browser key requires the demo hostname but the app sent `Referrer-Policy: no-referrer`. A live read reproduced `API_KEY_HTTP_REFERRER_BLOCKED`. The new `strict-origin-when-cross-origin` policy sends the allowed origin without sending cross-origin page paths or queries. Key restrictions remain enabled.
2. **Invalid quota serialization:** Firestore rejects arrays directly inside arrays. Quota events now use `{timestamp, units}` map records with the existing atomic transaction and hourly/daily limits. Invalid state still blocks analysis. Two synthetic live writes succeeded; the isolated record is covered by TTL.
3. **CI upload exclusions:** `.gcloudignore` previously excluded the tests and `requirements-dev.txt`. Both are now available in Cloud Build. `.dockerignore` keeps them out of the runtime container.
4. **Missed short contract changes:** lines shorter than 25 characters were skipped. All non-empty lines now participate, including case changes.
5. **Lost signup instructions:** sign-out callbacks could overwrite the email-verification notice. The client now retains it and offers a verification refresh for signed-in unverified users.

## Verification scope

- **40 tests passed; 80.33% Python statement coverage.** Python lint/format and JavaScript syntax passed.
- Live Firebase configuration read: allowed origin accepted, empty referrer rejected.
- Live Firestore: two transactional quota writes succeeded for a generated synthetic identity using developer ADC. This confirms record compatibility and project access, not the full deployed user path.
- Live Vertex: briefing, Q&A and comparison passed schema/citation validation for a tiny synthetic agreement using developer ADC in the configured project and `us` endpoint. This is not a broad legal-quality evaluation or proof of Cloud Run runtime IAM behavior.
- Real browser signup, email delivery, sign-in, App Check, upload, quota and generation together still require an authenticated acceptance run. No user's password was requested or used.

## Deployed release

- Revision `clearclause-api-00005-9wj` serves 100% of Cloud Run traffic at the canonical demo URL.
- Cloud Build `6b259e17-65fe-475c-819b-0e1f7d78099f` succeeded with the configured checks and image build.
- Immutable image digest: `sha256:3da3918b1362e40e818044d31dcbd17461be7f69b10d9c5ca36b82c5e871bbba`.
- Public page, configuration and new CSS/favicon return 200; `/api/health` returns `ok`; unauthenticated `/api/briefing` returns 401.
- Live response headers include the corrected referrer policy and homepage `Cache-Control: no-store`.
- Reloaded browser shows the new sign-in guidance, no observed warning/error logs, loaded accessibility stylesheet, and no horizontal overflow at the observed 407px viewport. This is a targeted check, not an accessibility certification.

## Reproduce checks locally

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check app tests
python -m ruff format --check app tests
python -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=75
node --check app/static/app.js
```

GitHub checks pushes to `main` and pull requests. Cloud Build runs lint, formatting, coverage and compilation before building the image. Tests use synthetic fixtures and mocked provider responses, with the separately recorded live diagnostics above.

## Remaining evidence

Cloud Armor remains absent from the temporary Cloud Run URL. Account farming, token replay, full accessibility review, dependency/image scans, sustained load, a reviewed legal-quality dataset and privacy/provider review remain open. Budget alerts do not cap spend. Re-run the evaluator to obtain new scores.

References: [API key restrictions](https://docs.cloud.google.com/api-keys/docs/add-restrictions-api-keys), [Firestore supported types](https://firebase.google.com/docs/firestore/manage-data/data-types).
