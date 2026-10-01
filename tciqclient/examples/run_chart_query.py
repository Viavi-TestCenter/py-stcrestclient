"""Query a view whose view_type is "chart" -- a live/time-series line
chart widget (e.g. "Port Frame Rate Chart"). See run_view_query.py for
the general query() walkthrough; this file is specifically about what's
different for this view_type.

Unlike every other supported view_type, "chart" doesn't use details.
user_data.tables/effective_details.system_data.query_providers at all --
its own real shape is a small query-templating engine instead (series[],
base_queries[], sampling_duration_providers[]), and non-live queries
need a real network round trip (learning this test's own real sampling
rate) before the actual per-series query can even be built. All of that
is now handled transparently inside query(name=...) itself -- see
view_query_builder.py's module docstring ("chart" section) and
build_chart_duration_probe_definitions()/build_chart_query_definitions()
for the full mechanism, CONFIRMED against a real local server
2026-09-24. From here, it's just query(name=...) like any other
view_type -- the one visible difference is the return shape, same as
histogram/boxplot: one query per real numeric series (the "Test Events"
plotlines marker series every chart view also lists is excluded
automatically), keyed by each series' internal name rather than its GUI
display_name.

There's no known "chart" view name to hardcode the way "Detailed Stream
Results" is for table -- a server can have many real chart views, each
referencing its own real measurement tables (a different, unrelated
"eCPRI Chart" view was tried first while building this and failed with
a real "unknown dimension" 400 -- its ecpri_device_live_stats tables
simply don't exist on this particular test's schema, the same "not
every provider matches every database" story auto_repair already deals
with elsewhere in this package). VIEW_NAME below is pinned to a known
real one; edit it, or use _find_view_of_type() instead, for a different
chart view.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_TYPE = "chart"
VIEW_NAME = "Port Frame Rate Chart"
DATABASE_ID = "f3okrp3jdfg6phw7"


def _find_view_of_type(iq, view_type, timeout=60):
    """Same lookup-by-view_type pattern as run_xy_chart_query.py/
    run_pie_chart_query.py -- there's no well-known chart view name to
    hardcode in general."""
    for view in iq.list_views(timeout=timeout):
        if (view.get("details") or {}).get("view_type") == view_type:
            return view
    return None


def main():
    iq = IQClient(debug=False)
    iq.use_test(DATABASE_ID)

    view = iq.find_view(VIEW_NAME, timeout=60)
    if not view:
        print("%r not found on this server -- falling back to the first "
              "%r view instead (a different one may not match this "
              "database's own real schema -- see the module docstring)."
              % (VIEW_NAME, VIEW_TYPE))
        view = _find_view_of_type(iq, VIEW_TYPE)
    if not view:
        print("No %r view found on this server -- add a chart widget to "
              "a dashboard in the GUI first." % (VIEW_TYPE,))
        return
    print("Querying %r (id=%s) on test %s\n" %
          (view["name"], view["id"], DATABASE_ID))

    for label, kwargs in [("Completed/snapshot data", {}),
                           ("Live data", {"test_live": True})]:
        print("== %s ==" % label)
        try:
            series = iq.query(name=view["name"], timeout=60, **kwargs)
        except (IQViewError, IQRequestError) as e:
            print("  FAILED: %s\n" % (e,))
            continue
        for name, rows in series.items():
            print("  %s: %d row(s)" % (name, len(rows)))
            for row in rows[:3]:
                print("    ", row)
            if len(rows) > 3:
                print("     ... (%d more)" % (len(rows) - 3))
        print()

    # The "Test Events" plotlines overlay isn't part of query(name=...)'s
    # own return value -- it's a fixed, generic query (not view-specific
    # at all, unlike the real numeric series above), available directly
    # for anyone who also wants it:
    from tciqrestclient.view_query_builder import CHART_EVENTS_DEFINITION
    print("== Test Events overlay ==")
    for row in iq.query(definition=CHART_EVENTS_DEFINITION, timeout=60):
        print("  ", row)


if __name__ == "__main__":
    main()
