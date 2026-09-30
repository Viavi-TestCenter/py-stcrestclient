# Getting Started with tciqrestclient (no repo clone needed)

Everything in this guide works from a single `pip install` — you do
**not** need to `git clone` this repository, check out any source files,
or run anything from inside it. If you just want to use `tciqrestclient` in your
own project or script, this is the only file you need to read. (If you
*do* have this repo checked out and want the example scripts, the
architecture writeup, or the test suite, see
[`README.md`](README.md)/[`QUICKGUIDE.md`](QUICKGUIDE.md) instead — they
assume you're working inside the repo.)

## Table of Contents

1. [Install](#1-install)
2. [Configure the connection](#2-configure-the-connection)
3. [A complete, copy-pasteable quickstart](#3-a-complete-copy-pasteable-quickstart)
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
16. [Known limitations](#16-known-limitations)
17. [Quick reference](#17-quick-reference)
18. [If you want more](#18-if-you-want-more)

---

## 1. Install

`tciqrestclient` is published to real, public PyPI
(https://pypi.org/project/tciqrestclient/):

```bash
pip install tciqrestclient
```

(or `pip install stcrestclient[iq]` to install it alongside
`stcrestclient` in one step).

If you need an unpublished commit instead — a fix that hasn't shipped a
new PyPI version yet, or a specific branch — `pip` can also install
directly from this repository's URL, with no manual `git clone` step:

```bash
pip install "git+https://github.com/Viavi-TestCenter/py-stcrestclient.git#subdirectory=tciqclient"
```

This is a private repo, so make sure `git` itself can already
authenticate to it (an existing SSH key, a Git credential manager, or a
personal access token) — the same credentials you'd use for any other
`git` command against this host. If you use SSH for GitHub, use the SSH
form instead:

```bash
pip install "git+ssh://git@github.com/Viavi-TestCenter/py-stcrestclient.git#subdirectory=tciqclient"
```

To pin a specific version instead of whatever `master` currently has,
add `@<tag-or-branch-or-commit>` right after `.git`:

```bash
pip install "git+https://github.com/Viavi-TestCenter/py-stcrestclient.git@v0.1.1#subdirectory=tciqclient"
```

Either way, verify the install:

```bash
python -c "import tciqrestclient; print(tciqrestclient.__version__)"
```

Requires Python 3.8+. Dependencies (`requests`, `python-dotenv`,
`PyYAML`) install automatically — nothing else to set up.

---

## 2. Configure the connection

`tciqrestclient` never hardcodes a server address. Pick exactly one of these —
each works as either a real environment variable or an `IQClient()`
keyword argument:

| Method | Environment variable(s) | Constructor kwarg(s) |
|---|---|---|
| **Direct URL** (simplest) | `TCIQ_BASE_URL=http://127.0.0.1:9200` | `base_url="http://127.0.0.1:9200"` |
| **Direct host/port** | `TCIQ_HOST=127.0.0.1`, `TCIQ_PORT=9200` (always set both) | `host="127.0.0.1", port=9200` |
| **STC install dir** | `TCIQ_INSTALL_DIR=<dir>` | `install_dir="<dir>"` |
| **AION platform** | `TCIQ_AION_URL`, `TCIQ_AION_USERNAME`, `TCIQ_AION_PASSWORD` | `aion_url=..., aion_username=..., aion_password=...` |

> Already set `AION_URL`/`AION_USERNAME`/`AION_PASSWORD` (no `TCIQ_`
> prefix) for `stcrestclient`'s `AionStcHttp`? Each `TCIQ_AION_*`
> variable above falls back to its bare counterpart when unset, so you
> don't need to set the same AION login twice.

You can set these as real environment variables, put them in a `.env`
file in your working directory (create one yourself — there's nothing to
copy since you don't have this repo checked out), or pass them straight
to `IQClient(...)`. All three work identically:

```bash
# .env — create this file yourself, next to your script
TCIQ_BASE_URL=http://127.0.0.1:9200
TCIQ_TIMEOUT=120
```

```python
# ...or skip the .env file entirely and pass it directly:
from tciqrestclient import IQClient
iq = IQClient(base_url="http://127.0.0.1:9200")
```

Other settings you can set the same way: `TCIQ_DATABASE_ID` (a default
test id, or just call `use_test()` at runtime instead), `TCIQ_TIMEOUT`
(HTTP timeout in seconds, default 120), `TCIQ_DEBUG=1` (log every request
before sending it).

**Precedence** when more than one is set: an explicit `IQClient(...)`
keyword argument always wins over the matching environment variable.
Among the discovery methods themselves: explicit `base_url` beats
`host`/`port` beats `install_dir` beats AION. See the docstring of
`tciqrestclient.config` (via `python -c "import tciqrestclient.config; help(tciqrestclient.config)"`,
no repo needed) for the exact rules if you're mixing methods.

> **Note:** `host=`/`TCIQ_HOST` must always be paired with `port=`/
> `TCIQ_PORT` — there is currently no way to give `tciqrestclient` just a bare host
> and have it look up the real port on its own.

---

## 3. A complete, copy-pasteable quickstart

```python
from tciqrestclient import IQClient

iq = IQClient(base_url="http://127.0.0.1:9200")   # or configure via .env — see §2

rows = iq.query(
    "Detailed Stream Results",                    # a named view, exactly as in the GUI
    "live",                                        # or False/"eot" for snapshot data (the default)
    user="jdoe",                                   # auto-finds jdoe's one running test
    filters=[("min_latency", "gt", 0)],
    sort="min_latency DESC",
)
for row in rows[:5]:
    print(row)
```

> **Every query is one HTTP request.** "Live" means calling `query()`
> again when you want fresh data — there is no subscription or
> long-poll mode.

Everything from here on is a deeper look at one piece of the above (and
everything else `tciqrestclient` can do) — read whichever sections you need.

---

## 4. Find your test

Every orion-res "database" is one test run's results. There's no owner
filter on the server itself, so `list_tests(owner=...)` filters
client-side on the `test.owner` metadata field (the GUI's "Run By"
column):

```python
tests = iq.list_tests(owner="jdoe")
for t in tests:
    print(t["id"], t["name"])

iq.use_test(tests[0]["id"])     # sets the default database_id for every
                                 # query()/get_test()/generate_report() call
                                 # below, until changed again
```

`use_test()` just remembers an id on the client instance — no network
call. Skip it and pass `database_id=` explicitly per call instead when a
script talks to more than one test at once (see
[§11](#11-query-multiple-databases)).

```python
iq.get_test()                        # full metadata for the current default test
iq.get_test(database_id="abc123")    # or a specific one, regardless of use_test()
```

For `query()` specifically, there's a third option: pass `user=` and
let it find the right `database_id` for you — see
[§6](#6-live-data-vs-snapshot-data).

---

## 5. Query a named view

`query()` is the **one** method for pulling rows out of any saved view —
it looks at the view's own `view_type` internally and builds the right
kind of request, rather than requiring a different call per widget type:

```python
rows = iq.query(name="Detailed Stream Results")
```

`rows` is a plain `list[dict]` — one dict per row, keyed by column name
— for the common case (table views, and every `definition=` call). Two
view types return one query's worth of rows *per sub-query* instead, as
a `{name: list[dict]}` dict: `histogram` (one entry per query provider)
and `boxplot` (one entry per statistic). See
[§16](#16-known-limitations) — `x_y_chart` and `histogram` currently
don't work at all against a real server.

By default `query()` caps results at 1000 rows — pass `limit=` to
change that, or `limit=None` to leave the view's own limit untouched:

```python
rows = iq.query(name="Detailed Stream Results", limit=5000)
all_rows = iq.query(name="Detailed Stream Results", limit=None)
```

> **There is no live/subscription mode.** Every call to `query()` is one
> HTTP request/response.

---

## 6. Live data vs. snapshot data

A view can have more than one underlying table — most commonly a live
table (the test is still running) and a snapshot (`eot`, **e**nd **o**f
**t**est) table. **By default, `query()` returns snapshot data**, not
whatever table the view happens to list first:

```python
rows = iq.query("Detailed Stream Results")          # snapshot by default
rows = iq.query("Detailed Stream Results", True)     # explicitly live instead
rows = iq.query("Detailed Stream Results", False)    # explicitly snapshot
```

`test_live` (the 2nd positional argument, or `test_live=` by name) also
accepts the strings `"live"` or `"eot"`/`"snapshot"`, case-insensitively:

```python
rows = iq.query("Detailed Stream Results", "live")
```

An unrecognized `test_live=` string raises `IQQueryError`; a view with
no matching table raises `IQViewError` -- use
[§8](#8-discover-a-views-columns) if you're not sure what a view has.

**Finding the right test without a database_id:** pass `user=` and, for
live data, `query()` finds the one test that user currently has running
and uses it automatically:

```python
rows = iq.query("Detailed Stream Results", "live", user="jdoe")
```

This only works for live data -- a user can have many *completed*
tests with no way to tell which one you mean, so `user=` for snapshot
data raises `IQQueryError` asking for an explicit `database_id=`
instead of guessing.

If a test has multiple named snapshots and you want just one, add
`snapshot_name=` (only valid alongside snapshot data):

```python
rows = iq.query(
    "Detailed Stream Results", False, database_id="abc123",
    snapshot_name="Baseline Run")
```

**Advanced/rarely needed:** `data_type=` (a table's exact `data_type`
string) and `table_index=` (pick a table by raw position) still work as
lower-level alternatives to `test_live=`.

---

## 7. Filter, sort, group, and limit a query

`filters=`, `sort=`, `group_by=`, and `time_range=` accept plain Python
values — no need to hand-build query-expression strings. With `name=`,
a field can be given as its GUI display name (e.g. `"Rx Count"`,
case-insensitive), raw attribute path (e.g.
`"rx_stream_stats.frame_count"`), a bare column name with no table
prefix (e.g. `"min_latency"`) *when it's unambiguous*, or internal
alias — all resolve to the same column (see
[§8](#8-discover-a-views-columns) to see what's available).

```python
rows = iq.query(
    "Detailed Stream Results",
    filters=[
        ("min_latency", "gt", 0),              # (field, op, value) -- bare name
        ("Rx Count", 100),                     # (field, value) -- op defaults to "eq"
    ],
    sort="min_latency DESC",                   # or [("min_latency", "DESC"), (...)]
    group_by="tx_stream_stream_id",            # or a list of field names
    time_range=("start_time", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"),
    limit=200,
)
```

> A bare column name only resolves when it's unambiguous -- if two
> columns on the same view end in the same name (e.g. both
> `tx_stream_stats.frame_count` and `rx_stream_stats.frame_count`
> exist), a bare `"frame_count"` is deliberately left unresolved rather
> than guessing; qualify it or use its GUI display name instead in that
> case.

Filter operators: `eq` (default), `ne`, `lt`, `lte`, `gt`, `gte`,
`contains` (substring match), and `in` (value is a list). `time_range=`
needs an explicit field name, and either bound can be `None` for an
open-ended range.

For a `histogram`/`boxplot` view, the same `filters=`/`sort=`/etc. are
applied identically to every one of its underlying sub-queries.

---

## 8. Discover a view's columns

Before writing filters/sort against a view you haven't used before,
list its columns to see the exact display names, aliases, and raw
attribute paths available:

```python
columns = iq.list_view_columns("Detailed Stream Results", active_only=True)
for c in columns[:5]:
    print(c["display_name"], "->", c["alias_name"], "/", c["name"])
```

`active_only=False` (the default) lists every column the view's query
provider *supports*; `active_only=True` restricts the list to columns
actually active on this table.

---

## 9. Create, reuse, and delete your own views

Clone an existing view's `details` (its raw GUI table spec) under a new
name — there's no supported way to build a view's `details` from
scratch:

```python
source = iq.find_view("Detailed Stream Results")

iq.save_view(
    name="My CI View",
    details=source["details"],
    description="Created from tciqrestclient for CI reporting.",
)

rows = iq.query("My CI View", limit=5)   # reuse it immediately -- snapshot data by default

iq.delete_view(name="My CI View")                              # clean up when done
```

Other view operations:

```python
views = iq.list_views()                       # every view on the server
view = iq.get_view(view_id="abc123")          # by id
view = iq.find_view("My CI View")             # by display name, or None
iq.delete_view(view_id="abc123")              # by id
```

`list_views()`/`find_view()` can be slow on a server with hundreds of
views — pass `timeout=` to give a specific call more time:
`iq.list_views(timeout=60)`.

A *profile* is a different, larger thing than a view — a saved
collection of views plus their dashboard layout (the GUI's results
"template"):

```python
profiles = iq.list_profiles()                 # every profile on the server
profiles = iq.list_profiles(detail="summary") # smaller response -- omits each profile's layout
profiles = iq.list_profiles(view_id="abc123") # only profiles that reference this view
```

Each profile's `views` list only carries each referenced view's `id` —
pass one to `get_view()` (above) for its full definition.

---

## 10. Inspect a database's schema

```python
tables = iq.list_table_names()                # every result_set + dimension_set
for t in tables[:5]:
    print(t["name"], t["kind"])                # "result_set" or "dimension_set"

fields = iq.list_fields()                      # every field, across all tables
fields = iq.list_fields(table_name="test")     # just one table's fields
for f in fields[:5]:
    print(f["name"], f.get("type"))            # data type, when reported

schema = iq.get_database_schema()              # the full raw record, if you need more
```

---

## 11. Query multiple databases

Every method that touches a specific test accepts `database_id=`
directly, overriding whatever `use_test()` set:

```python
ids = [t["id"] for t in iq.list_tests(owner="jdoe")]
for db_id in ids:
    rows = iq.query(name="Detailed Stream Results", database_id=db_id, limit=10)
    print(db_id, len(rows), "rows")
```

---

## 12. Rename or delete a test database

```python
iq.rename_test("New Test Name", database_id="abc123")
iq.delete_test(database_id="abc123")     # PERMANENT -- removes all results and snapshots
```

`delete_test()` is irreversible — no undo, no confirmation prompt built
into the client. Double-check `database_id` before calling it.
`rename_test()`'s exact wire format hasn't been confirmed against a real
server yet — see [§16](#16-known-limitations).

---

## 13. Generate and download a report

```python
templates = iq.list_report_templates()

path = iq.generate_report(
    templates[0]["id"],
    title="Nightly Regression Report",     # required -- the server 400s without it
    format="pdf",                          # lowercase -- "PDF" also 400s
    output_path="report.pdf",
)
```

> **Report generation is asynchronous on the server.** Passing
> `output_path=` downloads immediately — if the report hasn't finished
> generating yet, you can get an incomplete or 0-byte file. For anything
> beyond a trivially small report, generate without `output_path=`, poll
> `iq.get_report(report["id"])`'s status yourself until it's done, then
> call `iq.download_report(report["id"], save_as="report.pdf")`.

---

## 14. Run a raw JSON query definition

For a query the built-in filter helpers don't cover — or one captured
directly from the GUI's own network traffic — pass it as `definition=`,
either as a Python dict or a JSON string:

```python
rows = iq.query(definition='{"multi_result": {"subqueries": [...], "limit": 100}}')
```

`filters=`/`sort=`/`group_by=`/`time_range=`/`limit=` still work with
`definition=` (applied to its outermost node), except GUI display-name
resolution (there's no view to resolve labels against — use raw
attribute paths or whatever alias the definition itself uses).

---

## 15. Handle errors

Every exception `tciqrestclient` raises is a subclass of `IQError`:

| Exception | Raised when |
|---|---|
| `IQConfigError` | No connection info could be resolved at all. |
| `IQConnectionError` | orion-res's address couldn't be discovered (e.g. AION login failed). |
| `IQRequestError` | An HTTP request to orion-res failed or returned a non-2xx response. |
| `IQQueryError` | A query couldn't be built or run (bad `filters=` shape, malformed `definition=` JSON, no `database_id`, etc.). |
| `IQViewError` | A named-view operation failed (view not found, no matching `data_type=`, etc.). |
| `IQReportError` | Report generation/download failed (e.g. missing `title=`). |

```python
from tciqrestclient.exceptions import IQError, IQRequestError

try:
    rows = iq.query(name="Detailed Stream Results")
except IQRequestError as e:
    print("Server rejected the request:", e)
except IQError as e:
    print("tciqrestclient error:", e)
```

`query(name=..., auto_repair=True)` (the default) has one extra built-in
recovery: a view's query template can reference a column a specific
database's data doesn't have; `auto_repair` catches that, drops the
column, and retries silently. Check `iq.last_dropped_columns` after a
call to see whether anything was dropped.

---

## 16. Known limitations

Being upfront about what doesn't work yet, so you don't lose time
discovering it yourself:

- **`x_y_chart` and `histogram` views are confirmed broken** —
  `query(name=...)` currently raises `IQViewError` against a real server
  for both. `pie_chart`/`boxplot` are unconfirmed either way. Only
  `single_level_table`/`paged_single_level_table` (the common "table"
  view type) and `definition=` calls are confirmed working.
- **Report generation's async completion isn't handled for you** — see
  the callout in [§13](#13-generate-and-download-a-report).
- **`host=` always needs `port=`** — there's no way to give `tciqrestclient` just
  a bare host and have it discover the real port for you; use
  `install_dir=` or AION discovery instead if you don't already know the
  port (see [§2](#2-configure-the-connection)).
- **`rename_test()`'s exact wire format hasn't been confirmed** against
  a real server — it's implemented, unit-tested against mocks, but not
  yet verified end-to-end.

---

## 17. Quick reference

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
iq.list_profiles(view_id=None, detail=None, timeout=None)

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

## 18. If you want more

This file is deliberately self-contained. If you'd like the runnable
example scripts, the automated test suite, the full architecture
writeup, a symbol-by-symbol API reference (`API_REFERENCE.md`), or an
even shorter five-step version of this guide (`QUICKSTART.md`) — none
of which are needed just to *use* `tciqrestclient` — they live in the source
repository:
<https://github.com/Viavi-TestCenter/py-stcrestclient> (see `tciqclient/`
for everything IQ-related). You can browse those files directly on
GitHub with no clone needed either, or run the `pip install` command
from [§1](#1-install) again with `#subdirectory=tciqclient` to fetch a
copy into `pip`'s own build cache.

---

## Appendix: publishing `tciqrestclient` to PyPI (maintainers only)

Everything above this line is for *using* `tciqrestclient`. This last section is
for whoever maintains this package, so that `pip install tciqrestclient` in
[§1](#1-install) actually works for everyone else — skip it if that's
not you. (The full, always-current version of this checklist lives in
`HANDOVER.md` §10 for anyone with this repo checked out; it's repeated
here since this file is meant to stand alone.)

> **Note:** this package was previously published to real PyPI under the
> name `tciq` (versions `0.1.0`/`0.1.1` — still live at
> `https://pypi.org/project/tciq/`) before being renamed to
> `tciqrestclient`. Those old releases are left as-is, unmaintained.
> **`tciqrestclient` itself has now also been published** — `0.1.1` on
> 2026-09-23 (as a separate, from-scratch PyPI project), `0.1.2` on
> 2026-09-24, then `0.1.3` on 2026-09-28 at
> `https://pypi.org/project/tciqrestclient/0.1.3/`. The steps below are
> kept as a reference for the *next* version bump, not a from-scratch
> first-time walkthrough anymore.

1. **Check the name is free**: only relevant before a project's very
   first upload — moot now that `tciqrestclient` is already published at
   `https://pypi.org/project/tciqrestclient/`. (For any *other* future
   rename, visit that name's own PyPI URL first: a 404 means it's free;
   if someone else already owns it, `pyproject.toml`'s `name=` — and the
   import path everyone would use — needs to change before publishing.)
2. **PyPI account**: already have one — the same account used for both
   `tciq`'s and `tciqrestclient`'s real publishes. (Only relevant from
   scratch: create one at `https://pypi.org/account/register/`,
   optionally a TestPyPI account too for a dry run, and enable 2FA — PyPI
   requires it for uploads.)
3. **API token**: PyPI account → *Account settings* → *API tokens* →
   *Add API token*. `tciqrestclient`'s first upload necessarily used an
   "Entire account"-scoped token (a project-scoped one can't be created
   before that project's first upload) — that account-wide token should
   now be deleted and replaced with one scoped just to the
   `tciqrestclient` project, for every upload after this first one.
4. **Install the tools**: `pip install --upgrade build twine`.
5. **Build and check** (from a checkout's `tciqclient/` directory):
   ```bash
   python -m build
   twine check dist/*
   ```
6. **(Recommended) dry run on TestPyPI first**:
   ```bash
   twine upload --repository testpypi dist/*
   # username: __token__   password: <the TestPyPI token>
   pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ tciqrestclient
   ```
   (`--extra-index-url` is needed because `requests`/`python-dotenv`/
   `PyYAML` aren't published on TestPyPI.)
7. **Publish for real**:
   ```bash
   twine upload dist/*
   # username: __token__   password: <the real PyPI token, starts with "pypi-">
   ```
   Or store credentials in `~/.pypirc` (a `[pypi]` section with
   `username = __token__` / `password = pypi-...`) or as
   `TWINE_USERNAME`/`TWINE_PASSWORD` environment variables instead of
   typing them interactively.
8. **Verify**: `pip install tciqrestclient` in a brand-new venv, then
   `python -c "import tciqrestclient; print(tciqrestclient.__version__)"`.
   (Already done for the `0.1.1`, `0.1.2`, and `0.1.3` publishes — see
   the note above.)

**Before step 7 specifically**: a version number can never be reused on
PyPI once uploaded — no re-upload, no true delete, only "yanking" a
release (which hides it but doesn't free the number). `0.1.3` is now
published; the *next* fix or feature ships as `0.1.4`/`0.2.0`, never a
re-published `0.1.3` — make that a deliberate call, not an accident.

**Optional, for later releases**: PyPI's "Trusted Publishing" lets a
GitHub Actions workflow upload directly via OIDC, with no stored API
token at all — worth setting up once the first manual publish above is
done, so future version bumps don't need a human to run `twine upload`
by hand.
