# Testing tciqrestclient

This is the practical, step-by-step guide to testing this package — both
the automated suite (no server needed) and the manual/integration checks
that do need a real `orion-res`/AION deployment. See `HANDOVER.md` at the
repo root for architecture and known-gaps context; this file is just the
"how do I actually run things" reference.

There are two tiers:

1. **Automated unit tests** (`pytest`) — all HTTP is mocked, no server
   needed, runs in under a second, safe to run constantly. Covers every
   module's logic in isolation.
2. **Manual / integration testing** — needs a real `orion-res` server (or
   AION deployment) to talk to. Covers things a mock can't: whether the
   client's assumptions about the real API's shape still hold, and the
   four widget query builders that were never confirmed against a real
   capture in the first place (see `HANDOVER.md` §9).

Do (1) after every change, always. Do (2) before a release, and any time
you touch `view_query_builder.py`, `discovery.py`, `aion_discovery.py`,
or anything under `transport.py`/`client.py` that talks to the wire.

---

## 1. Automated Unit Tests

### 1.1 Setup

```bash
cd tciqclient
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[test]"
```

### 1.2 Run everything

```bash
pytest
```

Expected result: **309 passed, 0 skipped**, zero failed, zero errors.

`tests/data/*.json` (real captured request/response fixtures) used to be
missing from this checkout, which meant 33 tests skipped instead of
running at all — that's resolved as of 2026-09-03 (see `HANDOVER.md` §9
for the full story, including the one fixture that's a constructed
placeholder rather than an independently GUI-confirmed capture). The
skip machinery in `_load`/`_load_data` (in `test_client.py`,
`test_views.py`, `test_view_query_builder.py`) is left in place for
graceful degradation if those files ever go missing again — each prints
a skip reason pointing back to `HANDOVER.md` §9 with the exact steps to
re-capture them. **Any result other than "309 passed, 0 skipped" (a new
failure, a new error, a new skip) is a regression — investigate before
moving on.**

### 1.3 Useful variations

```bash
# One file, verbose (see every test name and its result)
pytest tests/test_view_query_builder.py -v

# One test by name
pytest tests/test_client.py::test_query_by_view_name_builds_and_runs_real_query -v

# Show print()/stdout instead of capturing it (handy when debugging a test)
pytest -s

# Stop at the first failure instead of collecting all of them
pytest -x

# Show why each skipped test was skipped
pytest -rs

# Re-run only what failed last time
pytest --lf
```

### 1.4 What each file covers

| Test file | Covers |
|---|---|
| `test_client.py` | `IQClient` end-to-end flows |
| `test_view_query_builder.py` | Query definition building for all supported `view_type`s |
| `test_aion_discovery.py` | AION IAM auth + inventory; `timeout=` compliance |
| `test_new_features.py` | Delete/rename test, save/delete view by name, JSON definition, AION params, database schema/table/field metadata (`TestDatabaseMetadata`) |
| `test_query.py` | `merge_modifiers()`, `rows_to_dicts()`, DSL tree manipulation |
| `test_databases.py` | `list_tests`, `get_test` (schema/table/field endpoint tests live in `test_new_features.py`, not here) |
| `test_views.py` | `list_views`, `find_view`, `save_view`, `delete_view` |
| `test_queries.py` | `run_query`, mode handling |
| `test_reports.py` | Templates, create, download |
| `test_transport.py` | HTTP error mapping, debug logging |
| `test_config.py` | Config resolution precedence, env loading |
| `test_discovery.py` | `stcbll.ini` / `orion-res.yaml` parsing |
| `test_examples_smoke.py` | Every `examples/*.py` script's `main()` actually runs against a mock without a Python error (see §3.2 for what this does and doesn't prove) |

If you add a new module or a new public method, add its test file/cases
here too, and to this table. **The same goes for a new example script**
— add it to `test_examples_smoke.py`'s parametrize list too (with
whatever extra mock routes it needs), so a future API change that breaks
it gets caught by `pytest` instead of silently bit-rotting until someone
manually runs it.

### 1.5 If you add or change a test fixture

`tests/fixtures.py` holds small, trimmed, real captured shapes as inline
Python constants (`DATABASES_RESPONSE`, `QUERY_DEFINITION`,
`QUERY_RESPONSE`, `VIEW`) — import from there rather than re-typing a
response shape inline in a new test. Never commit a full untrimmed real
capture (see §3.4) — trim it to only the fields the code under test
actually reads, the way the existing fixtures do, and say so in a comment
if you do.

---

## 2. Static / Packaging Checks

Run these before a release, or after touching `pyproject.toml`,
`version.py`, or moving files around.

### 2.1 Byte-compile everything (catches syntax errors fast)

```bash
python -m py_compile tciqrestclient/*.py examples/*.py tests/*.py
```

### 2.2 Build the package

```bash
pip install build
python -m build .
```

Expect a clean `tciqrestclient-<version>.tar.gz` and `tciqrestclient-<version>-py3-none-any.whl`
in `dist/`. This exercises `pyproject.toml`'s metadata (including that
`README.md` actually exists — it's referenced by `readme = "README.md"`
and the build fails outright if it's missing) and the dynamic version
pulled from `tciqrestclient/version.py`.

```bash
# Sanity-check the wheel installs and imports cleanly in a fresh venv
python -m venv /tmp/tciqrestclient-install-check
/tmp/tciqrestclient-install-check/bin/pip install dist/tciqrestclient-*.whl
/tmp/tciqrestclient-install-check/bin/python -c "import tciqrestclient; print(tciqrestclient.__version__)"
```

Clean up `dist/`, `build/`, and `*.egg-info/` afterwards (or just leave
them — all three are gitignored).

### 2.3 What CI runs

`.github/workflows/tciqrestclient-tests.yml` runs `pip install -e ".[test]"` then
`pytest`, on every push/PR touching `tciqclient/`, across Python
3.8–3.12. To reproduce a CI failure locally, match its Python version
(`python3.8 -m venv .venv`, etc.) — a version-specific failure is the
most common way CI and a local run disagree.

---

## 3. Manual / Integration Testing (needs a real server)

Nothing in this section runs in CI — it needs a real `orion-res`
(standalone TestCenter or AION) deployment. Work through it before a
release, or after changing anything in `discovery.py`,
`aion_discovery.py`, `transport.py`, `client.py`, or
`view_query_builder.py`.

Set `TCIQ_DEBUG=1` (or pass `debug=True` to `IQClient()`) for all of this
— it prints every request's method/URL/JSON body before sending, which is
what you'll compare against a browser DevTools capture when something
doesn't match.

### 3.1 Discovery modes

Test whichever modes are relevant to your deployment. `examples/
discover_local.py` covers A-D (standalone/on-prem TestCenter);
`examples/discover_aion.py` covers E (AION platform) — see
`HANDOVER.md` §5 for the corrected precedence order between them (it
used to be documented wrong, and a related real bug it surfaced — an
explicit `aion_url=` kwarg losing to an ambient `TCIQ_BASE_URL`/
`TCIQ_HOST`/`TCIQ_INSTALL_DIR` env var — has since been fixed; see
`HANDOVER.md` §9 and `test_config.py`'s `test_explicit_aion_kwarg_*`
tests for the regression coverage). Still worth unsetting those three
env vars while testing mode E if you want to isolate it cleanly from
whatever else your shell/`.env` happens to have configured.

| Mode | `.env` to set | How to verify |
|---|---|---|
| A — Explicit base URL | `TCIQ_BASE_URL=http://<host>:<port>` | `IQClient().base_url` matches; `list_tests()` succeeds |
| B — Explicit host/port | `TCIQ_HOST=<host>` + `TCIQ_PORT=<port>` | Same as A |
| C — Local STC install | `TCIQ_INSTALL_DIR=<dir>` (with a local `orion-res/etc/orion-res.yaml` under it) | `IQClient().base_url` matches `service.addr` in that file |
| D — Remote STC | `TCIQ_INSTALL_DIR=<dir>` (with `stcbll.ini`'s `[enhancedResults]` section) | `IQClient().base_url` matches `orionResServicePublicUrl` (or `orionResServiceUrl` if the public one isn't set) |
| E — AION platform | `TCIQ_AION_URL` + `TCIQ_AION_USERNAME` + `TCIQ_AION_PASSWORD` | `IQClient()` succeeds without throwing `IQConnectionError`; `IQClient()._transport` has a non-`None` auth token (bearer token shows up in `TCIQ_DEBUG` output on the first request) |

For mode E specifically, also check:
- `TCIQ_AION_NODE_NAME` actually restricts which node's instance is picked, if you have more than one.
- `TCIQ_AION_PORT_NAME` (default `iq` — confirmed against a real AION org 2026-09-08; see `HANDOVER.md` §0f) — if your AION deployment labels the port differently, override it and confirm discovery still finds the right instance.
- A deliberately wrong password raises `IQConnectionError` (not a silent fallback to a stale/cached address).

### 3.2 Run every example end-to-end

`test_examples_smoke.py` (part of the automated suite, §1) already proves
13 of the 18 examples' `main()` runs without a Python-level bug, against a
mocked server, with real assertions (not just "didn't raise") on the two
that are easiest to silently regress: `manage_views.py` (the created view
really is found, reused, and deleted -- not just that `save_view()` was
called) and `generate_report.py`. That's a permanent, automated check
that needs nothing from you for those 13. The remaining 5
(`list_tests_by_owner.py` and the four chart/widget examples) are not
yet in that suite -- see §1.4's note on adding new examples to it. What
no amount of mocking can prove, for any of them, is that an example
still behaves correctly against a *real* server (real response shapes,
real column names, the four unconfirmed widget builders) -- that's what
this section is for, and it does need one:

```bash
python examples/discover_local.py
python examples/discover_aion.py         # see the env-var caveat in 3.1 above
python examples/list_tests_by_owner.py
python examples/inspect_database_schema.py
python examples/manage_views.py          # self-cleaning -- creates + deletes its own throwaway view
python examples/run_view_query.py
python examples/fetch_view_data.py
python examples/run_live_query.py        # needs a currently-running test
python examples/query_modifiers.py
python examples/run_json_definition_query.py
python examples/multi_database_query.py  # most useful with 2+ tests for the same owner
python examples/run_xy_chart_query.py    # see 3.3 -- unconfirmed builder
python examples/run_pie_chart_query.py   # see 3.3 -- unconfirmed builder
python examples/run_histogram_query.py   # see 3.3 -- unconfirmed builder
python examples/run_boxplot_query.py     # see 3.3 -- unconfirmed builder
python examples/auto_repair_demo.py
python examples/generate_report.py
```

Most of these hardcode `"she83111"` as the example owner (updated
2026-09-03 from a placeholder that didn't exist on the local server used
to validate all of this — see `HANDOVER.md` §9) — edit that line to a
real owner on your own server, or you'll just get an empty list.

**`manage_test_database.py` is not in the list above on purpose.** It
demonstrates `rename_test()`/`delete_test()` — real, irreversible
operations. It refuses to run at all until you edit `TARGET_DATABASE_ID`
in the script to a disposable test database's id, and then requires
typing a literal confirmation phrase before either operation actually
fires. Only run it against a database you created specifically to throw
away — see the module docstring for the full warning.

For each one, confirm: it runs without raising, the printed output looks
like real data (not an empty list/dict unless that's genuinely correct),
and nothing in stderr looks like a swallowed exception.

### 3.3 Validate the four unconfirmed widget query builders

`x_y_chart`, `pie_chart`, `histogram`, and `boxplot` were reverse-engineered
from `magellan-frontend`'s TypeScript, not confirmed against a real
capture (`single_level_table`/`paged_single_level_table` are the only
ones that were — see `HANDOVER.md` §9). This is the most important manual
test if you have server access, because it's the biggest real gap in this
package's test coverage.

For each of the four view types:

1. Open a view of that type in the TestCenter IQ GUI.
2. Open the browser's DevTools → Network tab, and trigger the query (load
   the widget / apply a filter / change the snapshot selector).
3. Find the `POST /queries` (or proxied `/api/res/queries`) request; copy
   its JSON body.
4. Run the matching `examples/run_<type>_query.py` against the same view
   with `TCIQ_DEBUG=1`, and compare the request body it prints against
   what the browser sent.
5. If they differ, that's a real bug in `view_query_builder.py`'s builder
   for that type (`_build_xy_chart_query`, `_build_pie_chart_query`,
   `_build_histogram_queries`, or `_build_boxplot_queries`) — fix the
   builder, not the comparison. Each builder's own docstring lists exactly
   which fields are ASSUMED vs. confirmed, which is usually where the
   divergence will be.
6. If they match, save the pair (the view export + the request body) as
   new fixtures the same way `tests/data/` documents for table views (see
   §3.4) and add a `test_matches_real_*_capture`-style test for that
   view_type in `test_view_query_builder.py`, following the pattern
   already there for `single_level_table`.

### 3.4 Re-capturing table-view fixtures (already done for "Detailed Stream Results" — this is for a different view, or redoing it)

`tests/data/view_detailed_stream_results.json` and
`dsr_query_unfiltered.json` were recovered from a real server on
2026-09-03 (see `HANDOVER.md` §9) — no longer missing. One file,
`dsr_query_filtered_min_latency.json`, is currently a **constructed
placeholder**, not an independent GUI capture — replacing it with a real
one (step 3 below) is still open and is the single highest-value thing
left to do here. Use this section either for that, or to add fixtures
for a different `single_level_table` view later.

If you have access to a real server with a "Detailed Stream Results"
view (or an equivalent `single_level_table` view with a "live"/"eot"
split):

1. `GET /views` (or the single view by id) → save the view object as
   `view_detailed_stream_results.json`.
2. Run the same view's `eot`-table query with no filter, `limit: 120` →
   save the request body, wrapped as `{"definition": <body>}`, to
   `dsr_query_unfiltered.json`.
3. Add a `rx_stream_stats.min_latency < 0.17`-equivalent filter (or
   whatever your view's own low-cardinality numeric column supports)
   typed into the GUI's own filter box, re-run, and save the same way to
   `dsr_query_filtered_min_latency.json`. **This is the one step not yet
   done for real** — the current file was built by applying the
   push-down transform `test_matches_real_filtered_capture_gui_pushdown_
   shape` itself describes, not by actually capturing the GUI's network
   traffic (no browser was available in this environment). If what you
   capture here differs from what's currently checked in, the real
   capture wins — replace the file and update
   `test_view_query_builder.py`'s module docstring accordingly.
4. Drop all three into `tciqclient/tests/data/`, `pytest` again — should
   still be 309 passed, 0 skipped, since the algorithm was already
   validated against this exact shape. If anything fails instead, that's
   a real regression — fix the code, not the fixture.

**Never commit `views.json`, `.env`, or any `*.log` file** while doing
this — `.gitignore` blocks those specifically, but a full, untrimmed
capture saved under a different name would not be. `tests/data/*.json`
files are the one exception meant to be committed (once you have real
ones) — everything else captured from a live server for exploration
should stay local.

### 3.5 auto_repair

Deliberately exercise the retry loop against a database whose schema is
missing a column the view's `query_provider` template references (a
single-stack test's database querying a view with dual-IP/VLAN columns is
a reliable way to trigger this — see `HANDOVER.md` §4):

```python
rows = iq.query(name="Detailed Stream Results", data_type="eot", auto_repair=True)
print(iq.last_dropped_columns)   # should list the stripped column(s)
```

Then re-run with `auto_repair=False` against the same database/view and
confirm it raises `IQRequestError` with the original `VALIDATION_FAILED`
body instead of silently retrying.

### 3.6 Database lifecycle — be careful

`delete_test()` and `rename_test()` are real, irreversible operations
against the server. Test them only against a disposable test database you
created for this purpose — never against real data. Confirm:
- `rename_test()` changes the name visible via `get_test()`/the GUI.
- `delete_test()` actually removes the database (a subsequent
  `get_test()` for that id fails).

### 3.7 Reports

```python
templates = iq.list_report_templates()
iq.generate_report(
    templates[0]["id"], title="My Report", output_path="report.pdf")
```

Confirm the downloaded file is non-empty and actually opens as a valid
PDF/HTML/CSV (whichever `format=` you asked for).

---

## 4. Pre-Release Checklist

Run through this before bumping `tciqrestclient/version.py` and publishing:

- [ ] §1.2 — `pytest` is 309 passed / 0 skipped
- [ ] §3.4 — `dsr_query_filtered_min_latency.json` is a real GUI capture, not the constructed placeholder (see `HANDOVER.md` §9)
- [ ] §2.1 — `py_compile` clean
- [ ] §2.2 — `python -m build` produces a clean sdist + wheel, and the
      wheel installs and imports in a fresh venv
- [ ] §3.1 — the discovery mode(s) you actually support in production
      still resolve correctly
- [ ] §3.2 — every example script still runs end-to-end
- [ ] Version bumped in `tciqrestclient/version.py` only (never `pyproject.toml`)
- [ ] `tciqclient/CHANGELOG.md` has an entry for the new version
