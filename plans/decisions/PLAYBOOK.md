# FastAPI Microservice Playbook

Distilled from building **pobude** (the similarity microservice) in July 2026 — from PRD to
production-ready v0.1.7. This repo is the **reference implementation**: every section links into
real files here. The purpose of this document is that the next backend service — whatever its
domain — never starts from a bare directory again.

**How to read it:** each section states the *decision*, the *why* (compressed from ADRs and the
build sessions), a *reference* into pobude, and the *gotchas we paid for*. Domain logic
(embeddings, chunking, scoring, sync) is deliberately absent — this is scaffolding only.

**Planned follow-up:** once this playbook stabilizes, extract a stripped, `{{service_name}}`-ized
skeleton into this `starter-template/` directory so day 1 of a new service is a copy, not a
re-read.

---

## 1. Repo skeleton

```
backend/app/                # the importable package — all runtime code under one root
  main.py                   #   app factory + lifespan
  config.py                 #   pydantic-settings (one flat class)
  dependencies.py           #   DI hub: auth, DB session, app-wide singletons
  exceptions.py             #   ServiceError hierarchy + exception handlers
  middleware.py             #   request-id / access-log ASGI middleware
  logging_setup.py          #   loguru sinks + stdlib interception
  api/v1/router.py          #   v1 aggregate router (auth applied ONCE here)
  api/v1/routers/*.py       #   one file per route group (health, readyz, dev, <domain>)
  db/                       #   engine / session factory
  models/                   #   SQLAlchemy ORM models
  repositories/             #   thin DB access, one file per aggregate
  services/                 #   business logic, DI-friendly, pure-function-first
  schemas/                  #   pydantic request/response models
  domain/                   #   framework-free core types
  <boundary>/               #   one package per external dependency: ABC + factory + Mock/Http impls
alembic/, alembic.ini       # migrations (run by entrypoint before the app starts, not in lifespan)
tests/
  conftest.py               # tiny — cross-cutting env only ("keep this file small" is a rule)
  unit/    (+ conftest.py)  # no I/O, mocked boundaries
  integration/ (+ conftest) # real Postgres, faked externals
  fixtures/                 # real sample documents, golden files
docs/                       # internal, team-facing: WHY (see §12)
guides/                     # operator/consumer-facing: HOW TO RUN (see §12)
scripts/                    # ops CLIs — never part of the deployed app (see §13)
Makefile                    # the single UX surface (see §9)
Dockerfile, docker-compose.yml, entrypoint.sh
.gitlab-ci.yml, .cliff.toml, scripts/release.sh
.env.example                # exhaustive, commented, single source of truth for ports
AGENTS.md (CLAUDE.md →)     # agent/onboarding router (see §2)
CONTEXT.md                  # domain glossary (see §12)
.python-version             # pins Python for uv/pyenv alongside requires-python
```

Three schema layers, kept separate on purpose so each evolves independently:
**ORM models** (`models/`) vs **API request/response** (`schemas/`) vs **upstream DTOs**
(inside the boundary package). Never reuse one as another.

Reference: the whole repo; structure rationale in [docs/design/structure.md](../docs/design/structure.md).

## 2. AGENTS.md placement — progressive discovery

**Decision:** the canonical agent-instruction file is `AGENTS.md` (the emerging cross-tool
standard); `CLAUDE.md` is a symlink to it (`ln -s AGENTS.md CLAUDE.md`), so Claude Code, Codex,
and other agents all read the same file.

**The progressive-discovery principle:** the root file is loaded into *every* session; subtree
files are loaded only when an agent works in that subtree. So: keep the root file a **small
router** — it points to the authoritative location for each concern and duplicates nothing. Put
subtree-specific rules in a subtree `AGENTS.md`, where they cost tokens only when relevant.
Deep knowledge (domain glossary, ADRs, methodology) lives in normal docs that the root file
*points to*, loaded on demand.

**What each file should contain:**

- **Root `AGENTS.md`** (see [CLAUDE.md](../CLAUDE.md)) — a table of contents, ~1 screen:
  - where issues/PRDs live and the pointer to the issue-tracker convention doc
  - the triage-label pointer
  - the domain-doc pointer (`CONTEXT.md` + `docs/adr/`)
  - the `docs/` vs `guides/` split, in two sentences
  - a pointer to `scripts/` and any calibration/tuning docs
  - (optionally) the 2–3 commands an agent always needs: `make lint`, `make test`
  - **No content that lives elsewhere.** If a section grows past a few lines, it's a doc,
    and the root file keeps only the pointer.
- **Subtree `AGENTS.md`** — one per directory that has its own conventions. In pobude:
  [scripts/CLAUDE.md](../scripts/CLAUDE.md) (ops CLI usage, subcommand reference, calibration
  workflow). Candidates in any service: `scripts/`, `tests/` (if fixture/isolation conventions
  are non-obvious), a frontend dir in a mixed repo. Each should contain:
  - what this subtree is (and what it is *not* — e.g. "not part of the deployed app")
  - local commands / how to run things here
  - local conventions and gotchas that don't apply repo-wide
- **`docs/agents/*.md`** — meta-docs that *skills* consume (issue-tracker layout, triage
  vocabulary, how to use the domain docs). These are configuration for the AI workflow (§14),
  not general onboarding.

**Why:** agents (and new humans) get lost in duplicated, stale instructions. A router that is
always loaded + specifics that load lazily keeps instructions cheap, current, and in one place.

## 3. Configuration

**Decision:** one **flat** `pydantic-settings` `Settings` class; `.env` +
`SettingsConfigDict(env_file=..., extra="ignore", case_sensitive=False)`; `get_settings()`
wrapped in `@lru_cache` as the singleton *and* the FastAPI dependency-override seam for tests.

- Flat, not nested models: 1:1 env-var mapping, one `.env` mirrors every field. (Nested
  settings buy little in a microservice and complicate env naming.)
- `environment: Literal["dev", "local", "test", "prod"]` with derived properties —
  this is the single gating mechanism used everywhere:

  ```python
  @property
  def is_development(self) -> bool: return self.environment in ("dev", "local")
  @property
  def is_production(self) -> bool: return self.environment == "prod"
  ```
- Compute the `.env` path by walking up from `__file__`, so it works regardless of cwd.
- Group fields with `# ── Section ──` banners; stub fields for not-yet-wired features early,
  with a comment — keeps later feature rollout from reworking `Settings`.
- **Version from pyproject** — single source of truth, read once at import
  ([backend/app/\_\_init\_\_.py](../backend/app/__init__.py)):

  ```python
  import tomllib
  _pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
  __version__ = tomllib.load(_pyproject.open("rb"))["project"]["version"]
  ```

  Used in the FastAPI `version=`, the startup log line, `/readyz`, and cross-checked against
  the git tag by CI (§11). Never hardcode a version string anywhere else.
- **`.env.example` is exhaustive and commented**, and is the declared single source of truth
  for ports/URLs across Makefile, docker-compose and Dockerfile. `make backend` and
  `make docker` must expose the *same* ports.
- Runtime-tunable values (thresholds, feature knobs) can additionally be exposed via a
  `GET/POST /config` endpoint layered over env defaults — keep the merge logic a pure function
  so it's unit-testable.

Reference: [backend/app/config.py](../backend/app/config.py), [.env.example](../.env.example).

## 4. App composition

**Decision:** `create_app()` factory + module-level `app = create_app()` for the gunicorn
import string; tests always call the factory for a fresh app with their own
`dependency_overrides`.

Composition order and rules ([backend/app/main.py](../backend/app/main.py)):

1. **Lifespan** (`@asynccontextmanager`): build engine/session-factory as `app.state`
   singletons, dispose on shutdown, end with `logger.complete()` to flush the async log queue.
   Keep it thin. Migrations run in the container **entrypoint**, not in lifespan (multiple
   workers would race).
2. **Unauthenticated probe routers first** (`/healthz`, `/readyz`) mounted directly on `app` —
   they lead the Swagger docs and never require auth (§7).
3. **The v1 aggregate router** applies `Depends(require_api_key)` **once** at the aggregate
   level — never per-endpoint — and centralizes shared `responses={401: ..., 422: ...}` docs
   there too.
4. **Dev-only routers** registered conditionally: `if settings.is_development: app.include_router(dev_router)`.
   In prod the paths *don't exist* (no 403s to probe). Dev routes still sit behind the same
   API key — dev-only is never an excuse for an unauthenticated surface. Dev endpoints must
   call the *identical* production code paths (same functions), not reimplementations — that's
   what makes them a debugging surface and an incidental bug-finder.
5. **Docs gating:** `docs_url="/api-docs" if not settings.is_production else None` (same for
   redoc/openapi). Move docs off the default `/docs`. Declare `openapi_tags` centrally with
   one-line descriptions — cheap Swagger UX win.

**Auth:** single service API key via `APIKeyHeader(name="X-API-Key", auto_error=False)` as a
*dependency* (not middleware), declared as an OpenAPI security scheme so Swagger gets an
Authorize dialog. `auto_error=False` so missing and wrong keys collapse into one 401 shape.
Being a dependency means a later swap to multi-key/DB-backed auth touches one function
([backend/app/dependencies.py](../backend/app/dependencies.py)).

**Error envelope:** a `ServiceError(code, message, detail?)` hierarchy + `register_exception_handlers(app)`
covering `ServiceError`, `HTTPException`, `RequestValidationError`, and a catch-all `Exception`,
all normalized to one envelope:

```json
{"error": {"code": "...", "message": "...", "detail": "..."}, "request_id": "..."}
```

Every handler **logs before responding** (4xx → WARNING, 5xx → ERROR); the catch-all uses
`logger.exception` for the traceback but returns a generic body (no leaked internals). Silent
exception handlers were the single biggest blind spot found in the logging audit.
Reference: [backend/app/exceptions.py](../backend/app/exceptions.py).

**Correlation middleware:** a **raw ASGI middleware class**, not `BaseHTTPMiddleware` (which
buffers/breaks streaming). It generates/propagates `X-Request-Id`, binds it for the request
lifetime via `logger.contextualize()`, injects it into `http.response.start`, and writes the
access-log line. Probe paths (`/healthz`, `/readyz`) log at DEBUG so routine polling doesn't
drown the log. Reference: [backend/app/middleware.py](../backend/app/middleware.py).

## 5. Boundaries: ABC + factory + mock-mode-first

**Decision:** every external dependency (upstream API, model provider, …) gets its own
package with an **ABC**, at least two implementations (`Mock*`, `Http*`/real), and a
`factory.py` that selects by config (`MOCK=true` flag or similar). Everything else in the app
depends only on the ABC.

Why this is the load-bearing idiom of the whole project:

- **Mock-mode-first developer experience:** a committed, realistic mock corpus auto-loads on
  first run, so a new developer or external integrator gets a working, demoable service with
  zero access to production data. Real-data references become "contact <named person>", never
  a broken link.
- **Swappability proved its worth immediately:** the provider behind an "OpenAI-compatible"
  ABC was swapped (OpenRouter ↔ self-hosted vLLM) as a config change when a vendor
  incompatibility surfaced (§15).
- **Contract negotiation:** building the mock from a data dump *before* the real upstream API
  existed let us feed field-level requirements back to the upstream team — and ask for the
  payload shape *we want*, not a mirror of their legacy DB export
  ([ADR-0004](../docs/adr/0004-flat-upstream-contract.md)).
- Dev-only proxy endpoints can mirror the upstream shape exactly, so the external team can
  implement against our Swagger alone.

**Workaround rule:** when you must patch around a vendor limitation (e.g. client-side
fallback for a server feature), make the degraded mode a config switch and **log a WARNING
whenever it is active** — a stopgap must be visible, never a silent behavior change.

## 6. Logging

**Decision:** loguru as the single sink for everything, with a **written level contract**
([ADR-0005](../docs/adr/0005-file-only-logging-air-gapped.md)). The contract — what ERROR /
WARNING / INFO / DEBUG each *mean* project-wide, with every log call held to it — is the
reusable practice; the air-gapped trigger (no Sentry/Loki reachable) is just what forced the
discipline early.

The recipe ([backend/app/logging_setup.py](../backend/app/logging_setup.py)):

- stderr sink honoring `LOG_LEVEL`, plus optional rotating file sink: `LOG_FILE`, daily
  rotation at `00:00`, `LOG_RETENTION` (default ~30 days), gzip compression, and
  **`enqueue=True`** so file I/O never blocks the event loop.
- **Intercept stdlib loggers** (gunicorn, uvicorn, SQLAlchemy, httpx, scheduler) into loguru
  via the standard `InterceptHandler`; clamp noisy libraries to a WARNING floor even at
  `LOG_LEVEL=DEBUG`.
- **`diagnose` tied to `LOG_LEVEL == DEBUG`** — loguru's default `diagnose=True` dumps local
  variables (DB URLs, API keys in scope) into retained tracebacks. `backtrace` stays on.
- Custom formatter appends bound `.bind()` context (`{extra}`) only when present — structured
  fields (`request_id`, `job_id`, `status`) stay greppable in plain text without a JSON sink.
- **Never log a bare `{exc}` interpolation** — use `logger.exception`/`exc_info=True` so the
  traceback is captured. This was the single highest-value fix found pre-prod.
- **Write DEBUG logs proactively** where they'd help, even if unneeded today — so flipping
  `LOG_LEVEL=DEBUG` later works without a redeploy.
- Aggregate per-item loop failures into one summary WARNING; lifecycle milestones at INFO.
- Background jobs log start/finish with bound context (`job_id`, `trigger`, `status`,
  counts) — this exact pattern caught a real prod crash-loop within a day of shipping.

## 7. Health probes

**Decision:** two probes with strict semantics, both **unauthenticated** and mounted before
the auth-gated API so they lead the docs:

- **`/healthz`** — pure liveness. Always 200 while the process is up. Zero I/O, zero
  dependency checks.
- **`/readyz`** — component-level readiness: each dependency (DB, external APIs, background-job
  freshness) probed and marked `critical` or not. Overall status computed by a **pure
  function** (`compute_overall_status`): any critical down → 503 `unhealthy`; only
  non-critical down → 200 `degraded`; else 200 `healthy`. The pure-decision/thin-I/O split
  keeps the logic unit-testable without a DB.

Rules learned the hard way:

- Probes are infra-facing, not app-facing — **no API key**. (Retrofitted in v0.1.7.)
- Probes must be **live but cheap**: for an HTTP dependency, don't invoke the expensive
  operation — hit the cheapest endpoint that proves reachability + auth, and if its response
  body is large, stream and read only the status line. ("this way its cheap" — the origin of
  the whole design.)
- Readiness must reflect **background-job health** too: a sync/ingest job failing after N
  retries flips the component, not just process liveness.
- Docker `HEALTHCHECK` and compose `condition: service_healthy` both point at `/healthz`.

Reference: [backend/app/api/v1/routers/readyz.py](../backend/app/api/v1/routers/readyz.py),
[backend/app/services/health_service.py](../backend/app/services/health_service.py).

## 8. Testing

**Decision:** hard **unit / integration split** as separate trees (`tests/unit`,
`tests/integration`) with separate Make targets and CI jobs — not marker-filtering of one tree.

- **Layered conftests:** root `tests/conftest.py` stays tiny (shared constants, env defaults);
  each tier's `conftest.py` owns its fixtures.
- **Unit tier:** builds the *real* `create_app()` per test; overrides `get_settings` via
  `app.dependency_overrides` (never real env vars) with a hermetic `Settings`. Client is
  `httpx.AsyncClient` over `ASGITransport` — which **never runs the lifespan**, so no DB
  engine is ever created. Fast, no I/O, boundaries mocked (`pytest-httpx` for HTTP,
  `dependency_overrides` for everything else — no monkeypatching internals).
- **Integration tier:** real Postgres, faked externals. Session-scoped fixture creates a
  fresh test DB (admin connection, `DROP ... WITH (FORCE)` / `CREATE`), runs Alembic
  `upgrade head`, drops on teardown. **Savepoint-per-test isolation:** open a connection +
  outer transaction, wrap an `AsyncSession` with `join_transaction_mode="create_savepoint"`,
  roll back the outer transaction after each test. A companion fixture overrides
  `get_db_session` so the route handler shares the *same* session as the test — seeded,
  uncommitted rows are visible to the endpoint under test. A documented opt-in escape hatch
  exists for tests needing genuinely committed, cross-connection visibility (advisory locks,
  background tasks) — with mandatory truncation.
- **Skip, don't fail, when the DB is absent:** integration tier skips wholesale if
  `TEST_DATABASE_URL` is unset — unit tests run anywhere. But in CI, **"a skip is not a
  pass"**: the gate requires 0 skipped integration tests.
- **Real fixtures over synthetic ones:** commit real sample documents; check pipeline output
  against **golden files** regenerated only by an explicit, human-reviewed script run — never
  recomputed silently inside a test.
- **Test fixtures must be pinned, never fall back to gitignored data** — see §15.
- **Test schedulers for real:** "I want it to be tested so that it really triggers on its
  own" — cron/scheduler wiring gets a test that proves actual triggering, not just a mocked
  callback.
- Coverage: unit tier only (`--cov=backend/app --cov-report=term-missing`) — don't blend
  coverage across tiers.

Reference: [tests/unit/conftest.py](../tests/unit/conftest.py),
[tests/integration/conftest.py](../tests/integration/conftest.py).

## 9. Tooling: uv, Makefile, ruff, pytest

- **uv, not pip/poetry.** `uv sync --extra dev`, `uv run`, committed `uv.lock`; CI installs
  with `--locked`. Anything that bumps the version must also re-run `uv lock` (CI's `--locked`
  check *will* fail otherwise — automated into `release.sh`).
- **Makefile is the single UX surface** over uv/docker/alembic/ruff/pytest/trivy/release, with
  a self-documenting `help:` target and `-include .env` so Make sees the same config as the
  app. Canonical target set: `install`, `backend` (dev server, auto-starts DB), `db-start/stop/logs`,
  `migrate*`, `lint`/`lint-fix`/`format`, `test-unit`/`test-integration`/`test`/`test-cov`,
  `docker-build`/`up`/`down`, `trivy`, `test-before-release`, `release`, `gen-secret`, `clean`.
- **pyproject:** dev deps as an optional-dependencies group; ruff (`line-length=100`,
  `select=["E","F","I","UP"]`, `unfixable=["F401"]`, per-file ignore for `__init__.py`
  re-exports); pytest with `asyncio_mode="auto"`, `pythonpath=["backend"]` (tests import
  `app.*` without an editable install), `addopts="-ra --strict-markers"`, and custom markers
  *documented in place* (`unit: fast, no I/O` / `integration: requires Postgres`).

Reference: [Makefile](../Makefile), [pyproject.toml](../pyproject.toml).

## 10. Docker & Compose

**Hardening checklist** (all in [Dockerfile](../Dockerfile) / [docker-compose.yml](../docker-compose.yml)):

- **Digest-pinned base images** (`FROM ...@sha256:...`) — a rebuild can't silently pull a
  different image. Harden the base you have; a fancier base (UBI etc.) was evaluated and
  rejected as complexity without payoff.
- **Multi-stage:** builder runs `uv sync --locked --no-dev` with a BuildKit cache mount;
  runtime copies only `/app`. No tests, no dev deps, no docs in the final image. Curated
  `.dockerignore`.
- **Rootless:** system user (uid 1001); only writable dirs (e.g. `/app/logs`) chowned to it —
  code and venv stay root-owned/read-only, so a compromised process can't modify itself.
  `USER appuser` before `ENTRYPOINT`.
- **tini as PID 1** — signal handling + zombie reaping.
- **Entrypoint** runs migrations, then execs the server.
- **`HEALTHCHECK`** against the unauthenticated `/healthz`.
- **Explicit `TZ`** — see §15.
- Any third-party asset curled at build time: pin to a commit/version **and** verify with
  `sha256sum -c`.
- **Compose:** `security_opt: [no-new-privileges:true]` + `cap_drop: [ALL]` on every service
  (add back only the minimal caps a service truly needs, with a comment saying why);
  `deploy.resources.limits` (cpus/memory/pids) on every service — enforced by plain
  `docker compose up` since Compose v2; omit `reservations` (swarm-only — leaving it in is
  misleading). Real `healthcheck` on the DB + `depends_on: condition: service_healthy`.
  App image tag pinned via `${APP_VERSION:-vX.Y.Z}` from `.env`.
- **Named volume, not bind mount, for writable dirs** — see §15.
- **Trivy twice:** `make trivy` locally over the lockfile; in CI over the repo
  (`--scanners vuln,secret`) *and* over the built image before push.

## 11. CI/CD & release

**Decision:** tag-gated pipelines + a manual-but-guarded local release script. Flow:
`make release` locally → `git push origin main --tags` → CI takes over.

- **`workflow.rules`:** pipelines run only on pushes to `main` and on `v\d+\.\d+\.\d+` tags —
  no per-branch noise.
- **Stages `check → test → build → release`:**
  - `check-version` (tags only): asserts pyproject version == git tag, pre-flights that the
    registry tag doesn't already exist, emits `APP_VERSION` as a dotenv artifact.
  - `test`: trivy (repo, vuln+secret, `--severity HIGH,CRITICAL --exit-code 1`), ruff
    check + format-check, unit tests, integration tests against a real DB service container —
    uv cache keyed by ref slug.
  - `build`: docker build → trivy the built image (`--ignore-unfixed`) → push `:VERSION` and
    `:latest`; `needs:` on all check/test jobs. Release notes via git-cliff.
  - `release`: GitLab Release from the notes with the image as an asset link.
- **`scripts/release.sh`:** preflights (clean tree, **must be on `main`**), computes next
  semver, runs the *same* gates as CI (`make lint`, `make test-unit`, `make test-integration`)
  *before* touching anything, bumps pyproject, re-runs `uv lock`, regenerates `CHANGELOG.md`
  via git-cliff, commits, tags — and **prints** the push command instead of pushing.
- **Conventional Commits → git-cliff** ([.cliff.toml](../.cliff.toml)): `feat→Added`,
  `fix→Fixed`, `perf/refactor→Changed`, `security→Security`; `test/docs/ci/chore` skipped.
  Commit discipline: imperative subject ≤72 chars, 2–3 sentence why-focused body, bullets
  grouped by concern (not by file).
- **Copy-then-prune:** this pipeline was modeled on a sibling project's — then every copied
  job/secret was interrogated and the unused ones (a write token, a CI release-notes job)
  ripped out. Copy proven patterns; never keep cargo.

Reference: [.gitlab-ci.yml](../.gitlab-ci.yml), [scripts/release.sh](../scripts/release.sh),
[guides/operations/ci-cd.md](../guides/operations/ci-cd.md).

## 12. Documentation system

**The core split** — two surfaces, different audiences and volatility:

- **`docs/`** — internal, team/agent-facing: *why and how we decided*.
- **`guides/`** — operator/consumer-facing: *how to run and use it*. Plain markdown, browsed
  on GitLab/in an editor. **No docs-site build step** — mkdocs/Zensical was built and then
  deliberately removed as disproportionate infrastructure (its own dependency group, Docker
  stage, CI job and served mount) for a single microservice's docs. Don't stand that up
  unless audience/size genuinely justify it.

Inside `docs/`:

- **ADRs** (`docs/adr/000N-*.md`): one file per decision; template = `status` frontmatter,
  one-paragraph decision, Considered Options (chosen one bolded), Consequences. When a later
  ADR invalidates earlier work, *flag* the stale artifact — don't silently rewrite history.
- **Markdown issue tracker** (`docs/issues/<feature-slug>/`): `PRD.md` + numbered issues
  (`01-slug.md`, …), each with a `Status:` line (overwritten in place), `## Parent`,
  `## What to build`, `## Acceptance criteria` (checkboxes), `## Blocked by`, comments
  appended under `## Comments`. Conventions in [docs/agents/issue-tracker.md](../docs/agents/issue-tracker.md)
  + [docs/agents/triage-labels.md](../docs/agents/triage-labels.md). Dependency-free,
  reviewable in git history, and directly drivable by agents.
- **Design triad** (`docs/design/`), split by volatility: `specs.md` (the authoritative,
  kept-current contract), `analysis.md` (the messy reasoning scratchpad — data reality,
  decision log with ✅ marks, preserved "why we didn't do the obvious thing"), `structure.md`
  (repo layout + tooling rationale).
- **`CONTEXT.md`** (root): domain glossary — one entry per term with an explicit
  "_Avoid_: <synonyms>" line, relationships, an example dialogue, flagged ambiguities. Keep
  domain vocabulary in its real language (Slovenian `pobuda`/`ukrep` stayed untranslated).
  [docs/agents/domain.md](../docs/agents/domain.md) tells agents to use this exact vocabulary
  and to *flag* (never silently override) conflicts with ADRs.

Inside `guides/`: an `index.md` with a **role-based routing table** (new dev / integrator /
operator / decision-seeker), architecture overview with mermaid diagrams + a module-inventory
table + "deliberate non-features" list, a **decisions.md that summarizes ADRs and links back**
(readers get the digest where they look; the full record stays in `docs/adr/`), per-endpoint
API reference (which can double as the spec an external team implements against), and ops
runbooks (running, configuration, production, logging, ci-cd).

**README stays thin:** quick start, local dev, config pointer, logs note, one link into
`guides/` — it delegates, it doesn't duplicate.

## 13. Operational tooling & calibration

**`scripts/` is operator/agent tooling, never part of the deployed app**, documented by its
own subtree agents file ([scripts/CLAUDE.md](../scripts/CLAUDE.md)).

**Ops-CLI conventions** (from [scripts/simcheck.py](../scripts/simcheck.py)) — adopt for any
service's CLI:

- Config precedence: `--flag` > `ENV_VAR` > repo-root `.env`.
- Every subcommand prints **exactly one JSON document to stdout**; all progress/logs go to
  stderr — scriptable and pipeable.
- Nonzero exit on HTTP errors, echoing the server's error body as JSON.
- Subcommands mirror the service's endpoints 1:1, plus composite workflow commands.
- Destructive subcommands require `--yes` or interactive confirmation.

**Calibrated values are never just numbers.** Any empirically tuned parameter (thresholds,
ranking weights, rate limits, cutoffs) gets the **calibration triad**:

1. *Tool docs* — how to exercise the system (the CLI doc).
2. *Methodology notes* — how to recalibrate, including the lessons that would otherwise be
   lost ([scripts/calibration/README.md](../scripts/calibration/README.md)).
3. *The values themselves with evidence* — before/after table, human-judged evidence per
   zone, known limitations, and **one command that re-verifies** against a labeled,
   git-tracked regression case set ([scripts/calibration/THRESHOLDS.md](../scripts/calibration/THRESHOLDS.md)).

Calibration itself was human-in-the-loop (run requests, eyeball scores, judge pairs
qualitatively) rather than blind statistical optimization, with an explicit asymmetric-cost
policy stated up front (here: a missed match costs more than a false positive). Grow the case
set over time; never restart it. Batch data/fixture regeneration lives in deliberate,
human-reviewed scripts — never in the test suite's automatic path.

## 14. Process: how the work actually got done

The AI-assisted workflow is half of what made this project good. The pipeline:

1. **Grill → PRD → issues.** `/grill-with-docs` interview-drives the design against
   `CONTEXT.md`/ADRs (updating them inline as decisions crystallize) → `/to-prd` freezes the
   conversation into a PRD → `/to-issues` breaks it into **tracer-bullet vertical slices**
   (not horizontal layers), each with acceptance criteria and `Blocked by` links.
2. **TDD loop with a deterministic gate.** `/tdd-implement-scope` works issues sequentially
   (parallel was explicitly rejected), on a feature branch, one commit per issue:
   fresh implementer subagent → red-green-refactor → the *orchestrator itself* runs
   `make lint && make test` and trusts only exit codes and the pytest summary, never the
   subagent's prose — **"a skip is not a pass"** → independent review subagent → commit +
   flip `Status: done`. Max 2 attempts before escalating to the human.
3. **Never commit to `main`.** The agent checks the branch first and proposes a new one;
   the human does the actual commits/pushes in interactive sessions (agent stages in logical
   groups and drafts the message).

Recurring working-style rules that consistently paid off:

- **Propose-then-implement:** big changes start with "don't change anything yet" — a
  read-only investigation (often parallel subagents) producing a numbered findings list; a
  follow-up turn approves specific items ("do 1, 2, 3").
- **Research before adopting conventions:** current best practice looked up (context7/web)
  before proposing Swagger/OpenAPI/compose patterns — don't trust memorized conventions.
- **Copy proven sibling patterns over textbook novelty** (CI, Makefile, DB-test approach —
  testcontainers was rejected in favor of the pattern an existing project already used), then
  **prune what the sibling never actually used**.
- **Never trust docs over code:** when docs and code disagree, verify empirically — including
  full smoke tests (clone into a tmp dir, `make backend`, `make docker`, hit the running
  service) before believing onboarding claims.
- **Docs-as-you-build:** every infra/config change lands with its guide/ops doc in the same
  commit.
- **Verify prod-scale parameters before go-live:** rehearse capacity/config at production
  values, not dev defaults (the dev/prod embedding-dimension mismatch was caught this way as
  an open flag, not an incident).

## 15. Gotchas we paid for

Generalized — each of these cost real debugging time.

- **Container timezone.** Cron fired at the "wrong" hour and log timestamps misled — the
  image had no TZ configured. Set `TZ` explicitly in the image and document that it affects
  scheduling and log timestamps.
- **Bind mounts break rootless containers.** Bind-mounting a writable dir (logs) produced
  `PermissionError` — the host dir is root-owned, the app runs as uid 1001. A **named volume**
  inherits ownership from the image's directory on first use; prefer it for writable dirs,
  or fix ownership in the entrypoint. Don't "solve" it with permissive chmod.
- **`ASGITransport` never runs the lifespan.** Feature, not bug: unit tests get the real app
  factory with zero DB engine — but anything you wire in lifespan silently doesn't exist in
  that tier. Know which tier exercises startup.
- **The outermost error handler lives outside your middleware.** Starlette's
  `ServerErrorMiddleware` wraps everything, so responses from a catch-all exception handler
  bypass your correlation middleware — re-stamp `X-Request-Id` manually there.
- **loguru `diagnose=True` is a secret leak.** Its default traceback decoration dumps local
  variables (DB URLs, API keys) into log files. Force it off except at DEBUG.
- **Tests must pin their fixtures.** A test relied on a mock source falling back to a real,
  *gitignored* data file — green locally, "degraded" in CI where the file didn't exist. Any
  fixture a test needs must be tracked and referenced explicitly; never let a fallback path
  reach gitignored data.
- **"OpenAI-compatible" is a spectrum.** The same model behind OpenRouter honored the
  `dimensions` param; behind self-hosted vLLM it returned 400 (fixable only server-side,
  which we didn't control). When a vendor feature can't be assumed, make the fallback a
  config mode that logs a WARNING whenever active (§5).
- **Review/verify subagents can be rubber stamps.** A Haiku verification step approved
  everything because its prompts were too direct — a judgment agent needs enough ambiguity
  (and independence) in its brief to actually exercise judgment. Deterministic gates (exit
  codes) stay the ground truth.
- **Copied CI configs carry dead weight.** A secret and a release-notes job copied from the
  sibling template were never used there either. Interrogate every copied job/secret.
- **Health-probe polling floods logs.** Kubernetes/compose polling `/healthz` every few
  seconds at INFO drowns everything — log probe paths at DEBUG.
- **Compose `reservations` do nothing outside swarm.** Only `limits` are enforced by plain
  `docker compose up`; keeping `reservations` in the file is misleading.

## 16. Known gaps — flagged, not prescribed

Conscious omissions in the reference implementation. Decide deliberately per project rather
than inheriting them silently:

- **No mypy / type-checking gate.** Ruff covers lint/format only. A new service should decide
  up front whether to add mypy/pyright to `make lint` and CI.
- **No pre-commit hooks.** Enforcement lives in `make lint` + CI, not git hooks. Fine — but
  make it a choice, not an accident.
- **Load testing planned, not landed.** The direction chosen: Locust with *real* fixtures and
  seeded ids, plus a pragmatic `monitor.sh` (RAM/CPU/DB growth) instead of a full
  observability stack.
- **Rate limiting deliberately skipped** for a single-consumer internal service — revisit if
  the consumer profile changes.
- **Auth is a single shared API key** — the dependency seam makes upgrading localized, but
  multi-key/OAuth was consciously deferred.
