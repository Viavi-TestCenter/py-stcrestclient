# tciqrestclient Quick Guide

A practical, task-by-task guide to the `tciqrestclient` Python client for TestCenter
IQ's `orion-res` results service. Where [`README.md`](README.md) is a
short overview and [`HANDOVER.md`](../HANDOVER.md) is the architecture/
project-status writeup for maintainers, this guide is for someone who
just wants to **use** the client: connect, find a test, pull rows out of
a view, and handle the errors that come up along the way. In a hurry?
See [`QUICKSTART.md`](QUICKSTART.md) instead — five steps, no reading
required beyond that page.

Every example below is real, working `tciqrestclient` code — for a runnable,
end-to-end version of most of them, see [`examples/`](examples/) (listed
in full in [§17](#17-example-scripts)).

> **Known gap:** `x_y_chart` and `histogram` views are confirmed broken
> against a real server — `query(name=...)` currently raises
> `IQViewError` for both (`pie_chart`/`boxplot` are unconfirmed either
> way). Everything in this guide about `query()` is written against, and
> confirmed working for, the common "table" view types
> (`single_level_table`/`paged_single_level_table`) and `definition=`
> calls. See `HANDOVER.md` §9 ("Widget query builders") for detail.

## Table of Contents

1. [Install](#1-install)
2. [Configure the connection](#2-configure-the-connection)
3. [Connect and sanity-check](#3-connect-and-sanity-check)
4. [Find your test](#4-find-your-test)
5. [Query a named view](#5-query-a-named-view)
6. [Live data vs. snapshot data](#6-live-data-vs-snapshot-data)
7. [Filter, sort, group, and limit a query](#7-filter-sort-group-and-limit-a-query)
8. [Discover a view's columns](#8-discover-a-views-columns)
9. [Create, reuse, and delete your own views](#9-create-reuse-and-delete-your-own-views)
10. [Inspect a database's schema](#10-inspect-a-databases-schema)
11. [Query multiple databases](#11-query-multiple-databases)
12. [Rename or delete a test database](#12-rename-or-delete-a-test-database)
13. [Generate and download a report](#13-generate-and-download-a-report)
14. [Run a raw JSON query definition](#14-run-a-raw-json-query-definition)
15. [Handle errors](#15-handle-errors)
16. [Debug a request](#16-debug-a-request)
17. [Example scripts](#17-example-scripts)
18. [Quick reference](#18-quick-reference)
19. [Where to go next](#19-where-to-go-next)

---

## 1. Install

```bash
pip install tciqrestclient
```

Requires Python 3.8+. Dependencies (`requests`, `python-dotenv`, `PyYAML`)
install automatically. No `stcrestclient` dependency — `tciqrestclient` is fully
standalone.

Working from this checkout instead of PyPI:

```bash
cd tciqclient
pip install -e ".[test]"     # editable install + pytest/responses for testing
```

---

## 2. Configure the connection

`tciqrestclient` never hardcodes a server address. Every setting below can be a
`.env` file entry, a real environment variable, or an `IQClient()`
keyword argument — and nothing is required except *one* way to find the
server.

```bash
cp .env.example .env
# then edit .env
```

Pick exactly one discovery method:

| Method | `.env` keys | When to use it |
|---|---|---|
| **Direct URL** | `TCIQ_BASE_URL=http://127.0.0.1:9200` | You already know the address. Simplest, fastest, no discovery step. |
| **Direct host/port** | `TCIQ_HOST=127.0.0.1`, `TCIQ_PORT=9200` | Same as above, split into two parts. |
| **STC install dir** | `TCIQ_INSTALL_DIR=C:\Program Files\Spirent Communications\Spirent TestCenter` | Running on/near a Spirent TestCenter install — reads `orion-res.yaml` (local IQ) or `stcbll.ini` (remote IQ) to find the address for you. |
| **AION platform** | `TCIQ_AION_URL`, `TCIQ_AION_USERNAME`, `TCIQ_AION_PASSWORD` | orion-res is fronted by an AION lab — `tciqrestclient` logs into AION and looks up orion-res's real address + bearer token from AION's inventory. |

Other useful settings:

```bash
TCIQ_DATABASE_ID=          # default test id -- or just call use_test() at runtime
TCIQ_TIMEOUT=10            # HTTP timeout in seconds (default 10)
TCIQ_DEBUG=                # 1/true/yes to log every request before sending
```

**Precedence** (highest to lowest), when more than one is set at once:

1. Explicit `IQClient(...)` keyword arguments (e.g. `base_url=`, `aion_url=`)
2. `TCIQ_BASE_URL` → `TCIQ_HOST`/`TCIQ_PORT` → `TCIQ_INSTALL_DIR` (in that order)
3. AION env vars, if none of the above resolved anything

An explicit keyword argument always wins over an environment variable —
including `aion_url=` beating an ambient `TCIQ_BASE_URL` left over in
your shell. See `tciqrestclient/config.py`'s module docstring for the exact rules
if you're mixing methods.

Every `.env` key above also has a matching `IQClient()` constructor
argument (`base_url=`, `host=`, `port=`, `install_dir=`, `database_id=`,
`timeout=`, `aion_url=`, `aion_username=`, `aion_password=`,
`aion_node_name=`, `aion_port_name=`, `aion_ca_cert=`, `debug=`) if you'd
rather configure in code than in the environment.

---

## 3. Connect and sanity-check

```python
from tciqrestclient import IQClient

iq = IQClient()                 # reads everything from .env / the environment
print(iq)                       # <IQClient base_url='http://127.0.0.1:9200'>
```

Connecting doesn't make any HTTP request by itself — `IQClient()` only
resolves *where* the server is (and, for AION discovery, logs in to find
out). The first real request happens on your first `list_tests()`,
`query()`, etc. call. If something's misconfigured, you'll find out then,
as an `IQConfigError` (nothing resolved to an address) or
`IQConnectionError` (AION discovery itself failed) — see
[§15](#15-handle-errors).

A server with hundreds of views/tests can be slow to answer some calls
(see [§16](#16-debug-a-request)) — bump the timeout for a single client
for the rest of a script if 10s isn't enough:

```python
iq = IQClient(timeout=60)
```

---

## 4. Find your test

Every orion-res "database" is one test run's results. There's no
owner filter on the server itself, so `list_tests(owner=...)` filters
client-side on the `test.owner` metadata field (the GUI's "Run By"
column):

```python
tests = iq.list_tests(owner="jdoe")
for t in tests:
    print(t["id"], t["name"])

iq.use_test(tests[0]["id"])     # sets the default database_id for
                                 # every query()/get_test()/generate_report()
                                 # call below, until changed again
```

`use_test()` just remembers an id on the client instance — it's not a
network call. You can skip it entirely and instead pass `database_id=`
explicitly to any call that needs one, which is the better option when a
script talks to more than one test at once (see [§11](#11-query-multiple-databases)).

```python
iq.get_test()                        # full metadata for the current default test
iq.get_test(database_id="abc123")    # or a specific one, regardless of use_test()
```

For `query()` specifically, there's a third option that skips all of the
above: pass `user=` and let `query()` find the right `database_id` for
you — see [§6](#6-live-data-vs-snapshot-data).

---

## 5. Query a named view

`query()` is the **one** method for pulling rows out of any saved view —
it looks at the view's own `view_type` internally and builds the right
kind of request, rather than requiring a different call per widget type:

```python
rows = iq.query(name="Detailed Stream Results")
for row in rows[:5]:
    print(row)
# [{'tx_stream_stream_id': '1', 'rx_stream_key': '2', 'frame_count': 118273, ...}, ...]
```

`rows` is a plain `list[dict]` — one dict per row, keyed by column name —
for the common case (table views, `x_y_chart`, `pie_chart`, and every
`definition=` call). Two view types return one query's worth of rows
*per sub-query* instead, as a `{name: list[dict]}` dict: `histogram`
(one entry per query provider) and `boxplot` (one entry per statistic).
Check which you're dealing with by printing `type(rows)`, or just look
at the view in the IQ GUI — table/line-chart/pie views give you a flat
list; histograms and box plots give you a dict.

By default `query()` caps results at 1000 rows (`DEFAULT_QUERY_LIMIT`) as
a safety net — pass `limit=` to change that, or `limit=None` to leave the
view's own limit untouched:

```python
rows = iq.query(name="Detailed Stream Results", limit=5000)
all_rows = iq.query(name="Detailed Stream Results", limit=None)
```

> **There is no live/subscription mode.** Every call to `query()` is one
> HTTP request/response. "Watching" a running test just means calling
> `query()` again — there's no push, poll-loop, or websocket built in.

---

## 6. Live data vs. snapshot data

A view can have more than one underlying table — most commonly a live
table (the test is still running) and a snapshot (`eot`, **e**nd **o**f
**t**est) table. **By default, `query()` returns snapshot data**, not
whatever table the view happens to list first:

```python
rows = iq.query("Detailed Stream Results")                # snapshot by default
rows = iq.query("Detailed Stream Results", True)           # explicitly live instead
rows = iq.query("Detailed Stream Results", False)          # explicitly snapshot
```

`test_live` (the second positional argument, or pass it by name --
`test_live=True`) also accepts the strings `"live"` or
`"eot"`/`"snapshot"`, case-insensitively, if that reads more naturally
than a bare boolean in your code:

```python
rows = iq.query("Detailed Stream Results", "live")
rows = iq.query("Detailed Stream Results", "eot")           # same as False
```

Use `list_table_names()`/`list_fields()` (see [§10](#10-inspect-a-databases-schema))
or `iq.list_view_columns(name)` if you're not sure whether a given view
even has both tables — an unrecognized `test_live=` string raises
`IQQueryError`, and a view with no matching table raises `IQViewError`.

**Finding the right test without a database_id:** pass `user=` and, for
live data, `query()` finds the one test that user currently has running
(`metadata["test.running"]`) and uses it automatically — no
`list_tests(owner=...)` + pick-the-running-one dance needed:

```python
rows = iq.query("Detailed Stream Results", "live", user="jdoe")
```

This only works for live data — a user can have any number of
*completed* tests with no way to tell which one you mean, so `user=`
for snapshot data raises `IQQueryError` asking for an explicit
`database_id=` instead of guessing. Pass `database_id=` (see
[§4](#4-find-your-test)/[§11](#11-query-multiple-databases)) for
snapshot data, or whenever you already know which test you want.

If a test has multiple named snapshots and you want just one, add
`snapshot_name=` (only valid alongside snapshot data):

```python
rows = iq.query(
    "Detailed Stream Results", False, database_id="abc123",
    snapshot_name="Baseline Run",
)
```

**Advanced / rarely needed:** `data_type=` (the exact string a table's
own `data_type` field uses, e.g. `"eot"`) and `table_index=` (pick a
table by raw position) still work exactly as before, as lower-level
alternatives to `test_live=` — you're unlikely to ever need them, since
`test_live=` already selects the right table by name for every view
seen in practice.

---

## 7. Filter, sort, group, and limit a query

`filters=`, `sort=`, `group_by=`, and `time_range=` all accept plain
Python values — no need to hand-build query-expression strings yourself.
With `name=`, every field can be given four different ways and they all
resolve to the same column: the view's **GUI display name** (e.g.
`"Rx Count"`, case-insensitive), its **raw attribute path** (e.g.
`"rx_stream_stats.frame_count"`), a **bare column name** with no table
prefix at all (e.g. `"min_latency"`) *when it's unambiguous* — see the
callout below — or its internal **alias**
(`"rx_stream_stats_frame_count"`). Use
[`list_view_columns()`](#8-discover-a-views-columns) to see what's
available for a given view.

```python
rows = iq.query(
    "Detailed Stream Results",
    filters=[
        ("min_latency", "gt", 0),              # (field, op, value) -- bare name
        ("Rx Count", 100),                     # (field, value) -- op defaults to "eq"
        "view.tx_stream_stream_id = '1'",      # raw expression, passed through as-is
    ],
    sort="min_latency DESC",                   # or [("min_latency", "DESC"), ("rx_stream_key", "ASC")]
    group_by="tx_stream_stream_id",            # or a list of field names
    time_range=("start_time", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"),
    limit=200,
)
```

> **Bare column names only resolve when unambiguous.** If two columns on
> the same view end in the same bare name (e.g. this view has *both*
> `tx_stream_stats.frame_count` and `rx_stream_stats.frame_count`), a
> bare `"frame_count"` is deliberately left unresolved rather than
> silently guessing which one you meant — qualify it
> (`"rx_stream_stats.frame_count"`) or use its GUI display name
> (`"Rx Count"`) instead in that specific case. `"min_latency"` above
> only ever means one column on this view, so it resolves fine as-is.

Filter operators: `eq` (default), `ne`, `lt`, `lte`, `gt`, `gte`,
`contains` (substring match, becomes `LIKE '%value%'`), and `in` (value
is a list). A filter can also be a `{"field": ..., "op": ..., "value": ...}`
dict instead of a tuple, if that reads better in your code.

`time_range=` needs an explicit field name — there's no single universal
timestamp column across every view — and either bound can be omitted for
an open-ended range: `(field, start, None)` or `{"field": ..., "start": ...}`
with no `"end"`.

For a `histogram`/`boxplot` view (the `{name: rows}`-returning kind, see
[§5](#5-query-a-named-view)), the same `filters=`/`sort=`/etc. are
applied identically to every one of its underlying sub-queries.

> **Heads up on filters and the GUI:** `query()` qualifies your filters
> against the view's outermost alias, which isn't guaranteed to be
> byte-identical to how the IQ GUI's own filter box would place the same
> filter internally. If a filtered `name=` query doesn't behave the way
> the same filter does in the GUI, capture the GUI's own request with
> `debug=True` (see [§16](#16-debug-a-request)) and compare.

---

## 8. Discover a view's columns

Before writing filters/sort against a view you haven't used before, list
its columns to see the exact display names, aliases, and raw attribute
paths available:

```python
columns = iq.list_view_columns("Detailed Stream Results", active_only=True)
for c in columns[:5]:
    print(c["display_name"], "->", c["alias_name"], "/", c["name"])
```

`active_only=False` (the default) lists every column the view's
underlying query provider *supports*; `active_only=True` restricts the
list to columns actually active on this table — i.e. what a real query
against it returns.

---

## 9. Create, reuse, and delete your own views

You can save a new view from code — most simply by cloning an existing
view's `details` (its raw GUI table spec) under a new name, since there's
no supported way to build a view's `details` from scratch:

```python
source = iq.find_view("Detailed Stream Results")

created = iq.save_view(
    name="My CI View",
    details=source["details"],
    description="Created from tciqrestclient for CI reporting.",
)

# Reuse it immediately -- no extra steps needed:
rows = iq.query("My CI View", limit=5)

# Clean up when you're done with it:
iq.delete_view(name="My CI View")
```

`list_view_columns()`/`query(name=...)` work on a view you just created
exactly the same way they do on a pre-existing one — `tciqrestclient` transparently
finds a matching query template from elsewhere on the server if the
freshly created view doesn't have its own yet (a real quirk of
`POST /views` — see `HANDOVER.md` §9 if you're curious why).

Other view operations:

```python
views = iq.list_views()                       # every view on the server
view = iq.get_view(view_id="abc123")          # by id
view = iq.find_view("My CI View")             # by display name, or None
iq.delete_view(view_id="abc123")              # by id
iq.delete_view(name="My CI View")             # or by name (looks it up first)
```

`list_views()`/`find_view()` can be slow on a server with hundreds of
views (each one's full query-provider templates are included in the
response) — pass `timeout=` to give a specific call more time without
raising the client's global default:

```python
views = iq.list_views(timeout=60)
```

See [`examples/manage_views.py`](examples/manage_views.py) for the full
save → reuse → delete cycle end-to-end, with cleanup guaranteed even if
a step in between fails.

---

## 10. Inspect a database's schema

```python
tables = iq.list_table_names()                # every result_set + dimension_set
for t in tables[:5]:
    print(t["name"], t["kind"])                # "result_set" or "dimension_set"

fields = iq.list_fields()                      # every field, across all tables
fields = iq.list_fields(table_name="test")     # just one table's fields

schema = iq.get_database_schema()              # the full raw record, if you need
                                                # something list_table_names()/
                                                # list_fields() don't expose
```

All three default to whichever test `use_test()` set, or take an explicit
`database_id=` like every other call in this guide.

---

## 11. Query multiple databases

Every method that touches a specific test accepts `database_id=`
directly, overriding whatever `use_test()` set — handy for a script that
compares results across several test runs without juggling multiple
`IQClient` instances:

```python
ids = [t["id"] for t in iq.list_tests(owner="jdoe")]

for db_id in ids:
    rows = iq.query(name="Detailed Stream Results", database_id=db_id, limit=10)
    print(db_id, len(rows), "rows")
```

See [`examples/multi_database_query.py`](examples/multi_database_query.py)
for a complete version.

---

## 12. Rename or delete a test database

```python
iq.rename_test("New Test Name", database_id="abc123")

iq.delete_test(database_id="abc123")     # PERMANENT -- removes all results and snapshots
```

`delete_test()` is irreversible — there's no undo, and no confirmation
prompt built into the client. Useful for CI/CD pipelines cleaning up
completed test results after processing them, but double-check
`database_id` before calling it against anything you might still need.

---

## 13. Generate and download a report

```python
templates = iq.list_report_templates()
template_id = templates[0]["id"]

path = iq.generate_report(
    template_id=template_id,
    title="Nightly Regression Report",     # required -- the server 400s without it
    format="pdf",                          # lowercase -- "PDF" also 400s
    output_path="report.pdf",
)
```

`title=` and lowercase `format=` are both required by the real server,
not just style preferences. Without `output_path=`, `generate_report()`
returns the raw report object (including its `id`) instead of downloading
anything — useful if you want to poll for completion yourself:

```python
report = iq.generate_report(template_id=template_id, title="Nightly Regression Report")
# ... later, once it's finished generating ...
iq.download_report(report["id"], save_as="report.pdf")
```

> **Report generation is asynchronous on the server.** Passing
> `output_path=` downloads immediately — if the report hasn't finished
> generating yet, you can end up with an incomplete or 0-byte file for a
> report that takes more than an instant to produce. Check `get_report(id)`'s
> status field yourself and only call `download_report()` once it reports
> done, for anything beyond a trivially small report.

---

## 14. Run a raw JSON query definition

For a query the built-in view/filter helpers don't cover — or one
captured directly from the GUI's own network traffic (DevTools → the
`POST /queries` request body) — pass it straight through as
`definition=`, either as a Python dict or a JSON string:

```python
import json

with open("captured_query.json") as f:
    definition = json.load(f)

rows = iq.query(definition=definition)

# A JSON string works too -- no need to json.loads() it yourself:
rows = iq.query(definition='{"multi_result": {"subqueries": [...], "limit": 100}}')
```

`filters=`/`sort=`/`group_by=`/`time_range=`/`limit=` still work with
`definition=` — they're applied to the definition's outermost node the
same way as with `name=` — except display-name resolution (since there's
no view to resolve GUI labels against; use raw attribute paths or
whatever alias the captured definition itself uses).

See [`examples/run_json_definition_query.py`](examples/run_json_definition_query.py).

---

## 15. Handle errors

Every exception `tciqrestclient` raises is a subclass of `IQError`:

| Exception | Raised when |
|---|---|
| `IQConfigError` | No connection info could be resolved at all — no `base_url`/`host`/`install_dir`/AION settings found anywhere. |
| `IQConnectionError` | orion-res's address couldn't be discovered (e.g. AION login or inventory lookup failed). |
| `IQRequestError` | An HTTP request to orion-res failed or returned a non-2xx response. |
| `IQQueryError` | A query couldn't be built or run — bad `filters=`/`sort=` shape, malformed `definition=` JSON, neither/both of `name=`/`definition=` given, no `database_id` available, etc. |
| `IQViewError` | A named-view operation failed — view not found, no table matches the requested `data_type=`, etc. |
| `IQReportError` | Report generation/download failed (e.g. missing `title=`). |

```python
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQError, IQRequestError

iq = IQClient()
try:
    rows = iq.query(name="Detailed Stream Results")
except IQRequestError as e:
    print("Server rejected the request:", e)
except IQError as e:
    print("tciqrestclient error:", e)
```

Catching the base `IQError` is usually enough for a script that just
wants to report a failure and move on; catch the specific subclasses
when you need to react differently (e.g. retry on `IQRequestError` but
not on `IQViewError`).

**`query(name=..., auto_repair=True)`** (the default) has one extra
built-in recovery: a view's query template is shared across every
database that uses that view, but not every database's actual data has
every column the template can reference (e.g. an optional per-protocol
config column that only exists for a test that used that config).
`auto_repair` catches exactly that "unknown attribute" error, drops the
offending column, and retries — silently. Check `iq.last_dropped_columns`
after a call if you want to know whether (and which) columns were
dropped from the result:

```python
rows = iq.query(name="Detailed Stream Results")
if iq.last_dropped_columns:
    print("Missing from this database:", iq.last_dropped_columns)
```

Pass `auto_repair=False` to turn this off and let the original
`IQRequestError` propagate instead.

---

## 16. Debug a request

Pass `debug=True` to `IQClient()` (or set `TCIQ_DEBUG=1`) to print every
request's method, URL, and JSON body — plus timing — before it's sent.
Invaluable for comparing what `tciqrestclient` sends against what the GUI's own
DevTools network tab shows for the same action:

```python
iq = IQClient(debug=True)
```

If a specific call is slow rather than wrong (a server with hundreds of
views/tests can take longer than the default 10s timeout just to list
them), pass `timeout=` to that one call instead of raising the timeout
globally:

```python
views = iq.list_views(timeout=60)
rows = iq.query(name="Detailed Stream Results", timeout=60)
```

Narrowing the query itself (`filters=`, `time_range=`, a smaller `limit=`)
is the better fix when it's the *query* that's slow — a longer timeout
doesn't reduce how much work the server has to do, but it does help when
it's specifically the `/views` lookup itself (needed to resolve `name=`)
that's slow on a server with many views.

---

## 17. Example scripts

Every script in [`examples/`](examples/) is runnable end-to-end against a
real server (edit the connection settings/owner/view names at the top of
each as needed):

| Script | Demonstrates |
|---|---|
| `discover_local.py` | Direct URL / host-port / install-dir discovery modes |
| `discover_aion.py` | AION platform discovery |
| `list_tests_by_owner.py` | `list_tests(owner=...)`, `use_test()` |
| `fetch_view_data.py` | Exercising every `query()` feature generically against any view |
| `run_view_query.py` | A basic named-view query |
| `run_live_query.py` | `test_live=True/"live"` vs `False/"eot"`, plus `user=` to auto-find a running test |
| `query_modifiers.py` | `filters=`, `sort=`, `group_by=`, `time_range=` |
| `run_json_definition_query.py` | Raw JSON `definition=` queries |
| `modify_query_definition.py` | Editing a query definition's raw dict directly (OR-combined filters, removing a projection, overwriting `orders=`) — for when `filters=`/`sort=`/`group_by=` aren't expressive enough |
| `aion_end_to_end.py` | Connecting via AION, then the same query/view coverage as the local-mode examples, against whatever the AION deployment actually has |
| `bulk_cleanup_databases.py` | `delete_databases_over_size()`/`delete_databases_older_than()` — bulk cleanup, dry-run by default |
| `run_xy_chart_query.py` | An `x_y_chart` view — **confirmed broken against a real server, see the callout at the top of this guide** |
| `run_pie_chart_query.py` | A `pie_chart` view — unconfirmed against a real server |
| `run_histogram_query.py` | A `histogram` view (the `{name: rows}` return shape) — **confirmed broken against a real server, see the callout at the top of this guide** |
| `run_boxplot_query.py` | A `boxplot` view — unconfirmed against a real server |
| `manage_views.py` | `save_view()`/`list_view_columns()`/`query(name=...)`/`delete_view()` — the full custom-view lifecycle |
| `inspect_database_schema.py` | `list_table_names()`, `list_fields()`, `get_database_schema()` |
| `multi_database_query.py` | Looping `query(database_id=...)` across several tests |
| `manage_test_database.py` | `rename_test()`, `delete_test()` |
| `auto_repair_demo.py` | `auto_repair=True` and `last_dropped_columns` |
| `generate_report.py` | `generate_report()`, `download_report()` |

Run any of them the normal way, from the `tciqclient` directory:

```bash
python examples/run_view_query.py
```

---

## 18. Quick reference

```python
from tciqrestclient import IQClient, IQError, IQViewError   # all public names are in __all__

iq = IQClient(base_url=None, host=None, port=None, install_dir=None,
              database_id=None, timeout=None, use_https=False,
              load_env=True, env_file=None, session=None, debug=None,
              aion_url=None, aion_username=None, aion_password=None,
              aion_node_name=None, aion_port_name=None, aion_ca_cert=None)

# Tests / databases
iq.list_tests(owner=None, detail="summary")
iq.get_test(database_id=None)
iq.use_test(database_id)
iq.rename_test(new_name, database_id=None)
iq.delete_test(database_id=None)                      # irreversible
iq.get_database_schema(database_id=None)
iq.list_table_names(database_id=None)
iq.list_fields(table_name=None, database_id=None)

# Views
iq.list_views(timeout=None)
iq.get_view(view_id, timeout=None)
iq.find_view(name, timeout=None)
iq.list_view_columns(name, test_live=None, active_only=False,
                      timeout=None, data_type=None, table_index=None)
iq.save_view(name, details=None, description="", definition=None)
iq.delete_view(view_id=None, name=None, timeout=None)

# Query -- the one method for every view type
iq.query(name=None, test_live=None, database_id=None, user=None,
         snapshot_name=None, filters=None, sort=None, group_by=None,
         time_range=None, limit=1000, mode="once", raw_result=False,
         timeout=None, auto_repair=True,
         definition=None, data_type=None, table_index=None)  # last 3: advanced/legacy
iq.last_dropped_columns                               # after a query() call

# Reports
iq.list_report_templates()
iq.get_report_template(template_id)
iq.generate_report(template_id, title=None, database_id=None,
                    format="pdf", output_path=None, **extra)
iq.get_report(report_id)
iq.download_report(report_id, save_as=None)
```

Exceptions: `IQError` (base), `IQConfigError`, `IQConnectionError`,
`IQRequestError`, `IQQueryError`, `IQViewError`, `IQReportError`.

---

## 19. Where to go next

- [`QUICKSTART.md`](QUICKSTART.md) — the five-step fast path, if this guide's depth is more than you need right now.
- [`API_REFERENCE.md`](API_REFERENCE.md) — complete symbol-by-symbol reference (every parameter, return shape, exception) once you know which method you want, rather than this guide's task-by-task organization.
- [`README.md`](README.md) — short overview, install, and the discovery precedence table.
- [`TESTING.md`](TESTING.md) — running the automated test suite, packaging checks, and the manual/integration test plan against a real server.
- [`HANDOVER.md`](../HANDOVER.md) at the repo root — full architecture writeup, per-requirement status against the product requirements, and known gaps/next steps for anyone extending `tciqrestclient` itself.
- [`examples/`](examples/) — one runnable script per use case (see [§17](#17-example-scripts)).
