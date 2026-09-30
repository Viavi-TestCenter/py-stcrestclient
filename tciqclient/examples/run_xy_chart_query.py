"""Query a view whose view_type is "x_y_chart" -- an XY/line-chart
widget. See run_view_query.py for the general query() walkthrough
(filters/sort/limit/etc. all work the same way here); this file is
specifically about what's different for this view_type -- namely, the
*return shape*, same as histogram/boxplot.

CONFIRMED against a real server 2026-09-24 (a real "StreamBlock Frame
Loss Duration Chart" view/capture) -- superseding the previous NOT-yet-
confirmed v1, which unconditionally ignored snapshot_name= and assumed
a "tables" list x_y_chart's real shape doesn't have at all. Like
histogram, x_y_chart needs no new templating mechanism once its real
shape is understood: `details.user_data.series[]` (one entry per
plotted series) each names a single `query_provider` directly, plus
`h_axis`/`v_axis`/`filter_columns` -- ordinary attribute/derived-fact
columns on that provider, walked through the exact same machinery
table/histogram already use. See
view_query_builder.build_xy_chart_query_definitions()'s own docstring
for the full mechanism.

Unlike histogram, each series has no `name` field of its own -- so
query() returns {<query_provider name>: rows}, one entry per series,
keyed by provider name (same fallback histogram/boxplot already use
when there's nothing more specific to key by).

There's no known x_y_chart view name to hardcode the way "Detailed
Stream Results" is a known table view for run_view_query.py in general
-- VIEW_NAME below is pinned to a known real one; edit it, or use
_find_view_of_type() instead, for a different x_y_chart view.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError
from tciqrestclient.view_query_builder import build_xy_chart_filter_dropdown_query

VIEW_TYPE = "x_y_chart"
VIEW_NAME = "StreamBlock Frame Loss Duration Chart"


def _find_view_of_type(iq, view_type, timeout=60):
    """Look up the first view on the server with this view_type -- there
    isn't a well-known view name to hardcode in general."""
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

    view = iq.find_view(VIEW_NAME, timeout=60)
    if not view:
        print("%r not found on this server -- falling back to the first "
              "%r view instead." % (VIEW_NAME, VIEW_TYPE))
        view = _find_view_of_type(iq, VIEW_TYPE)
    if not view:
        print(
            "No %r view found on this server -- add an XY chart widget "
            "to a dashboard in the GUI first." % (VIEW_TYPE,))
        return
    print("Found view %r (id=%s)" % (view["name"], view["id"]))

    try:
        # A dict of {<provider name>: rows} back, not a plain row list --
        # see the module docstring above.
        rows_by_provider = iq.query(
            name=view["name"], snapshot_name="Snapshot", limit=100,
            timeout=60)
    except IQViewError as e:
        print("Couldn't build a query from that view: %s" % e)
        return
    except IQRequestError as e:
        print("Query failed or timed out: %s" % e)
        print(
            "Try a smaller limit=, narrowing further with filters/"
            "time_range, or a larger timeout= to query().")
        return

    for provider_name, rows in rows_by_provider.items():
        print("\nprovider %r -- %d rows:" % (provider_name, len(rows)))
        for row in rows[:10]:
            print(" ", row)

    # The separate, standalone "which snapshots are available, in
    # order" query the real GUI also sends alongside the main data
    # query above -- not part of query(name=...)'s own return value,
    # same as "chart"'s Test Events overlay is kept separate.
    print("\nAvailable snapshots (for the filter dropdown/x-axis order):")
    dropdown_definition = build_xy_chart_filter_dropdown_query(view)
    for row in iq.query(definition=dropdown_definition, timeout=60):
        print(" ", row)


if __name__ == "__main__":
    main()
