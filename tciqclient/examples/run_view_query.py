"""Set the test to query, then run a query and get JSON rows back --
this file covers view_type == "single_level_table"/"paged_single_level_
table" (the common case: a plain results table, e.g. "Detailed Stream
Results" below), querying its finished-test ("eot") data. See
run_live_query.py for querying a still-running test's "live" data
instead, and run_xy_chart_query.py/run_pie_chart_query.py/
run_histogram_query.py/run_boxplot_query.py for the other view_types --
each view_type gets its own example file since the query shape (and, for
histogram/boxplot, even the *return* shape) differs.

Covers PLAN.md steps 3-4: pick a test id, then fire a single request
-- with optional filters/sort/group_by/time_range -- and get the results
back in the same response.

query(name="<view name>") builds an executable query from the view's own
server-side query_provider templates (see tciqrestclient/view_query_builder.py) --
confirmed byte-for-byte against real captured requests for table views. A
view with more than one table (e.g. split into live vs. snapshot data,
like "Detailed Stream Results" below) needs test_live= to say which one
(True/"live" or False/"eot"/"snapshot" -- omit it entirely for the
default, snapshot data). data_type=/table_index= still work too, as
advanced/legacy alternatives to test_live=.

query() is the *only* query method, for every view_type -- there's no
query_pie_chart()/query_histogram()/etc. It looks at the view's own
view_type internally and dispatches accordingly; the one thing that
depends on view_type is the return shape. This only works for view_type
in tciqrestclient.view_query_builder.SUPPORTED_VIEW_TYPES -- currently
single_level_table/paged_single_level_table (confirmed against real
captures) plus x_y_chart/pie_chart/histogram/boxplot (reverse-engineered
from the GUI's own TS source, NOT yet confirmed against a real capture --
see WIDGET_QUERY_PLAN.md and the other example files). Any other
view_type (health_indicator/chart/gauge/etc.), or if a name= query ever
behaves unexpectedly for a supported one (see the note in
tciqrestclient/view_query_builder.py about filters not being byte-identical to the
GUI's own filter box), fall back to query(definition=...) with a
`multi_result` tree captured directly from the GUI's own POST /queries
request (your browser's DevTools Network tab while that view is open).
RAW_DEFINITION below shows what a captured definition looks like, in case
you need one.

snapshot_name= restricts results to one specific named snapshot (see
below for a worked example). It's only valid against snapshot (eot)
data -- a live table (a test still running) has no completed snapshots
to filter by, so passing it alongside test_live=True raises IQViewError
rather than silently doing nothing -- see run_live_query.py for that
case specifically.

A note on large tests: query() defaults to limit=1000 so a test with
millions of rows doesn't blow past the HTTP timeout by default -- pass a
different limit=, or limit=None to use the definition's own limit
instead. If a query still runs long even with a limit applied (an
expensive join/filter can take a while to compute before the limit is
applied), pass timeout= to give just that call more time, rather than
raising TCIQ_TIMEOUT globally for every request this client makes.

A note on per-database schema differences: a view's columns can name an
attribute (e.g. a "dual IP/MAC/VLAN config" column) that only exists for
databases whose test actually used that config -- querying a different
test's database with the same view can 400 with VALIDATION_FAILED
"unknown attribute name: ...". query(name=...) handles this by default
(auto_repair=True): it drops the offending column and retries, silently
-- nothing is printed. Check iq.last_dropped_columns after the call if
you want to know whether (and which) columns were dropped. Pass
auto_repair=False to see the original error instead.

filters=/sort=/group_by= on a name= query accept a column's GUI label
(display_name, e.g. "Rx Count"), its raw attribute path (e.g.
"rx_stream_stats.frame_count"), or its internal alias (e.g.
"rx_stream_stats_frame_count") interchangeably -- use
list_view_columns(name) to see what a column's actually called before
guessing.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

# For reference only -- what a captured `multi_result` definition looks
# like, in case you hit a view_type query(name=...) doesn't support and
# need to fall back to query(definition=...). Captured from the GUI's own
# POST /queries request while viewing "Detailed Stream Results" for a
# real test (PLAN.md, section 2.3) -- trimmed to 2 columns for brevity.
RAW_DEFINITION = {
    "multi_result": {
        "subqueries": [
            {
                "alias": "view",
                "subqueries": [
                    {
                        "alias": "rxss",
                        "subqueries": [],
                        "projections": [
                            "stream_block.name as stream_block_name",
                            "(rx_stream_stats.frame_count) as frame_count",
                        ],
                        "filters": [],
                        "groups": [],
                        "orders": [],
                    },
                    {
                        "alias": "txss",
                        "subqueries": [],
                        "projections": [
                            "stream_block.name as stream_block_name",
                            "(tx_stream_stats.frame_count) as frame_count",
                        ],
                        "filters": [],
                        "groups": [],
                        "orders": [],
                    },
                ],
                "projections": [
                    "rxss.test_snapshot_name as test_snapshot_name",
                    "txss.frame_count as tx_stream_stats_frame_count",
                    "rxss.frame_count as rx_stream_stats_frame_count",
                ],
                "filters": [
                    "rxss.tx_stream_stream_id=txss.tx_stream_stream_id",
                    "rxss.test_snapshot_name=txss.test_snapshot_name",
                ],
                "groups": [],
                "orders": [],
            }
        ],
        "projections": [
            "view.test_snapshot_name as test_snapshot_name",
            "view.tx_stream_stats_frame_count as tx_stream_stats_frame_count",
            "view.rx_stream_stats_frame_count as rx_stream_stats_frame_count",
        ],
        "filters": [],
        "groups": [],
        "orders": [
            "view.test_snapshot_name_order ASC",
            "view.tx_stream_stream_id ASC",
        ],
        "limit": 120,
        "pagination": {"mode": "forward"},
    }
}


def main():
    # debug=True (or TCIQ_DEBUG=1 in .env) prints every request's
    # method/URL/JSON body before sending, and its status/timing (or
    # error) after -- useful for copying a slow/failing query straight
    # into Postman/curl to reproduce it outside of tciqrestclient. Leave it on
    # while troubleshooting a timeout, then drop it once things work.
    #
    # timeout=60: a server with hundreds of views (GET /views returns
    # every one's full effective_details) can take longer than the 10s
    # default to list them all -- confirmed 2026-09-03 against a real
    # 500+-view server (see HANDOVER.md section 9). Set once here rather
    # than per-call, since find_view()/list_view_columns()/query(name=...)
    # below all hit that same listing internally.
    iq = IQClient(debug=False, timeout=60)

    # Step 2/3: find the test to query and make it the default. list_tests()
    # is sorted however orion-res returns it -- print the row counts so you
    # can pick a small one instead of blindly using the first match, since a
    # multi-million-row test is a common source of query timeouts.
    my_tests = iq.list_tests(owner="test-owner")
    if not my_tests:
        print("No tests found for that owner.")
        return

    for t in my_tests:
        print("  %s  %-40s rows=%s" % (
            t["id"], t["name"], t.get("summary", {}).get("count", "?")))

    test = my_tests[0]
    iq.use_test(test["id"])
    print("\nQuerying test: %s (%s)" % (test["name"], test["id"]))

    # GET /views returns every view's full effective_details (needed to
    # build a query from name= below) -- on a server with many views
    # this response can be large and slow, well past the default 10s
    # timeout. timeout=60 here overrides it for just this lookup.
    view = iq.find_view("Detailed Stream Results", timeout=60)
    if view:
        tables = view["details"]["user_data"]["tables"]
        print("Found view %r (id=%s), tables: %s" % (
            view["name"], view["id"],
            [t.get("data_type") for t in tables]))

    # Not sure what a column's actually called? list_view_columns() shows
    # every column's GUI label (display_name) alongside its raw attribute
    # path and internal alias -- any of the three works in filters=/sort=
    # below.
    if view:
        columns = iq.list_view_columns(
            "Detailed Stream Results", test_live=False, active_only=True)
        print("Filterable/sortable columns (showing display_name):")
        for c in columns[:5]:
            print("  %-14s %s" % (c["display_name"], c["name"]))

    # Step 4: run the view by name, with a filter/sort/limit applied.
    # test_live=False picks this view's snapshot (eot) table (vs.
    # True/"live", which only has data while a test is actively
    # running) -- it's also the default, so omitting it entirely does
    # the same thing; passed explicitly here just to show it.
    # "Rx Count" here is the column's GUI display_name -- its raw
    # attribute path ("rx_stream_stats.frame_count"), unambiguous bare
    # column name ("frame_count" -- but NOT here, since this view also
    # has a "tx_stream_stats.frame_count"), or internal alias
    # ("rx_stream_stats_frame_count") work identically when unambiguous.
    # limit=100 here (instead of the default 1000) keeps this example's
    # output short; narrowing with filters/time_range also cuts down how
    # much work orion-res has to do, and is usually the better fix if a
    # query is slow.
    try:
        rows = iq.query(
            "Detailed Stream Results",
            False,
            filters=[("Rx Count", "gt", 16680)],
            sort="Rx Count DESC",
            limit=100,
            # Per-call override: only this query gets extra time, not
            # every request this client makes. Bump this (or TCIQ_TIMEOUT
            # in .env, to raise the client's default instead) if a big
            # test still times out even with a limit applied.
            timeout=60,
        )
    except IQViewError as e:
        print("Couldn't build a query from that view: %s" % e)
        print("Falling back to a captured definition= (see RAW_DEFINITION).")
        # RAW_DEFINITION was captured from a specific real server's
        # "Detailed Stream Results" -- CONFIRMED 2026-09-08 that a
        # *different* real server (this view genuinely didn't exist on
        # one AION-managed deployment tested) can also reject this exact
        # fallback, since its own schema/aliases differ too. Don't let
        # that second failure crash the script -- report it the same way
        # as the primary one and stop, rather than assume the fallback
        # is guaranteed to work just because the first attempt failed.
        try:
            rows = iq.query(
                definition=RAW_DEFINITION,
                filters=[("frame_count", "gt", 100000)],
                sort=("frame_count", "desc"),
                limit=100,
                timeout=60,
            )
        except (IQViewError, IQRequestError) as e2:
            print("Fallback definition= also didn't work on this server: "
                  "%s" % e2)
            print(
                "Edit VIEW_NAME to a real table view on your server (see "
                "run_view_query.py's find_view() calls above), or capture "
                "your own definition= from the GUI's DevTools Network tab.")
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

    # Same query, but with raw_result=True: the raw result object
    # (columns, pagination, timing) instead of row dicts.
    raw = iq.query(
        "Detailed Stream Results", False, raw_result=True,
        limit=100, timeout=60)
    print("\nquery took %.3fs, %d columns" % (
        raw.get("execute_time", 0), len(raw.get("columns", []))))

    # snapshot_name= restricts results to one specific named snapshot --
    # pick a real one out of the rows we already have, rather than
    # guessing one. "test_snapshot_name" is this view's own alias for it
    # (see list_view_columns() above if a different view names it
    # differently). This only works against the eot table -- see
    # run_live_query.py for why the same argument raises against "live".
    snapshot_name = rows[0].get("test_snapshot_name") if rows else None
    if snapshot_name:
        snapshot_rows = iq.query(
            "Detailed Stream Results", False,
            snapshot_name=snapshot_name, limit=10, timeout=60)
        print("\n%d rows restricted to snapshot %r:" % (
            len(snapshot_rows), snapshot_name))
        for row in snapshot_rows[:5]:
            print(" ", row)


if __name__ == "__main__":
    main()
