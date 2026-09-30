# tciqrestclient API Reference

A complete, symbol-by-symbol reference for every public name `tciqrestclient`
exports. Where [`QUICKGUIDE.md`](QUICKGUIDE.md)/[`GETTING_STARTED.md`](GETTING_STARTED.md)
are organized by **task** ("how do I filter a query?"), this page is
organized by **symbol** — look up an exact method here once you already
know which one you want. [`QUICKSTART.md`](QUICKSTART.md) is the
fastest way to get oriented if you're brand new.

Every signature and behavior below is taken directly from the current
source (`tciqrestclient/client.py`, `tciqrestclient/query.py`, `tciqrestclient/exceptions.py`,
`tciqrestclient/__init__.py`) — nothing here is aspirational or planned.

```python
from tciqrestclient import IQClient, IQError, IQViewError   # all public names are in __all__
```

## Table of Contents

1. [`IQClient` — constructor](#1-iqclient--constructor)
2. [Properties and attributes](#2-properties-and-attributes)
3. [Tests / databases](#3-tests--databases)
   - [`list_tests`](#list_testsownernone-detailsummary)
   - [`get_test`](#get_testdatabase_idnone)
   - [`use_test`](#use_testdatabase_id)
   - [`delete_test`](#delete_testdatabase_idnone)
   - [`rename_test`](#rename_testnew_name-database_idnone)
   - [`get_database_schema`](#get_database_schemadatabase_idnone)
   - [`list_table_names`](#list_table_namesdatabase_idnone)
   - [`list_fields`](#list_fieldstable_namenone-database_idnone)
   - [`get_database_tables`](#get_database_tablesdatabase_idnone)
   - [`get_table_schema`](#get_table_schematable_name-database_idnone)
   - [`get_database_summary`](#get_database_summarydatabase_idnone)
   - [`list_databases_over_size`](#list_databases_over_sizemin_size_kb) / [`delete_databases_over_size`](#delete_databases_over_sizemin_size_kb-dry_runtrue)
   - [`list_databases_older_than`](#list_databases_older_thandays) / [`delete_databases_older_than`](#delete_databases_older_thandays-dry_runtrue)
4. [Views](#4-views)
   - [`list_views`](#list_viewstimeoutnone)
   - [`get_view`](#get_viewview_id-timeoutnone)
   - [`find_view`](#find_viewname-timeoutnone)
   - [`list_profiles`](#list_profilesview_idnone-detailnone-timeoutnone)
   - [`list_view_columns`](#list_view_columnsname-test_livenone-active_onlyfalse-timeoutnone-data_typenone-table_indexnone)
   - [`save_view`](#save_viewname-detailsnone-description-definitionnone)
   - [`delete_view`](#delete_viewview_idnone-namenone-timeoutnone)
5. [`query` — the one query method](#5-query--the-one-query-method)
6. [Reports](#6-reports)
   - [`list_report_templates`](#list_report_templates)
   - [`get_report_template`](#get_report_templatetemplate_id)
   - [`generate_report`](#generate_reporttemplate_id-titlenone-database_idnone-database_namenone-formatpdf-snapshot_filternone-excluded_sectionsnone-output_pathnone-extra)
   - [`find_unsupported_report_sections`](#find_unsupported_report_sectionstemplate_id-timeoutnone)
   - [`get_report`](#get_reportreport_id)
   - [`download_report`](#download_reportreport_id-save_asnone)
7. [Module-level functions](#7-module-level-functions)
   - [`merge_modifiers`](#merge_modifiersdefinition-filtersnone-sortnone-group_bynone-time_rangenone-limitnone-resolve_fieldnone)
   - [`rows_to_dicts`](#rows_to_dictsresult)
8. [Exceptions](#8-exceptions)
9. [Constants](#9-constants)

---

## 1. `IQClient` — constructor

```python
IQClient(base_url=None, host=None, port=None, install_dir=None,
         database_id=None, timeout=None, use_https=False,
         load_env=True, env_file=None, session=None, debug=None,
         aion_url=None, aion_username=None, aion_password=None,
         aion_node_name=None, aion_port_name=None, aion_ca_cert=None,
         verify=None)
```

Connects to `orion-res`. Every argument is optional — anything not
passed falls back to the matching `TCIQ_*` environment variable (or
`.env` file entry); `IQClient()` with no arguments at all works on a
properly configured machine. Raises `IQConfigError` immediately if no
address can be resolved from any source, or `IQConnectionError` if AION
discovery is attempted and fails.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `base_url` | `str` | `None` | Full base URL, e.g. `"http://127.0.0.1:9200"`. Highest-priority way to point at `orion-res`; skips discovery entirely. Falls back to `TCIQ_BASE_URL`. |
| `host` | `str` | `None` | Explicit `orion-res` host. Must be paired with `port=` — `host=` alone composes a URL with no port at all, it does not look one up. Falls back to `TCIQ_HOST`. |
| `port` | `int`/`str` | `None` | Explicit `orion-res` port. Falls back to `TCIQ_PORT`. |
| `install_dir` | `str` | `None` | STC install directory to discover the address from (`stcbll.ini` for a remote IQ deployment, `orion-res.yaml` for a local one). Falls back to `TCIQ_INSTALL_DIR`. |
| `database_id` | `str` | `None` | Default test id for `query()`/`get_test()`/etc. calls made on this client. Changeable later with [`use_test()`](#use_testdatabase_id), or overridden per call. Falls back to `TCIQ_DATABASE_ID`. |
| `timeout` | `float` | `120.0` | HTTP request timeout, in seconds, for every call this client makes (override per-call with most methods' own `timeout=`). Falls back to `TCIQ_TIMEOUT`. |
| `use_https` | `bool` | `False` | Use `https://` when composing a base URL from `host`/`port` or a discovered address. |
| `load_env` | `bool` | `True` | Load a `.env` file before reading environment variables. |
| `env_file` | `str` | `None` | Explicit `.env` file path. `None` searches upward from the current directory (`python-dotenv`'s default). |
| `session` | `requests.Session` | `None` | Optional session to use instead of creating one — mainly for tests. |
| `debug` | `bool` | `None` | Print every request's method/URL/JSON body before sending, and its status/timing after. `None` falls back to `TCIQ_DEBUG`. |
| `aion_url` | `str` | `None` | AION platform base URL, e.g. `"https://aion.example.com"`. Given together with `aion_username`/`aion_password`, `orion-res`'s address is discovered via AION's inventory API instead. Falls back to `TCIQ_AION_URL`, then to the bare `AION_URL` env var (`stcrestclient`'s own `AionStcHttp` convention, no `TCIQ_` prefix) if that's unset too. |
| `aion_username` | `str` | `None` | AION login email. Falls back to `TCIQ_AION_USERNAME`, then to the bare `AION_USERNAME` env var. |
| `aion_password` | `str` | `None` | AION login password. Falls back to `TCIQ_AION_PASSWORD`, then to the bare `AION_PASSWORD` env var. |
| `aion_node_name` | `str` | `None` | Optional AION node name to restrict instance discovery. Falls back to `TCIQ_AION_NODE_NAME`. |
| `aion_port_name` | `str` | `"iq"` | Name of the `orion-res` port entry in AION's product-instances list (confirmed against a real AION org 2026-09-08). Falls back to `TCIQ_AION_PORT_NAME`. |
| `aion_ca_cert` | `str` | `None` | Optional CA certificate path for AION HTTPS. Falls back to `TCIQ_AION_CA_CERT`. |
| `verify` | `bool`/`str` | `None` | TLS certificate verification for the *main* `orion-res` connection (separate from `aion_ca_cert=`, which only covers the AION login itself) — `True`/`False`/a CA bundle file path, exactly like `requests`' own `verify=`. `None` (default) falls back to `TCIQ_VERIFY_SSL`, then to normal verification if that's unset too. `False` only overrides a caller-supplied `session=`'s own default when explicitly set — `None` leaves it alone. |

> ✅ **CONFIRMED needed 2026-09-22** against a real lab deployment (`labserver`) whose HTTPS certificate is self-signed — connecting with `use_https=True` alone raised `SSLCertVerificationError`. `IQClient(host=..., port=..., use_https=True, verify=False)` (or `verify="/path/to/ca.pem"` for an internal CA) fixes it. Only set `verify=False` for a deployment you already trust on your own network, never for anything reachable over the open internet. See `examples/list_databases_labserver.py`.

**Precedence** when more than one source is set: explicit constructor
kwarg beats every environment variable, including an explicit
`aion_url=` beating an ambient `TCIQ_BASE_URL` left in the shell. Among
discovery methods themselves: `base_url` > `host`/`port` > `install_dir`
> AION. See [`QUICKGUIDE.md` §2](QUICKGUIDE.md#2-configure-the-connection)
for the full precedence table.

**Raises:** `IQConfigError` if no address resolves from any source;
`IQConnectionError` if AION discovery is attempted and fails.

**Example**

```python
from tciqrestclient import IQClient

iq = IQClient()                                        # everything from .env
iq = IQClient(base_url="http://127.0.0.1:9200")        # explicit, skips discovery
iq = IQClient(install_dir=r"C:\Program Files\Viavi Solutouns\TestCenter")
iq = IQClient(aion_url="https://aion.example.com",
              aion_username="jdoe", aion_password="secret")
```

---

## 2. Properties and attributes

### `base_url`

Read-only property. The resolved base URL this client is actually using
(after discovery), e.g. `"http://127.0.0.1:9200"`.

### `last_dropped_columns`

Instance attribute, updated by every [`query()`](#5-query--the-one-query-method)
call made with `name=` and `auto_repair=True` (the default). `[]` if
nothing was dropped, if the last call didn't use `name=`, or if
`auto_repair=False`. For a view whose query is genuinely one request
(most view types), this is a flat `list[str]` of the raw projection
fragments that were stripped. For a "multi"-kind view type (`histogram`,
`boxplot` — one query per provider/statistic; `chart` — one per real
numeric series), this is instead `dict[str, list[str]]`, keyed the same
way the returned rows are.

```python
rows = iq.query("Detailed Stream Results", database_id="abc123")
if iq.last_dropped_columns:
    print("Missing from this database:", iq.last_dropped_columns)
```

---

## 3. Tests / databases

### `list_tests(owner=None, detail="summary")`

List tests (databases) on the server.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `owner` | `str` | `None` | Filter by `metadata["test.owner"]` (the GUI's "Run By" column). Matched client-side — the server itself has no owner filter. `None` returns every test. |
| `detail` | `str` | `"summary"` | `"summary"` or `"full"` (includes schema information such as table names and field descriptors when available). |

**Returns:** `list[dict]` — one dict per test, each including at least
`id`, `name`, `description`, `metadata` (a dict of string key/value
pairs including `test.owner`, `test.running`, `test.started`, etc.), and
`summary` (a dict including `count`, the row count).

```python
tests = iq.list_tests(owner="jdoe")
for t in tests:
    print(t["id"], t["name"])
```

### `get_test(database_id=None)`

Get full metadata for one test.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `database_id` | `str` | `None` | Which test. Uses the default set via [`use_test()`](#use_testdatabase_id) / `TCIQ_DATABASE_ID` when omitted. |

**Returns:** `dict` — the full test record (same shape as one entry
from `list_tests(detail="full")`).

**Raises:** `IQQueryError` if `database_id` is omitted and no default is set.

### `use_test(database_id)`

Set the default database (test) id for subsequent `query()` /
`get_test()` / `generate_report()` / etc. calls made on this client
instance. Does not make a network call — just remembers the id.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `database_id` | `str` | *(required)* | The test id to make the default. |

**Returns:** `None`.

### `delete_test(database_id=None)`

Permanently delete a test database and all its stored results and
snapshots. **Irreversible — no undo, no confirmation prompt.**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `database_id` | `str` | `None` | Which test to delete. Uses the default set via `use_test()` when omitted. |

**Returns:** `None`.

**Raises:** `IQQueryError` if no `database_id` is available; `IQRequestError` if the server rejects the request.

### `rename_test(new_name, database_id=None)`

Rename a test database.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `new_name` | `str` | *(required)* | The new display name. |
| `database_id` | `str` | `None` | Which test to rename. Uses the default set via `use_test()` when omitted. |

**Returns:** `dict` — the updated test record.

**Raises:** `IQQueryError` if no `database_id` is available; `IQRequestError` if the server rejects the request (including the underlying `PUT` — see below).

> ✅ **CONFIRMED against a real server 2026-09-17** (see `HANDOVER.md` §9), and the original design was wrong: `PUT /databases/{id}` with a partial `{"name": ...}` body 400s (`RESOURCE_ID_MISMATCH`), and even `{"id": ..., "name": ...}` 500s with a real server-side panic. The real requirement is a full-object replace — fetch the current record (`get_test()`) and `PUT` it back with only `name` changed — which `rename_test()` now does internally; nothing changes for callers. Verified via a real rename-then-revert round trip against a live database (see `examples/rename_test_roundtrip.py`).

### `get_database_schema(database_id=None)`

Get the full raw schema record for a database (`GET /databases/{id}?detail=full`). Prefer [`list_table_names()`](#list_table_namesdatabase_idnone)/[`list_fields()`](#list_fieldstable_namenone-database_idnone) for structured access — use this only if you need something they don't expose.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `database_id` | `str` | `None` | Which database. Uses the default set via `use_test()` when omitted. |

**Returns:** `dict` — top-level keys include `id`, `datastore`, `name`, `description`, `metadata`, `result_sets`, `dimension_sets`, `profile`, `summary`.

### `list_table_names(database_id=None)`

List the available tables within a database.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `database_id` | `str` | `None` | Which database. Uses the default set via `use_test()` when omitted. |

**Returns:** `list[dict]` — one dict per table, each with at least
`name` and `kind` (`"result_set"` for a fact table, or `"dimension_set"`
for a lookup/reference table).

### `list_fields(table_name=None, database_id=None)`

List available fields (attributes) in a database, optionally scoped to one table.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `table_name` | `str` | `None` | Restrict to one table's fields (its `name`, from `list_table_names()`). `None` returns fields from every table. |
| `database_id` | `str` | `None` | Which database. Uses the default set via `use_test()` when omitted. |

**Returns:** `list[dict]` — one dict per field, each including at least
`name`; also `type` (the field's data type), `display_name`,
`description`, and `unit` when reported by the server.

```python
fields = iq.list_fields(table_name="test_events")
for f in fields:
    print(f["name"], f.get("type"))
```

### `get_database_tables(database_id=None)`

Alias for [`list_table_names()`](#list_table_namesdatabase_idnone) — same thing, under the name requested in review feedback. Both names work; `list_table_names()` is what the rest of this doc and the examples use.

### `get_table_schema(table_name, database_id=None)`

Get one table's own schema by name, instead of every table's (`list_table_names()`) or every field across every table (`list_fields()`).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `table_name` | `str` | *(required)* | The table's `name` (see `list_table_names()`) to look up. |
| `database_id` | `str` | `None` | Which database. Uses the default set via `use_test()` when omitted. |

**Returns:** `dict` — the matching table descriptor (`kind` plus `facts` or `attributes`, per `list_table_names()`).

**Raises:** `IQError` if no table on this database has this name.

### `get_database_summary(database_id=None)`

Get a database's summary metadata: row count and storage size, without the rest of the schema.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `database_id` | `str` | `None` | Which database. Uses the default set via `use_test()` when omitted. |

**Returns:** `dict` — CONFIRMED real shape (see `tests/fixtures.py`'s captured data): `{"count": <row count>, "value_storage_kb": <int>, "index_storage_kb": <int>}`. `{}` if the server didn't include a summary.

### `list_databases_over_size(min_size_kb)` / `delete_databases_over_size(min_size_kb, dry_run=True)`

Preview/bulk-delete every database at or over a total storage size (`value_storage_kb + index_storage_kb`, from `get_database_summary()`).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `min_size_kb` | `float` | *(required)* | Size threshold, in KB. |
| `dry_run` | `bool` | `True` | `delete_*` only. `True`: report matches without deleting anything. `False`: delete every match. |

**Returns:** `list[dict]` — matching database dicts (largest first), whether or not `delete_databases_over_size()` actually deleted them.

> ⚠️ `delete_databases_over_size(..., dry_run=False)` is destructive, irreversible, and can affect **many** databases in one call. See `examples/bulk_cleanup_databases.py` for a safety-gated way to run this interactively.

### `list_databases_older_than(days)` / `delete_databases_older_than(days, dry_run=True)`

Preview/bulk-delete every database whose `metadata["test.started"]` is more than `days` days in the past.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | `float` | *(required)* | Age threshold, in days. |
| `dry_run` | `bool` | `True` | `delete_*` only. `True`: report matches without deleting anything. `False`: delete every match. |

**Returns:** `list[dict]` — matching database dicts (oldest first). A database with no parseable `test.started` is excluded (there's no age to compare).

> ⚠️ Same destructive-and-irreversible caveat as `delete_databases_over_size()` above.

---

## 4. Views

### `list_views(timeout=None)`

List every view known to the server.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `timeout` | `float` | `None` | Per-call HTTP timeout override. A server with hundreds of views can make this response large and slow (each view includes its full `effective_details.system_data.query_providers`) — pass this instead of raising the client's global timeout. |

**Returns:** `list[dict]` — one full view record per view (`id`, `name`, `details`, `effective_details`, etc.).

### `get_view(view_id, timeout=None)`

Get one view by id.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `view_id` | `str` | *(required)* | The view's id. |
| `timeout` | `float` | `None` | Per-call HTTP timeout override. |

**Returns:** `dict` — the full view record.

**Raises:** `IQViewError` if `view_id` is falsy.

### `find_view(name, timeout=None)`

Find a view by its display name.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *(required)* | Exact display name, e.g. `"Detailed Stream Results"`. |
| `timeout` | `float` | `None` | Per-call HTTP timeout override — see [`list_views()`](#list_viewstimeoutnone). |

**Returns:** `dict` (the full view record) or `None` if no view has that name. Matched client-side, by scanning `list_views()`.

### `list_profiles(view_id=None, detail=None, timeout=None)`

List result profiles — a saved collection of views plus their dashboard layout (the GUI's results "template"), not to be confused with a single view. CONFIRMED against a real server 2026-09-30 (112 real profiles) — see `tciqrestclient/profiles.py`'s module docstring for the full shape notes.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `view_id` | `str` | `None` | Restrict to profiles that reference this view id (in their `views` list). Matched server-side — confirmed real query param. |
| `detail` | `str` | `None` | `"full"` (the server's own default when omitted) or `"summary"` (excludes each profile's `details.layouts`; every other field, including `views`, is unchanged — confirmed real, ~20% smaller response). |
| `timeout` | `float` | `None` | Per-call HTTP timeout override. |

**Returns:** `list[dict]` — one profile record per profile (`id`, `serial`, `name`, `description`, `metadata`, `details`, `views`). Each entry in `views` only carries that view's `id` — use [`get_view()`](#get_viewview_id-timeoutnone) with it to fetch the view's real definition.

### `list_view_columns(name, test_live=None, active_only=False, timeout=None, data_type=None, table_index=None)`

List every column a view's table can reference — including each one's
GUI display name — for discovering what
[`query()`](#5-query--the-one-query-method)'s `filters=`/`sort=`/`group_by=`
will accept.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *(required)* | View name (looked up the same way as `query(name=)`). |
| `test_live` | `bool`/`str` | `None` | Which table to list columns for — same as `query()`'s `test_live=` (see [§5](#5-query--the-one-query-method)). `None` resolves to the snapshot/`eot` table. |
| `active_only` | `bool` | `False` | `False` lists every column the view's query provider *supports*. `True` restricts to only the columns actually active on this table (what a real query against it returns). |
| `timeout` | `float` | `None` | Per-call HTTP timeout override, applied to the underlying `/views` lookup. |
| `data_type` | `str` | `None` | Advanced/legacy alternative to `test_live=` — an exact `data_type` string. Case-insensitive. Takes precedence over `test_live=` if both are given. |
| `table_index` | `int` | `None` | Advanced/legacy — pick a table by raw position, bypassing `test_live=`/`data_type=` entirely. |

**Returns:** `list[dict]`, each `{"name": <raw attribute path>, "alias_name": <query-safe alias>, "display_name": <GUI label>}`.

**Raises:** `IQViewError` if no view has that name, or if `test_live=`/`data_type=` doesn't match any table on it; `IQQueryError` if `test_live=` is an unrecognized string.

```python
columns = iq.list_view_columns("Detailed Stream Results", active_only=True)
for c in columns[:5]:
    print(c["display_name"], "->", c["alias_name"])
```

### `save_view(name, details=None, description="", definition=None)`

Create a new view, or update an existing one (pass the target view's
own `details` back with changes, and use `IQClient.delete_view()` +
`save_view()` again to effectively "rename", since there's no separate
update-by-id call here). Persisted server-side, not just in the client
session.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *(required)* | Display name for the view. |
| `details` | `dict` | `None` | The view's raw GUI table spec — **not** a query definition. Typically read via `get_view()`/`find_view()`, modified, and passed back; there is no supported way to build one from scratch. |
| `description` | `str` | `""` | Optional description text. |
| `definition` | `dict` | `None` | Alias for `details` — exactly one of the two names is needed; both work identically. |

**Returns:** `dict` — the server's response (shape depends on server version; look the view up by name afterward, e.g. with `find_view()`, to be sure of its final state rather than relying on this response alone).

**Raises:** `IQViewError` if `name` is falsy.

```python
source = iq.find_view("Detailed Stream Results")
iq.save_view(name="My CI View", details=source["details"],
             description="Created from tciqrestclient for CI reporting.")
```

### `delete_view(view_id=None, name=None, timeout=None)`

Delete a view. Exactly one of `view_id` or `name` must be given.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `view_id` | `str` | `None` | Delete by id directly. |
| `name` | `str` | `None` | Delete by display name — looked up first (same cost as `find_view()`). |
| `timeout` | `float` | `None` | Per-call HTTP timeout override, applied to the name lookup (if `name=` is used). |

**Returns:** `None`.

**Raises:** `IQViewError` if `name=` is given but no view has that name; `IQViewError` if `view_id` ends up falsy.

---

## 5. `query` — the one query method

```python
query(name=None, test_live=None, database_id=None, user=None,
      snapshot_name=None, filters=None, sort=None, group_by=None,
      time_range=None, limit=1000, mode="once", raw_result=False,
      timeout=None, auto_repair=True,
      definition=None, data_type=None, table_index=None)
```

The single method for pulling rows out of **any** saved view, or
running a raw query definition. Looks at the view's own `view_type`
internally and dispatches accordingly — there's no separate method per
widget type. Exactly one of `name` or `definition` must be given.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `None` | Name of an existing view to build a query from (looked up via `find_view()`). |
| `test_live` | `bool`/`str` | `None` | `True` (or the string `"live"`, case-insensitively) for in-progress-test data. `False`/`None` (or `"eot"`/`"snapshot"`) for completed-test snapshot data — **the default**. Ignored with `definition=`. Raises `IQViewError` for `"histogram"`/`"x_y_chart"` — no live-mode query template has been found in either's own real templates; only snapshot/eot data is confirmed working. |
| `database_id` | `str` | `None` | Which test's results to query. Defaults to the database set via `use_test()`/`TCIQ_DATABASE_ID`. Always wins over `user=` if both are given. |
| `user` | `str` | `None` | Username/email to resolve `database_id` from automatically (matches `metadata["test.owner"]`) instead of passing `database_id=` yourself. **Only resolved for `test_live=True`/`"live"`** — finds the one test owned by `user` whose `metadata["test.running"]` is true. For snapshot data, `user=` alone raises (a user can have many completed tests with no signal for which one is meant) — pass `database_id=` explicitly instead. |
| `snapshot_name` | `str` | `None` | With `name=` only: restrict to one specific named snapshot (mirrors the GUI's snapshot selector). Only valid against snapshot (`eot`) data. Silently has no effect for a `"histogram"` provider that has no snapshot filter of its own (not every one does — confirmed against a real server). Raises `IQViewError` for `"chart"` — no snapshot filter has been found in a real chart view's own templates at all. |
| `filters` | `list` | `None` | See [`merge_modifiers()`](#merge_modifiersdefinition-filtersnone-sortnone-group_bynone-time_rangenone-limitnone-resolve_fieldnone). With `name=`, a field may be given as its GUI display name, raw attribute path, unambiguous bare column name, or internal alias. |
| `sort` | `str`/`list`/`tuple` | `None` | See `merge_modifiers()`. Same field-name resolution as `filters=` with `name=`. |
| `group_by` | `str`/`list` | `None` | See `merge_modifiers()`. Same field-name resolution as `filters=` with `name=`. |
| `time_range` | `tuple`/`dict` | `None` | See `merge_modifiers()`. Same field-name resolution as `filters=` with `name=`. |
| `limit` | `int`/`None` | `1000` (`DEFAULT_QUERY_LIMIT`) | Max rows to return. `None` leaves the view's/definition's own limit untouched instead of overriding it. |
| `mode` | `str` | `"once"` | Always `"once"` in practice — every query is a single synchronous request/response; there is no separate live/subscription mode. |
| `raw_result` | `bool` | `False` | `False` returns a list of row dicts. `True` returns the raw `result` object (`id`, `columns`, `rows`, `pagination`, `timing`) instead. |
| `timeout` | `float` | `None` | Per-call HTTP timeout override, applied to both the `/queries` request(s) and (with `name=`) the underlying `/views` lookup. |
| `auto_repair` | `bool` | `True` | With `name=` only: automatically strip a column and retry (up to 100 times) if the server 400s with `VALIDATION_FAILED: unknown attribute name: ...` — a real, confirmed occurrence when a view's template references a column a specific database's schema doesn't have. Check [`last_dropped_columns`](#last_dropped_columns) afterward. `False` lets the original `IQRequestError` propagate instead. |
| `definition` | `dict`/`str` | `None` | Advanced escape hatch: a raw query definition (a `dict`, or a JSON string — parsed automatically) to run directly instead of building one from a view. |
| `data_type` | `str` | `None` | Advanced/legacy alternative to `test_live=` — an exact `data_type` string (e.g. `"eot"`). Case-insensitive. Takes precedence over `test_live=` if both are given. Ignored with `definition=`. |
| `table_index` | `int` | `None` | Advanced/legacy — pick a view's table by raw position, bypassing `test_live=`/`data_type=` entirely. Almost never needed. Ignored with `definition=`. Raises `IQViewError` for `"chart"`/`"histogram"`/`"x_y_chart"` — none of them have a `details.user_data.tables` list to index into at all. |

**Returns:**
- For a view type that's genuinely one query (the common table view
  types, `pie_chart` — or always, with `definition=`): a `list[dict]`
  of row dicts, or the raw result object if `raw_result=True`.
- For a view type that isn't (`x_y_chart`/`histogram`: one query per
  provider; `boxplot`: one per statistic; `chart`: one per real numeric
  series, keyed by its internal name): a `dict[str, list[dict]]` — one
  entry per underlying query. `table_index=`/`snapshot_name=` both raise
  `IQViewError` for `chart`.

**Raises:**
- `IQQueryError` — neither/both of `name=`/`definition=` given; `definition=` is an invalid JSON string; `test_live=` is an unrecognized string; no `database_id` available and no default set; `user=` couldn't resolve a database (no/multiple running tests, or used with snapshot data).
- `IQViewError` — no view has the given `name`; `test_live=`/`data_type=` doesn't match any table on the view; `snapshot_name=` given against live data; the view's `view_type` isn't supported.
- `IQRequestError` — the server rejected the request (and `auto_repair` either didn't apply or ran out of attempts).

**Examples**

```python
# The common case
rows = iq.query("Detailed Stream Results", "live", user="jdoe")

# Pointing at a specific test directly
rows = iq.query("Detailed Stream Results", database_id="abc123")

# Filters, sort, limit
rows = iq.query(
    "Detailed Stream Results", database_id="abc123",
    filters=[("frame_count", "gt", 0)],
    sort="frame_count DESC",
    limit=100,
)

# A raw captured/hand-built definition
rows = iq.query(definition=my_query_definition, database_id="abc123")

# The raw result object instead of row dicts
result = iq.query("Detailed Stream Results", database_id="abc123", raw_result=True)
print(result["columns"], len(result["rows"]))
```

---

## 6. Reports

### `list_report_templates()`

**Returns:** `list[dict]` — every report template on the server, each including at least `id` and `name`.

### `get_report_template(template_id)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `template_id` | `str` | *(required)* | The template's id. |

**Returns:** `dict` — the full template record.

**Raises:** `IQReportError` if `template_id` is falsy.

### `generate_report(template_id, title=None, database_id=None, database_name=None, format="pdf", snapshot_filter=None, excluded_sections=None, output_path=None, **extra)`

Generate a report from an existing template and, when `output_path` is
given, download it.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `template_id` | `str` | *(required)* | Id of an existing report template. |
| `title` | `str` | `None` | Report title. **Required by the server** — raises `IQReportError` if left `None`. |
| `database_id` | `str` | `None` | Database (test) to report on. Defaults to the one set via `use_test()`/`TCIQ_DATABASE_ID`. |
| `database_name` | `str` | `None` | Optional — the real GUI request also sends `database.name` alongside `database.id` (see below). `None`: omitted — CONFIRMED against a real server that this is fine too. |
| `format` | `str` | `"pdf"` | Output format. **Must be lowercase** — e.g. `"pdf"`, not `"PDF"` (the server 400s on the uppercase form). |
| `snapshot_filter` | `str` \| `list[str]` | `None` | CONFIRMED real (see below) — a string or list of strings, JSON-encoded into `parameters.test_snapshot_filter`. Combine `REPORT_ALL_SNAPSHOTS_FILTER`/`REPORT_LIVE_INCLUDED_FILTER` in a list for a "live and snapshot" report. `None`: omitted entirely (this method's pre-existing behavior). |
| `excluded_sections` | `list[str]` | `None` | CONFIRMED real and CONFIRMED as a working fix for a real report-rendering crash (see below) — a list of the template's own section names (e.g. `["section_2"]`), JSON-encoded into `parameters.excluded_sections`. Use [`find_unsupported_report_sections()`](#find_unsupported_report_sectionstemplate_id-timeoutnone) to compute this generically instead of hardcoding section names. `None`: omitted entirely. |
| `output_path` | `str` | `None` | Local path to download the finished report to. |
| `**extra` | — | — | Additional report fields (`parameters`, `page_layout`, `metadata`, etc. — see below for confirmed real shapes) — passed through as-is. If `extra["parameters"]` is given together with `snapshot_filter=`/`excluded_sections=`, those two are merged into the given `parameters` dict rather than replacing it. |

> ✅ **CONFIRMED against two real captures of the GUI's own
> `POST /reports` request, 2026-09-11** (superseding an earlier, wrong
> guess — an earlier version of this parameter sent top-level `"live"`/
> `"snapshot_name"` fields that a real capture showed don't exist at
> all). The real body looks like:
> ```json
> {"id": "", "report_template_id": "...", "database": {"id": "...", "name": "..."},
>  "title": "...", "format": "pdf",
>  "page_layout": {"paper_size": "us-letter", "orientation": "landscape"},
>  "parameters": {"application.id": "...", "application.name": "...",
>                 "owner": "...", "test.type": "traffic", "description": "",
>                 "test_snapshot_filter": "[\"is_all_included\"]", "...": "..."},
>  "metadata": {"aftViewIds": "{}"}}
> ```
> `test_snapshot_filter` is the one field this parameter maps to, and
> it's a **list of independent filter flags**, not a single mode — a
> second real capture, this time for "live and snapshot" report
> generation, was byte-identical except `test_snapshot_filter` was
> `["is_all_included", "is_live_included"]` instead: the *same* flag
> from the first capture, plus a second one added to the list, not a
> different value entirely. Two confirmed real flags so far:
> `"is_all_included"` (`tciqrestclient.reports.REPORT_ALL_SNAPSHOTS_FILTER` —
> every snapshot) and `"is_live_included"`
> (`tciqrestclient.reports.REPORT_LIVE_INCLUDED_FILTER` — also include live/
> in-progress data). Combine both in a list for "live and snapshot":
> `generate_report(..., snapshot_filter=[REPORT_ALL_SNAPSHOTS_FILTER,
> REPORT_LIVE_INCLUDED_FILTER])`. Passing a specific snapshot's *name*
> here instead of one of these two flags is a reasonable *inference*
> from the list shape, not independently confirmed — capture a real
> request that actually picks one named snapshot if exact fidelity
> matters there. The rest of `parameters` (`application.*`,
> `company_name`, `owner`, `test.type`, `dut.details`,
> `report_preferences`) looks GUI-populated from the target database's
> own metadata for display purposes — pass any of it through `**extra`
> (as `parameters={...}`) for exact fidelity; `generate_report()`
> doesn't try to reproduce it automatically. `page_layout` (confirmed
> keys: `paper_size`, `orientation`) already works via `**extra` — no
> dedicated parameter needed for it. `excluded_sections` is the one
> exception — it has its own dedicated parameter, documented below.

**Returns:** the download path (a `str`, equal to `output_path`) if
`output_path` was given, else the raw report object (`dict`, including
its `id` for a later `download_report()`/`get_report()` call).

**Raises:** `IQReportError` if `title` is omitted, or `template_id`/`database_id` is missing.

> **Known gap:** report generation is asynchronous server-side.
> `generate_report(output_path=...)` downloads immediately with no
> wait/poll for completion, which can produce an incomplete or 0-byte
> file for anything beyond a trivially small report. Omit `output_path=`
> and poll [`get_report()`](#get_reportreport_id)'s status yourself
> before calling `download_report()`, for anything real.

> ✅ **`excluded_sections` CONFIRMED as a working fix for a real
> report-rendering crash, 2026-09-16.** A report template's chart-type
> sections (`view_type` e.g. `x_y_chart`) can crash the report-rendering
> frontend with a real, 100%-reproducible `TypeError` — confirmed via
> Chrome DevTools Protocol inspection of the live report tab, universal
> across every database tried, root-caused down to specific frontend
> source (not a guess). The real `POST /reports` body's
> `parameters.excluded_sections` field (a JSON-encoded list of section
> names) skips a section during rendering entirely. Against a real
> "Traffic Test Report" template with one chart section
> (`"section_2"`), excluding it produced a genuine, complete,
> correctly-paginated report with real data where the unmodified
> template crashed every time. Use
> [`find_unsupported_report_sections()`](#find_unsupported_report_sectionstemplate_id-timeoutnone)
> to compute which sections to exclude generically, rather than
> hardcoding section names:
> ```python
> unsupported = iq.find_unsupported_report_sections(template["id"])
> iq.generate_report(template["id"], title="...", excluded_sections=unsupported)
> ```
> This fixes a crash in the report-rendering *frontend* specifically —
> it does not address a separate, still-open bug in `orion-res`'s Go
> report worker that can leave a report stuck at `"generating"`
> indefinitely even once the frontend crash is avoided (out of scope
> for this library; see the project's HANDOVER.md for the full trace).

### `find_unsupported_report_sections(template_id, timeout=None)`

Find which of a report template's sections reference a view whose real
`view_type` isn't confirmed safe for report generation (see the
`excluded_sections` note above).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `template_id` | `str` | *(required)* | Id of an existing report template. |
| `timeout` | `float` | `None` | Per-request timeout override. |

**Returns:** `list[str]` — the section *names* (matching the template's
own `details.sections[].name`, e.g. `"section_2"`) that reference a
view whose `view_type` isn't in `tciqrestclient.reports.REPORT_SAFE_VIEW_TYPES`
(currently `"single_level_table"`/`"paged_single_level_table"`) — or
whose view can't be resolved at all. `[]` if every section only
references a confirmed-safe (table) view. Pass the result straight to
`generate_report(..., excluded_sections=...)`.

### `get_report(report_id)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `report_id` | `str` | *(required)* | The report's id (from `generate_report()`'s return value). |

**Returns:** `dict` — the report's current status/metadata.

**Raises:** `IQReportError` if `report_id` is falsy.

### `download_report(report_id, save_as=None)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `report_id` | `str` | *(required)* | The report's id. |
| `save_as` | `str` | `None` | Local path to write the file to. `None` returns the raw bytes instead of writing to disk. |

**Returns:** `save_as` (`str`) if given, else the raw file `bytes`.

**Raises:** `IQReportError` if `report_id` is falsy.

---

## 7. Module-level functions

These live in `tciqrestclient.query` but are re-exported from the top-level
`tciqrestclient` package — `IQClient.query()` uses them internally, and you can
call them directly if you're building a query definition by hand
(`definition=`) rather than from a saved view.

### `merge_modifiers(definition, filters=None, sort=None, group_by=None, time_range=None, limit=None, resolve_field=None)`

Return a **copy** of `definition` (the input is never mutated) with
`filters`/`sort`/`group_by`/`time_range` appended to its outermost
node's arrays, and `limit` set directly.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `definition` | `dict` | *(required)* | An existing query definition (e.g. from a saved view, or hand-built). |
| `filters` | `list` | `None` | Each entry is a raw SQL-ish expression string (passed through as-is), a `(field, value)` or `(field, op, value)` tuple, or a `{"field", "op", "value"}` dict. `op` defaults to `"eq"`; must be one of `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`. |
| `sort` | `str`/`tuple`/`list` | `None` | A field name, `"field ASC"`/`"field DESC"` string, a `(field, order)` tuple, or a list of those for multi-column sort. |
| `group_by` | `str`/`list` | `None` | A field name, or a list of field names. |
| `time_range` | `tuple`/`dict` | `None` | `(field, start, end)` or `{"field", "start", "end"}`. `field` is required; `start`/`end` may each be omitted for an open-ended range. |
| `limit` | `int` | `None` | Max rows. Unlike the other modifiers (which append), this **replaces** the definition's existing limit. `None` leaves it untouched. |
| `resolve_field` | `callable` | `None` | Optional `function(field_name) -> field_name`, applied to every field name in `filters=`/`sort=`/`group_by=`/`time_range=` before qualification — this is how `query(name=...)` resolves GUI display names and bare column names to internal aliases (see `tciqrestclient.view_query_builder.build_field_resolver()`). |

Field names are qualified automatically with the outermost node's
single child alias (e.g. `"view."`) when the definition has exactly one
top-level subquery. Already-qualified names (`"alias.field"`) and raw
expression strings are left untouched.

**Returns:** `dict` — a new definition; the input is not mutated.

**Raises:** `IQQueryError` for a malformed filter/sort entry, an unsupported filter operator, or a definition with none of the recognized query-type keys.

### `rows_to_dicts(result)`

Zip a query result's positional `rows` against its `columns` into a
list of row dicts.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `result` | `dict` | *(required)* | The `result` object from a query response (an empty/missing one is tolerated). |

**Returns:** `list[dict]` — one dict per row, keyed by column name.

---

## 8. Exceptions

All importable from the top-level `tciqrestclient` package. Every exception
`tciqrestclient` raises is one of these — catching the base `IQError` is enough
for a script that just wants to report a failure and move on.

```python
from tciqrestclient.exceptions import IQError, IQRequestError
```

| Exception | Base | Raised when |
|---|---|---|
| `IQError` | `Exception` | Base class for every error below. |
| `IQConfigError` | `IQError` | No connection info could be resolved at all — no `base_url`/`host`/`install_dir`/AION settings found anywhere. |
| `IQConnectionError` | `IQError` | `orion-res`'s address couldn't be discovered — e.g. AION login or inventory lookup failed. |
| `IQRequestError` | `IQError` | An HTTP request to `orion-res` failed or returned a non-2xx response. |
| `IQQueryError` | `IQError` | A query couldn't be built or run — bad `filters=`/`sort=` shape, malformed `definition=` JSON, neither/both of `name=`/`definition=` given, no `database_id` available, an unrecognized `test_live=` string, a `user=` that couldn't be resolved, etc. |
| `IQViewError` | `IQError` | A named-view operation failed — view not found, no table matches the requested `test_live=`/`data_type=`, `snapshot_name=` against live data, etc. |
| `IQReportError` | `IQError` | Report generation/download failed — e.g. a missing `title=`, or a missing id. |

```python
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQError, IQRequestError

iq = IQClient()
try:
    rows = iq.query("Detailed Stream Results", database_id="abc123")
except IQRequestError as e:
    print("Server rejected the request:", e)
except IQError as e:
    print("tciqrestclient error:", e)
```

---

## 9. Constants

| Name | Value | Description |
|---|---|---|
| `DEFAULT_QUERY_LIMIT` | `1000` | `query()`'s default row limit when `limit=` isn't passed. |
| `__version__` | e.g. `"0.1.0"` | The installed `tciqrestclient` package version. |

```python
import tciqrestclient
print(tciqrestclient.__version__)
```

---

See [`QUICKSTART.md`](QUICKSTART.md) for the fastest path to a first
result, [`QUICKGUIDE.md`](QUICKGUIDE.md)/[`GETTING_STARTED.md`](GETTING_STARTED.md)
for task-by-task walkthroughs, and [`HANDOVER.md`](../HANDOVER.md) at
the repository root for architecture, known gaps, and requirement
status.
