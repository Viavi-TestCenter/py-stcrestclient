"""Query a view whose view_type is "pie_chart". See run_view_query.py
for the general query() walkthrough (filters/sort/limit/etc. all work
the same way here); this file is specifically about what's different
for this view_type.

Unlike table (run_view_query.py), pie_chart support here is
reverse-engineered from PieChartWidgetModel.getQueryDefinition()
(pie.chart.widget.model.ts:114) in magellan-frontend's own TS source --
the production GUI that already does this translation -- rather than
confirmed against a real captured request. See WIDGET_QUERY_PLAN.md
section 2.3 for exactly what's assumed (in particular: which provider
fields hold the slice-category/aggregate-value columns). Two things to
know if a query here behaves unexpectedly:

  - It's one query, same shape as table's.
  - snapshot_name= DOES have an effect here (unlike x_y_chart) --
    demonstrated below.

There's no known pie_chart view name to hardcode the way "Detailed
Stream Results" is a known table view for run_view_query.py -- this
looks one up by view_type instead of by name. If your server has none,
this prints a message and stops; use the GUI to add a pie chart widget
to a dashboard first.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_TYPE = "pie_chart"


def _find_view_of_type(iq, view_type, timeout=60):
    """Look up the first view on the server with this view_type -- there
    isn't a well-known view name to hardcode the way table's "Detailed
    Stream Results" is, so this scans list_views() instead."""
    for view in iq.list_views(timeout=timeout):
        if (view.get("details") or {}).get("view_type") == view_type:
            return view
    return None


def main():
    iq = IQClient(debug=False)

    my_tests = iq.list_tests(owner="test-owner")
    if not my_tests:
        print("No tests found for that owner.")
        return
    test = my_tests[0]
    iq.use_test(test["id"])
    print("Querying test: %s (%s)" % (test["name"], test["id"]))

    view = _find_view_of_type(iq, VIEW_TYPE)
    if not view:
        print(
            "No %r view found on this server -- add a pie chart widget "
            "to a dashboard in the GUI first, or point VIEW_TYPE/this "
            "lookup at a view you already know the name of (see "
            "run_view_query.py's find_view(name) for that pattern)." %
            (VIEW_TYPE,))
        return

    tables = view["details"]["user_data"]["tables"]
    print("Found view %r (id=%s), tables: %s" % (
        view["name"], view["id"], [t.get("data_type") for t in tables]))

    try:
        rows = iq.query(
            name=view["name"], data_type="eot", limit=100, timeout=60)
    except IQViewError as e:
        print("Couldn't build a query from that view: %s" % e)
        return
    except IQRequestError as e:
        print("Query failed or timed out: %s" % e)
        print(
            "Try a smaller limit=, narrowing further with filters/"
            "time_range, or a larger timeout= to query().")
        return

    print("\n%d rows:" % len(rows))
    for row in rows[:10]:
        print(" ", row)

    # snapshot_name= restricts results to one specific named snapshot --
    # pick a real one out of the rows we already have, same as
    # run_view_query.py does for table. Only valid against the eot table
    # (data_type="eot", already used above) -- see run_live_query.py for
    # why the same argument raises against a "live" one.
    snapshot_name = rows[0].get("test_snapshot_name") if rows else None
    if snapshot_name:
        snapshot_rows = iq.query(
            name=view["name"], data_type="eot",
            snapshot_name=snapshot_name, limit=10, timeout=60)
        print("\n%d rows restricted to snapshot %r:" % (
            len(snapshot_rows), snapshot_name))
        for row in snapshot_rows[:5]:
            print(" ", row)
    else:
        print(
            "\n(no test_snapshot_name column in this view's rows -- "
            "can't demo snapshot_name= automatically; pass a real "
            "snapshot name for this view/test explicitly instead.)")


if __name__ == "__main__":
    main()
