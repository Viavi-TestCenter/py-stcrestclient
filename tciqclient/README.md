# tciqrestclient — Python Client for TestCenter IQ

`tciqrestclient` is a standalone Python client for TestCenter IQ's `orion-res` results
service REST API. It gives automation engineers Python-native access to
IQ's named views, live/snapshot data, query modifiers, database lifecycle
management, and report generation — without hand-crafting query JSON or
managing discovery/reconnect logic themselves.

It is packaged independently of `stcrestclient` (no WAMP, no socket code,
no shared dependency) but is designed to be installed alongside it — see
[Installation](#installation).

## Installation

```bash
pip install -e ".[test]"      # from this directory, editable + test deps
# or, once published:
pip install tciqrestclient
```

Requires Python 3.8+.

**Don't have this repo cloned?** See
[`GETTING_STARTED.md`](GETTING_STARTED.md) — it covers installing
straight from this repo's URL (no manual `git clone` needed) and using
every feature, entirely self-contained.

## Quick Start

See [`QUICKSTART.md`](QUICKSTART.md) — five steps from install to your
first real result, no reading required beyond that page.

> **Every query is one HTTP request.** "Live" means calling `query()` again
> when you want fresh data — there is no subscription or long-poll mode.

See [`examples/`](examples/) for one runnable script per use case (named
views, live queries, each chart widget type, report generation, and both
discovery modes), or [`QUICKGUIDE.md`](QUICKGUIDE.md) for a detailed,
task-by-task walkthrough of the whole API with copy-pasteable examples.

## Discovery

Precedence (highest to lowest): explicit `base_url` kwarg → explicit
`host`/`port` kwarg → `install_dir` kwarg → explicit `aion_url` kwarg →
`TCIQ_BASE_URL` env → `TCIQ_HOST`/`TCIQ_PORT` env → `TCIQ_INSTALL_DIR` env
→ AION resolved purely from `TCIQ_AION_*` env vars (lowest priority).
Every explicit kwarg outranks every environment variable, including
`aion_url=` beating an ambient `TCIQ_BASE_URL` left over in your shell.

| Option | How to use |
|---|---|
| Explicit base URL | `TCIQ_BASE_URL=http://127.0.0.1:9200` |
| Explicit host/port | `TCIQ_HOST` + `TCIQ_PORT` (always pass both — `host` alone composes a URL with no port at all, it does not look one up) |
| Local STC install | `TCIQ_INSTALL_DIR=<dir>` (reads `orion-res.yaml`) |
| Remote STC | `TCIQ_INSTALL_DIR=<dir>` (reads `stcbll.ini`) |
| AION platform | `TCIQ_AION_URL` + `TCIQ_AION_USERNAME` + `TCIQ_AION_PASSWORD` |

Every option can also be passed as a constructor kwarg to `IQClient()`;
explicit kwargs always override the environment. See `.env.example` for
the full list of recognized `TCIQ_*` variables, and `tciqrestclient/config.py`'s
module docstring for the authoritative reference.

## API Surface

See [`API_REFERENCE.md`](API_REFERENCE.md) for the complete,
method-by-method reference (every parameter, return shape, and
exception) — the summary below is just an index.

Import only from the top-level package:

```python
from tciqrestclient import IQClient, IQError, IQViewError   # all public names are in __all__
```

| Area | Key methods |
|---|---|
| Tests / databases | `list_tests()`, `get_test()`, `use_test()`, `delete_test()`, `rename_test()`, `get_database_schema()`, `list_table_names()`, `list_fields()` |
| Views | `list_views()`, `get_view()`, `find_view()`, `list_view_columns()`, `save_view()`, `delete_view()` |
| Query | `query(name=... \| definition=..., test_live=, database_id=\|user=, snapshot_name=, filters=, sort=, group_by=, time_range=, limit=, timeout=, auto_repair=)` |
| Reports | `list_report_templates()`, `generate_report()`, `get_report()`, `download_report()` |

`query()` is the single public query method for every view type — it
inspects the view's `view_type` internally and dispatches accordingly. It
returns a plain `list[dict]` for `single_level_table`,
`paged_single_level_table`, `x_y_chart`, `pie_chart`, and any
`definition=` call, or a `{name: list[dict]}` dict for `histogram`
(one query per provider) and `boxplot` (one query per statistic).

> **`x_y_chart` and `histogram` are confirmed broken against a real
> server** — `query(name=...)` currently raises `IQViewError` for both
> (`pie_chart`/`boxplot` are unconfirmed either way). Only
> `single_level_table`/`paged_single_level_table` (the common "table"
> view type) are confirmed working end-to-end. See `HANDOVER.md` §9
> ("Widget query builders") for the root cause and status of each type.

All errors raise a subclass of `IQError` (`IQConfigError`,
`IQConnectionError`, `IQRequestError`, `IQQueryError`, `IQViewError`,
`IQReportError`) — see `tciqrestclient/exceptions.py`.

## Running the Tests

All HTTP is mocked via the `responses` library — no running orion-res
server is needed.

```bash
pytest                    # from this directory
pytest -v                 # verbose
pytest -s                 # show stdout
```

See [`TESTING.md`](TESTING.md) for the full guide — automated tests,
packaging/build checks, and the manual/integration test plan for
validating this client against a real `orion-res`/AION server (including
how to re-capture the fixtures needed to un-skip the 33 tests that depend
on real captured data).

## Further Reading

See [`QUICKSTART.md`](QUICKSTART.md) for the fastest path to your first
result, and [`API_REFERENCE.md`](API_REFERENCE.md) for the complete
symbol-by-symbol reference once you know which method you're looking
for. See [`GETTING_STARTED.md`](GETTING_STARTED.md) if you (or whoever
you're handing this to) don't have this repo cloned — it's a fully
self-contained usage guide that works from just a `pip install`. See
[`QUICKGUIDE.md`](QUICKGUIDE.md) for the equivalent full task-by-task
guide assuming you do have the repo (it also links to the runnable
`examples/` scripts), and [`HANDOVER.md`](../HANDOVER.md) at the
repository root for the full architecture writeup, per-requirement
status against the PRD, known gaps, and prioritized next steps.
