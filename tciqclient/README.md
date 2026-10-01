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

## Quick Start

```python
from tciqrestclient import IQClient

iq = IQClient()                      # discovers orion-res via env/config
rows = iq.query(name="My View")      # one HTTP request per call
```

> **Every query is one HTTP request.** "Live" means calling `query()` again
> when you want fresh data — there is no subscription or long-poll mode.

See [`examples/`](examples/) for one runnable script per use case (named
views, live queries, each chart widget type, report generation, and both
discovery modes).

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

Already have `AION_URL`/`AION_USERNAME`/`AION_PASSWORD` set for
`stcrestclient`'s `AionStcHttp` against the same AION deployment? Each
`TCIQ_AION_*` variable above falls back to its bare (no `TCIQ_` prefix)
counterpart if unset, so both packages can share one set of AION
credentials — no need to set the same login twice under two different
names.

## API Surface

The table below is an index of the key methods; see each method's own
docstring in `tciqrestclient/*.py` for the complete parameter, return
shape, and exception reference.

Import only from the top-level package:

```python
from tciqrestclient import IQClient, IQError, IQViewError   # all public names are in __all__
```

| Area | Key methods |
|---|---|
| Tests / databases | `list_tests()`, `get_test()`, `use_test()`, `delete_test()`, `rename_test()`, `get_database_schema()`, `list_table_names()`, `list_fields()` |
| Views | `list_views()`, `get_view()`, `find_view()`, `list_view_columns()`, `save_view()`, `delete_view()` |
| Profiles | `list_profiles()` — a saved collection of views plus dashboard layout |
| Query | `query(name=... \| definition=..., test_live=, database_id=\|user=, snapshot_name=, filters=, sort=, group_by=, time_range=, limit=, timeout=, auto_repair=)` |
| Reports | `list_report_templates()`, `generate_report()`, `get_report()`, `download_report()` |

`query()` is the single public query method for every view type — it
inspects the view's `view_type` internally and dispatches accordingly. It
returns a plain `list[dict]` for `single_level_table`,
`paged_single_level_table`, and any `definition=` call, or a
`{name: list[dict]}` dict for `x_y_chart`/`histogram` (one query per
provider), `boxplot` (one query per statistic), and `chart` (one query
per real numeric series, e.g. "Port Frame Rate Chart" —
`table_index=`/`snapshot_name=` both raise `IQViewError` for it).

> **`pie_chart`/`boxplot` are unconfirmed against a real server** — no
> real `pie_chart` view has ever been found anywhere to even test
> against. `single_level_table`/`paged_single_level_table` (the common
> "table" view type), `x_y_chart`, `chart`, and `histogram` are all
> confirmed working end-to-end.

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
