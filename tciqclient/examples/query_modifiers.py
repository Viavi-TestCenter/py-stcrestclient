"""Query modifiers -- IQ-PYTHON-005: filters, sort, grouping, and time
range as plain Python values, mapped to orion-res's native query
capabilities without ever hand-building modifier expression strings.
This file demonstrates all four together as this one requirement's
dedicated example; see run_view_query.py for the broader "query a named
view" walkthrough these same filters=/sort= also appear in, and
run_json_definition_query.py for IQ-PYTHON-003's separate "arbitrary
query as a JSON string" capability.

See tciqrestclient/query.py's merge_modifiers() docstring for the full accepted
shapes -- summarized here:
  filters=    [(field, op, value), ...] -- op in eq/ne/lt/lte/gt/gte/
              contains/in (default eq); or a raw SQL-ish expression
              string, passed through as-is.
  sort=       "field ASC"/"field DESC", a (field, order) tuple, or a
              list of those for multi-column sort.
  group_by=   a field name, or a list of them.
  time_range= (field, start, end) -- start/end may be omitted
              individually for an open-ended range.

All four accept a column's GUI display_name (e.g. "Rx Count"), its raw
attribute path, or its internal alias interchangeably with name= --
see list_view_columns() to discover what's available for a given view.
"""
import datetime

from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQQueryError, IQRequestError, IQViewError

VIEW_NAME = "Detailed Stream Results"


def main():
    iq = IQClient()

    my_tests = iq.list_tests(owner="test-owner")
    if not my_tests:
        print("No tests found for that owner.")
        return
    iq.use_test(my_tests[0]["id"])

    # filters= / sort= -- see run_view_query.py for the fuller walkthrough
    # of these two (including the auto_repair/timeout notes); shown again
    # here briefly so this file is a complete, standalone demo of every
    # IQ-PYTHON-005 modifier in one place.
    try:
        rows = iq.query(
            name=VIEW_NAME, data_type="eot",
            filters=[("Rx Count", "gt", 0)],
            sort="Rx Count DESC",
            limit=10, timeout=60)
        print("filters=/sort= -- %d row(s):" % len(rows))
        for row in rows[:5]:
            print(" ", row)
    except (IQViewError, IQRequestError) as e:
        print("Couldn't build that query: %s" % e)

    # group_by= -- aggregate rows by one or more fields. A list groups by
    # more than one field at once. Note: real SQL semantics apply here --
    # grouping by only some of a wide view's columns while still
    # projecting the rest 400s with a real "must appear in the GROUP BY
    # clause or be used in an aggregate function" error (confirmed
    # 2026-09-03 against a real server -- see HANDOVER.md section 9);
    # that's expected for a view with many non-aggregated columns like
    # this one, not a tciqrestclient bug.
    try:
        rows = iq.query(
            name=VIEW_NAME, data_type="eot",
            group_by=["Stream Block Name"],
            limit=50, timeout=60)
        print("\nGrouped by Stream Block Name -- %d row(s):" % len(rows))
        for row in rows[:5]:
            print(" ", row)
    except IQViewError as e:
        print("Couldn't build/group that query: %s" % e)
    except IQQueryError as e:
        print("group_by= rejected -- check the field name with "
              "list_view_columns(): %s" % e)
    except IQRequestError as e:
        print("group_by= rejected by the server (likely needs every "
              "projected column grouped or aggregated -- see the note "
              "above): %s" % e)

    # time_range= -- restrict to a window on a timestamp-like field.
    # There's no single universal timestamp column across every query
    # type, so the field name is always required; start/end may each be
    # omitted for an open-ended range. Using "now minus a day" here just
    # so this example has *something* concrete to pass -- pick whatever
    # field/window is meaningful for your own view.
    now = datetime.datetime.utcnow()
    one_day_ago = now - datetime.timedelta(days=1)
    try:
        rows = iq.query(
            name=VIEW_NAME, data_type="eot",
            time_range=("test.started", one_day_ago, now),
            limit=10, timeout=60)
        print("\n%d row(s) from tests started in the last 24h:" % len(rows))
        for row in rows[:5]:
            print(" ", row)
    except (IQViewError, IQQueryError, IQRequestError) as e:
        print("\ntime_range= against 'test.started' didn't work here "
              "(%s) -- this view/field combination may not support it; "
              "try a field from list_view_columns() instead." % e)


if __name__ == "__main__":
    main()
