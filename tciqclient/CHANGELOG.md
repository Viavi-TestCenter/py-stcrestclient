# Changelog

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
