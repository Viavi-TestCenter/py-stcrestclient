"""Query a view whose view_type is "histogram". See run_view_query.py
for the general query() walkthrough (filters/sort/limit/etc. all work
the same way here); this file is specifically about what's different
for this view_type -- namely, the *return shape*.

Unlike table/x_y_chart/pie_chart (one query, a plain row list back),
histogram is one of the two view_types (boxplot is the other -- see
run_boxplot_query.py) where a single view can need more than one query
-- one per distinct query_provider its selected statistics reference.
query() still returns from one call, but the shape changes: a dict of
{<provider name>: rows}, one entry per underlying query, instead of a
plain row list. There's still only the one query() method -- no
query_histogram() -- this dict-vs-list distinction is the only thing
that depends on which view_type you're querying (see query()'s own
docstring in tciqrestclient/client.py).

CONFIRMED against a real server 2026-09-24 (a real "Frame Loss Duration
Histogram" view/capture, and a second real view -- "Stream Latency
Histogram View" -- that surfaced a genuine "not every provider supports
snapshot_name=" gap along the way) -- superseding the previous NOT-yet-
confirmed v1. Histogram's real `details.user_data` shape has no
"tables" list at all -- it's {"statistics": [...], "group_by",
"h_axis", "v_axis", "buckets_config", ...} instead -- but once a
selected statistic is resolved to its provider + raw stat name via
`effective_details.system_data.statistics`, it turns out to need no new
templating mechanism: it's an ordinary derived_fact_query_updates entry
on that provider, walked through the exact same machinery table/x_y_chart/
pie_chart already use. See view_query_builder.py's
build_histogram_query_definitions() for the full mechanism and
HANDOVER.md section 9's "histogram" entry for the real capture this was
built and confirmed against.

VIEW_NAME below is pinned to a known real view rather than looked up by
view_type -- a server can have several real histograms, each with
different snapshot-filter support (some providers have none at all --
snapshot_name= is silently ignored for those, the same "ignored where
not applicable" precedent x_y_chart already sets). _find_view_of_type()
is kept as the fallback/customization point for a different one.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_TYPE = "histogram"
VIEW_NAME = "Frame Loss Duration Histogram"


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
            "No %r view found on this server -- add a histogram widget "
            "to a dashboard in the GUI first." % (VIEW_TYPE,))
        return
    print("Found view %r (id=%s)" % (view["name"], view["id"]))

    try:
        # A dict of {<provider name>: rows} back, not a plain row list --
        # see the module docstring above. snapshot_name= is silently
        # ignored for any provider that doesn't support it.
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
