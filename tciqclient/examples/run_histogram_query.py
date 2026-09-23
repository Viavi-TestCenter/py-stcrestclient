"""Query a view whose view_type is "histogram". See run_view_query.py
for the general query() walkthrough (filters/sort/limit/etc. all work
the same way here); this file is specifically about what's different
for this view_type -- namely, the *return shape*.

Unlike table/x_y_chart/pie_chart (one query, a plain row list back),
histogram is one of the two view_types (boxplot is the other -- see
run_boxplot_query.py) where a single view can need more than one query
-- one per distinct query_provider its active statistics reference.
query() still returns from one call, but the shape changes: a dict of
{<provider name>: rows}, one entry per underlying query, instead of a
plain row list. There's still only the one query() method -- no
query_histogram() -- this dict-vs-list distinction is the only thing
that depends on which view_type you're querying (see query()'s own
docstring in tciqrestclient/client.py).

Also unlike table, histogram support here is reverse-engineered from
HistogramWidgetModel.buildQueryDefinitions() (histogram.widget.model.
ts:172) in magellan-frontend's own TS source -- the production GUI that
already does this translation -- rather than confirmed against a real
captured request. See WIDGET_QUERY_PLAN.md section 2.4 for exactly
what's assumed, including that this v1 only builds one query even if a
real histogram references more than one provider (the multi-provider
case hasn't been seen in a real capture yet). Bucketing itself (turning
raw values into histogram bars) is entirely client-side in the GUI --
this only fetches the raw rows, same as everything else here; you'd
still need to bucket them yourself if that's what you're after.

There's no known histogram view name to hardcode the way "Detailed
Stream Results" is a known table view for run_view_query.py -- this
looks one up by view_type instead of by name. If your server has none,
this prints a message and stops; use the GUI to add a histogram widget
to a dashboard first.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_TYPE = "histogram"


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
            "No %r view found on this server -- add a histogram widget "
            "to a dashboard in the GUI first, or point VIEW_TYPE/this "
            "lookup at a view you already know the name of (see "
            "run_view_query.py's find_view(name) for that pattern)." %
            (VIEW_TYPE,))
        return

    # NOTE: unlike single_level_table, a histogram view's `details.
    # user_data` has no "tables" list at all -- CONFIRMED 2026-09-03
    # against a real server (see HANDOVER.md section 9): its shape is
    # {"statistics": [...], "group_by", "h_axis", "v_axis",
    # "buckets_config", ...} instead. That's also *why* the query()
    # call below currently always raises IQViewError for a real
    # histogram view -- view_query_builder.py assumes every view_type
    # has a "tables" list, which doesn't hold here.
    print("Found view %r (id=%s)" % (view["name"], view["id"]))

    try:
        # A dict of {<provider name>: rows} back, not a plain row list --
        # see the module docstring above.
        rows_by_provider = iq.query(
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

    print("\n%d underlying quer%s:" % (
        len(rows_by_provider),
        "y" if len(rows_by_provider) == 1 else "ies"))
    for provider_name, rows in rows_by_provider.items():
        print("\n  provider %r -- %d rows:" % (provider_name, len(rows)))
        for row in rows[:5]:
            print("   ", row)

    # last_dropped_columns is also keyed the same way for a "multi"-kind
    # view_type -- {<provider name>: [<dropped fragment>, ...]} -- rather
    # than the plain list it is for table/x_y_chart/pie_chart.
    if any(iq.last_dropped_columns.values()):
        print("\nSome columns were dropped by auto_repair:")
        print(" ", iq.last_dropped_columns)


if __name__ == "__main__":
    main()
