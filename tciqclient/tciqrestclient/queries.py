"""POST /queries wrapper -- PLAN.md, section 2.3.

Every query, live or snapshot, is one request/response: mode="once"
returns the result synchronously in the same response. No WAMP, no
polling, no subscriptions -- "live" just means the caller re-runs the
query when they want fresh data.
"""
from .exceptions import IQQueryError


def run_query(transport, database_id, definition, mode="once",
               datastore_id="", timeout=None):
    """Execute a query and return the raw response (a dict with
    id/database/datastore/mode/context/result keys).

    Arguments:
    database_id  -- Database (test) id to query.
    definition   -- Query definition -- see tciqrestclient.query.merge_modifiers().
    mode         -- 'once' (default) for a synchronous result.
    datastore_id -- Optional; usually left as "" (server default).
    timeout      -- Optional per-call HTTP timeout override, in seconds.
                    Use this for queries expected to take longer than the
                    client's default timeout (e.g. large/unfiltered
                    result sets) instead of raising the default for every
                    call.
    """
    if not database_id:
        raise IQQueryError("database_id is required")
    if not definition:
        raise IQQueryError("definition is required")

    body = {
        "id": "",
        "database": {"id": database_id, "name": ""},
        "datastore": {"id": datastore_id or ""},
        "mode": mode,
        "definition": definition,
    }
    return transport.post("/queries", json_body=body, timeout=timeout)
