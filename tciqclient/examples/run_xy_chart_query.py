"""Query a view whose view_type is "x_y_chart" -- an XY/line-chart
widget. See run_view_query.py for the general query() walkthrough
(filters/sort/limit/etc. all work the same way here); this file is
specifically about what's different for this view_type.

Unlike table (run_view_query.py), x_y_chart support here is
reverse-engineered from XYChartWidgetModel.getQueryDef()
(xy.chart.widget.model.ts:244) in magellan-frontend's own TS source --
the production GUI that already does this translation -- rather than
confirmed against a real captured request. See WIDGET_QUERY_PLAN.md
section 2.2 for exactly what's assumed. Two things to know if a query
here behaves unexpectedly:

  - It's one query, same shape as table's.
  - snapshot_name= is accepted (for a consistent call signature) but has
    NO effect for this view_type -- xy-chart's own query-building method
    never applies a snapshot filter, even against its eot table (unlike
    every other chart type here). Don't be surprised if passing it
    changes nothing.

There's no known x_y_chart view name to hardcode the way "Detailed
Stream Results" is a known table view for run_view_query.py -- this
looks one up by view_type instead of by name. If your server has none,
this prints a message and stops; use the GUI to add an XY chart widget
to a dashboard first.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_TYPE = "x_y_chart"


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

    my_tests = iq.list_tests(owner="she83111")
    if not my_tests:
        print("No tests found for that owner.")
        return
    test = my_tests[0]
    iq.use_test(test["id"])
    print("Querying test: %s (%s)" % (test["name"], test["id"]))

    view = _find_view_of_type(iq, VIEW_TYPE)
    if not view:
        print(
            "No %r view found on this server -- add an XY chart widget "
            "to a dashboard in the GUI first, or point VIEW_TYPE/this "
            "lookup at a view you already know the name of (see "
            "run_view_query.py's find_view(name) for that pattern)." %
            (VIEW_TYPE,))
        return

    # NOTE: unlike single_level_table, an x_y_chart view's `details.
    # user_data` has no "tables" list at all -- CONFIRMED 2026-09-03
    # against a real server (see HANDOVER.md section 9): its shape is
    # {"series": [{"chart_type", "h_axis", "v_axis", "query_provider",
    # "filter_columns", ...}], ...} instead. That's also *why* the
    # query() call below currently always raises IQViewError for a real
    # x_y_chart view -- view_query_builder.py assumes every view_type
    # has a "tables" list, which doesn't hold here.
    print("Found view %r (id=%s)" % (view["name"], view["id"]))

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


if __name__ == "__main__":
    main()
