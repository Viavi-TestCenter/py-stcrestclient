"""Databases (= tests) listing, metadata, schema, and lifecycle management.

Each orion-res "database" is one test run's results. There is no
owner/user filter on the server side (confirmed against the real API), so
"get test IDs by username" is: fetch the list, then filter client-side on
metadata["test.owner"].
"""
import datetime

from .exceptions import IQError, IQRequestError

#: Confirmed real metadata key holding the username that ran the test
#: (shown as "Run By" in the TestCenter IQ GUI).
OWNER_METADATA_KEY = "test.owner"

#: Confirmed real metadata key holding a test's start time, as an ISO 8601
#: string (e.g. "2021-03-16T09:34:04.000Z") -- see tests/fixtures.py's
#: real captured DATABASES_RESPONSE. Used by list_databases_older_than().
STARTED_METADATA_KEY = "test.started"


def list_tests(transport, detail="summary", owner=None):
    """List tests (databases).

    Arguments:
    detail -- 'summary' (default) or 'full' (includes schema information
              such as table names and field descriptors when available).
    owner  -- Optional username to filter by (metadata["test.owner"]).
             Matched client-side since the server has no owner filter.

    Return:
    List of database dicts.
    """
    data = transport.get("/databases", params={"detail": detail})
    tests = data or []
    if owner:
        tests = [t for t in tests if _owner_of(t) == owner]
    return tests


def get_test(transport, database_id):
    """Get full metadata for one test (database) by id."""
    if not database_id:
        raise IQError("database_id is required")
    return transport.get("/databases/%s" % database_id)


def get_database_schema(transport, database_id):
    """Get the full schema for a database, including table and field info.

    Calls GET /databases/<id>?detail=full to retrieve the extended database
    record. CONFIRMED against a real server 2026-09-03 -- top-level keys
    are: id, datastore, name, description, metadata, first_created,
    last_updated, dimension_sets, result_sets, profile, summary. There is
    no top-level "tables" key -- see list_table_names()/list_fields()
    below for how "result_sets"/"dimension_sets" map to that concept (an
    earlier version of this docstring assumed "tables", which doesn't
    exist; those two functions were broken as a result until this fix).

    Arguments:
    database_id -- The database id to query.

    Return:
    Full database record dict.
    """
    if not database_id:
        raise IQError("database_id is required")
    return transport.get("/databases/%s" % database_id,
                         params={"detail": "full"})


def list_table_names(transport, database_id):
    """List the available tables within a database -- both its result
    sets (fact tables, e.g. "test_events") and dimension sets (lookup/
    reference tables, e.g. "test"). CONFIRMED against a real server
    2026-09-03: get_database_schema()'s response has no "tables" key;
    "result_sets" and "dimension_sets" are the real two lists, each a
    dict with at least {"name", "raw_name", "description", "summary"}
    plus "facts" (result_sets) or "attributes" (dimension_sets) -- see
    list_fields() below for those.

    Each returned dict is the server's own table descriptor, with one
    added key: "kind" -- "result_set" or "dimension_set" -- so callers
    (and list_fields()) can tell which field key it carries without
    guessing from shape alone.

    Arguments:
    database_id -- The database id to inspect.

    Return:
    List of table descriptor dicts. Empty list if the schema has neither
    a "result_sets" nor a "dimension_sets" key.
    """
    schema = get_database_schema(transport, database_id)
    tables = [dict(t, kind="result_set")
              for t in schema.get("result_sets") or []]
    tables += [dict(t, kind="dimension_set")
               for t in schema.get("dimension_sets") or []]
    return tables


def list_fields(transport, database_id, table_name=None):
    """List available fields in a database, optionally scoped to one
    table.

    Retrieves the full schema (via list_table_names(), see its docstring
    for the real result_sets/dimension_sets shape this was CONFIRMED
    against 2026-09-03) and extracts every result set's "facts" and every
    dimension set's "attributes" -- both are lists of {"name",
    "display_name", "description", "type", "unit"} field descriptors, per
    the real server's own shape.

    Arguments:
    database_id -- The database id to inspect.
    table_name  -- Optional table name to restrict the result to fields
                   belonging to that one result_set/dimension_set (match
                   against its "name" -- see list_table_names()). None
                   returns fields from every table.

    Return:
    List of field descriptor dicts.
    """
    fields = []
    for table in list_table_names(transport, database_id):
        if table_name is not None and table.get("name") != table_name:
            continue
        key = "facts" if table.get("kind") == "result_set" else "attributes"
        fields.extend(table.get(key) or [])
    return fields


def get_database_tables(transport, database_id):
    """Alias for list_table_names() -- same thing, under the name
    requested in review feedback. See list_table_names()'s docstring for
    the real return shape (result_sets/dimension_sets, each tagged with
    "kind")."""
    return list_table_names(transport, database_id)


def get_table_schema(transport, database_id, table_name):
    """Get one table's schema by name (its own descriptor dict -- "kind"
    plus "facts" or "attributes", per list_table_names()).

    Arguments:
    database_id -- The database id to inspect.
    table_name  -- The table's "name" (see list_table_names()) to look up.

    Return:
    The matching table descriptor dict.

    Raises:
    IQError -- if no table on this database has this name.
    """
    if not table_name:
        raise IQError("table_name is required")
    for table in list_table_names(transport, database_id):
        if table.get("name") == table_name:
            return table
    raise IQError(
        "no table named %r on database %r" % (table_name, database_id))


def get_database_summary(transport, database_id):
    """Get a database's summary metadata -- row count and storage size.

    CONFIRMED real shape (see tests/fixtures.py's captured
    DATABASES_RESPONSE): {"count": <row count>, "value_storage_kb": <int>,
    "index_storage_kb": <int>}. Already present on the plain (summary-
    detail) database record -- this doesn't need detail=full.

    Arguments:
    database_id -- The database id to inspect.

    Return:
    The database's "summary" dict, or {} if the server didn't include one.
    """
    return get_test(transport, database_id).get("summary") or {}


def _size_kb(test):
    """Total storage size (value + index, in KB) from a test's summary --
    see get_database_summary()'s docstring for the confirmed real keys.
    Missing/non-numeric values count as 0 rather than raising, since a
    still-importing or empty test can legitimately have no storage
    numbers yet."""
    summary = test.get("summary") or {}
    total = 0
    for key in ("value_storage_kb", "index_storage_kb"):
        try:
            total += float(summary.get(key) or 0)
        except (TypeError, ValueError):
            pass
    return total


def _started_at(test):
    """Parse a test's metadata["test.started"] (real ISO 8601 shape, e.g.
    "2021-03-16T09:34:04.000Z" -- see tests/fixtures.py -- confirmed both
    with and without a fractional-seconds component) into a naive UTC
    datetime, or None if missing/unparseable.

    fromisoformat() doesn't accept a bare "Z" suffix before Python 3.11
    -- swap it for "+00:00" first, which it does accept (with or without
    fractional seconds) on every supported Python version (3.8+).
    """
    value = (test.get("metadata") or {}).get(STARTED_METADATA_KEY)
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(
            value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def list_databases_over_size(transport, min_size_kb):
    """List databases whose total storage (value_storage_kb +
    index_storage_kb -- see get_database_summary()) is at least
    min_size_kb. Preview for delete_databases_over_size() -- doesn't
    delete anything.

    Arguments:
    min_size_kb -- Size threshold, in KB.

    Return:
    List of database dicts (full list_tests() shape, each still carrying
    its own "summary"), largest first.
    """
    matches = [t for t in list_tests(transport, detail="summary")
               if _size_kb(t) >= min_size_kb]
    matches.sort(key=_size_kb, reverse=True)
    return matches


def delete_databases_over_size(transport, min_size_kb, dry_run=True):
    """Bulk-delete every database at or over a size threshold.

    This is a destructive, irreversible, potentially multi-database
    operation -- dry_run=True (the default) does NOT delete anything; it
    only returns what would be deleted, same list as
    list_databases_over_size(). Pass dry_run=False to actually delete.

    Arguments:
    min_size_kb -- Size threshold, in KB (see list_databases_over_size()).
    dry_run     -- True (default): report matches without deleting. False:
                  delete every match.

    Return:
    The list of matching database dicts (whether or not they were
    actually deleted).
    """
    matches = list_databases_over_size(transport, min_size_kb)
    if not dry_run:
        for test in matches:
            delete_test(transport, test["id"])
    return matches


def list_databases_older_than(transport, days):
    """List databases whose metadata["test.started"] is more than `days`
    days in the past. Preview for delete_databases_older_than() -- doesn't
    delete anything. Databases with no parseable test.started are
    excluded (there's no age to compare -- see _started_at()).

    Arguments:
    days -- Age threshold, in days.

    Return:
    List of database dicts, oldest first.
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    matches = [t for t in list_tests(transport, detail="summary")
               if (_started_at(t) or cutoff) < cutoff]
    matches.sort(key=lambda t: _started_at(t) or cutoff)
    return matches


def delete_databases_older_than(transport, days, dry_run=True):
    """Bulk-delete every database older than a given age.

    This is a destructive, irreversible, potentially multi-database
    operation -- dry_run=True (the default) does NOT delete anything; it
    only returns what would be deleted, same list as
    list_databases_older_than(). Pass dry_run=False to actually delete.

    Arguments:
    days    -- Age threshold, in days (see list_databases_older_than()).
    dry_run -- True (default): report matches without deleting. False:
              delete every match.

    Return:
    The list of matching database dicts (whether or not they were
    actually deleted).
    """
    matches = list_databases_older_than(transport, days)
    if not dry_run:
        for test in matches:
            delete_test(transport, test["id"])
    return matches


def delete_test(transport, database_id):
    """Delete a test database (permanently removes stored results).

    This is a destructive, irreversible operation. The database and all
    of its snapshots and result data are removed from the IQ server.
    CI/CD pipelines can use this to clean up completed test results after
    processing them.

    Arguments:
    database_id -- The id of the database to delete.

    Raises:
    IQError       -- if database_id is falsy.
    IQRequestError -- if the server returns a non-2xx response.
    """
    if not database_id:
        raise IQError("database_id is required")
    transport.delete("/databases/%s" % database_id)


def rename_test(transport, database_id, new_name):
    """Rename a test database.

    CONFIRMED against a real server 2026-09-17 -- PUT /databases/<id>
    does NOT accept a partial body the way the rest of this codebase's
    PUT/PATCH-style calls do. Two real failure modes found (an earlier
    version of this function sent just `{"name": new_name}`, which had
    only ever been checked against mocks -- see HANDOVER.md):
      - `{"name": new_name}` alone 400s: `RESOURCE_ID_MISMATCH:
        "Resource identifier in URL doesn't match value in body"` -- the
        body must include `id` matching the URL.
      - `{"id": database_id, "name": new_name}` 500s with a real Go
        panic (`"assignment to entry in nil map"`) -- the handler
        apparently writes into a nested map (e.g. metadata) that comes
        back nil when the body doesn't already carry a full record.
    The only body shape that actually works: fetch the current full
    record (GET /databases/<id>, the same shape get_test() returns) and
    PUT it straight back with only `name` changed -- a full-object
    replace, not a partial patch.

    Arguments:
    database_id -- The id of the database to rename.
    new_name    -- The new display name string.

    Return:
    Updated database dict.
    """
    if not database_id:
        raise IQError("database_id is required")
    if not new_name:
        raise IQError("new_name is required")
    current = get_test(transport, database_id)
    current["name"] = new_name
    return transport.put("/databases/%s" % database_id, json_body=current)


def _owner_of(test):
    return (test.get("metadata") or {}).get(OWNER_METADATA_KEY)
