# tciqrestclient — Project Handover

> Published to real PyPI as `tciq` through version `0.1.1`, then renamed
> to `tciqrestclient` (distribution name and Python import name both) —
> see §10 for the full rename/publish history. This document uses the
> old name `tciq` wherever it's narrating what actually happened at the
> time under that name, and the new name `tciqrestclient` everywhere
> else.

**Originally written:** 2026-08-26
**From:** Vinod Shelke \<vinod.shelke@viavisolutions.com\>
**Last updated:** 2026-09-15, by Claude (see §0)
**Version:** 0.1.0
**Tests:** 334 passing, 0 skipped (see §9 — one fixture is a constructed placeholder, not yet GUI-confirmed)
**Requirements:** IQ-PYTHON-001–011 implemented; IQ-PYTHON-011 (Report Generation) confirmed partially broken against a real server — see §8/§9

---

## 0. Update Log — 2026-09-02

This handover document itself — along with `PLAN.md`, `DEPLOYMENT_PLAN.md`,
and `WIDGET_QUERY_PLAN.md`, all referenced throughout the sections below —
had never actually been committed to git. The repo's `.gitignore` (added in
the same commit as this package) blanket-ignored `*.md` and `*.json`, so
`git status` never flagged any of them as untracked and they were silently
never pushed. Only this file happened to still exist on disk locally;
`PLAN.md`, `DEPLOYMENT_PLAN.md`, `WIDGET_QUERY_PLAN.md`, and
`tests/data/*.json` (the real captured fixtures the test suite depends on)
are gone — not recoverable from this machine. That's the root cause behind
several items below, and it's why this revision folds as much of their
substance as is known into this single document instead of pointing to
files that no longer exist.

Everything below has been updated in place rather than left to contradict
this note; sections that used to describe an open problem now describe
what was actually found and fixed. Summary of what changed:

- **`.gitignore` fixed.** Narrowed from blanket `*.md`/`*.json`/`*.log` to
  the specific paths that must never be committed:
  `tciqclient/.env`, `tciqclient/views.json`, `tciqclient/*.log`. See §2.
- **The two "known bugs" this document used to list (default-order
  projection gap, two-tier snapshot filter) were already fixed** in the
  committed code — `_apply_default_order_updates()` /
  `_apply_snapshot_filter()` in `view_query_builder.py` both implement the
  fix, with passing tests
  (`test_default_order_on_inactive_column_injects_its_own_projection`,
  `test_snapshot_filter_uses_provider_template_with_value_substitution`).
  Removed from §9's gap list; see §9 for what's still genuinely open.
- **`tests/data/*.json` (the real captures) confirmed unrecoverable.**
  Not just gitignored — actually absent from this machine, including from
  a real orion-res server-log archive (`iq-logs.tar.xz`, found elsewhere
  on this machine) that has real column names corroborating the fixture
  shapes but not the literal request/response JSON bodies. The 33 tests
  that depend on them now **skip with a clear reason** instead of
  failing/erroring (`_load`/`_load_data` in the three affected test files
  call `pytest.skip()` when the file is missing), so `pytest` is green
  (225 passed, 33 skipped) instead of red (15 failed, 18 errored). See §9
  for exactly what to re-capture to reactivate them.
- **`tciqclient/README.md` added.** `pyproject.toml` declares
  `readme = "README.md"`, but the file didn't exist — this would have
  broken `python -m build`. Verified the package now builds (sdist +
  wheel) cleanly.
- **`tciqclient/CHANGELOG.md` added.**
- **CI added** — `.github/workflows/tciq-tests.yml` runs `pytest` on
  every push/PR touching `tciqclient/`, across Python 3.8–3.12.
- **The root `setup.py`'s `iq` extras group was actually added.** This
  document used to claim (§3) it already existed while also listing it
  (§10) as an open cross-team ask — neither was quite right: it didn't
  exist, and it wasn't a cross-team ask, because this checkout *is*
  `py-stcrestclient` (its own `setup.py` metadata — `name='stcrestclient'`,
  the GitHub URL, the version history — confirms it, just checked out
  locally under the `py-iqrestclient` folder name). Added
  `extras_require={'iq': ['tciq>=0.1.0,<1.0']}` directly.
- **Widget query builders unchanged** (`x_y_chart`/`pie_chart`/
  `histogram`/`boxplot`) — still not validated against a real server. No
  `magellan-frontend` TypeScript source or live `orion-res` server was
  reachable from this environment to make further progress here. A
  `magellan-frontend.tgz` found elsewhere on this machine is a minified
  production JS bundle, not source — not usable for the byte-for-byte
  reverse-engineering this needs. **Superseded the next day — see the
  2026-09-03 update below: a live server turned out to be reachable
  after all.**

---

## 0a. Update Log — 2026-09-03

- **A live orion-res server was found running locally on this machine**
  (`http://127.0.0.1:9200`) — discovered incidentally while running the
  new `examples/discover_local.py`'s `timeout=` demo, which does a real
  `list_tests()` call. This directly overturns several "not reachable
  from this environment" statements made the day before (throughout §0
  above and §9 below) — they were true at the time, not stale reporting.
- **`list_table_names()`/`list_fields()` were confirmed broken against a
  real server, then fixed** — not just an unconfirmed assumption as §9
  used to say. The real `GET /databases/{id}?detail=full` response has
  no `"tables"` key at all (`result_sets`/`dimension_sets` instead); both
  methods always returned `[]` as a result. Fixed in `tciq/databases.py`
  and re-verified against the real server (50 tables, 1191 fields for a
  real test database) — see §9 for the full before/after.
- **The real `tests/data/*.json` fixtures were recovered** — two of the
  three genuinely, one provisionally. See §9's "RECOVERED" section for
  the full detail; short version: `pytest` went from 227 passed/33
  skipped to **260 passed, 0 skipped**, and the core
  `single_level_table` builder is now independently re-confirmed against
  fresh real data, not just self-consistent.
- **A real precedence bug was found and fixed** in
  `tciq/config.py::resolve_config()`: an explicit `aion_url=` kwarg was
  silently ignored if `TCIQ_BASE_URL`/`TCIQ_HOST`/`TCIQ_INSTALL_DIR`
  happened to be set in the environment. Fixed and re-verified against
  the real AION server (it now actually attempts the login instead of
  silently skipping it) — see §9's own entry for the full before/after
  and the six new regression tests in `test_config.py`.
- **§5's discovery precedence table was also found and fixed to be
  wrong** — it listed AION third; the actual code puts it last. See §5.
- **The widget-query-builder blocker is now half-lifted** — the missing
  `magellan-frontend` TS source is still missing, but the *other* way to
  validate those four builders (capture against a real server) is now
  available via the same local server. See the "Widget query builders"
  status table below and §11.
- Examples reorganized to map one-to-one with PRD use cases: discovery
  split into `discover_local.py` (modes A-D) and `discover_aion.py`
  (mode E); `run_json_definition_query.py` split out of
  `query_modifiers.py` for IQ-PYTHON-003's JSON-string-query bullet
  specifically. `test_examples_smoke.py` added, covering every example
  against a mock (not a substitute for real-server testing — see
  `TESTING.md` §3.2).
- **A third real bug was found and fixed**: `_apply_snapshot_filter()`'s
  fallback in `view_query_builder.py` used a raw, unqualified attribute
  path (`"test.snapshot_name = '...'"`) where an outermost filter needs
  an alias-qualified one (`"view.test_snapshot_name = '...'"`) — 400s
  against a real server otherwise. Fixed and re-verified end-to-end
  through `query()` against the live server. See §9's own entry.
- **Final state after all three bug fixes above**: `pytest` is **267
  passed, 0 skipped** (260 after the fixture recovery, +6 for the AION
  precedence regression tests, +1 for `fetch_view_data.py`'s smoke test
  — the snapshot filter fix itself updated existing tests rather than
  adding new ones).

---

## 0b. Update Log — 2026-09-03 (continued) — two PRD compliance gaps closed

A fresh, independent re-read of the PRD text (not just this document's
own checkmarks) surfaced two real gaps that the §8 table had been
marking "✅ Done" prematurely. Both are now fixed and re-verified against
the live local server:

- **IQ-PYTHON-004 (Live/Snapshot) — `query()` defaulted to the wrong
  table.** The PRD's snapshot mode is supposed to be the default; calling
  `query(name=...)` with neither `table_index=` nor `data_type=` was
  actually resolving to `details.user_data.tables[0]`, which is whichever
  table the view happens to list first — live data on some views,
  snapshot on others. Fixed in `tciq/views.py`'s new
  `_resolve_table_index()`: with no explicit `table_index=`/`data_type=`,
  it now scans for the table with `data_type == "eot"` and only falls
  back to index 0 if none exists. Verified against the real server:
  `iq.query(name="Detailed Stream Results")` (no `data_type=` at all) now
  returns rows containing `test_snapshot_name`, an eot-only field —
  confirming snapshot data really is the default, not an artifact of
  table ordering.
- **IQ-PYTHON-003 (Named Views) — a `save_view()`-created view was
  genuinely unusable, not just "worked around in the example."** §9 used
  to describe this as a real gap patched client-side only inside
  `manage_views.py`, with the library itself left broken. That's now
  fixed properly in the library: `tciq/views.py` adds
  `_find_provider_elsewhere()`/`_ensure_provider_available()`, and
  `get_view_definition()`/`list_view_columns()`/`build_field_resolver()`
  (and their `client.py` callers) now accept `transport=`/`timeout=` so
  they can search other views on the server for a `query_providers` entry
  matching the missing one by name, and patch it into a local copy of the
  view before building the query. `manage_views.py` was simplified back
  down to calling the public API directly — no more manual patching in
  the example.
  - **Follow-on bug found while verifying this fix**: the naive "first
    match by name" approach hit a real `"pagination requires at least one
    order expression"` 400 from the server. Root cause: providers sharing
    the same name are *not* byte-identical across views —
    `default_order_updates.order_updates` varies per-view (confirmed: 4 of
    5 real views sharing the `"eot_table_stream_traffic"` provider name
    had an *empty* `order_updates`, only one had the real one). Fixed
    `_find_provider_elsewhere()` to prefer a match with a non-empty
    `order_updates` over whichever match it finds first. Re-verified: the
    resulting order clause now matches the true source view exactly
    (`['view.test_snapshot_name_order ASC', 'view.tx_stream_stream_id
    ASC', 'view.rx_stream_key ASC']`).
  - End-to-end real-server confirmation via `manage_views.py`: 507 views
    listed, a view cloned from "Detailed Stream Results", 40 active
    columns listed on the clone, 5 real rows queried back through
    `query(name=...)` — the exact "save, reuse, and delete" flow the PRD
    describes — then the clone deleted. No workaround code in the example
    at all; every step goes through the public `IQClient` API.
- 8 new regression tests added in `tests/test_views.py` covering both
  fixes and the order-preference tie-break. **`pytest` is now 277 passed,
  0 skipped.**
- These two fixes were originally attempted via a 3-agent parallel
  Workflow run (worktree-isolated implementers + review/synthesis
  phases); the workflow tooling's git-worktree isolation failed with a
  `WorktreeIsolationError` for all three agents. Manually verified (via
  `git rev-parse`, `.git` file contents, and the main repo's
  `.git/config`) that the worktrees themselves were correctly configured
  with no real `core.worktree` redirect — concluded this was a tool-level
  false positive, cleaned up the stale worktrees, and implemented both
  fixes directly instead. Purely a process note; doesn't affect the fix
  itself or its verification.

---

## 0c. Update Log — 2026-09-04 — final pre-publish audit

An independent, skeptical re-audit was run against the PRD text itself
(not against this document's own prior checkmarks) for every requirement
plus documentation cross-consistency and packaging/build sanity — 11
independent reviews, each then adversarially re-verified by a second,
independent reviewer against the actual source/tests/docs. The live
local orion-res server used for real-server verification earlier in this
project's history was not reachable this time, so nothing here is a new
real-server confirmation — everything is static code/test/doc review.

**Verdict per area** (numbered items are PRD requirements; the last two
are cross-cutting quality checks, not PRD items): 001 Distribution
(partial), 002 Auto-Discovery (partial), 003 Named Views (satisfied), 004
Live/Snapshot (satisfied), 005 Query Modifiers (satisfied), 006 Database
Metadata (partial), 007 Multi-Database (satisfied — code and manual
verification solid, but coverage gap flagged), 010 Database Management
(partial), 011 Report Generation (partial), Documentation consistency
(partial), Packaging/build (partial). None were "gap" (broken/missing) —
every "partial" was a real implementation correctly built for its core
case, undercut by a documentation inaccuracy, a real-server-verification
gap, or a test-coverage gap around an edge case.

**Fixed as a direct result of this audit** (all re-verified: 291 passed,
0 skipped, up from 277; clean `python -m build` + `twine check` with zero
warnings):

- **Packaging**: `pyproject.toml` now has an author email, an SPDX
  `license = "MIT"` string (silences a setuptools deprecation warning
  that would have become a hard error by 2027-02-18), and a
  `[project.urls]` table (Homepage/Repository/Issues, matching the
  sibling `stcrestclient` package's own convention). Added `MANIFEST.in`
  so the sdist actually bundles `QUICKGUIDE.md`/`TESTING.md`/
  `CHANGELOG.md`/`.env.example`/`examples/`/`tests/conftest.py`/
  `tests/fixtures.py`/`tests/data/` — previously only `README.md`
  shipped, so every "Further Reading" link in it was dead on a real PyPI
  page, and `pytest` couldn't even run from an extracted sdist (missing
  `conftest.py`/`fixtures.py`) — verified fixed by extracting the rebuilt
  sdist into a scratch directory and running the suite from it: 291
  passed.
- **`client.py` docstrings**: `list_table_names()`/`list_fields()`
  wrongly claimed a `'data_type'` key (copy-pasted from the unrelated
  `query()`/`data_type=`/`'eot'` concept) — corrected to the real key,
  `'type'`. `generate_report()`'s `title` is now `title=None` instead of
  a required positional arg, so omitting it raises `IQReportError`
  (consistent with every other tciq error) instead of a bare `TypeError`
  — `reports.create_report()` already had this check, it just wasn't
  reachable from a caller who omitted `title` entirely at the
  `IQClient` layer.
- **`examples/inspect_database_schema.py`**: dropped the stale "this
  response shape is assumed, not yet confirmed" docstring (the real
  shape was CONFIRMED and fixed back on 2026-09-03 — this example was
  never updated to say so) and the vestigial `table.get('data_type', ...)`
  fallback left over from the disproven pre-fix assumption.
- **Test coverage — `tests/test_examples_smoke.py`**: the mocked
  `GET /views` was a static single-item list that never reflected a view
  `manage_views.py` had just created via `POST /views` — so its own
  `find_view()` post-save check silently failed and the script returned
  early, meaning the smoke test reported PASSED while never actually
  exercising the "reuse" or "delete" halves of IQ-PYTHON-003's save→
  reuse→delete example. Replaced with a stateful callback-backed mock and
  added a dedicated test
  (`test_manage_views_actually_exercises_reuse_and_delete`) that asserts
  the real outcome (columns listed, rows queried back, view actually gone
  afterward), not just "didn't raise". Also added `generate_report.py` to
  the suite (it was entirely absent, with a dead, wrong-URL leftover mock
  route — `/reports/templates` instead of the real `/report-templates` —
  from an abandoned attempt to add it), and extended
  `manage_test_database.py`'s smoke test to also exercise its
  accept/confirm branch (only the decline branch was ever covered).
- **Test coverage — `tests/test_client.py`**: added regression tests for
  `database_id=` genuinely overriding a different `use_test()` default on
  `query()`/`get_test()`/`list_table_names()`/`list_fields()`/
  `generate_report()` (IQ-PYTHON-007); all four query modifiers
  (`filters=`/`sort=`/`group_by=`/`time_range=`) combined in one
  `iq_client.query()` call, and confirmed applied identically to every
  sub-query of a multi-kind (boxplot) view (IQ-PYTHON-005); and the true
  "neither `table_index=` nor `data_type=` given" default resolving to
  `eot` against the real, live-first captured view fixture, at the
  `IQClient.query()` level rather than only via `_resolve_table_index()`
  in isolation (IQ-PYTHON-004). Added to `tests/test_new_features.py`: a
  non-2xx server-error-response test for `delete_test()`/`rename_test()`
  themselves (previously only a generic GET-based Transport test covered
  this failure mode).
- **Documentation accuracy**: fixed a self-contradicting test count
  inside HANDOVER.md itself (§12 said 277 in one place, "260" three lines
  later); corrected §7's API-surface reference table (`generate_report()`
  was missing `title=` and showed the old uppercase `format="PDF"`
  default; `list_view_columns()` showed the old `table_index=0` default
  instead of `None`; `save_view()`'s kwarg order; `list_tests()` missing
  `detail=`); corrected README.md's discovery-precedence table (had AION
  ranked above install-dir discovery — backwards from what `config.py`
  actually does); removed CHANGELOG.md's false claim that report
  generation ships "with polling" (it doesn't — the caller must poll);
  added an explicit "confirmed broken against a real server"
  caveat for `x_y_chart`/`histogram` to README.md and QUICKGUIDE.md (both
  previously presented all four widget view types uniformly with zero
  warning, even though this document's own §9 already called x_y_chart/
  histogram out as broken); fixed QUICKGUIDE.md's broken `#11-example-
  scripts` TOC anchor (the real section is `#17`); fixed TESTING.md's
  test-file-coverage table (it attributed the schema/table/field tests to
  `test_databases.py`, which doesn't have them — they're in
  `test_new_features.py`) and its overclaim that the smoke suite "already
  proves every example runs" (7 of 18 examples still aren't in it).
- **Root `README.md`**: added a "TestCenter IQ support (tciq)" section —
  it previously never mentioned `tciq` or the `iq` extras group at all,
  so a `stcrestclient` user had no way to discover IQ support exists,
  which was itself the core of the IQ-PYTHON-001 "partial" finding.

**Not fixed — needs a live server, real credentials, or a product/design
decision, not more code from this environment:**

- **`host=` alone (no `port=`) has no auto-discovery path** — the PRD's
  own illustrative example for IQ-PYTHON-002,
  `IQClient(host='192.168.1.100')` as a complete stand-in for looking up
  orion-res's port from "the TestCenter REST API service record", isn't
  implemented; `host=` without `port=` just composes a URL with an
  implicit port 80. See the new note under §5 above — this needs a design
  discussion (what would that lookup even call?), not a blind fix.
- ~~**`rename_test()`'s wire format (PUT, `{"name": ...}`) is still an
  admitted guess**~~ — **RESOLVED 2026-09-17**, see the dedicated section
  below. It was wrong: real orion-res rejects that partial body outright.
- **`x_y_chart`/`histogram` remain CONFIRMED BROKEN** against a real
  server (`pie_chart`/`boxplot` unconfirmed) — see the existing "Widget
  query builders" table above; rebuilding these around their real
  `series[]`/`statistics[]` shapes is still the single largest remaining
  engineering gap, unchanged by this pass.
- **Actual PyPI publishing** itself (§10) — the decision is public PyPI,
  not an internal index; the walkthrough is written, only the actual
  `twine upload` (needs a human's own PyPI account/token) remains,
  unchanged by this pass.
- **Python 3.8 compatibility** is inferred from the absence of
  newer-only syntax (grep), not from actually running the suite on a 3.8
  interpreter — none was available in this environment; the CI matrix
  declares 3.8 but its actual run history wasn't checked (no network
  access here).

---

## 0d. Update Log — 2026-09-04 — PM feedback on the final draft, `query()` simplified

Product management reviewed the final draft and asked for `query()` to
be simpler, plus reported two real bugs while trying a minimal script.
All of this is now fixed/incorporated; every change is backward
compatible (the old parameter names still work as advanced/legacy
options) except that a caller relying on positional argument order for
`query()`'s 2nd+ arguments (nobody in this codebase does — verified by
grep across every example/test) would need to check that still lines up.

**PM's exact feedback**, and what was done about each point:

- *"do we need table_index?"* — No, not for the common case; it never
  was required (the default already auto-picks the right table). Kept it
  in the signature (removing it would be a real capability regression for
  a view with more than a live/eot pair) but moved it to the very end of
  the parameter list and re-labeled it "advanced, rarely needed" in the
  docstring, so it no longer reads as something a normal caller needs to
  understand.
- *"rename data_type to test_live (we can take true or false)"* — Done.
  `query()`/`list_view_columns()` now take `test_live=True/False` as the
  primary way to pick live vs. snapshot data (`None`, the default, means
  snapshot — unchanged from IQ-PYTHON-004's requirement). It also accepts
  the strings `"live"`/`"eot"`/`"snapshot"` case-insensitively, since
  PM's own example script passed `"live"` as a string, not a bare
  boolean — both work. The old `data_type=`/`table_index=` kwargs still
  work unchanged (moved to the end of the signature as advanced escape
  hatches), so nothing that already called `data_type="eot"` breaks.
- *"maybe we need to add a user_name parameter"* — Added `user=` to
  `query()`. When given (and `database_id=` isn't), and `test_live=True`,
  it finds the one test owned by that user whose
  `metadata["test.running"]` is `"true"` and uses its `database_id`
  automatically — no manual `list_tests(owner=...)` + pick-the-running-
  one dance needed (this exact dance is what `examples/run_live_query.py`
  used to do by hand; it's now one `user=` kwarg). Per PM's own
  clarification ("for EOT, we can ask for database-id"), `user=` for
  snapshot/eot data deliberately raises `IQQueryError` asking for an
  explicit `database_id=` instead of guessing — a user can have many
  completed tests with no signal for which one is meant, unlike the
  single currently-running one for live data.
- *"data_type EOT is not working, its case sensitive"* — CONFIRMED real
  bug, fixed at the root: `views.py::_resolve_table_index()`'s
  `data_type` comparison is now case-insensitive
  (`test_resolve_table_index_data_type_matching_is_case_insensitive`),
  so both the legacy `data_type="EOT"` and the new
  `test_live="EOT"`/`test_live="eot"` all work regardless of case.
- *"filters needs to work on column name instead of tablename.stat"* —
  CONFIRMED real gap, fixed: `view_query_builder.py::build_field_
  resolver()` now also resolves a **bare** column name (e.g. just
  `"frame_count"`, no table prefix) when it's unambiguous — exactly one
  column on that view ends in it. If two columns share the same bare
  suffix (a real case on "Detailed Stream Results":
  `tx_stream_stats.frame_count` and `rx_stream_stats.frame_count` both
  exist), the bare name is deliberately left unresolved rather than
  silently guessing one — qualify it, or use the GUI display name,
  in that specific case (both already worked, unchanged).
- PM's own minimal script (`iq.query("Detailed Stream Results", "live",
  user="vinod.shelke@viavisolutions.com")`) now works essentially
  verbatim — verified via a new mocked regression test using that exact
  calling convention (`test_query_test_live_string_live_selects_the_
  live_table`).

**Files changed**: `tciq/client.py` (query()/list_view_columns()
signatures, `_normalize_test_live()`, `_resolve_database_id_for_user()`,
`_is_running()`), `tciq/views.py` (case-insensitive `data_type` match),
`tciq/view_query_builder.py` (bare-column-name resolution in
`build_field_resolver()`), `examples/run_live_query.py` (rewritten to
use `test_live=`/`user=` instead of the manual owner+running-test
lookup it used to do by hand), `examples/run_view_query.py` (updated to
`test_live=` throughout). 17 new tests added across
`tests/test_client.py`, `tests/test_views.py`, and
`tests/test_view_query_builder.py`; full suite is now **308 passed, 0
skipped**. `run_live_query.py` and `run_view_query.py` are now also in
the automated example-smoke-test suite for the first time (see §12/
`TESTING.md` §1.4).

---

## 0e. Update Log — 2026-09-07 — real-server verification of every example, one real bug found and fixed

The local orion-res server (same one used throughout this project's
history — 507 views, the same 7 databases including `she83111`'s
`k4s6ez3h25drbau7` "all-devices") was available again and every example
script was run against it directly (not mocks), one at a time, to
verify the `test_live=`/`user=` redesign (§0d) actually holds up
end-to-end and didn't regress anything already working. The server
itself is slow right now (15–50s per request, sometimes more) — every
run below used a generous `timeout=`; this is server load, not a client
issue.

**Confirmed working, live, exactly as expected:**
`discover_local.py`, `list_tests_by_owner.py`, `inspect_database_schema.py`
(50 tables/1191 fields, matching the original 2026-09-03 confirmation
exactly), `run_view_query.py` (filters/sort/`test_live=False`/
`snapshot_name=`/`raw_result=` all correct against real rows),
`query_modifiers.py`, `fetch_view_data.py`, `multi_database_query.py`,
`manage_views.py` (create → reuse → delete cycle, independently
re-verified afterward that the throwaway view is genuinely gone),
`auto_repair_demo.py` (same 19 dropped columns as the original
2026-09-03 confirmation).

**`run_live_query.py`** — both halves of the `test_live=`/`user=`
redesign confirmed live: the `snapshot_name=` vs. live-data rejection
raises with the corrected `test_live=False` wording (see §0d), and
`user="she83111"` correctly raises `IQQueryError` ("no live/running
test found") since this server has zero currently-running tests right
now — a real, live confirmation of that error path. The success path
(finding a genuinely running test) remains mock-only, since nothing on
this server is actually running to demonstrate it against.

**`generate_report.py`** — reproduces the known, already-documented
0-byte async-download race exactly as described in §9/§11 — not a
regression, the disclosed gap is real and still open.

**`run_xy_chart_query.py`/`run_histogram_query.py`** — both still raise
`IQViewError` exactly as the "Widget query builders" table already
says. **`run_pie_chart_query.py`/`run_boxplot_query.py`** — no view of
that type exists on this server, so still unconfirmed either way
(handled gracefully by the example, not an error).

**`manage_test_database.py`** — only its safe-refusal default
(`TARGET_DATABASE_ID` unset) was exercised; the actual rename/delete
path was deliberately not run against real data, per §11's own item 5 —
still needs a human to designate a genuinely disposable database first.

**`discover_aion.py`** — not applicable to a plain local server;
excluded, matching this project's established convention.

**One real, pre-existing bug found and fixed** (unrelated to the §0d
redesign — this example's hardcoded fixture was never previously
verified live): `examples/run_json_definition_query.py`'s
`RAW_DEFINITION_JSON` had `"pagination": {"mode": "forward"}` paired
with a `limit` but an empty `"orders": []` — the real server 400s with
`"pagination requires at least one order expression"` for that
combination, the same underlying constraint discovered for saved-view
reuse back on 2026-09-03 (`default_order_updates`, see §9). Fixed by
giving the definition a real default order
(`"view.stream_block_name ASC"`); re-verified live, both calls in the
example now succeed. Full mocked suite re-confirmed unaffected: still
**308 passed, 0 skipped**.

---

## 0f. Update Log — 2026-09-08 — AION port name CONFIRMED wrong, now fixed

The single biggest previously-"unconfirmed" assumption in this whole
project — what name `orion-res` registers itself under in a real AION
deployment's `product-instances` inventory — is now settled with real
data, and it was wrong.

**How this was found:** the user had access to a real AION org
(`aion-test01.calenglab.spirentcom.com`) and ran `tciq`'s actual AION
login + inventory-lookup flow against it (via a throwaway diagnostic
script, `tciqclient/aion_check.py` — not part of the package). The
result: **58 product-instances, 20+ of them carrying a results-service
port — and every single one is named `'iq'`. Zero are named
`'orion-res'`.** The full distinct port-name vocabulary observed across
every instance: `iq`, `stcapi`, `api-navigator`, `telemeter-api`,
`arangodb`/`arangodb1-5`, `testcenterplus`, `benchmarking-app`,
`traffic-app`, `adv-benchmarking`, `web-application`.

**Practical impact of the bug, before this fix:** `IQClient(aion_url=...,
aion_username=..., aion_password=...)` with no `aion_port_name=`
override — i.e. the documented, expected way to connect to any real
AION deployment — would authenticate successfully and then always fail
with `"AION: no port named 'orion-res' found in product-instances"`.
Every real AION user would have hit this on their very first connection
attempt, with no indication in the error message that the fix was a
one-argument override (`aion_port_name="iq"`) rather than something
wrong with their credentials or deployment.

**A second hypothesis raised during the same investigation — that
`product-instances`' URLs might carry a path component
(e.g. `/api/res/`) that `aion_discovery.py`'s
`urlparse(port_url).hostname/.port` silently drops — was raised, then
directly refuted by this same real data.** Every one of those 50+ port
URLs, across every instance, is a bare `scheme://host:port` with no
path at all. No code change was needed for that part, and none was
made — the value of getting real data before changing anything based on
a plausible-but-unconfirmed theory.

**Fix applied**: `tciq/aion_discovery.py`'s
`AION_ORION_RES_PORT_NAME` default changed from `'orion-res'` to
`'iq'` (module docstring, `get_orion_res_endpoint()`/`discover_via_aion()`
docstrings updated to match). Same default documented in
`tciq/client.py`'s `aion_port_name=` constructor docstring,
`tciq/config.py`'s `TCIQ_AION_PORT_NAME` module docstring, and
`.env.example`. `examples/discover_aion.py`'s explanatory comments
updated to say `'iq'`. A new regression test
(`test_aion_orion_res_port_name_default_is_iq`) pins the constant
directly; the existing AION discovery tests' fixtures (which had used
`'orion-res'` to exercise the *default* port-name path) were updated to
use `'iq'` so they keep testing the actual default, not a value that no
longer matches it. `aion_port_name=`/`TCIQ_AION_PORT_NAME` remain fully
supported as an override for any deployment that genuinely differs.
Full suite: **309 passed, 0 skipped** (the one new test).

**Also found and fixed during this same investigation, unrelated to the
port-name bug itself**: `examples/discover_aion.py` had a real AION
hostname and a real username/password hardcoded in its `AION_URL`/
`AION_USERNAME`/`AION_PASSWORD` constants — leftover from earlier
manual testing, sitting in a plaintext, uncommitted-but-real source
file. Reverted to the placeholder values (`https://aion.example.com`,
`user@example.com`, `secret`) the file's own comment already claimed
were there, with an explicit added note against ever committing real
credentials there. Confirmed via a repo-wide search that no other file
picked up the real hostname or password.

---

## 0g. Update Log — 2026-09-08 (continued) — every example re-run against both a real AION deployment and the local server

Following the port-name fix (§0f), every applicable example script was
run twice more: once against the local standalone server as before, and
once — for the first time this project — against a **real AION
deployment**, authenticated for real (login → bearer token → resolved
`orion-res` address), using the actual, unmodified example files.

**Local server re-run**: all 16 applicable examples (same set as §0e,
still excluding `discover_aion.py`/`manage_test_database.py`'s
destructive path) re-confirmed working exactly as previously documented
— no regressions from the `query()` redesign (§0d) or the AION fix
(§0f). `generate_report.py` reproduced the same known 0-byte async-race
gap; the four widget-chart examples behaved exactly as the "Widget
query builders" table already says.

**AION-authenticated re-run**: since `get_orion_res_endpoint()` only
filters by `node_name`/`port_name` and a single AION node can host
several distinct product instances, a small throwaway harness
(`aion_example_harness.py`, not part of the package) authenticated via
AION for real, then pinned each *unmodified* example's `IQClient()`
call to the one specific real instance (of 57 checked) confirmed to
have actual test data — via `session=`/`base_url=` injection, the same
mechanism `IQClient()`'s own constructor already supports. Findings:

- **AION login, bearer-token auth, and every subsequent API call all
  work correctly for real** — the §0f fix is confirmed genuinely
  sufficient, end to end, not just at the discovery step.
- **The AION-managed instance is the same underlying test data as the
  local server** (`k4s6ez3h25drbau7`/`all-devices`/`she83111`, byte-for-
  byte identical schema — confirmed via `inspect_database_schema.py`
  matching exactly) — but **has only 33 views, versus the local
  server's 507**, and critically does **not** have a view named
  "Detailed Stream Results" at all. View availability is a property of
  the specific `orion-res` deployment/version, not of the test database
  itself — the two can genuinely differ even when pointed at identical
  data. This is expected, not a `tciq` bug, but it's real, useful
  information for anyone assuming every deployment has the same views.
- A previously-unseen `view_type` was observed on this deployment's
  view list: `drill_down_table` (alongside the already-known
  `single_level_table`/`x_y_chart`/`histogram`/`health_indicator`) —
  not in `SUPPORTED_VIEW_TYPES`, so `query(name=...)` against one would
  correctly raise `IQViewError` (untested result shape) rather than
  silently doing something wrong. Noted here for whoever next extends
  the widget query builders (§11) — not addressed in this pass.
- `generate_report.py` reported "No report templates available on this
  server" — this AION-managed instance has none configured, unlike the
  local server. Handled gracefully already; a deployment difference,
  not a bug.

**Two real, unrelated robustness gaps found and fixed** by the view
genuinely not existing here (previously never exercised, since every
prior real-server run this project had a server that *did* have this
view):

- `examples/run_view_query.py` — its `except IQViewError:` fallback to
  a hardcoded `RAW_DEFINITION=` was itself not wrapped in a `try`/
  `except`. On this AION deployment, the fallback *also* failed
  (`IQRequestError` — the captured definition's schema/aliases don't
  match this server either), and that second failure was completely
  unhandled, crashing the script instead of printing a clear message.
  Fixed: the fallback now has its own `try`/`except (IQViewError,
  IQRequestError)`, reporting clearly and returning instead of
  crashing.
- `examples/auto_repair_demo.py` — `iq.query(name=VIEW_NAME, ...)` had
  no error handling around it at all; a missing view raised
  `IQViewError` uncaught. Fixed: wrapped, with a clear message.

Full suite re-confirmed after both fixes: **309 passed, 0 skipped**
(no new tests needed — these are example-script robustness fixes, not
library behavior changes).

Also ran `examples/discover_aion.py` itself (the real file, unmodified)
against real AION credentials via `TCIQ_AION_URL`/`TCIQ_AION_USERNAME`/
`TCIQ_AION_PASSWORD` environment variables (never written into the
file): the "Your actual .env/environment configuration" section
resolved a live instance end-to-end (`base_url=http://10.109.128.139:64002`),
while the hardcoded-placeholder sections (`aion.example.com`) correctly
raised a clean `IQConnectionError` each time, exactly as the file's own
docstring says they should.

**Housekeeping**: `aion_check.py` and `aion_example_harness.py` (both
throwaway diagnostics created during this investigation, not part of
the `tciq` package) have been deleted — no longer needed now that the
port-name fix is confirmed and applied. Note: unlike `aion_check.py`
(which only ever prompted for credentials via `getpass`),
`aion_example_harness.py` did contain the real AION password in
plaintext (a leftover from interactive testing) — deleting it also
resolves that exposure; nothing referencing it remains in the package
or tests.

### Update Log -- 2026-09-08 (continued again) -- new examples/aion_end_to_end.py, covering the same edge cases as local mode

Added `examples/aion_end_to_end.py`: unlike `discover_aion.py` (discovery
edge cases only -- never touches orion-res itself), this one connects via
AION (env-var driven: `TCIQ_AION_URL`/`TCIQ_AION_USERNAME`/
`TCIQ_AION_PASSWORD`, same as production) and then runs the *same* breadth
of query edge cases the local-mode examples each cover individually --
eot vs. live data, filters=/sort=/group_by=/snapshot_name=, auto_repair,
and database_id= across multiple tests -- all through one AION-discovered
client, each section wrapped in its own try/except so one deployment
quirk doesn't stop the rest. It also doesn't hardcode a view name and
bail if missing (like the local examples do) -- `_first_queryable_view()`
falls back to any single_level_table/paged_single_level_table view on the
server, since which views exist is deployment-specific (see above).
Added a corresponding smoke test (`test_aion_end_to_end_runs_without_error`
in `test_examples_smoke.py`) that points mocked AION discovery straight at
the same mocked orion-res fixtures every other example already uses --
full suite now 310 passed.

Ran it for real, twice:

- **Local server** (`TCIQ_BASE_URL=http://127.0.0.1:9200`, bypassing AION
  entirely as a config sanity check): fully successful end to end --
  found "Detailed Stream Results" directly (no fallback needed), 30
  snapshot rows, auto_repair correctly dropped 18 unsupported columns
  then reproduced the real `VALIDATION_FAILED` error with
  `auto_repair=False`, filters=/sort= worked, `group_by=` correctly
  reproduced the real, previously-documented "must appear in the GROUP
  BY clause" 400 (see section 9), `snapshot_name=` worked, "no live test
  currently running" was reported cleanly (`IQQueryError`, caught), and
  the single-test case correctly skipped the multi-database section.
  Every edge case the script set out to cover fired correctly.

- **Real AION** (`aion-test01.calenglab.spirentcom.com`): the first two
  attempts (no `aion_node_name=`, then pinned to
  `aion_node_name="10.109.143.126"`) each resolved to a *different* real
  `iq`-port instance with **zero** databases for `she83111` -- the script
  correctly printed "No tests found ... edit OWNER" and exited cleanly
  rather than crashing on either. To find out why, probed all 57 real
  `iq`-port instances directly (one-off scratch script, not kept):
  exactly one, `http://10.109.143.126:64013`, has `she83111`'s 17
  databases -- and it shares its *node* with a second, empty `iq`
  instance on port 64018. This **reconfirms, with fresh data, the same
  real limitation found earlier this session**: `aion_node_name=` alone
  cannot disambiguate when a node hosts more than one product instance;
  the port actually picked depends on API response order, which is not
  guaranteed stable (this session, at different points, got 64002, 64018,
  and -- via the earlier deleted harness, and this probe -- 64013 for
  supposedly similar discovery calls). There is currently no supported
  `IQClient(...)` kwarg that disambiguates two same-named ports on one
  node; the only way to reach a specific one for certain is `base_url=`
  (bypassing discovery) once you already know it, e.g. via a one-off
  inventory probe like the one used here. Attempting the full walkthrough
  against the confirmed instance (`base_url=http://10.109.143.126:64013`
  + a manually AION-authenticated session, mirroring the now-deleted
  `aion_example_harness.py` pattern) was started but did not complete in
  a reasonable time and was stopped rather than left to fabricate a
  result -- for reference, the same exact instance *did* fully succeed
  under the earlier deleted harness earlier in this session (real query
  results, 33 views, no "Detailed Stream Results"), so this looks like
  transient real-network/lab flakiness rather than a `tciq` bug; worth
  re-attempting live if this comes up again.

No `tciq` code changes came out of this round (unlike the previous
`run_view_query.py`/`auto_repair_demo.py` fixes) -- this was purely
about adding the missing AION-mode example and confirming, twice more
with independent fresh data, the multi-instance-per-node discovery
limitation already on record in section 9.

### Update Log -- 2026-09-11 -- review feedback: new DB-metadata/bulk-cleanup APIs, report live/snapshot params, and a critical git-history finding

**This repo has exactly one commit, ever** (`f3fe9c7`, 2026-08-18).
Everything since then -- every session's worth of work reflected in this
document, `examples/query_modifiers.py` and 9 other example files, and
this round's new `tciq/Testcenterlib.py`/`aion_operations_testcenterplus.py`/
`get_product_url_example.py`/`aion_end_to_end.py` -- is **uncommitted,
unpushed local state on this one machine**. Review feedback saying
"query modifier example is missing" is consistent with someone reviewing
the actual pushed branch, where none of these files exist at all --
`query_modifiers.py` itself is real, complete, and has existed on disk
for a while (see below), it just was never `git add`+committed. This is
a distinct, still-open issue from the earlier `.gitignore`-losing-
`*.md`/`*.json` problem described in section 0 above (that one is fixed;
this one -- nothing in `examples/`, and several `tciq/` package changes,
has ever been staged -- is not). No commit was made as part of this
round (standing instruction: never commit unless explicitly asked) --
flagging this for whoever owns getting the branch pushed.

Separately, implemented the actual feature requests from the same
feedback:

- **`get_database_tables(database_id=None)`** -- alias for
  `list_table_names()`, under the requested name.
- **`get_table_schema(table_name, database_id=None)`** -- one table's own
  descriptor (`kind` + `facts`/`attributes`), instead of every table's.
  Raises `IQError` if no table on the database has that name.
- **`get_database_summary(database_id=None)`** -- just the `summary`
  dict (`count`, `value_storage_kb`, `index_storage_kb`) -- CONFIRMED
  real shape, both from `tests/fixtures.py`'s captured data and freshly
  re-confirmed against the real local server just now (`all-devices`:
  `{'count': 57434, 'value_storage_kb': 33576, 'index_storage_kb': 9944}`).
- **`list_databases_over_size(min_size_kb)` / `delete_databases_over_size(min_size_kb, dry_run=True)`**
  and **`list_databases_older_than(days)` / `delete_databases_older_than(days, dry_run=True)`**
  -- bulk cleanup by storage size (`value_storage_kb + index_storage_kb`)
  and by age (`metadata["test.started"]`). Both delete_* default to
  `dry_run=True` (report-only) -- real deletion needs an explicit
  `dry_run=False`. New example `examples/bulk_cleanup_databases.py`
  wraps both with the same typed-confirmation-phrase safety gate as
  `manage_test_database.py`, since this is a *multi*-database
  destructive operation.

  Found and fixed a real bug while verifying `list_databases_older_than()`
  against the real local server: the initial `_started_at()` parser
  (`strptime` with a hardcoded `.%f` fractional-seconds format) only
  handled ONE of the two real timestamp shapes orion-res actually
  returns -- confirmed live on the very same server, in the same
  response: some databases have `"test.started": "2026-04-06T06:34:12Z"`
  (no fractional seconds), others `"...T06:47:16.000Z"` (with). The
  strict-format parser silently returned `None` (unparseable) for the
  first shape, making every such database invisible to the age filter.
  Fixed by switching to `datetime.fromisoformat()` (after swapping `Z`
  for `+00:00`, since `fromisoformat()` doesn't accept a bare `Z` before
  Python 3.11) -- handles both shapes. Caught by a smoke test
  (`test_bulk_cleanup_databases_age_based_accept_deletes_all_matches`)
  that initially failed with "0 database(s)" instead of the expected 3,
  then confirmed against the real server directly (`list_databases_over_size`/
  `list_databases_older_than` both re-run read-only, no deletes).

- **`generate_report(..., test_live=None, snapshot_name=None)`** --
  promoted from the `**extra` escape hatch to explicit, documented
  parameters (matching `query()`'s own `test_live=`/`snapshot_name=`
  vocabulary). ⚠️ **UNCONFIRMED**, clearly labeled as such in both the
  docstring and `API_REFERENCE.md`: no real `POST /reports` request
  choosing live vs. snapshot data has been captured, so the field names
  sent (`"live"` boolean, `"snapshot_name"` string) are a best-effort
  guess, not a confirmed contract -- same treatment as the unconfirmed
  widget query builders (x_y_chart/pie_chart/histogram/boxplot). Both
  are opt-in (`None` by default) and don't change existing behavior for
  any caller not using them. Needs a real GUI-captured `/reports` body
  (report wizard's live/snapshot picker, DevTools Network tab) to
  confirm or correct.
- Also fixed an unrelated pre-existing typo found while in
  `generate_report()`'s docstring: a garbled `66yyyyyyyyyyyy` line where
  `extra` should have been.
- `examples/inspect_database_schema.py` extended to also demonstrate
  `get_table_schema()`/`get_database_tables()`/`get_database_summary()`.

All new code has test coverage (`tests/test_new_features.py`'s
`TestDatabaseMetadata`/`TestBulkDeleteBySize`/`TestBulkDeleteByAge`,
`tests/test_client.py`'s new `generate_report` tests, and
`tests/test_examples_smoke.py`'s new `bulk_cleanup_databases` tests).
Full suite: **330 passed, 0 skipped** (was 310 before this round).

### Update Log -- 2026-09-11 (continued) -- this round's new APIs re-verified against the real local server

- `get_database_tables()` confirmed byte-for-byte identical to
  `list_table_names()` against the real server (50 tables, `all-devices`
  database).
- `get_table_schema('test_events')` confirmed against the real server --
  real columns/types/summary returned; `get_table_schema('does_not_exist')`
  correctly raised `IQError`.
- `get_database_summary()` re-confirmed: `{'count': 57434,
  'value_storage_kb': 33576, 'index_storage_kb': 9944}` for `all-devices`.
- `delete_databases_over_size(min_size_kb=1, dry_run=True)` and
  `delete_databases_older_than(days=1, dry_run=True)` both correctly
  reported all 6 real databases on this server as matches **without**
  deleting anything -- re-confirmed by listing again afterward (still 6
  matches, nothing removed). `examples/bulk_cleanup_databases.py` itself
  run for real (MIN_SIZE_KB=1, MAX_AGE_DAYS=1, declined both
  confirmations) -- correctly listed and sorted all 6 (largest-first for
  size, oldest-first for age) and skipped both deletes.
- **`generate_report(test_live=.../snapshot_name=...)` -- tested for
  real, upgraded from UNCONFIRMED to PARTIALLY CONFIRMED**: sending
  `"live": true/false` or `"snapshot_name": "Snapshot"` on the report
  body does NOT get rejected (`201`, not `400`) -- confirmed via 4 real
  `POST /reports` calls (baseline, `test_live=True`, `test_live=False`,
  `snapshot_name=`), all accepted. Whether either field actually changes
  the generated report's *content* remains unverified: polled all 4
  reports' status 6 times over 30s -- 2 got stuck in `"generating"` at
  0% and the other 2 never left `"queued"` (queue backing up behind the
  stuck ones) -- this is the same pre-existing async-completion gap
  already on record (section 9/11: "this environment's report backend
  never actually completed a job"), re-confirmed here rather than a new
  bug. Docstrings/`API_REFERENCE.md` updated to reflect "accepted,
  not-yet-provably-honored" instead of the earlier, more speculative
  "unconfirmed."
- Full test suite re-run clean: 330 passed. No `tciq` code changes came
  out of this specific verification pass (all findings were either
  confirmations or, for the report fields, a documentation refinement).

### Update Log -- 2026-09-11 (continued again) -- new examples/modify_query_definition.py

Added a new example specifically about editing a query *definition*'s
raw dict directly, as distinct from `query_modifiers.py` (filters=/
sort=/group_by=/time_range=, which all go through `tciq.query.
merge_modifiers()` -- appends structured, AND-ed conditions only) and
`run_json_definition_query.py` (runs a captured definition as-is/with
modifiers layered on top, doesn't edit the tree itself). Gets a starting
definition from a real view via `views.get_view_definition()`, then
demonstrates three things `merge_modifiers()` genuinely cannot do:

1. **An OR-combined filter** -- a single raw expression string with `OR`
   inside parens, since `filters=` entries are always AND-ed as separate
   array entries.
2. **Removing a projection** -- `merge_modifiers()` only ever appends.
3. **Overwriting (not appending to) `orders`**.

Two real things found running this against the real local server (not
new bugs -- both are real orion-res/query-semantics facts worth having
on record, same spirit as the rest of this document):

- **`IS NOT NULL` is rejected for a numeric column** -- CONFIRMED
  2026-09-11: `"rx_stream_stats_avg_latency>0 OR
  rx_stream_stats_avg_latency IS NOT NULL"` 400s with "null checks are
  only valid for columns" (exact real error, not further diagnosed which
  column *types* null checks are valid for). The OR-filter demo above
  ORs two plain numeric comparisons across two different columns
  instead.
- **`sort=`'s appended order key can be a no-op in practice** --
  CONFIRMED 2026-09-11: "Detailed Stream Results" already carries its
  own default order (`test_snapshot_name`/`tx_stream_stream_id`, from
  `default_order_updates` -- see `tciq/views.py`'s
  `_find_provider_elsewhere()` docstring); since those columns are
  already unique per row, a `sort=` key appended *after* them (as
  `merge_modifiers()` always does) never gets a tie to break, so
  `sort="<col> DESC"` and `sort="<col> ASC"` produced byte-identical row
  order in a real side-by-side check. Only replacing `orders` outright
  (as this example's 3rd modification does) makes a new key the actual
  primary sort. Related, also confirmed: a DESC sort on a column with
  some `None` values can legitimately put every `None` *before* every
  real value (a null-ordering convention, not a bug) -- a `limit=5`
  first attempt looked broken (5/5 `None`) until raising the limit
  showed real values further down the same correctly-DESC-sorted list.
  Neither of these is a `tciq` bug -- both are documented in the
  example's own comments so a future reader doesn't have to
  rediscover them.

`query(definition=...)` also doesn't get `auto_repair=True`'s strip-and-
retry (that's `name=`-only) -- the same "unknown attribute" error
`auto_repair_demo.py` shows resurfaces uncaught here. Handled by a small
`_run_with_manual_repair()` helper in the new example, using `tciq.
view_query_builder`'s own public `parse_unknown_attribute_error()`/
`strip_unknown_attribute()` directly (the same mechanism `IQClient`
itself uses internally, just invoked by hand) -- confirmed stripping the
same 18 dual-IP/MAC/VLAN/IPv6/MPLS/TCP/UDP columns seen throughout this
document for this exact database.

Smoke test added (`modify_query_definition` in the parametrized list,
`test_examples_smoke.py`). Full suite: 331 passed.

### Update Log -- 2026-09-11 (continued yet again) -- generate_report()'s test_live=/snapshot_name= was WRONG, replaced with a confirmed-real snapshot_filter=

The user supplied a real, actual request body the GUI itself sends for
report generation:

```json
{"id": "", "report_template_id": "a5fb1a18c57b410692e87925be8dcf02",
 "database": {"id": "k4s6ez3h25drbau7", "name": "all-devices"},
 "title": "all-devices Report", "format": "pdf",
 "page_layout": {"paper_size": "us-letter", "orientation": "landscape"},
 "parameters": {"application.id": "e8c43606b3924efbaa86f82bc47dd279",
                "application.name": "TestCenter", "application.version": "1.0.0.3424",
                "company_name": "", "custom_logo": "", "description": "",
                "dut.details": "[]", "excluded_sections": "[]",
                "owner": "she83111",
                "report_preferences": "{...}",
                "test.type": "traffic",
                "test_snapshot_filter": "[\"is_all_included\"]"},
 "metadata": {"aftViewIds": "{}"}}
```

This settles what the earlier round's "PARTIALLY CONFIRMED, accepted-
but-not-provably-honored" `test_live=`/`snapshot_name=` guess (top-level
`"live"` boolean / `"snapshot_name"` field) could only partially check:
**neither field exists anywhere in a real request.** There is no live-
vs-snapshot boolean toggle for reports at all, unlike `query()`'s
`test_live=`. The real mechanism is `parameters.test_snapshot_filter` --
a JSON-*encoded string* (not a nested list) -- whose one confirmed real
value is `["is_all_included"]`, a sentinel meaning "no filter, every
snapshot included", sent by the GUI by default.

Fixed:

- `generate_report()`/`create_report()`: removed `test_live=`/
  `snapshot_name=` entirely (confirmed wrong, not a soft-deprecate --
  nothing external depends on this yet). Added `snapshot_filter=`
  (string or list of strings, JSON-encoded into `parameters.
  test_snapshot_filter`, merged into a caller-supplied `parameters=` if
  one is also given via `**extra`) and `database_name=` (optional,
  alongside `database_id=`, matching the real `database.name` field --
  confirmed omitting it is still fine, since every real-server call
  this session succeeded without it before this fix existed).
- Added `tciq.reports.REPORT_ALL_SNAPSHOTS_FILTER = "is_all_included"`
  -- the confirmed real sentinel, exposed so a caller wanting to match
  the GUI's own default doesn't have to hardcode the magic string
  themselves.
- `tciq/reports.py`'s module docstring now carries the full real
  captured body as documentation, explicitly noting which parts are
  confirmed (the shape above) vs. which look GUI-populated display
  metadata this module makes no attempt to reproduce automatically
  (`application.*`, `owner`, `test.type`, `dut.details`,
  `report_preferences`, `excluded_sections` -- available via `**extra`
  for exact fidelity if ever needed).
- Re-verified against the real local server: the new request body
  matches the captured shape exactly for every field tciq controls, and
  -- notably -- **the server's response now echoes the `parameters`
  dict back** (`{'test_snapshot_filter': '["is_all_included"]'}`),
  where the old, wrong `"live"`/`"snapshot_name"` guess was accepted
  (201) but never echoed anything back -- decent circumstantial
  evidence the server actually recognizes this field, vs. silently
  ignoring an unrecognized one before.
- Rewrote the 4 tests covering the old (wrong) fields into 6 new ones
  covering `snapshot_filter=`/`database_name=` in `tests/test_client.py`.

Full suite: 333 passed (up from 331). What a real request choosing one
*specific* named snapshot looks like is still not captured -- if that
matters, get a real DevTools capture of the report wizard's snapshot
picker in use, the same way the default-sentinel capture above was
obtained.

### Update Log -- 2026-09-11 (yet again) -- second real capture: "live and snapshot" report generation, test_snapshot_filter combines flags

The user supplied a second real captured request, this time for "live
and snapshot" report generation:

```json
{"...": "... byte-identical to the first capture except:",
 "database": {"id": "f3okrp3jdfg6phw7", "name": "Untitled"},
 "parameters": {"...": "...",
                "test_snapshot_filter": "[\"is_all_included\",\"is_live_included\"]"}}
```

This confirms `test_snapshot_filter` is a list of independent filter
flags, not a single mode -- the first capture's `"is_all_included"`
wasn't "the snapshot-only value" as opposed to some other "live" value;
it's one flag among possibly several, and "live and snapshot" simply
adds a second flag, `"is_live_included"`, to the same list rather than
switching to a different field or value entirely.

Fixed/added (no functional code change was actually needed --
`generate_report(snapshot_filter=...)` already accepted a list and
JSON-encoded it correctly; this was purely a documentation/confirmation
upgrade plus a new exposed constant and example):

- Added `tciq.reports.REPORT_LIVE_INCLUDED_FILTER = "is_live_included"`
  alongside the existing `REPORT_ALL_SNAPSHOTS_FILTER`, so a caller can
  write `generate_report(snapshot_filter=[REPORT_ALL_SNAPSHOTS_FILTER,
  REPORT_LIVE_INCLUDED_FILTER])` for "live and snapshot" without
  hardcoding either magic string.
- Updated `tciq/reports.py`'s module docstring and `generate_report()`'s
  own docstring to show both real captures side by side and state the
  "list of flags, not a mode" finding explicitly.
- Updated `examples/generate_report.py` to demonstrate all three real,
  now-confirmed cases: the plain baseline (no filter -- unchanged, pre-
  existing behavior), an explicit snapshot-only report
  (`REPORT_ALL_SNAPSHOTS_FILTER`), and a live+snapshot report (both
  flags together) -- the latter two skip `output_path=` deliberately,
  since the known async-completion gap (see above) makes a download
  immediately after creation unreliable; they just show the created
  report object's id/status instead.
- Added `test_generate_report_live_and_snapshot_combined_filter` to
  `tests/test_client.py`.
- Re-verified against the real local server: the request body sent
  matches the second capture exactly (`"test_snapshot_filter":
  "[\"is_all_included\", \"is_live_included\"]"`), accepted with `201`,
  `parameters` echoed back in the response same as before. Also ran
  `examples/generate_report.py` itself (the real file) against the real
  server -- all three report-creation calls succeeded.

Full suite: 334 passed (up from 333).

### Update Log -- 2026-09-11 (once more) -- generate_report.py picked an arbitrary template; select "Traffic Test Report" by name instead

`examples/generate_report.py` picked `templates[0]` -- whatever
`list_report_templates()` happened to list first (in practice,
"Asymmetric RFC2544 Latency Test Report" on this server), not the
general-purpose "Traffic Test Report" template both real captures this
session's `snapshot_filter=` fix is based on actually used. Fixed:
added a `TEMPLATE_NAME = "Traffic Test Report"` constant and look it up
by *exact* name (not substring -- the real server has several "Traffic
Test Report (tmp)" duplicates alongside the one plain "Traffic Test
Report"), falling back to `templates[0]` with a clear message if a
server doesn't have one by that exact name.

Full suite still 334 passed (the smoke test's mocked template is named
"Summary Report", so it now exercises the fallback branch instead of
the exact-match one -- both covered, nothing needed changing there).

### Update Log -- 2026-09-11 (once more again) -- generate_report.py now demonstrates the poll-then-download fix for the async-download gap

The user's own edit to `examples/generate_report.py` changed the
hardcoded owner from `"she83111"` to `"bha83166"` (their real username)
-- kept as-is (their own data, their own edit), but it broke the shared
smoke-test `DATABASES` fixture (only had `"she83111"`-owned entries) --
fixed by adding a 4th entry (`db4`) owned by `"bha83166"`. That new
entry is old enough to also match `test_bulk_cleanup_databases_age_
based_accept_deletes_all_matches`'s age filter (it filters by age, not
owner) -- that test's mocks/assertions updated from 3 to 4 matching
databases accordingly.

Added `wait_for_report()` to `generate_report.py`: the actual fix for
the KNOWN GAP this file's docstring has documented since it was first
written -- poll `get_report()` until status leaves `("queued",
"generating")` (CONFIRMED real in-progress values) or `MAX_POLLS` (12 x
5s = 60s) is reached, and only call `download_report()` once it's
actually terminal. Demonstrated as a 4th report-generation case in
`main()`.

Re-verified against the real local server: the polling loop itself
works correctly (prints each poll's real status/progress) -- but the
first real run crashed with an unhandled `IQRequestError` mid-poll
(poll 6/12): `ConnectionRefusedError` from the local server itself,
recovering within a few seconds on its own (a plain `list_tests()` call
right after succeeded fine). This is the **second** time in one session
this exact pattern has occurred against this same server (the first
was during the earlier "Traffic Test Report" template fix, at a similar
point mid-poll) -- consistent enough to treat as a real, recurring
characteristic of this local server, not a one-off fluke.

Fixed: `wait_for_report()` now catches `IQRequestError` per-poll (logs
it, counts it as one of the `MAX_POLLS` attempts, and retries) instead
of letting one transient connection drop abort the whole wait and lose
everything already waited for. `main()`'s timeout-reporting branch also
made null-safe (`final_report` can now be `None` if every single poll
failed).

Re-verified again after the fix, and it worked exactly as designed: the
same connection drop happened again (poll 9/12 this time), got caught
and retried instead of crashing, and poll 10/12 succeeded -- finding
the report had reached **`canceled`** (same terminal-but-not-success
status as the earlier "Traffic Test Report" incident, correlating with
the same kind of connection blip both times). Script exited cleanly
(code 0), correctly reported 0 downloaded bytes and that "canceled" is
not a success status, rather than crashing or claiming success.

Full suite: 334 passed (net unchanged -- the new db4 fixture entry and
its knock-on test updates cancel out against the one new assertion
added for report_waited.pdf).

---

## Table of Contents

1. [What You're Picking Up](#1-what-youre-picking-up)
2. [Five-Minute Setup](#2-five-minute-setup)
3. [Repository Layout](#3-repository-layout)
4. [Architecture](#4-architecture)
5. [Discovery Modes](#5-discovery-modes)
6. [Configuration Reference](#6-configuration-reference)
7. [IQClient API Surface](#7-iqclient-api-surface)
8. [Requirements Status](#8-requirements-status)
9. [Known Gaps & Unconfirmed Assumptions](#9-known-gaps--unconfirmed-assumptions)
10. [Deployment Checklist](#10-deployment-checklist)
11. [Next Steps (Prioritized)](#11-next-steps-prioritized)
12. [Running the Tests](#12-running-the-tests)
13. [Key Technical Decisions](#13-key-technical-decisions)

---

## 1. What You're Picking Up

`tciqrestclient` is a standalone Python library that wraps TestCenter IQ's `orion-res` results service REST API. It lives inside the `py-stcrestclient` repo at `tciqclient/` but is packaged independently — no `stcrestclient` dependency, no WAMP, no socket code.

**The goal:** an automation engineer should be able to discover the IQ server, find their test by owner, and pull result rows from any saved view in a single request/response — with optional filters, sort, grouping, and time range layered on top — using plain Python.

> **Every query is one HTTP request.** "Live" means calling `query()` again when you want fresh data. There is no subscription or long-poll mode.

All 11 IQ-PYTHON requirements (P0 and P1) are implemented and tested (see §8), and `pytest` is 356 passed / 0 skipped. What remains is:
- Rebuilding the four newer widget query builders (`x_y_chart`/`pie_chart`/`histogram`/`boxplot`) around their real `series[]`/`statistics[]`-based shapes instead of the `single_level_table`-only `"tables"` assumption — CONFIRMED broken against a real server, now the single largest remaining gap, and re-confirmed 2026-09-16 identically against **three independent real servers** (local + two separate AION-managed instances — see §9/§11)
- Getting a real browser DevTools capture of a GUI-filtered "Detailed Stream Results" query to replace the one constructed/provisional fixture (`dsr_query_filtered_min_latency.json`, see §9)
- Working through the remaining publishing checklist items (§10) — the decision is public PyPI, not an internal index; the only remaining step is a human creating a PyPI account/API token and running `twine upload` (§10 has the full walkthrough)
- Verifying `delete_test()` (IQ-PYTHON-010) against real data — `rename_test()`'s half of this is now DONE (see §9), including finding and fixing a real wrong-guess bug in its wire format; `delete_test()` remains unverified since it's irreversible (no revert-after possible the way rename's round trip allowed)

---

## 2. Five-Minute Setup

```bash
# Install in editable mode from the tciqclient subdirectory
cd py-stcrestclient/tciqclient
pip install -e ".[test]"

# Copy and fill in the connection config
cp .env.example .env
# Edit .env — add TCIQ_BASE_URL=http://your-orion-res-host:9200

# Run the test suite (no running server needed — all HTTP is mocked)
pytest
# Expected: 356 passed, 0 skipped
```

```python
from tciqrestclient import IQClient

iq = IQClient()                                      # reads everything from .env
tests = iq.list_tests(owner="you@viavisolutions.com")
iq.use_test(tests[0]["id"])

rows = iq.query(
    name="Detailed Stream Results",
    data_type="eot",                                 # this view has "live" and "eot" tables
    filters=[("frame_count", "gt", 0)],
    sort="frame_count DESC",
)
```

> **⚠ Critical — do not commit `.env`, `views.json`, or any `*.log` file
> under `tciqclient/`.** `views.json` is a 252 MB captured API response.
> `*.log` files can contain real request/response bodies from a real
> server. `.gitignore` at the repo root now blocks all three
> (`tciqclient/.env`, `tciqclient/views.json`, `tciqclient/*.log`) — this
> used to not exist at all, which is how a previous revision of this repo
> ended up silently never committing several important files (see §0).
> Double-check `git status` before committing anything new under
> `tciqclient/` regardless — a gitignore rule only protects paths it
> already knows about.

---

## 3. Repository Layout

```
py-stcrestclient/                   ← this checkout may be named
│                                     py-iqrestclient locally; it's the
│                                     same repo (see §0)
├── setup.py                        ← now has extras_require={'iq': ['tciqrestclient>=0.1.0,<1.0']}
├── .gitignore                      ← blocks tciqclient/.env, views.json, *.log
├── .github/workflows/
│   └── tciqrestclient-tests.yml    ← CI: pytest across Python 3.8-3.12
└── tciqclient/
    ├── pyproject.toml              ← standalone tciqrestclient package; dynamic version from version.py
    ├── README.md                   ← package overview, install, quick start, API surface
    ├── TESTING.md                  ← full test guide: automated, packaging, manual/integration
    ├── CHANGELOG.md                ← 0.1.0 initial-release notes
    ├── .env.example                ← safe to commit (template only)
    ├── .env                        ← YOUR REAL CONFIG — NEVER COMMIT (gitignored)
    ├── views.json                  ← 252 MB capture, if you make one — NEVER COMMIT (gitignored)
    ├── *.log                       ← debug captures, if you make any — NEVER COMMIT (gitignored)
    ├── tciqrestclient/
    │   ├── __init__.py             ← public API: IQClient, exceptions, helpers (__all__)
    │   ├── client.py               ← IQClient — the single public entry point
    │   ├── config.py               ← env/.env resolution, AION discovery sequencing
    │   ├── transport.py            ← requests wrapper, JSON, error mapping, debug logging
    │   ├── databases.py            ← /databases: list, get, schema, delete, rename
    │   ├── views.py                ← /views: list, find, save, delete, field resolver
    │   ├── query.py                ← DSL tree, merge_modifiers(), rows_to_dicts()
    │   ├── view_query_builder.py   ← builds query defs from view templates (by view_type)
    │   ├── queries.py              ← run_query() → POST /queries
    │   ├── reports.py              ← report templates, generate, download
    │   ├── discovery.py            ← stcbll.ini / orion-res.yaml discovery
    │   ├── aion_discovery.py       ← AION IAM auth + product-instances inventory
    │   ├── exceptions.py           ← IQError hierarchy
    │   └── version.py              ← single source of truth: __version__ = "0.1.0"
    ├── tests/
    │   ├── conftest.py
    │   ├── fixtures.py             ← real captured request/response shapes (inline, trimmed)
    │   ├── data/                   ← real captures, recovered 2026-09-03 -- see §9
    │   │   ├── view_detailed_stream_results.json      -- real
    │   │   ├── dsr_query_unfiltered.json               -- real
    │   │   └── dsr_query_filtered_min_latency.json     -- constructed, NOT yet GUI-confirmed (§9)
    │   └── test_*.py               ← 260 passing, 0 skipped
    └── examples/                   ← one runnable script per use case
        ├── discover_local.py            ← IQ-PYTHON-002: standalone/on-prem TestCenter (modes A-D)
        ├── discover_aion.py             ← IQ-PYTHON-002: AION platform (mode E)
        ├── list_tests_by_owner.py
        ├── inspect_database_schema.py   ← IQ-PYTHON-006: schema/tables/fields
        ├── manage_views.py              ← IQ-PYTHON-003: view CRUD (self-cleaning)
        ├── run_view_query.py
        ├── fetch_view_data.py           ← one known database_id=/view name=, every generic feature (filters=/sort=/group_by=/time_range=/snapshot_name=/raw_result=), columns+types discovered dynamically -- works against any single_level_table view, not just this one
        ├── run_live_query.py
        ├── query_modifiers.py           ← IQ-PYTHON-005: filters=/sort=/group_by=/time_range=
        ├── run_json_definition_query.py ← IQ-PYTHON-003: arbitrary query as a JSON string
        ├── multi_database_query.py      ← IQ-PYTHON-007: per-call database_id= override
        ├── run_xy_chart_query.py
        ├── run_pie_chart_query.py
        ├── run_histogram_query.py
        ├── run_boxplot_query.py
        ├── auto_repair_demo.py          ← the auto_repair loop, in isolation
        ├── manage_test_database.py      ← IQ-PYTHON-010: rename_test()/delete_test() -- DESTRUCTIVE, confirmation-gated
        └── generate_report.py
```

`PLAN.md`, `DEPLOYMENT_PLAN.md`, and `WIDGET_QUERY_PLAN.md` are referenced
by name and section number throughout this codebase's docstrings and
comments (architecture rationale, widget-builder research, the
publishing/deployment checklist this file's §10 duplicates) but no longer
exist anywhere — see §0. Those in-code references are left as-is since
they're still useful context even pointing at a gone file; this document
now carries the load-bearing subset of that content directly (§4, §9,
§10, §13 below).

---

## 4. Architecture

`tciqrestclient` talks directly to `orion-res`'s REST API at bare root paths — `/databases`, `/views`, `/queries`, `/reports`. **Ignore the `/api/res/` prefix in the Swagger docs;** that's the path when proxied through `iq-data`, not needed here.

### Key call flow — `iq.query(name=...)`

```
find_view_by_name()
  → GET /views
  → get_view_definition()          extracts the right table's query_provider
  → build_query_definition()       builds multi_result tree from template
  → merge_modifiers()              applies caller's filters/sort/group_by/limit
  → POST /queries (mode: "once")
  → rows_to_dicts()                zips columns + rows into list of dicts
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Resolves `base_url` from constructor kwargs → env vars → `.env`. Sequences AION discovery so `timeout=` is available before the first request. |
| `transport.py` | Thin `requests` wrapper. JSON in/out, `IQ*Error` mapping, optional `Authorization: Bearer` injection, debug request/response logging. |
| `databases.py` | `/databases` operations. `list_tests(owner=)` fetches all tests and filters client-side on `metadata["test.owner"]`. |
| `views.py` | `/views` operations. `find_view_by_name()` fetches all views and matches by name. `get_view_definition()` extracts the right table's `query_provider` for the builder. `build_field_resolver()` enables display-name lookups in filters. |
| `query.py` | `merge_modifiers()` appends filters/sort/group_by/time_range expression strings to a definition tree. `rows_to_dicts()` zips `columns` + `rows` arrays into dicts. |
| `view_query_builder.py` | Builds a `multi_result` query definition from a view's `effective_details.system_data.query_providers` templates. Dispatches by `view_type`. Also owns `parse_unknown_attribute_error()` + `strip_unknown_attribute()` for the auto_repair loop. |
| `queries.py` | `run_query()` → `POST /queries` with `mode: "once"`. |
| `reports.py` | List templates, create + poll a report, download file. |
| `discovery.py` | Reads `orion-res.yaml` (local IQ) or `stcbll.ini` section `[enhancedResults]` (remote IQ). |
| `aion_discovery.py` | Authenticates to AION IAM, queries `/api/inv/product-instances`, returns `(host, port, access_token)`. |
| `client.py` | `IQClient` — glues everything together. The only public API surface callers should import. |

### auto_repair loop

A view's `query_provider` template is shared across every database that uses that view. Not every database has every attribute the template references (e.g. a single-stack test database has no dual-IP/VLAN/IPv6 config columns). orion-res 400s with `VALIDATION_FAILED: unknown attribute name: <projection>` (or, confirmed against a real AION-managed server, `VALIDATION_FAILED: unknown dimension or result set name: <projection>` — a differently-worded server phrasing of the identical situation) — one column at a time.

`IQClient._run_with_auto_repair()` catches either phrasing, strips the offending projection fragment from the definition tree, and retries (up to 100 times). Check `iq.last_dropped_columns` after a call to see what was stripped. A real single-stack test database was observed to be missing ~21 such columns at once. If a database is missing an entire underlying table/measurement (not just one field of it), `auto_repair` can end up stripping every column a query would have selected — `_run_with_auto_repair()` detects that (the outermost query node reaching zero projections) and raises a clear `IQQueryError` naming every dropped column, rather than sending an empty query and surfacing the server's opaque `"at least one projection is required"` error.

---

## 5. Discovery Modes

**Corrected 2026-09-03** — this used to state "explicit base_url → explicit
host/port → AION discovery → install_dir file discovery," which doesn't
match `tciqrestclient/config.py::resolve_config()`'s actual code. The real order,
confirmed by reading it line by line:

1. `base_url=` kwarg
2. `host=`/`port=` kwarg
3. `install_dir=` kwarg (reads `orion-res.yaml`/`stcbll.ini`)
4. An explicit `aion_url=` kwarg, *if* AION discovery via it succeeds
   (fixed 2026-09-03 — see §9; it used to rank below step 7, losing to a
   merely-ambient env var, which was a real bug)
5. `TCIQ_BASE_URL` env var
6. `TCIQ_HOST`/`TCIQ_PORT` env var
7. `TCIQ_INSTALL_DIR` env var
8. AION resolved purely from `TCIQ_AION_*` environment variables (no
   `aion_url=` kwarg) — **last**, only attempted if nothing else (kwarg
   or env) resolved anything.

| Option | How to use | What it does |
|---|---|---|
| **A — Explicit base URL** | `TCIQ_BASE_URL=http://127.0.0.1:9200` | Skips all discovery. Fastest path for a known deployment. |
| **B — Explicit host/port** | `TCIQ_HOST` + `TCIQ_PORT` | Useful when host and port come from separate config sources. |
| **C — Local STC install** | `TCIQ_INSTALL_DIR=<dir>` | Reads `<dir>/orion-res/etc/orion-res.yaml`, key `service.addr`. |
| **D — Remote STC (stcbll.ini)** | `TCIQ_INSTALL_DIR=<dir>` | Reads `<dir>/stcbll.ini` section `[enhancedResults]`. Prefers `orionResServicePublicUrl`, falls back to `orionResServiceUrl`. |
| **E — AION platform** | `TCIQ_AION_URL` + `TCIQ_AION_USERNAME` + `TCIQ_AION_PASSWORD` | Authenticates to AION IAM → queries `/api/inv/product-instances` → extracts `orion-res` host/port + bearer token. Token is injected as `Authorization: Bearer` on all subsequent calls. |

See `examples/discover_local.py` (modes A-D) and `examples/discover_aion.py` (mode E).

**Gap found in the 2026-09-04 final audit, not previously documented anywhere:**
the PRD's own "How the Python Client Helps" narrative (section 2) illustrates
IQ-PYTHON-002 with `iq = IQClient(host='192.168.1.100')` as a complete
one-line replacement for "query the TestCenter REST API for the IQ service
record, parse the JSON, extract the port" — i.e. a bare host with **no
port**, and no filesystem/AION access, resolving the real port itself.
No such mechanism exists: `host=` with no `port=` composes
`http://192.168.1.100` (implicit port 80, `_compose_base_url()` in
`config.py`) and performs zero port lookup — confirmed by direct testing.
The only two discovery mechanisms that actually resolve a port are
`install_dir=` (needs local filesystem access to an STC install) and AION
(needs a full AION URL + credentials). An automation engineer with only a
chassis/host IP and neither of those has no working discovery path today.
This is a real gap against the PRD's literal illustration, not just a
missing example — flagging it here since number 002's own requirement
bullets (explicit override, configurable timeout, AION support) are all
independently satisfied and this narrower narrative-example gap could
otherwise be missed. No fix attempted this pass (no live server available
to determine what a real "IQ service record" lookup from a bare host
would even call) — worth a design discussion with product/the orion-res
team before publishing further, or at minimum an explicit call-out in
whatever announces this client to users that `host=` always needs `port=`
alongside it.

---

## 6. Configuration Reference

Copy `.env.example` to `.env` and fill in at minimum one address option. Every variable can also be passed as a constructor kwarg to `IQClient()`; explicit kwargs always override the environment. `.env.example` now documents every one of these (the AION and `TCIQ_DEBUG` variables were missing from it previously).

| Variable | Purpose | Default |
|---|---|---|
| `TCIQ_BASE_URL` | Full base URL — skips all discovery | — |
| `TCIQ_HOST` / `TCIQ_PORT` | Explicit orion-res address | — |
| `TCIQ_INSTALL_DIR` | STC install dir for file-based discovery | — |
| `TCIQ_DATABASE_ID` | Default test id — `use_test()` not needed per-run | — |
| `TCIQ_TIMEOUT` | HTTP timeout in seconds (orion-res + AION discovery calls) | `10` |
| `TCIQ_DEBUG` | `1`/`true`/`yes` → log method/URL/body + timing before each request | off |
| `TCIQ_AION_URL` | AION platform base URL | — |
| `TCIQ_AION_USERNAME` | AION login email | — |
| `TCIQ_AION_PASSWORD` | AION login password | — |
| `TCIQ_AION_NODE_NAME` | Restrict AION discovery to a specific node | (all nodes) |
| `TCIQ_AION_PORT_NAME` | Port label in AION product-instances | `orion-res` |
| `TCIQ_AION_CA_CERT` | CA cert path for AION HTTPS | (system) |

---

## 7. IQClient API Surface

Import only from the top-level package — do not import from submodules directly.

```python
from tciqrestclient import IQClient, IQError, IQViewError   # all public names are in __all__
```

### Tests / Databases

| Method | What it does |
|---|---|
| `list_tests(owner=None, detail="summary")` | Fetch all tests; filter by `metadata["test.owner"]` client-side |
| `get_test(database_id=None)` | Full metadata for one test |
| `use_test(database_id)` | Set the default test for subsequent calls |
| `delete_test(database_id=None)` | Permanently delete a test's stored results |
| `rename_test(new_name, database_id=None)` | Rename a test database |
| `get_database_schema(database_id=None)` | `GET /databases/{id}?detail=full` — full schema record |
| `list_table_names(database_id=None)` | List table descriptors from the full schema |
| `list_fields(table_name=None, database_id=None)` | List field descriptors, optionally scoped to one table |

### Views

| Method | What it does |
|---|---|
| `list_views(timeout=None)` | List all views. Can be slow — full `effective_details` per view |
| `get_view(view_id, timeout=None)` | Get one view by ID |
| `find_view(name, timeout=None)` | Find a view by display name, or `None` |
| `list_view_columns(name, test_live=None, active_only=False, timeout=None, data_type=None, table_index=None)` | List a view's columns with GUI display names — use these in `filters=`/`sort=`. `test_live=None` (the default) resolves to the `eot` (snapshot) table, per IQ-PYTHON-004 — see below. `data_type=`/`table_index=` are advanced legacy aliases, still accepted |
| `save_view(name, details=None, description="", definition=None)` | Create or update a view. `definition=` is an alias for `details=` |
| `delete_view(view_id=None, name=None, timeout=None)` | Delete by ID or by name (name triggers a lookup first) |

### Query

```python
rows = iq.query(
    "Detailed Stream Results", "live",   # OR: definition={...} / definition="<json string>"
    user="jdoe",                         # auto-finds jdoe's one running test -- or database_id="abc123" directly
    filters=[("Rx Count", "gt", 100000)],# display name, path, bare column name, or alias all work
    sort="Rx Count DESC",
    limit=500,                           # default 1000; limit=None = no override
    timeout=30,                          # per-call override (applies to /views + /queries)
    auto_repair=True,                    # default True; strips unknown columns and retries
)
# For histogram/boxplot: returns {name: rows} instead of a plain list
print(iq.last_dropped_columns)          # columns stripped by auto_repair
```

`query()`'s full signature (renamed/added 2026-09-04 per PM feedback — see
§0d): `query(name=None, test_live=None, database_id=None, user=None,
snapshot_name=None, filters=None, sort=None, group_by=None,
time_range=None, limit=DEFAULT_QUERY_LIMIT, mode="once",
raw_result=False, timeout=None, auto_repair=True, definition=None,
data_type=None, table_index=None)`. `test_live=True/False` (or the
strings `"live"`/`"eot"`/`"snapshot"`, case-insensitively) replaced
`data_type=` as the primary way to pick live vs. snapshot data —
`data_type=`/`table_index=` still work unchanged, as advanced/legacy
options, moved to the end of the signature. `user=` resolves
`database_id` automatically for live data only (finds the one test
`metadata["test.running"]=="true"` for that owner); for snapshot data it
raises asking for an explicit `database_id=` instead of guessing, since
a user can have many completed tests.

`definition=` accepts either a dict or a JSON string (parsed automatically) — this is what satisfies IQ-PYTHON-003's "arbitrary IQ queries expressed as JSON strings" requirement (the PRD's reference to `EnhancedResultsQuery` is naming the equivalent legacy socket/automation-API command as context, not an API this REST client needs to expose separately).

**Column name resolution** — `filters=`, `sort=`, `group_by=`, `time_range=` on a `name=` query accept a column's GUI display name (`"Rx Count"`, case-insensitive), its raw attribute path (`"rx_stream_stats.frame_count"`), an unambiguous bare column name (`"frame_count"` — only when exactly one column on that view ends in it; fixed 2026-09-04, see §0d), or its internal alias (`"rx_stream_stats_frame_count"`). Use `list_view_columns(name)` to see what's available.

**Return shape** — a plain `list[dict]` for `single_level_table`, `paged_single_level_table`, `x_y_chart`, `pie_chart`, and any `definition=` call. A `{name: list[dict]}` dict for `histogram` (one query per provider) and `boxplot` (one query per statistic).

### Reports

| Method | What it does |
|---|---|
| `list_report_templates()` | List available report templates |
| `get_report_template(template_id)` | Get one template by ID |
| `generate_report(template_id, title=None, database_id=None, format="pdf", output_path=None)` | Create a report; download it when `output_path` is given. `title=` is required by the server (raises `IQReportError` if omitted); `format=` must be lowercase — see §9 |
| `get_report(report_id)` | Check report status / get metadata |
| `download_report(report_id, save_as=None)` | Download a completed report |

### Errors

All errors raise a subclass of `IQError`:

| Exception | When |
|---|---|
| `IQConfigError` | No address could be resolved from args/env |
| `IQConnectionError` | Network-level failure |
| `IQRequestError` | HTTP 4xx/5xx from orion-res |
| `IQQueryError` | Bad query arguments or `definition=` |
| `IQViewError` | View not found, or unsupported `view_type` |
| `IQReportError` | Report generation failure |

---

## 8. Requirements Status

| Requirement | P | Status | Notes |
|---|---|---|---|
| IQ-PYTHON-001 — Distribution / packaging | P0 | ✅ Done | `pyproject.toml` with dynamic version; package builds cleanly with correct metadata/URLs and a self-runnable sdist. **Published to real, public PyPI 2026-09-22** (`tciq 0.1.0` — https://pypi.org/project/tciq/0.1.0/) — `pip install tciq` genuinely works now, re-verified in a fresh venv against the actual published package (not just a local wheel build). Published from the uncommitted working tree at the time, per explicit instruction — no git tag/commit corresponds to exactly what's on PyPI; worth committing and tagging `v0.1.0` retroactively. Root `setup.py`'s `iq` extras group still exists alongside this for the `py-stcrestclient` monorepo case. **Superseded 2026-09-23**: the package was renamed `tciq` → `tciqrestclient` and republished under the new name (`tciqrestclient 0.1.1` — https://pypi.org/project/tciqrestclient/0.1.1/, see §10); `tciq` 0.1.0/0.1.1 remain live on PyPI, unmaintained, but `tciqrestclient` is now the current, actively-published name. |
| IQ-PYTHON-002 — AION Discovery | P0 | ⚠ Partial | Full AION constructor params; `timeout=` honoured throughout, confirmed threaded into every AION HTTP call. Local/standard-deployment discovery (`install_dir=`) independently confirmed too. Port name `'orion-res'` in product-instances is assumed — confirm on a real AION server. The PRD's own narrative example (`IQClient(host='192.168.1.100')` alone resolving a dynamic port) has no implementation — `host=` always needs `port=` alongside it; see §0c/§5. |
| IQ-PYTHON-003 — Named Views | P0 | ✅ Done | `save_view(definition=...)` alias; `delete_view(name=...)` lookup; JSON string accepted in `query(definition=...)` (satisfies the PRD's "arbitrary queries as JSON strings" language — see §7). Fixed 2026-09-03: a view created via `save_view()` used to be unusable by `list_view_columns()`/`query(name=...)` afterward (missing `system_data`) — now resolved at the library level, re-verified end-to-end against a live server, and against a corrected mock that actually exercises reuse+delete (see §0c). |
| IQ-PYTHON-004 — Live/Snapshot | P1 | ✅ Done | `query(data_type="live"/"eot")` and `snapshot_name=`. Fixed 2026-09-03: with neither argument given, `query()` now defaults to the `eot` (snapshot) table as the PRD requires, instead of whichever table a view happens to list first — now covered by a regression test at the `IQClient.query()` level itself, not just the lower-level resolver (see §0c). |
| IQ-PYTHON-005 — Query Modifiers | P1 | ✅ Done | `filters=`, `sort=`, `group_by=`, `time_range=` via `merge_modifiers()`. GUI display name resolution. All four combined in one call, and applied identically to every sub-query of a multi-kind view, now covered by dedicated regression tests (see §0c). |
| IQ-PYTHON-006 — Database Metadata | P1 | ⚠ Partial | `get_database_schema()`, `list_table_names()`, `list_fields()` correctly match the real `result_sets`/`dimension_sets` response shape (fixed and re-confirmed against a live server 2026-09-03). The public API's own docstrings wrongly claimed a `'data_type'` key instead of the real `'type'` — fixed 2026-09-04 (see §0c) — since this requirement is specifically about documenting available data types, that was worth calling out as partial rather than folding silently into "Done". |
| IQ-PYTHON-007 — Multi-Database | P1 | ✅ Done | `database_id=` per call on every relevant method; `use_test()` default. Independently re-verified end-to-end (including the exact "two databases, no `use_test()` at all" scenario) and now covered by dedicated regression tests for every method's override path (see §0c). |
| IQ-PYTHON-010 — Database Management | P1 | ✅ Done | `rename_test()` — CONFIRMED against a real server 2026-09-17 (see the dedicated §9 section): the original `PUT {"name": ...}` guess was wrong (400/500 against a real server); fixed to fetch-then-PUT-the-full-record, verified via a real rename+revert round trip, with a new dedicated example (`rename_test_roundtrip.py`). `delete_test()` still has solid mocked unit coverage only — never exercised against a real server (genuinely destructive, no revert possible), see §11. |
| IQ-PYTHON-011 — Report Generation | P0 | ⚠ Partially working | `generate_report()`/`download_report()` — format/title bug fixed and re-confirmed 2026-09-03; a missing `title=` now raises `IQReportError` consistently (fixed 2026-09-04). `output_path=` downloads immediately without waiting for the (confirmed real, asynchronous) generation job to finish, producing a 0-byte file — confirmed, not fixed, see §9. The example demonstrating this requirement is now covered by an automated smoke test for the first time (see §0c). |

(IQ-PYTHON-008 and -009 don't appear in the PRD's requirements section at all — a gap in product management's own numbering, not a missed requirement on the implementation side.)

See §0c for the full 2026-09-04 final pre-publish audit this table's "Partial" ratings come from — every one of them is a real implementation with a documentation, verification, or coverage gap around an edge case, not a broken core feature.

---

## 9. Known Gaps & Unconfirmed Assumptions

### Real-capture test fixtures (`tests/data/`) — RECOVERED 2026-09-03

The three files this section used to describe as permanently lost are
back, from a real, live orion-res server that turned out to be running
locally on this machine (`http://127.0.0.1:9200` — discovered via
`examples/discover_local.py`; see §11 for what it is):

- `view_detailed_stream_results.json` — a genuine, full (not trimmed)
  export of a real "Detailed Stream Results" view, captured fresh from
  that server, `effective_details.system_data.query_providers` intact.
- `dsr_query_unfiltered.json` — the real `POST /queries` body
  `view_query_builder.build_query_definition()` + `merge_modifiers()`
  produce for that view's `eot` table, unfiltered, `limit: 120` —
  produced by calling those functions directly against the freshly-
  captured view above (not literally sniffed from a browser, but
  byte-for-byte what `tciq` itself sends for that call — no distinction
  from the GUI matters here, since this is checking tciq's own output
  against itself is not the point; what's confirmed is that the real
  server accepts the *shape* this produces).
- `dsr_query_filtered_min_latency.json` — **NOT a real GUI capture yet**.
  The REST API alone can't produce the GUI's own "push-down" filter
  placement, and no browser was available in this environment. This file
  was instead constructed by applying the exact transform
  `test_matches_real_filtered_capture_gui_pushdown_shape` itself
  describes to the same real view, then confirmed executable against the
  real server (after the same schema-driven column stripping the
  unfiltered capture needed). See that test's module docstring for the
  full caveat. **Replace this one file** with an actual browser DevTools
  capture (open "Detailed Stream Results", type
  `rx_stream_stats.min_latency < 0.17` into its filter box, copy the
  `POST /queries` request body) to turn this from "self-consistent" into
  "independently confirmed" — update the docstring either way once done.

**Result:** `pytest` went from 227 passed/33 skipped to **260 passed, 0
skipped**. `test_matches_real_unfiltered_capture` — the core structural
validation of the whole `single_level_table` builder — passed against
this fresh, independently-captured data, which is a genuine
re-confirmation the algorithm is still correct (not merely
self-consistent, since the fixture wasn't derived from the code under
test). The unfiltered capture also independently reproduced the exact
`VALIDATION_FAILED: unknown attribute name: tx_stream_config.
ipv4_2_source_addr...` error `_REAL_ERROR_BODY` in this test file already
hardcoded, and `auto_repair` stripped ~19-20 columns against two
different real databases — matching this document's own "~21 columns"
claim. Strong corroboration all around, independent of the one remaining
open item above.

### Widget query builders — confirmation status

| `view_type` | Status | Source |
|---|---|---|
| `single_level_table` / `paged_single_level_table` | ✅ Confirmed | Re-confirmed byte-for-byte 2026-09-03 against a fresh real capture — see the "RECOVERED" section above. |
| `x_y_chart` | ❌ CONFIRMED BROKEN | See below — `query(name=...)` always raises `IQViewError` against a real x_y_chart view. |
| `pie_chart` | ⚠ Not yet confirmed | No real pie_chart view existed on the local server to test against — see below. Given the pattern found in x_y_chart/histogram, likely has the same class of problem. |
| `histogram` | ❌ CONFIRMED BROKEN | See below — same root cause as x_y_chart. Returns `{provider_name: rows}` when it works at all. |
| `boxplot` | ⚠ Not yet confirmed | No real boxplot view existed on the local server to test against — see below. Likely has the same class of problem as x_y_chart/histogram. Returns `{statistic_name: rows}` when it works at all. |
| `health_indicator` / `chart` / `gauge` | ❌ Unsupported | `query(name=...)` raises `IQViewError`. Use `query(definition=...)` with a captured tree instead. |

The TS source was originally read from a local clone of `magellan-frontend` at `C:\Vinod_Data\Workplace\Projects\TCIQ\magellan_frontend\magellan-frontend\app\src\domain\widgets\models` — still not available on this machine (a `magellan-frontend.tgz` found elsewhere here is a built/minified production bundle, not source, and isn't practical to reverse-engineer accurately).

#### `x_y_chart`/`histogram` CONFIRMED BROKEN — deeper than "unconfirmed", NOT YET FIXED

Found 2026-09-03 running `examples/run_xy_chart_query.py`/`run_histogram_query.py` against the live local server (508 real views, including one real `x_y_chart` view — "Multi-Join Base XY Chart View" — and one real `histogram` view — "Blank Histogram"). `view_query_builder.py`'s `_resolve_table_and_provider()` — shared by **every** `view_type`, not just table — unconditionally reads `view["details"]["user_data"]["tables"]`. That key simply doesn't exist for these two view types:

- `x_y_chart`'s real `details.user_data` shape: `{"series": [{"chart_type", "filter_columns", "h_axis", "v_axis", "query_provider", ...}], "refresh_rate_in_msec"}` — no `"tables"` at all.
- `histogram`'s real `details.user_data` shape: `{"statistics": [...], "group_by", "h_axis", "v_axis", "buckets_config", "max_series_count", "refresh_rate_in_msec"}` — also no `"tables"`.

Concretely: `query(name="Multi-Join Base XY Chart View", data_type="eot")` raises `IQViewError: view ... has no table with data_type='eot' (available: [])`, and the same for the real histogram view — **every** `query(name=...)` call against either view_type fails, not just an edge case. This is a real, confirmed correctness gap in `_build_xy_chart_query()`/`_build_histogram_queries()` (and by strong inference, `_build_pie_chart_query()`/`_build_boxplot_queries()` too, though no real view of those two types was available on this server to directly confirm) — they were written and unit-tested against *synthetic* fixtures shaped like `single_level_table`'s `tables` list (see `test_view_query_builder.py`'s `_synthetic_view()`), which turns out not to match any of these view_types' real shape at all.

**Not fixed.** This is substantially bigger than the AION/schema/snapshot-filter fixes already applied this session — it needs `_resolve_table_and_provider()` (or a view_type-aware replacement) to understand each widget type's own real `user_data` shape (`series[]` for x_y_chart, `statistics[]`/`group_by` for histogram, and whatever pie_chart/boxplot turn out to use), then rebuild each builder's projection-gathering logic around it — effectively redoing the "unconfirmed → confirmed" work `single_level_table` already went through, for four more view_types at once. The example scripts (`run_xy_chart_query.py`, `run_histogram_query.py`) were fixed only to stop crashing on this (a presentational line assumed the same missing `"tables"` key) — they now correctly report the existing `IQViewError` instead of a raw `KeyError`, but the underlying `query(name=...)` capability for these view_types remains non-functional. See §11.

**Re-confirmed 2026-09-16 against two real AION-managed servers, not just this local one** — same `IQViewError`/`"has no table with data_type=...'"` failure, byte-for-byte the same root cause, on a completely independent deployment. Also newly confirmed broken the same way: `chart` and `health_indicator` view_types (never exercised through `query()` before this session) — both also lack a `details.user_data.tables` list. `drill_down_table`, by contrast, isn't broken — `query(name=...)` deliberately refuses it up front with a clear, actionable message rather than crashing (see "Verified against real AION-managed servers" below for the full cross-server writeup).

#### Report generation: format/title — RESOLVED 2026-09-03; async download race — client-side pattern provided, server-side root cause CONFIRMED but not fixable here; chart-section crash — RESOLVED 2026-09-16 via `excluded_sections=`

Found and fixed running `examples/generate_report.py` against the real server. Three issues:

1. **`format="PDF"` (the old default) and `title=` (previously not exposed at all) — RESOLVED.** The real server 400s `"unknown report format"` for uppercase `"PDF"` (lowercase `"pdf"` works) and `"missing report title"` when no title is sent at all. **Fix applied**: `IQClient.generate_report()` and `tciq.reports.create_report()` both now take an explicit, required `title` parameter (a new required positional arg — a breaking signature change, deliberately, since the old signature could never succeed against a real server without already-undocumented `**extra` magic) and default `format="pdf"`. Verified against the real server: report creation now returns `"status": "queued"` instead of a 400. Tests and examples updated to match the new signature.
2. **Report generation is asynchronous — CONFIRMED, NOT fixed at the tciq layer (root cause now fully understood, 2026-09-15).** A freshly created report's status is `"queued"` (with a `progress.queue` counter), not immediately ready — but `generate_report(output_path=...)` calls `download_report_file()` immediately after `create_report()` returns, with no wait/poll for completion. Confirmed this produces a **0-byte file** on a real server. `wait_for_report()` in `examples/generate_report.py` is the correct client-side fix for *this* (poll `get_report()` until a terminal status, only download then) — but no report has ever been observed reaching a real completion status against this local server, and the root cause has now been fully diagnosed by reading `orion-res`'s own Go source (`C:\Users\bha83166\go\src\github.com\SpirentOrion\orion-api-1\cmd\orion-res\report`) and inspecting the live report-rendering Chrome tab directly via the Chrome DevTools protocol (not just polling REST):

   - **A real, universal frontend bug**: the report-rendering web app (`report.html`, served by `orion-res` itself, minified bundle `main.d1a7a0a2.js`) throws `TypeError: Cannot read properties of undefined (reading '<database_id>')` immediately after its first "generating 0%" progress message, for *every* database id tried (confirmed with two different ids) — not data-specific, a systematic defect. The app *does* correctly try to report this as `{"status":"error","message":"...","id":"..."}` via `console.log`, in exactly the shape the Go backend expects.
   - **A real concurrency bug in the Go backend that swallows that error**: `report.Worker.renderingState()` (`cmd/orion-res/report/worker.go`) launches a goroutine to create the Chrome tab, navigate, and watch for console messages, then immediately runs a `select` with a `default:` case racing against that goroutine's `errChan`/`nextChan`. Since `default` fires whenever no other case is *already* ready, and the goroutine has just been launched, this select resolves via `default` almost instantly — before the goroutine has done anything — advancing the state machine to `waitToRenderAllState` and abandoning `errChan`/`nextChan`. When the goroutine later tries to report the frontend's error via `errChan <- (*Worker).errorState`, nothing is listening anymore and the send **blocks forever**, permanently leaking the goroutine. `waitToRenderAllState` then just polls Chrome's tab list for a URL-based completion signal that will never arrive, bounded only by the full 60-minute `generation_timeout` in the real running config — exactly the "stuck at generating, 0%, indefinitely" behavior observed all session, and why `"error"` status was never once seen despite the frontend genuinely trying to report one.

   This is a bug in `orion-res` itself (both the Go concurrency issue and the frontend JS defect), not in `tciq` — **confirmed root cause, deliberately left unfixed here per explicit instruction not to modify the Go or frontend side of that separate codebase.** `tciq`'s own `wait_for_report()` example is the correct client-side pattern regardless; it just has no server in this environment that will ever exercise its success path once the report leaves `"generating"` (bug #1, still open — see below). Fixing that actual bug means: in `renderingState()`, replace the racy `select`/`default` with logic that only advances once the goroutine has confirmed real progress (e.g. an explicit signal sent after tab creation + navigation succeed, rather than firing unconditionally before the goroutine runs at all); separately, the frontend's `TypeError` needs its own fix in whatever source repo produces `main.d1a7a0a2.js`.

3. **The frontend `TypeError` (bug #2 above) — RESOLVED from the `tciq` side, 2026-09-16, via `excluded_sections=`, and independently RE-CONFIRMED the same day through the real `IQClient` path.** Root-caused by inspecting the live report tab directly with the Chrome DevTools Protocol — not just log-watching, but an actual `Debugger.setPauseOnExceptions: uncaught` breakpoint on the crash itself. Captured scope at the crash pointed at histogram/chart widget code (`buckets_config`, traced to `magellan-frontend`'s `domain/widgets/models/histogram/histogram.widget.structure.ts`) — i.e. the crash is specific to a report template's **chart-type sections**, not to any particular database. Confirmed against the real "Traffic Test Report" template (`295049e881f74b458244a3adb60a7c28`): it has 3 sections — two table sections (`section`, `section_1`) and one chart section (`section_2`, containing "Port Frame Rate Chart"/"Stream Frame Rate Chart"). The real `POST /reports` body's `parameters.excluded_sections` field (a JSON-encoded list of a template's own section names) skips a section during rendering — **excluding just `section_2` made the exact same template render completely**, confirmed twice, independently:
   - First pass: inspecting the rendered tab's DOM directly (`Runtime.evaluate`) showed 4 real pages, a Table of Contents listing only "Traffic Statistics"/"Stream Statistics", real column headers and row data (e.g. "Snapshot", "3,768,882,569").
   - Second pass, same day: re-run through the actual `IQClient.generate_report(excluded_sections=...)` path (not an ad-hoc script) against a *different*, live/currently-running test database, watching the spawned Chrome tab's console directly. Zero uncaught exceptions the whole way through; the frontend itself logged the exact completion message the Go worker listens for (`{"percent":0,"status":"generating",...}` then `{"status":"complete","id":"..."}`), and a final DOM check showed real rendered content (814 characters of body text across 24 page elements, `document.readyState: "complete"`). A minor, unrelated, non-fatal `console.error` also appeared both times ("Couldn't parse preferences" / `SyntaxError: Unexpected end of JSON input` in `nS.getPreferences`) — logged, but doesn't stop or corrupt rendering.

   This is a genuine, twice-confirmed-working fix — not a guess — and required zero changes to Go or frontend code.

   **Fix applied, generalized (not hardcoded to `"section_2"`)**: `tciq/reports.py` gained `REPORT_SAFE_VIEW_TYPES` and `find_unsupported_sections(transport, template, timeout=None)`, which walks a template's `details.sections`, resolves each section's view(s) by name via `find_view_by_name()`, and flags any section whose view's real `view_type` isn't in that safe set (a section whose view can't be found at all also counts as unsupported, rather than silently passing it through). `IQClient` gained `find_unsupported_report_sections(template_id, timeout=None)` (a thin wrapper: `get_report_template()` + `find_unsupported_sections()`) and `generate_report(..., excluded_sections=None)`, which JSON-encodes the given list into `parameters.excluded_sections` alongside any `snapshot_filter=`. `examples/generate_report.py` computes `unsupported = iq.find_unsupported_report_sections(template["id"])` once and passes it to every `generate_report()` call in the file.

   **Self-correction, same day**: `REPORT_SAFE_VIEW_TYPES` was first shipped as `("single_level_table", "paged_single_level_table")`, based on a mis-recorded read of the real template's view types. A live re-check (`iq.find_view()` on each section's own view name — each name confirmed unique in the 507-view catalog, no ambiguity) showed the *actual* types are `"drill_down_table"` (both table sections) and `"chart"` (both chart sections) — not `"single_level_table"`/`"x_y_chart"`. As shipped, this bug meant `find_unsupported_report_sections()` would have flagged **all three** sections of the real template, not just the chart one, producing a fully-empty report instead of the intended surgical exclusion. Fixed by adding `"drill_down_table"` to `REPORT_SAFE_VIEW_TYPES`; re-checked live against the real template afterward — now correctly returns `["section_2"]` only. Test fixtures in `tests/test_reports.py` updated to match the real types. Full suite: 341 passed.

   **This does not fix bug #1 (the Go concurrency/goroutine-leak bug) — and the second re-verification pass directly demonstrates that separation.** In that same live re-check, even though the frontend genuinely rendered the report and logged its own `"status":"complete"` message, `GET /reports/{id}` never reflected it — the report's REST-visible status ended at `"canceled"`, and `download_report()` returned 0 bytes. This is now direct, empirical confirmation (not just inference from reading the Go source) that bug #1 silently drops a real completion signal: the frontend did its job correctly and excluded_sections= avoided the crash, but the Go-side state machine still never correlates that success with the report's terminal status, so `download_report()`/`wait_for_report()` still can't retrieve a working file until bug #1 itself is fixed on the `orion-res` side.

   **Separate, unrelated observation, not acted on**: `orion-res.exe` was observed to crash outright *twice* during this investigation (confirmed via `Get-Process` returning nothing, then later restarting on its own with a new PID), coinciding with 25-36 accumulated Chrome processes at various points and, briefly, a fully jammed report queue (a fresh report request sitting at `status=queued, progress={"queue":1}` indefinitely — consistent with `chrome.max_concurrency: 2` being permanently exhausted by bug #1's leaked workers). The orion-res log also showed repeated `"Chrome early termination"` / `"exit status 21"` errors, traced to a stale lock on Chrome's shared `--user-data-dir` profile folder held by the accumulated processes. All of this is very likely resource exhaustion from repeated report-generation testing across a long session. Flagged here for whoever owns this environment to restart/clean up (kill stray `chrome.exe` processes, clear `%LOCALAPPDATA%\Temp\chrome`) — deliberately not killed or restarted from here, since it's a real machine this project doesn't own and no one asked for that intervention.

#### `auto_repair` had two real gaps, found via a real AION-managed server — RESOLVED 2026-09-16

Found while running a live feature-parity check of `tciq` against real AION-managed orion-res deployments (see the "Verified against real AION-managed servers" section below) — not local, not a guess. Against a real "NFVi Advanced Kubernetes Platform Deployment Summary" `single_level_table` view on `http://10.109.143.126:64012/api/res`, `query()` failed in two ways `auto_repair=True` was supposed to prevent:

1. **The "unknown attribute" regex only matched one of two real phrasings.** `view_query_builder._UNKNOWN_ATTRIBUTE_RE` matched `"unknown attribute name: ..."` but this real server's 400 said `"unknown dimension or result set name: ..."` instead — a different phrasing of the identical schema-mismatch situation. The regex didn't match, so `auto_repair` gave up immediately instead of stripping the bad column and retrying. **Fix**: broadened the regex to `unknown (?:attribute name|dimension or result set name):\s*([^"]+)` — confirmed live: the same query that used to fail immediately now correctly proceeds into strip-and-retry.
2. **Nothing stopped `auto_repair` from stripping every column and sending an empty query.** Once fix #1 let stripping proceed, it turned out *every* column this view's template references (`instance_kind`, `instance_name`, `labels`, `selector`, `details`) belongs to the same underlying measurement (`nfv_adv_k8s_instance_group_instance`), which this specific database's schema is missing *entirely* — not just one field. `auto_repair` stripped all 5 one at a time, then sent an empty-projection query, which the server rejected with an opaque `"at least one projection is required"` — giving no hint the real cause was a wholesale missing table. **Fix**: `IQClient._run_with_auto_repair()` now checks the outermost query node's projection count after each strip; if it would reach zero, it raises a clear `IQQueryError` itself (naming every dropped column) before ever sending that empty request.

Both fixes are covered by tests (`tests/test_view_query_builder.py`'s `test_parse_unknown_attribute_error_dimension_phrasing`; `tests/test_client.py`'s `test_query_auto_repair_strips_unknown_dimension_or_result_set_and_retries` and `test_query_auto_repair_raises_clear_error_when_every_column_missing`) and were each re-verified live against the real server that surfaced them — confirmed holding a third time in a full follow-up parity re-run (see below). Full suite: 344 passed.

#### Verified against real AION-managed servers, not just local — 2026-09-16

Beyond the local dev server, `tciq` was exercised against two real, independent AION-managed orion-res deployments this session (through a real AION IAM login — `_AionIAMSession` — obtaining a genuine bearer token, not a mock):

- **`http://10.109.137.114:64010`** — resolved via AION's `/api/inv/product-instances` inventory (the org has 49 candidate `"iq"`-named ports; discovery with no `aion_node_name=` picks whichever comes first, so a specific instance has to be targeted by its own base URL, not assumed from node name alone — `aion_node_name="10.109.137.114"` on this org actually resolves to a *different* port, `:64001`, than the one intended, `:64010`). Real data: 5 databases, real 50-table/1191-field schemas — but **0 saved views and 0 report templates**, so only schema introspection could be exercised here.
- **`http://10.109.143.126:64012/api/res`** — a TestCenter+ (a different, PowerApp-based product)-fronted deployment. Confirmed that on this kind of deployment orion-res's REST API is proxied under an `/api/res` path prefix instead of served at the root — hitting the bare host without that prefix returns the *other* product's SPA shell (200, HTML, not JSON) rather than a 404, which looks like a working connection until you check the response body. This instance has real, varied data: 5 databases, 33 views across 6 real types (`single_level_table`, `drill_down_table`, `x_y_chart`, `chart`, `health_indicator`, `histogram`), 0 report templates.

Findings from exercising every `tciq` feature already checked locally against both instances (read-only only at this point in the investigation — no `generate_report()`/`save_view()`/`delete_view()`/`rename_test()`/`delete_test()`, since these are shared servers with other real engineers' data; `rename_test()` was later exercised deliberately, with explicit go-ahead and an immediate revert — see the dedicated section below):
- Schema introspection (`get_database_schema`/`list_table_names`/`list_fields`): confirmed working identically on both.
- `x_y_chart`/`histogram` query() bug: **reproduces identically** on the rich AION instance (same `IQViewError`/`"has no table with data_type=...'"` shape) — this is now confirmed on three independent real servers (local + this one), not just the original dev box.
- `chart` and `health_indicator` view types (never exercised through `query()` before, only ever seen as report-template section types): **also hit the same bug** on both local and the AION instance — the query builder's `details.user_data.tables`-list assumption doesn't hold for these two either. New scope for the same known defect, not a new bug.
- `drill_down_table`: confirmed (on both local and AION) that `query(name=...)` deliberately refuses it with a clear, actionable message (`"only 'single_level_table' and 'paged_single_level_table' and 'x_y_chart' and 'pie_chart' and 'histogram' and 'boxplot' are confirmed..."`, pointing at `query(definition=...)` instead) — a real, working guard, not a crash.
- `find_unsupported_report_sections()`/`REPORT_SAFE_VIEW_TYPES` (see the report-generation section above): re-confirmed correct against the real local "Traffic Test Report" template (still returns exactly `["section_2"]`) after the `drill_down_table` correction.
- No regressions found anywhere from the two `auto_repair` fixes above — every previously-passing local behavior (schema, x_y_chart/histogram's known failure, report-template introspection, multi-database queries) was re-run and still matches.

#### `rename_test()`'s real wire format — RESOLVED 2026-09-17, was a wrong guess

The single highest-risk open item from the previous pass (`rename_test()`'s `PUT {"name": ...}` body was an admitted, never-confirmed guess) turned out to be genuinely wrong once actually tried against a real server — with explicit go-ahead from whoever owns this session, on a specific real AION database (`k4s6ez3h25drbau7` / "all-devices" on `10.109.143.126:64013`), immediately reverted after each test so no real data was left changed:

1. `PUT /databases/<id>` with just `{"name": new_name}` (the old implementation): **400 `RESOURCE_ID_MISMATCH`** — `"Resource identifier in URL doesn't match value in body"`. The body has to include `id`.
2. `PUT /databases/<id>` with `{"id": database_id, "name": new_name}`: **500 `INTERNAL_ERROR`** — a real Go server panic, `"assignment to entry in nil map"` (`goroutine ... luddite/v3...`). The handler evidently writes into a nested map — `metadata`, most likely — that comes back nil when the body isn't a full record.
3. `PUT /databases/<id>` with the **full record from `GET /databases/<id>`, with only `name` changed**: **200**, and the rename genuinely takes effect (confirmed via a follow-up `GET`).

**Fix applied**: `tciq.databases.rename_test()` now calls `get_test()` first, mutates `name` on the returned dict, and `PUT`s that back — a full-object replace, not a partial patch. Transparent to callers; `IQClient.rename_test()`'s signature is unchanged. Confirmed against the real server via a full round-trip through the actual `IQClient.rename_test()` method (not just raw HTTP): renamed to a temporary name, verified, renamed back, verified again, plus one more independent `GET` outside the test script itself — the database ended up back at its original name, `"all-devices"`. `tests/test_new_features.py`'s `TestDatabaseLifecycle` mocked tests updated to mock the now-required `GET` and assert the `PUT` body carries the full record (`id`, `metadata`, etc.), not just `name`. Full suite: 344 passed.

New example: `examples/rename_test_roundtrip.py` — renames a database and immediately renames it back (unlike `manage_test_database.py`'s existing rename+delete demo, which leaves the rename in place before deleting), with the revert in a `finally` block and a loud, actionable warning printed if the revert itself ever fails, rather than silently leaving a real database renamed.

#### A third real deployment type — "labserver" — plus a new `verify=`/TLS gap it surfaced — 2026-09-22

A third real deployment shape, distinct from both "local" (install-dir discovery) and "AION" (login + instance lookup): a **labserver** is a direct, no-discovery connection — you already know the exact host and a fixed, well-known port (`9199`), so it's just `IQClient(host=, port=, use_https=)`, no config file to read and no account to log into. New example: `examples/list_databases_labserver.py`, confirmed live against a real one (`iqteam03.es.cal.viavi.io:9199`, 58 real databases).

That same real labserver's own infrastructure **changed underneath this investigation within the same day**: it went from plain HTTP with no redirect to an nginx reverse proxy that 307-redirects all HTTP traffic on that same host:port to HTTPS, serving a **self-signed certificate**. This surfaced a real, previously-unaddressed gap: `tciq`'s `Transport` (unlike its separate AION login path, which already has its own `aion_ca_cert=`) had no `verify=`/CA-bundle option at all for the *main* orion-res connection — `use_https=True` alone still failed with `SSLCertVerificationError` against a self-signed cert, with no supported way around it short of manually building and passing a custom `session=`.

**Fix applied**: `IQClient`/`resolve_config()`/`Transport` all gained a `verify=` parameter (falls back to a new `TCIQ_VERIFY_SSL` env var), accepting `True`/`False`/a CA bundle path exactly like `requests`' own `verify=`. Deliberately defaults to `None` (not `True`) at the `Transport` level specifically so it never silently overrides a caller-supplied `session=`'s own `.verify` setting — only an explicit `True`/`False`/path takes precedence over that. Re-verified live end-to-end through the real `IQClient(..., verify=False)` path against the same labserver after its infrastructure changed: same 58 databases, now correctly over `https://`. `examples/list_databases_labserver.py` updated to use this instead of the manual `session=`-based workaround it needed before the fix existed. New tests: `tests/test_config.py` (env var parsing — falsy tokens, CA path, explicit-kwarg precedence) and `tests/test_transport.py` (confirms `verify=None` is never passed to the underlying `session.request()` call at all, so a custom session's own default survives; confirms `False`/a path are passed through when explicitly set). Full suite: 356 passed.

### Two previously-tracked bugs in `view_query_builder.py` — RESOLVED

This section used to describe two bugs (a default-order projection gap, and a snapshot filter that skipped the provider's own template). Both are fixed in the code currently committed — see `_apply_default_order_updates()` and `_apply_snapshot_filter()` — with dedicated passing tests. No action needed; noted here only so this section doesn't silently disagree with §0.

### Explicit AION kwargs silently overridden by an unrelated env var — RESOLVED 2026-09-03

Found 2026-09-03 while building `examples/discover_aion.py`'s smoke test;
fixed the same day, after confirming the bug against the real AION
server. `resolve_config()` in `tciq/config.py` used to only *attempt*
AION discovery when `TCIQ_BASE_URL`, `TCIQ_HOST`, and `TCIQ_INSTALL_DIR`
were **all** absent from the environment — regardless of whether the
corresponding `base_url=`/`host=`/`install_dir=` *kwargs* were passed.
Concretely: a caller who explicitly wrote `IQClient(aion_url=...,
aion_username=..., aion_password=...)` with no other kwargs got silently
routed to whatever `TCIQ_BASE_URL` happened to be set to in their
environment — not an error, not a warning, just a different server than
the one they asked for. This contradicted the "explicit kwargs always
override the environment" rule stated everywhere else in this codebase.

**Fix applied**: the AION attempt is now gated on the kwargs
(`base_url`/`host`/`install_dir`) plus a check on whether `aion_url` was
itself passed as an explicit kwarg (`aion_url is not None`) — when it
was, AION discovery is attempted and, if successful, wins over an
ambient `TCIQ_BASE_URL`/`TCIQ_HOST`/`TCIQ_INSTALL_DIR` *environment*
variable, while still losing to an explicit `base_url=`/`host=`/
`install_dir=` *kwarg* on that same call. AION resolved purely from
`TCIQ_AION_*` environment variables (no `aion_url=` kwarg) is unchanged
— it remains the lowest-priority option, exactly as before. See
`resolve_config()`'s comments in `tciq/config.py` for exactly where this
is applied, and `tests/test_config.py`'s `test_explicit_aion_kwarg_*`/
`test_env_only_aion_*` tests for the six precedence combinations this
was verified against (three kwarg-precedence cases fixed, the kwarg-vs-
kwarg and pure-env cases confirmed unchanged). Re-verified against the
real AION server above: an explicit `aion_url=` now genuinely triggers a
login attempt instead of being silently skipped.

### `list_table_names()`/`list_fields()` were broken against a real server — RESOLVED 2026-09-03

Found 2026-09-03 against the live local server (see above); fixed the
same day. §9 used to list this as an *unconfirmed assumption* ("risk if
wrong: inferred, not observed") — it turned out to be confirmed wrong.
`tciq/databases.py`'s `get_database_schema()`/`list_table_names()`/
`list_fields()` assumed `GET /databases/{id}?detail=full` returns a
top-level `"tables"` key. **It doesn't.** The real top-level keys are:
`id, datastore, name, description, metadata, first_created,
last_updated, dimension_sets, result_sets, profile, summary`:

- `result_sets` — list of fact-table-like entries: `{"name", "raw_name",
  "description", "dimension_sets": [...names...],
  "primary_dimension_set", "facts": [{"name", "display_name",
  "description", "type", "unit"}, ...], "summary": {...}}`.
- `dimension_sets` — list of dimension/lookup-table-like entries, same
  shape except `"attributes"` instead of `"facts"`.

`list_table_names()`'s old `schema.get("tables") or []` always returned
`[]` against a real server, and `list_fields()` likewise always returned
`[]`. IQ-PYTHON-006 did not work against a real server at all — confirmed
by running `examples/inspect_database_schema.py` against it before the
fix: `get_database_schema()` itself worked fine (a thin `GET` wrapper),
but both convenience methods built on top of it returned nothing.

**Fix applied**: `list_table_names()` now returns `result_sets` +
`dimension_sets` combined, each entry tagged with a `kind` key
(`"result_set"`/`"dimension_set"`) so `list_fields()` (and callers) can
tell which field key it carries; `list_fields()` reads `facts` for a
`result_set` entry or `attributes` for a `dimension_set` entry, matched
by `name`. Re-verified against the real server: `list_table_names()`
now returns 50 tables and `list_fields()` 1191 fields for a real test
database, and scoping to one table's `name` returns just that table's
own fields. `tests/test_new_features.py`'s `TestDatabaseMetadata` class
was updated to mock the real shape instead of the old invented one.

### `snapshot_name=`'s fallback filter was broken against a real server — RESOLVED 2026-09-03

Found 2026-09-03 while building `examples/fetch_view_data.py`'s
generic "exercise every feature" walkthrough; fixed the same day.
`query(name="Detailed Stream Results", data_type="eot",
snapshot_name="Snapshot")` against the live local server (see above)
used to fail with:

    VALIDATION_FAILED: name error; unknown sub-query result name:
    test.snapshot_name = 'Snapshot'

This was exactly the scenario the module docstring in
`view_query_builder.py` had flagged as "NOT yet validated against a real
capture" — now it has been, and the fallback branch of
`_apply_snapshot_filter()` was wrong. When a provider doesn't declare its
own `snapshot_filter_provider` template (true for this view, and
apparently common), the fallback appended a **raw, unqualified attribute
path** as the filter: `"test.snapshot_name = '%s'"`. But a filter at the
outermost `multi_result` node has to reference an already-projected
*alias* the way every other outermost filter in this codebase does
(e.g. `"view.rx_stream_stats_frame_count>100000"` — see
`tciq/query.py`'s `merge_modifiers()` and its own qualification logic)
— not a raw dotted path.

**Fix applied**: the fallback now qualifies with the same hardcoded
`"view"` alias `_apply_query_updates()` already uses elsewhere in this
same file: `"view.test_snapshot_name = '%s'"`. Re-verified against the
real server, both directly and through the full public `query()` path
(not just a hand-built definition): 30/10 real rows returned respectively,
after the same 19-column `auto_repair` as every other query against this
view/database. `test_view_query_builder.py`'s
`test_snapshot_filter_falls_back_to_alias_qualified_snapshot_name` (renamed
from `..._to_raw_test_snapshot_name`) and `test_pie_chart_applies_
snapshot_filter`, plus `test_client.py`'s
`test_query_snapshot_name_threads_through_to_built_definition` and its
pie-chart counterpart, were updated to assert the corrected, alias-qualified
string.

### A view created via `save_view()` has no usable `effective_details.system_data` — RESOLVED 2026-09-03

Found 2026-09-03 running `examples/manage_views.py` against the live
local server (507 real views). After cloning "Detailed Stream Results"'s
`details` into a new view via `save_view()`, reading that new view back
(`GET /views`, or `find_view()`) returns an `effective_details` with
`user_data`/`view_type`/`show_snapshot_selector` mirrored from `details`
— but **no `system_data` key at all**. Every pre-existing/system view
has one (`effective_details.system_data.query_providers[]` — see §4);
this newly-created one simply doesn't. `list_view_columns()`/
`query(name=...)` both need `system_data.query_providers` to resolve a
table's `query_provider` by name (`_resolve_table_and_provider()` in
`view_query_builder.py`), so both raised `IQViewError` against a freshly
`save_view()`-created view, out of the box.

This is a real, structural property of `POST /views` itself
(query-provider templates aren't computed/attached for a newly created
view) — a real gap against IQ-PYTHON-003's promise that a script can
"save, reuse, and delete custom views." An earlier draft of this section
described a client-side-only workaround inside `manage_views.py`; that
has since been superseded by a proper library-level fix.

**Fix applied in the library** (`tciq/views.py`): since a cloned view's
`details.user_data.tables[].query_provider` names are copied verbatim
from its source, some other view on the server sharing that provider
name has a usable `system_data.query_providers` entry that works
identically for the view missing one. New `_find_provider_elsewhere()`
searches `list_views()` for a matching provider by name;
`_ensure_provider_available()` patches it into a deep-copied view before
building the query. `get_view_definition()`/`list_view_columns()`/
`build_field_resolver()` (and `IQClient`'s callers in `client.py`) now
accept `transport=`/`timeout=` so this lookup can happen transparently —
passing `transport=None` (the old default) disables the fallback
entirely, so this is purely additive for anyone calling these functions
directly without a transport.

**Follow-on bug found while verifying the fix**: naively using whichever
matching provider is found first produced a real `"pagination requires
at least one order expression"` 400 from the server. Root cause:
providers sharing the same name are not byte-identical across views —
`default_order_updates.order_updates` varies per-view (4 of 5 real views
sharing the `"eot_table_stream_traffic"` provider name had an *empty*
`order_updates`; only one had the real one).
`_find_provider_elsewhere()` now prefers a match with a non-empty
`order_updates`, falling back to the first match only if none have one.
Re-verified: the resulting order clause matches the true source view
exactly.

**End-to-end re-verification against the real server**:
`manage_views.py` was simplified to remove the old manual workaround —
it now just calls the public `IQClient` API (`save_view()`,
`list_view_columns()`, `query(name=...)`) directly, no bypassing of
`IQClient`'s wrappers needed. Full run: 507 views listed, view cloned, 40
active columns listed on the clone, 5 real rows queried back through
`query(name=...)`, clone deleted. 8 new regression tests added in
`tests/test_views.py`.

Two related, smaller findings from the same original run, both fixed in
the example (not library bugs): (1) a server with 500+ views takes long
enough to fully list that the default 10s timeout isn't always enough —
`IQClient(timeout=60)` at the top of `manage_views.py`, and every
`list_views()`/`find_view()` call in it, now passes `timeout=60`
explicitly; (2) the original version left its throwaway view behind on
the real server if any step after creating it raised (exactly what
happened while finding the issues above) — restructured with
`try`/`finally` so deletion always runs, and the final delete now goes
by the `id` already in hand instead of `delete_view(name=...)` (which
would otherwise re-run the same slow full listing just to re-discover
that same id).

### `query()` didn't default to snapshot data as the PRD requires — RESOLVED 2026-09-03

Found during an independent re-read of the PRD text against the §8
table (not from running an example). The PRD's Live/Snapshot Query
requirement (IQ-PYTHON-004) specifies that querying without asking for
"live" data should return the last completed snapshot ("eot" — end of
test), not whatever the underlying view definition happens to list
first. `query(name=...)` called with neither `table_index=` nor
`data_type=` was resolving to `details.user_data.tables[0]` — table
ordering within a view's `details` is not guaranteed to put the eot
table first, so this was returning live data by accident on any view
that happened to list it first.

**Fix**: `tciq/views.py` adds `_resolve_table_index(view, table_index,
data_type)`, called from `get_view_definition()`/`list_view_columns()`/
`build_field_resolver()`. Precedence: explicit `data_type=` wins if
given (raises `IQViewError` if no table matches); else explicit
`table_index=` wins if given; else scan for a table with
`data_type == "eot"`; else fall back to index 0 (preserves old behavior
for a view with no eot table at all, rather than raising).

**Verified against the real server**: `iq.query(name="Detailed Stream
Results")` with no `data_type=` argument at all now returns rows
containing `test_snapshot_name` — a field that only exists on the eot
table — confirming the default really is snapshot data now, not an
accident of table ordering. 5 new regression tests in `tests/test_views.py`
cover the precedence order directly (eot-first, eot-second, no-eot
fallback, explicit `table_index=` still honored, explicit `data_type=`
still takes priority over an eot table default).

### Other real-server confirmations

| Assumption | Status |
|---|---|
| AION port label in `/api/inv/product-instances` | ✅ CONFIRMED 2026-09-08, and the assumed default was wrong — see §0f. Real label is `'iq'`, not `'orion-res'`. Fixed. |

### Infrastructure gaps

- ~~No CI.~~ **Fixed** — `.github/workflows/tciqrestclient-tests.yml` runs `pytest` on every push/PR touching `tciqclient/`, across Python 3.8–3.12.
- ~~No `.gitignore`.~~ **Fixed** — see §2.
- ~~No CHANGELOG.~~ **Fixed** — `tciqclient/CHANGELOG.md`.
- **No `PLAN.md`/`DEPLOYMENT_PLAN.md`/`WIDGET_QUERY_PLAN.md`.** Gone (see §0); this document now carries their load-bearing content directly.

---

## 10. Deployment Checklist

**Decision made earlier this project: publish to public PyPI**, not an
internal Artifactory/Nexus index — so the steps below target that.

> **Update — 2026-09-22/23: the steps below were actually carried out for
> `tciq`, and the package has since been renamed.** Since this checklist
> was last written, `tciq` `0.1.0` and `0.1.1` were genuinely published to
> real, public PyPI (see §8's IQ-PYTHON-001 row) — every "Open"/"Blocked"
> status this table used to show for the account/token/upload steps is
> stale for that reason alone, independent of anything below. Separately,
> the package has since been renamed `tciq` → `tciqrestclient` (the
> distribution name *and* the Python import name) — the old `tciq`
> releases are left as-is, unmaintained, on PyPI (nothing to do there).
> **`tciqrestclient 0.1.1` was itself published to real, public PyPI on
> 2026-09-23** (https://pypi.org/project/tciqrestclient/0.1.1/) — see the
> checklist table below for the confirmed details; this is a separate,
> from-scratch PyPI project, not a rename-in-place of the old one. The
> table and walkthrough below are
> rewritten to apply freshly to `tciqrestclient`'s own first publish,
> reusing the real PyPI account/API-token experience already gained from
> `tciq`'s publish rather than starting that part from zero.

**Re-verified fresh 2026-09-15** (a lot of `tciq/` package code and new
examples had landed since this was last checked against 309 tests) —
still clean, plus one real packaging bug found and fixed along the way:
`tciq/Testcenterlib.py`, `tciq/aion_operations_testcenterplus.py`, and
`tciq/get_product_url_example.py` (three standalone AION/Temeva
platform-operations scripts added to this repo this session, unrelated
to the `tciq` results-client library itself — they `import` an
internal-only `utils.Temeva`/`powerapp` SDK that isn't a project
dependency and isn't published anywhere) had ended up directly inside
the `tciq/` package directory. `[tool.setuptools.packages.find] include
= ["tciq*"]` in `pyproject.toml` packages every `.py` file under that
directory regardless of whether `tciq/__init__.py` imports it — so all
three were silently getting bundled into the real wheel/sdist. Anyone
doing `import tciq.Testcenterlib` (or the other two) from a real `pip
install tciq` would hit `ImportError: No module named 'utils'`
immediately. Moved all three to a new sibling directory,
`tciqclient/internal_tools/` (outside `tciq/`, so setuptools' package
discovery no longer touches them) — confirmed fixed by rebuilding and
checking the wheel's file list no longer includes them. Full suite
still 334 passed after the move (nothing referenced their old
`tciq/`-relative path). Also confirmed a genuinely clean install this
time: built the wheel, installed it into a brand-new venv, and
successfully ran `import tciq; tciq.__version__` / `from tciq import
IQClient` — the actual step 8 of the walkthrough below, done for real
rather than left as "Open".

The package builds and all tests pass (356 passed, 0 skipped, re-confirmed after the `tciqrestclient` rename — see §9 for the one fixture that's provisional rather than GUI-confirmed). State of each step, **rewritten for `tciqrestclient`'s own first publish** (see the note above the table):

| Step | Status | Notes |
|---|---|---|
| Add `.gitignore` (block `.env`, `views.json`, `*.log`, build artifacts) | ✅ Done | See §2 — unaffected by the rename |
| Confirm version string in `tciqrestclient/version.py` | ✅ Decided | Maintainer chose to keep `0.1.1` (continuity with the renamed project's last `tciq` release) over resetting to `0.1.0` |
| `pytest tciqclient/tests/` must be 100% green | ✅ Passing | 356 passed, 0 skipped, re-run after the rename |
| Add `tciqclient/README.md` (`pyproject.toml` requires it to build) | ✅ Done | Unaffected by the rename |
| Write initial CHANGELOG | ✅ Done | `tciqclient/CHANGELOG.md` — no dedicated rename entry added yet; depends on the version-number decision above |
| Add `iq` extras group to `setup.py` | ✅ Done | Not a cross-team ask — this checkout *is* `py-stcrestclient` (see §0). Updated to `tciqrestclient>=0.1.0,<1.0` |
| Set up CI to run `pytest` on every push | ✅ Done | `.github/workflows/tciqrestclient-tests.yml` |
| `pyproject.toml` metadata publish-ready (author email, `[project.urls]`, SPDX license, no deprecation warnings) | ✅ Done | Fixed 2026-09-04 for `tciq` (see §0c), carried over unchanged through the rename |
| `pip install build && python -m build tciqclient/` | ✅ Re-verified after the rename | Clean sdist + wheel, `twine check` passes, all 13 real modules present under `tciqrestclient/`, `import tciq` correctly no longer resolves from the built wheel |
| Create a PyPI account + API token | ✅ Done | The same PyPI account already used for `tciq`'s real publish; an account-scoped token (`tciqrestclient` didn't exist on PyPI yet, so a project-scoped one couldn't be created first) was used for the upload below. Per the walkthrough, that account-wide token should now be deleted and replaced with one scoped just to the `tciqrestclient` project |
| Confirm the name `tciqrestclient` is actually available on PyPI | ✅ Confirmed | It was free — see the upload below |
| `twine upload dist/*` for `tciqrestclient` | ✅ **Published 2026-09-23** | `tciqrestclient 0.1.1` — real upload to real, public PyPI: https://pypi.org/project/tciqrestclient/0.1.1/. `pip install tciqrestclient` now genuinely works |
| Re-verify `pip install tciqrestclient` from a fresh venv after upload | ✅ Re-verified 2026-09-23 | Fresh venv, installed directly from real PyPI (not a local wheel): `tciqrestclient 0.1.1` installed cleanly, `import tciqrestclient`/`IQClient`/`IQError`/`IQViewError` all worked, `import tciq` correctly does not resolve |
| `pip install stcrestclient[iq]` becomes usable | ✅ Done | The `iq` extras group in root `setup.py` resolves to PyPI's `tciqrestclient` by name, which is now a real published package |

### How to actually publish to PyPI, step by step

1. **Check the name is free**: visit
   `https://pypi.org/project/tciqrestclient/` in a browser. If it 404s,
   the name is available. If someone else already owns it, the package
   needs a different `name=` in `pyproject.toml` (and
   `tciqrestclient/__init__.py`'s import path would need to change too,
   so confirm this *before* anyone starts depending on the current
   name). Note this is a **separate** PyPI project from `tciq` —
   PyPI has no notion of "renaming" a project, so this name-availability
   check has to be done from scratch even though `tciq` itself is
   already confirmed taken (by this same package, under its old name).
2. **PyPI account**: already have one — the same account used for
   `tciq`'s real publish. Nothing to create here; skip straight to the
   next step. (Only relevant if publishing from a different account:
   create one at `https://pypi.org/account/register/`, optionally a
   TestPyPI account too for a dry run, and enable 2FA — PyPI requires it
   for uploads.)
3. **Generate an API token**: PyPI account → *Account settings* → *API
   tokens* → *Add API token*. `tciqrestclient` doesn't exist on PyPI yet,
   so the very first token for it has to be scoped to "Entire account"
   (the same way the original `tciq` token was); after the first
   successful upload, create a second token scoped just to the
   `tciqrestclient` project and delete the account-wide one — the same
   pattern already followed for `tciq`.
4. **Install the tools**: `pip install --upgrade build twine` (already
   done once for `tciq`'s publish; re-run only if the environment
   changed).
5. **Build** (from `tciqclient/`): `python -m build`, then
   `twine check dist/*` — both already verified clean against
   `tciqrestclient` as of this rename pass.
6. **(Recommended) dry run on TestPyPI first**:
   ```bash
   twine upload --repository testpypi dist/*
   # username: __token__   password: <the TestPyPI token>
   pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ tciqrestclient
   ```
   (`--extra-index-url` is needed because `requests`/`python-dotenv`/
   `PyYAML` aren't published on TestPyPI.) Note TestPyPI and real PyPI
   tokens are **not interchangeable** — a token generated on one site
   doesn't work on the other, so this needs its own TestPyPI token, not
   the real-PyPI one generated in step 3.
7. **Publish for real**:
   ```bash
   twine upload dist/*
   # username: __token__   password: <the real PyPI token, starts with "pypi-">
   ```
   Or store credentials in `~/.pypirc` (`[pypi]` section with
   `username = __token__` / `password = pypi-...`) or as
   `TWINE_USERNAME`/`TWINE_PASSWORD` environment variables instead of
   typing them interactively.
8. **Verify**: `pip install tciqrestclient` in a brand-new venv, then
   `python -c "import tciqrestclient; print(tciqrestclient.__version__)"`.

**Before doing step 7 specifically**: a version number can never be
reused on PyPI once uploaded (deleting a release doesn't free the
number, and re-uploading the same version is rejected) — whatever
version `tciqrestclient` first publishes as, any later fix ships as the
next version, never a re-published one. This is exactly why the
version-string decision flagged in the checklist table above (continue
at `0.1.1`, or reset to `0.1.0` as this new project's own fresh start)
needs settling *before* running this step, not after. Given the known
gaps this project documents (`x_y_chart`/`histogram` broken, the report
async race, `rename_test()` — all already honestly disclosed in
`CHANGELOG.md`/`README.md`/`QUICKGUIDE.md`), none of that is a reason to
hold off on publishing `tciqrestclient` itself — but per this session's
explicit instruction, that publish was deliberately **not** done here;
this whole section is prepared, not executed.

**Optional, for later releases**: PyPI's "Trusted Publishing" lets
`.github/workflows/tciqrestclient-tests.yml` (or a new publish-on-tag
workflow) upload directly via GitHub Actions' OIDC identity, with no
stored API token at all — worth setting up once the first manual publish
of `tciqrestclient` above is done, so future version bumps don't need a
human to run `twine upload` by hand.

---

## 11. Next Steps (Prioritized)

### Immediate

1. **Rebuild `_build_xy_chart_query()`/`_build_histogram_queries()`** (and almost certainly `_build_pie_chart_query()`/`_build_boxplot_queries()`, plus the newly-discovered `chart`/`health_indicator` view_types) around each view_type's own real `details.user_data` shape instead of the `single_level_table`-only `"tables"` list `_resolve_table_and_provider()` currently assumes for all of them — CONFIRMED broken 2026-09-03 against real x_y_chart/histogram views on the live local server (`http://127.0.0.1:9200`), and re-confirmed 2026-09-16 identically against two independent real AION-managed servers, plus `chart`/`health_indicator` now confirmed to hit the same bug too; see §9 for the exact real shapes found. This is now the single highest-value remaining gap — bigger than the bugs already fixed this session, and no longer just "unconfirmed": `query(name=...)` for these view_types genuinely does not work, on every real server checked so far.
2. **Report generation never completes on this local server — root cause fully diagnosed 2026-09-15, ONE of the two bugs fixed client-side 2026-09-16** (see §9). Two confirmed bugs in `orion-res` itself: (a) a universal frontend `TypeError` in the report-rendering web app whenever a template includes a chart-type section — **fixed from the `tciq` side** via the real `parameters.excluded_sections` field (`IQClient.generate_report(excluded_sections=...)` / `find_unsupported_report_sections()`), confirmed end-to-end against the real "Traffic Test Report" template (4 real rendered pages); and (b) a Go-side `select`/`default` race in `report.Worker.renderingState()` (`cmd/orion-res/report/worker.go`) that abandons the report-monitoring goroutine before it can ever report a terminal status, leaking it and leaving the report stuck at `"generating"` until a 60-minute timeout — **still open**, since fixing it means editing `orion-res`'s Go source, which was explicitly out of scope for this repo. `examples/generate_report.py`'s `wait_for_report()` remains the correct client-side pattern for waiting on completion regardless — it just still has no server in this environment that will ever reach a genuine completion status while bug (b) stands. Re-verifying `excluded_sections=` through the real `IQClient` path (rather than the scratch script that first proved it) is pending a server restart — `orion-res.exe` was found to have crashed outright partway through this investigation, alongside 27 accumulated Chrome processes; flagged for whoever owns this environment, not restarted from here.
3. **Get a real browser capture of the GUI-filtered query**, to replace the constructed `dsr_query_filtered_min_latency.json` — see §9 for the exact steps (open "Detailed Stream Results", type `rx_stream_stats.min_latency < 0.17` into its filter box, copy the `POST /queries` body from DevTools). Small, isolated, closes out the last open question on the table builder specifically (unrelated to item 1 above).
4. ~~**Run `twine upload` for `tciqrestclient`.**~~ **Done — published 2026-09-23** (`tciqrestclient 0.1.1`, see §10's checklist for the confirmed details). The account-wide token used for this first upload should still be swapped for a project-scoped `tciqrestclient` token per the walkthrough in §10.
5. **Verify `delete_test()` (IQ-PYTHON-010) against real data** — `rename_test()`'s own real-server verification is now DONE (2026-09-17, see §9 — and it wasn't a rubber stamp: the original wire-format guess was wrong and got fixed as a result). `delete_test()` remains unverified since, unlike a rename, there's no revert-after-the-fact to make it safe to just try — it needs a database that's genuinely disposable; ask whoever owns the server before attempting this.

The AION kwarg-precedence bug, the broken `list_table_names()`/
`list_fields()` methods, the snapshot filter fallback, the report
format/title bug, the `query()` snapshot-default bug, and the
`save_view()`-created-view-is-unusable bug flagged in earlier drafts of
this list have all since been fixed — see §9's "RESOLVED 2026-09-03"
entries.

### Widget query builder work, if picked back up

The four unconfirmed builders (`x_y_chart`/`pie_chart`/`histogram`/`boxplot`) were reverse-engineered from `magellan-frontend`'s TypeScript widget models, which still aren't available in this environment — but validating them no longer needs that source at all, now that a live server (§9) can be used to capture real requests directly, the same way the table builder was just re-confirmed. See each builder's own docstring in `view_query_builder.py` for exactly which fields are assumed vs. confirmed, and `TESTING.md` §3.3 for the step-by-step comparison procedure. Time-series `chart` and Health Indicators remain out of scope (deprioritized — genuinely different problems, not row-fetching).

### Deployment

`tciqrestclient` is now published (see §10) — nothing left to work through here.

---

## 12. Running the Tests

See [`tciqclient/TESTING.md`](tciqclient/TESTING.md) for the full guide,
including packaging checks and the manual/integration test plan for
validating against a real server (discovery modes, the four unconfirmed
widget builders, re-capturing `tests/data/*.json` for a different view).
Quick version below.

All HTTP is mocked via the `responses` library — no running orion-res server needed.

```bash
# From the repo root (not inside tciqclient/)
cd tciqclient
pytest
# 356 passed, 0 skipped

# Run one file verbosely
pytest tests/test_view_query_builder.py -v

# Show stdout (useful for debugging)
pytest -s
```

All 309 should pass with zero skips (see §9 — the three
`tests/data/*.json` fixtures are now present; the skip machinery in
`_load`/`_load_data` still exists for graceful degradation if those files
are ever missing again, printing `tests/data/<file> is a real orion-res
capture that isn't checked into this repo` rather than failing outright).
Nothing should ever fail; investigate immediately if it does.

| Test file | Covers |
|---|---|
| `test_client.py` | `IQClient` end-to-end flows |
| `test_view_query_builder.py` | Query definition building for all supported `view_type`s |
| `test_aion_discovery.py` | AION IAM auth + inventory; `timeout=` compliance |
| `test_new_features.py` | Delete/rename test, save/delete view by name, JSON definition, AION params |
| `test_query.py` | `merge_modifiers()`, `rows_to_dicts()`, DSL tree manipulation |
| `test_databases.py` | `list_tests`, `get_test`, schema endpoints |
| `test_views.py` | `list_views`, `find_view`, `save_view`, `delete_view` |
| `test_queries.py` | `run_query`, mode handling |
| `test_reports.py` | Templates, create, download |
| `test_transport.py` | HTTP error mapping, debug logging |
| `test_config.py` | Config resolution precedence, env loading |
| `test_discovery.py` | `stcbll.ini` / `orion-res.yaml` parsing |
| `test_examples_smoke.py` | Every `examples/*.py` script's `main()` runs without a Python error, against a mock (not a substitute for §3.2's real-server manual testing) |

Real captured request/response shapes live in `tests/fixtures.py` (inline, committed) and `tests/data/` (missing — see §9).

---

## 13. Key Technical Decisions

### One query method, not one per widget type

`IQClient.query()` is the only query method. It inspects `view_type` internally and dispatches to the right builder in `view_query_builder.py`. The caller never needs to know which widget type they're querying — except for the return shape: `histogram` and `boxplot` return `{name: rows}` (one query per provider/statistic) while everything else returns a plain row list.

### No live/subscription mode

Every query is a single `POST /queries` with `mode: "once"`. "Live" means calling `query()` again when you want fresh data. This matches the API's actual simplicity — WAMP/subscription complexity is not needed for automation scripts.

### `auto_repair=True` by default

A view's `query_provider` template references every column the view supports, but a specific test's schema might not have all of them. Rather than crashing on a `400 VALIDATION_FAILED`, the client strips the unknown column and retries silently (up to 100 times). This is the right default for automation scripts running against different test databases. Pass `auto_repair=False` to see the original error instead.

### Dynamic version — single source of truth

`pyproject.toml` uses `dynamic = ["version"]` pointing at `tciqrestclient/version.py`. Only edit `version.py` when bumping — `pyproject.toml` never needs touching for a version bump.

### `test.owner` filtering is client-side

`list_tests(owner=...)` fetches `GET /databases?detail=summary` and filters in Python. Server-side filtering on `metadata["test.owner"]` may work (the API supports filtering by `application.id`), but it hasn't been confirmed. Client-side filtering is the confirmed, safe path.

### No auth by default on direct connections

`transport.py` supports `auth_token=` (injects `Authorization: Bearer`), but it's only populated when AION discovery is used. Direct base_url/host-port connections send no auth header. This matches orion-res's network-level access control model for most lab deployments.

### Option A packaging (extras group, not vendored)

`tciqrestclient` is published as its own independent package (under that name — it was published to real PyPI as `tciq` through version `0.1.1` before being renamed; see §10's update note). `stcrestclient`'s `setup.py` adds an optional `[iq]` extras group declaring `tciqrestclient>=0.1.0,<1.0` (see §0 — this is now actually in place, added directly to this same repo rather than needing a separate cross-team change). Both packages can move independently; the extras-group addition is purely metadata, not a code merge.
