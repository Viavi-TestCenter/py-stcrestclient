# tciqrestclient Quickstart

The fastest path from zero to your first real result. Five steps, no
reading required beyond this page — for everything else (every feature,
every parameter, troubleshooting), see [`QUICKGUIDE.md`](QUICKGUIDE.md)
(if you have this repo checked out) or
[`GETTING_STARTED.md`](GETTING_STARTED.md) (if you don't).

## 1. Install

```bash
pip install -e .          # from this directory (tciqclient/)
```

No repo checked out? See [`GETTING_STARTED.md`](GETTING_STARTED.md) §1 —
`pip` can install straight from this repo's URL, no manual clone needed.

## 2. Point it at your server

Pick **one** of these — environment variables, a `.env` file, or
`IQClient()` keyword arguments all work identically:

```bash
export TCIQ_BASE_URL=http://127.0.0.1:9200
```

Don't know the address? See [`QUICKGUIDE.md` §2](QUICKGUIDE.md#2-configure-the-connection)
for install-dir and AION discovery instead of a hardcoded URL.

## 3. Run your first query

```python
from tciqrestclient import IQClient

iq = IQClient()

rows = iq.query(
    "Detailed Stream Results",   # any named view, exactly as in the GUI
    "live",                      # or omit entirely for snapshot data (the default)
    user="jdoe",                 # auto-finds jdoe's one running test
)
for row in rows[:5]:
    print(row)
```

No test currently running? Point at a finished one directly instead:

```python
tests = iq.list_tests(owner="jdoe")
rows = iq.query("Detailed Stream Results", database_id=tests[0]["id"])
```

## 4. Add filters, sort, and a limit

```python
rows = iq.query(
    "Detailed Stream Results", database_id=tests[0]["id"],
    filters=[("frame_count", "gt", 0)],   # GUI label, raw path, or bare column name all work
    sort="frame_count DESC",
    limit=100,
)
```

## 5. Handle errors

```python
from tciqrestclient.exceptions import IQError

try:
    rows = iq.query("Detailed Stream Results", database_id=tests[0]["id"])
except IQError as e:
    print("tciqrestclient error:", e)
```

That's it — you're up and running. From here:

| Want to... | See |
|---|---|
| See every feature with full explanations | [`QUICKGUIDE.md`](QUICKGUIDE.md) / [`GETTING_STARTED.md`](GETTING_STARTED.md) |
| Look up an exact method's parameters/return/exceptions | [`API_REFERENCE.md`](API_REFERENCE.md) |
| Save/reuse/delete named views | [`QUICKGUIDE.md` §9](QUICKGUIDE.md#9-create-reuse-and-delete-your-own-views) |
| Inspect a database's schema | [`QUICKGUIDE.md` §10](QUICKGUIDE.md#10-inspect-a-databases-schema) |
| Generate a report | [`QUICKGUIDE.md` §13](QUICKGUIDE.md#13-generate-and-download-a-report) |
| See a runnable example per use case | [`examples/`](examples/) |
| Know what's tested and what to run before a release | [`TESTING.md`](TESTING.md) |
| Understand the architecture / known gaps | [`HANDOVER.md`](../HANDOVER.md) |
