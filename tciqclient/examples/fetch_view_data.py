"""Fetch results from one specific view of one specific database --
exercising every generic query() feature a table view can support:
column discovery, filters=, sort=, group_by=, time_range=,
snapshot_name=, raw_result=, and picking the right table by data_type=.

Nothing about which columns to use is hardcoded to "Detailed Stream
Results" below -- they're discovered from the view's own
list_view_columns() and cross-referenced against the database's own
list_fields() for type info (a view column's raw attribute path, e.g.
"rx_stream_stats.frame_count", ends in the same field name,
"frame_count", that list_fields() reports a type for -- see
_field_types_by_raw_name()). That's what makes this work against any
single_level_table/paged_single_level_table view, not just this one.

Not every view has a column of the type each feature needs -- e.g.
time_range= needs a timestamp-typed column, which a per-stream results
table (like this one) usually doesn't have. Each section below says so
and skips instead of guessing or crashing. See query_modifiers.py for a
more compact single-view walkthrough of filters=/sort=/group_by=/
time_range= with hardcoded column names, and run_view_query.py for
options this file doesn't repeat (limit=/timeout=, the definition=
fallback, auto_repair=/last_dropped_columns in more depth).
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQQueryError

# Edit these two to a real database id (see list_tests_by_owner.py or
# discover_local.py's database listing to find one) and a real view name
# on your server.
DATABASE_ID = "k4s6ez3h25drbau7"
VIEW_NAME = "Detailed Stream Results"

#: orion-res field "type" values, grouped by which query() features they
#: support meaningfully.
NUMERIC_TYPES = {"integer", "number", "float"}
TIMESTAMP_TYPES = {"timestamp", "date", "datetime"}


def _print_rows(label, rows, limit=5):
    print("%s -- %d row(s):" % (label, len(rows)))
    for row in rows[:limit]:
        print(" ", row)


def _field_types_by_raw_name(iq, database_id):
    """{raw field name: type} across every table in the database, e.g.
    {"frame_count": "integer", "min_latency": "number", ...}."""
    types = {}
    for table in iq.list_table_names(database_id=database_id):
        key = "facts" if table.get("kind") == "result_set" else "attributes"
        for field in table.get(key) or []:
            types.setdefault(field["name"], field.get("type"))
    return types


def _find_column(columns, field_types, wanted_types):
    """First column (as returned by list_view_columns()) whose raw
    attribute path's tail resolves to one of wanted_types, or None."""
    for c in columns:
        leaf = c["name"].rsplit(".", 1)[-1]
        if field_types.get(leaf) in wanted_types:
            return c
    return None


def main():
    iq = IQClient(timeout=30)

    test = iq.get_test(database_id=DATABASE_ID)
    print("Database: %s (%s)" % (test["name"], DATABASE_ID))

    view = iq.find_view(VIEW_NAME, timeout=60)
    if not view:
        print("No view named %r on this server." % VIEW_NAME)
        return

    # Pick this view's "eot" table if it has one (a finished-test
    # snapshot -- supports the most features, snapshot_name= in
    # particular); otherwise its first/only table.
    tables = view["details"]["user_data"]["tables"]
    data_types = [t.get("data_type") for t in tables]
    data_type = "eot" if "eot" in data_types else data_types[0]
    print("Tables: %s -- using data_type=%r" % (data_types, data_type))

    columns = iq.list_view_columns(
        VIEW_NAME, data_type=data_type, active_only=True)
    if not columns:
        print("This view/table has no active columns.")
        return
    field_types = _field_types_by_raw_name(iq, DATABASE_ID)

    # Baseline: no modifiers, just to have real rows/values to compare
    # against and pull a real snapshot name from further down.
    baseline = iq.query(
        name=VIEW_NAME, database_id=DATABASE_ID, data_type=data_type,
        limit=20)
    _print_rows("\nBaseline (no modifiers)", baseline)

    # raw_result=True -- the raw result object (columns/rows/pagination/
    # timing) instead of row dicts.
    raw = iq.query(
        name=VIEW_NAME, database_id=DATABASE_ID, data_type=data_type,
        limit=5, raw_result=True)
    print("\nraw_result=True -- %d column(s), execute_time=%.3fs" % (
        len(raw.get("columns", [])), raw.get("execute_time", 0)))

    # filters=/sort=/group_by= -- all need comparable/orderable values;
    # a numeric column is the safest generic choice.
    numeric_column = _find_column(columns, field_types, NUMERIC_TYPES)
    if numeric_column:
        name = numeric_column["display_name"]
        try:
            rows = iq.query(
                name=VIEW_NAME, database_id=DATABASE_ID,
                data_type=data_type, filters=[(name, "gt", 0)], limit=10)
            _print_rows("\nfilters=[(%r, 'gt', 0)]" % name, rows)
        except (IQRequestError, IQQueryError) as e:
            print("\nfilters=[(%r, ...)] didn't work here: %s" % (name, e))

        try:
            rows = iq.query(
                name=VIEW_NAME, database_id=DATABASE_ID,
                data_type=data_type, sort="%s DESC" % name, limit=10)
            _print_rows("\nsort=%r DESC" % name, rows)
        except (IQRequestError, IQQueryError) as e:
            print("\nsort=%r didn't work here: %s" % (name, e))

        try:
            rows = iq.query(
                name=VIEW_NAME, database_id=DATABASE_ID,
                data_type=data_type, group_by=[name], limit=10)
            _print_rows("\ngroup_by=[%r]" % name, rows)
        except (IQRequestError, IQQueryError) as e:
            print("\ngroup_by=[%r] didn't work here: %s" % (name, e))
    else:
        print("\nNo numeric column on this view -- skipping filters=/"
              "sort=/group_by= (see query_modifiers.py for a worked "
              "example against a view that has one).")

    # time_range= -- needs a timestamp-typed column, which a per-stream
    # results table often doesn't have.
    ts_column = _find_column(columns, field_types, TIMESTAMP_TYPES)
    if ts_column:
        name = ts_column["display_name"]
        try:
            rows = iq.query(
                name=VIEW_NAME, database_id=DATABASE_ID,
                data_type=data_type,
                time_range=(name, "2000-01-01", None), limit=10)
            _print_rows(
                "\ntime_range=(%r, '2000-01-01', None)" % name, rows)
        except (IQRequestError, IQQueryError) as e:
            print("\ntime_range=(%r, ...) didn't work here: %s" % (name, e))
    else:
        print("\nNo timestamp-typed column on this view -- skipping "
              "time_range= (a per-stream results table often doesn't "
              "have one; a test-events or history view usually does).")

    # snapshot_name= -- only valid against an "eot" table; pick a real
    # snapshot name out of the baseline rows already fetched, rather
    # than guessing one.
    if data_type == "eot":
        snapshot_name = next(
            (row.get("test_snapshot_name") for row in baseline
             if row.get("test_snapshot_name")), None)
        if snapshot_name:
            try:
                rows = iq.query(
                    name=VIEW_NAME, database_id=DATABASE_ID,
                    data_type=data_type, snapshot_name=snapshot_name,
                    limit=10)
                _print_rows("\nsnapshot_name=%r" % snapshot_name, rows)
            except (IQRequestError, IQQueryError) as e:
                print("\nsnapshot_name=%r didn't work here: %s" % (
                    snapshot_name, e))
        else:
            print("\nNo 'Snapshot Name'-like column on this view -- "
                  "can't demonstrate snapshot_name= with a real value.")
    else:
        print("\nsnapshot_name= skipped -- only valid against an 'eot' "
              "table; this view is using data_type=%r." % data_type)

    if iq.last_dropped_columns:
        print("\n%d column(s) silently dropped by auto_repair on the "
              "most recent call (see auto_repair_demo.py)." %
              len(iq.last_dropped_columns))


if __name__ == "__main__":
    main()
