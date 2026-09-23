"""Query a view whose view_type is "boxplot". See run_view_query.py for
the general query() walkthrough (filters/sort/limit/etc. all work the
same way here); this file is specifically about what's different for
this view_type -- namely, the *return shape*, same story as
run_histogram_query.py.

boxplot is the other view_type (histogram is the first -- see
run_histogram_query.py) where a single view can need more than one
query -- one per selected statistic, since a boxplot tile can show
several independent distributions side by side. query() still returns
from one call, but the shape changes: a dict of {<statistic name>:
rows}, one entry per underlying query, instead of a plain row list.
There's still only the one query() method -- no query_boxplot() -- this
dict-vs-list distinction is the only thing that depends on which
view_type you're querying (see query()'s own docstring in
tciqrestclient/client.py).

Also unlike table, boxplot support here is reverse-engineered from
BoxplotWidgetModel.buildQueryDefinitions() (boxplot.widget.model.
ts:213) in magellan-frontend's own TS source -- the production GUI that
already does this translation -- rather than confirmed against a real
captured request. See WIDGET_QUERY_PLAN.md section 2.5 for exactly
what's assumed, including that this v1 derives the statistic names from
the view's own details.user_data.tables[].groups list (falling back to
a single query keyed by the provider's name if that list is empty) --
the real per-statistic column split (v-axis/h-axis/etc.) isn't
derivable from a view's own effective_details in any confirmed way yet.
Min/max/median/quartile/IQR computation is entirely client-side in the
GUI -- this only fetches the raw rows; you'd still need to compute those
yourself if that's what you're after.

There's no known boxplot view name to hardcode the way "Detailed Stream
Results" is a known table view for run_view_query.py -- this looks one
up by view_type instead of by name. If your server has none, this
prints a message and stops; use the GUI to add a boxplot widget to a
dashboard first.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_TYPE = "boxplot"


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
            "No %r view found on this server -- add a boxplot widget "
            "to a dashboard in the GUI first, or point VIEW_TYPE/this "
            "lookup at a view you already know the name of (see "
            "run_view_query.py's find_view(name) for that pattern)." %
            (VIEW_TYPE,))
        return

    tables = view["details"]["user_data"]["tables"]
    print("Found view %r (id=%s), tables: %s" % (
        view["name"], view["id"], [t.get("data_type") for t in tables]))

    try:
        # A dict of {<statistic name>: rows} back, not a plain row list
        # -- see the module docstring above.
        rows_by_statistic = iq.query(
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

    print("\n%d statistic(s):" % len(rows_by_statistic))
    for stat_name, rows in rows_by_statistic.items():
        print("\n  %r -- %d rows:" % (stat_name, len(rows)))
        for row in rows[:5]:
            print("   ", row)

    # last_dropped_columns is also keyed the same way for a "multi"-kind
    # view_type -- {<statistic name>: [<dropped fragment>, ...]} -- rather
    # than the plain list it is for table/x_y_chart/pie_chart.
    if any(iq.last_dropped_columns.values()):
        print("\nSome columns were dropped by auto_repair:")
        print(" ", iq.last_dropped_columns)


if __name__ == "__main__":
    main()
