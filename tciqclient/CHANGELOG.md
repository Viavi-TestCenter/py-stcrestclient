# Changelog

## 0.1.3

- Added `IQClient.list_profiles(view_id=None, detail=None, timeout=None)`
  — result profiles (`GET /profiles`), a saved collection of views plus
  their dashboard layout (the GUI's results "template"). CONFIRMED
  against a real server (112 real profiles), including the `view_id=`
  and `detail=` query-param filters. See `tciqrestclient/profiles.py`'s
  module docstring and `API_REFERENCE.md`.
- `TCIQ_AION_URL`/`TCIQ_AION_USERNAME`/`TCIQ_AION_PASSWORD` now fall back
  to the bare `AION_URL`/`AION_USERNAME`/`AION_PASSWORD` env vars (no
  `TCIQ_` prefix — `stcrestclient`'s own `AionStcHttp` convention) when
  unset, so a machine already configured for `stcrestclient`'s AION
  login needs no extra config for `tciqrestclient` too. Each of the
  three resolves independently; explicit `aion_url=`/`aion_username=`/
  `aion_password=` kwargs still win over both env conventions. One-way
  only — `stcrestclient` itself is unchanged. See `HANDOVER.md` §9's
  "AION credential env vars consolidated" entry.
- The default HTTP timeout (used when neither `timeout=` nor
  `TCIQ_TIMEOUT` is given) is now **120 seconds**, up from 10 —
  `config.DEFAULT_TIMEOUT`, `aion_discovery.AION_DISCOVERY_TIMEOUT`, and
  `Transport`'s own constructor default all updated together to stay in
  sync.

## 0.1.2

- `TCIQ_INSTALL_DIR`/`install_dir=` now also accepts a value wrapped in
  a matching pair of quotes (e.g.
  `TCIQ_INSTALL_DIR="C:\...\TestCenter"`) — needed for a real
  environment variable set directly in a Windows `cmd.exe` session
  (`set VAR="value"` keeps the quotes as part of the value itself,
  unlike a `.env` file, which `python-dotenv` already unquotes on its
  own).
- `query(name=...)` now also supports the `"chart"` view_type (a live/
  time-series line chart widget, e.g. "Port Frame Rate Chart") —
  CONFIRMED against a real server. Returns `{<series name>: rows}`, one
  entry per real numeric series (its "Test Events" plotlines marker
  series is excluded automatically); `table_index=`/`snapshot_name=`
  both raise `IQViewError` for it (neither is a concept that's been
  found in a real chart view's own query templates). See `HANDOVER.md`
  section 9's "chart" entry for the full mechanism.
- `query(name=...)`'s `"histogram"` support is now CONFIRMED against a
  real server (two real views/captures), superseding the previous
  never-confirmed implementation, which turned out to have a real,
  wrong assumption (`provider["group_by"]` is a list of every *allowed*
  choice, not the one actually selected by the view). Returns
  `{<provider name>: rows}`, one entry per distinct `query_provider` the
  selected statistics reference. `table_index=`/`test_live=True` both
  raise `IQViewError` for it; `snapshot_name=` silently has no effect
  for a provider that doesn't support snapshot filtering at all (not
  every one does).
- `query(name=...)`'s `"x_y_chart"` support is now CONFIRMED against a
  real server (a real "StreamBlock Frame Loss Duration Chart" view/
  capture), superseding the previous never-confirmed implementation,
  which unconditionally ignored `snapshot_name=` and assumed a `tables`
  list x_y_chart's real shape doesn't have at all. Returns
  `{<query_provider name>: rows}`, one entry per series. A new
  `view_query_builder.build_xy_chart_filter_dropdown_query(view)` helper
  exposes the separate, standalone "available snapshots, in order"
  query the real GUI also sends alongside the main data query -- not
  part of `query()`'s own return value, kept optional the same way
  `chart`'s `CHART_EVENTS_DEFINITION` is.
- Fixed a real `"pagination requires at least one order expression"`
  400 that any query/sub-query with no `orders` at all (`chart`'s own
  live-mode queries; some real `histogram` providers; the new
  `x_y_chart` filter-dropdown query above) would hit the moment
  `query()`'s default row limit got attached — the caller's `limit=` is
  now left off that specific query instead, generalized to cover
  `definition=`/single-query calls too, not just multi-query ones.
- `_apply_snapshot_filter()`'s resolution generalized again: when a
  provider's `snapshot_filter_provider` is entirely unset, its
  canonical `"test.snapshot_name"` attribute's own
  `interactive_query_updates` is now tried too (CONFIRMED needed for
  the real `x_y_chart` capture above) -- but only if that template's
  values actually contain a `"$(value)"` placeholder token, ruling out
  a real, confirmed counter-example ("Detailed Stream Results"'s own
  `test.snapshot_name` attribute has a same-shaped but unrelated
  `action == "filters"` entry with no placeholder at all, for something
  else entirely) that would otherwise have silently broken the
  already-confirmed table behavior.
## 0.1.1

- `verify=`/`TCIQ_VERIFY_SSL`: TLS certificate verification for the main
  `orion-res` connection (separate from `aion_ca_cert=`, which only
  covers the AION login itself) — `True`/`False`/a CA bundle path,
  matching `requests`' own `verify=`. Needed for a real lab deployment
  with a self-signed certificate. Defaults to leaving a caller-supplied
  `session=`'s own verification setting untouched rather than always
  overriding it.
- `auto_repair`'s "unknown column" detection now also recognizes a
  second real server error phrasing ("unknown dimension or result set
  name", not just "unknown attribute name"), and raises a clear error
  instead of sending an empty, doomed query if every column a view
  references turns out to be missing on a specific database.
- `rename_test()`'s wire format corrected — it now fetches the full
  database record and `PUT`s it back with only the name changed, rather
  than the partial body a real server rejects with a 400 or a 500
  server-side panic depending on what's included. Confirmed against a
  real server via a full rename-then-revert round trip.

## 0.1.0 — Initial release

Implements IQ-PYTHON-001 through IQ-PYTHON-011 (P0/P1) from the TestCenter
IQ Python Client PRD. Most are fully working and real-server-confirmed;
`x_y_chart`/`histogram` queries and a server-side (`orion-res`) report-worker
bug that can leave a report stuck "generating" are known, documented gaps —
see the caveats below and `HANDOVER.md` for detail.

- Auto-discovery of `orion-res`'s address (explicit base URL/host+port,
  local/remote STC install file discovery, AION platform discovery).
- Named views: list, find, save, delete, persisted server-side.
- `query()` — a single entry point for `single_level_table`/
  `paged_single_level_table` (confirmed working) and `x_y_chart`/
  `pie_chart`/`histogram`/`boxplot` (not yet reliable — `x_y_chart` and
  `histogram` are confirmed to raise against a real server; `pie_chart`/
  `boxplot` are unconfirmed), plus arbitrary `definition=` queries.
- Live/snapshot (`test_live=True/False`, or the strings
  `"live"`/`"eot"`/`"snapshot"`) and snapshot-name (`snapshot_name=`)
  modes, defaulting to snapshot data. `data_type=`/`table_index=` remain
  as advanced/legacy alternatives to `test_live=`.
- `user=` on `query()`: resolves `database_id` automatically for live
  data by finding the one test the given owner currently has running —
  no manual `list_tests(owner=...)` lookup needed. Not supported for
  snapshot data (a user can have many completed tests) — pass
  `database_id=` explicitly for that.
- Query modifiers: `filters=`, `sort=`, `group_by=`, `time_range=`,
  resolved by GUI display name, raw attribute path, unambiguous bare
  column name, or internal alias.
- Database metadata: schema, table, and field discovery.
- Multi-database support via `database_id=`/`use_test()`.
- Database lifecycle management: `delete_test()`, `rename_test()`.
- Report generation from existing templates, and download. Generation is
  asynchronous server-side; the caller is responsible for polling
  `get_report()`'s status before `download_report()` — this library does
  not poll for you. `snapshot_filter=` selects snapshot/live data;
  `excluded_sections=` (with `find_unsupported_report_sections()` to
  compute it) works around a real report-rendering crash triggered by a
  template's chart-type sections.
- `auto_repair=True` by default: strips and retries past
  `VALIDATION_FAILED: unknown attribute name` errors caused by a view's
  query_provider template referencing a column a specific database's
  schema doesn't have.

See `HANDOVER.md` at the repository root for architecture, requirements
status, and known gaps.
