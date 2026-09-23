"""Run an arbitrary IQ query expressed as a JSON string -- the specific
bullet in IQ-PYTHON-003 (Named Views): "The client SHALL continue [to]
support execution of arbitrary IQ queries expressed as JSON strings" --
naming the same capability the legacy socket/automation-API
`EnhancedResultsQuery` command exposed. See manage_views.py for named-
view CRUD (the rest of IQ-PYTHON-003) and run_view_query.py for the
name= path (build a query from a saved view instead of supplying one
yourself); this file is specifically about definition= with a raw JSON
string.

Where would a JSON string like this come from in practice?
  - A browser's DevTools Network tab, while a view is open in the
    TestCenter IQ GUI -- copy the POST /queries request body verbatim.
  - A legacy automation script's own EnhancedResultsQuery JSON blob,
    carried over as-is rather than rewritten as a Python dict.
  - tciqrestclient's own debug=True output from a previous run (see
    run_view_query.py's RAW_DEFINITION for what one looks like as a
    dict -- this file is the same shape, just as the JSON string form).

query(definition=...) accepts either a dict or a JSON string
interchangeably -- passing a string is parsed automatically (see
IQClient.query() in tciqrestclient/client.py) and raises IQQueryError with a clear
message if it isn't valid JSON, rather than a confusing error from
further down the call.

CONFIRMED against a real server 2026-09-07: any definition combining a
`limit` with `pagination` (as any real captured query with a limit
does) needs at least one entry in `orders` somewhere in the tree, or the
server 400s with "pagination requires at least one order expression" --
the same underlying constraint discovered earlier for saved-view
reuse (see HANDOVER.md section 9, `default_order_updates`). An earlier
version of RAW_DEFINITION_JSON below had an empty `orders: []` and
failed this way on its very first (unmodified) call -- fixed by giving
it a real default order.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQQueryError, IQRequestError

# A real captured request body, trimmed to 2 columns for brevity (see
# run_view_query.py's RAW_DEFINITION for the same shape as a Python dict
# instead of a string -- e.g. if you're building one up programmatically
# rather than pasting a captured request verbatim).
RAW_DEFINITION_JSON = """
{
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
              "(rx_stream_stats.frame_count) as frame_count"
            ],
            "filters": [], "groups": [], "orders": []
          }
        ],
        "projections": [
          "rxss.stream_block_name as stream_block_name",
          "rxss.frame_count as rx_stream_stats_frame_count"
        ],
        "filters": [], "groups": [], "orders": []
      }
    ],
    "projections": [
      "view.stream_block_name as stream_block_name",
      "view.rx_stream_stats_frame_count as rx_stream_stats_frame_count"
    ],
    "filters": [], "groups": [],
    "orders": ["view.stream_block_name ASC"],
    "limit": 50,
    "pagination": {"mode": "forward"}
  }
}
"""


def main():
    iq = IQClient()

    my_tests = iq.list_tests(owner="she83111")
    if not my_tests:
        print("No tests found for that owner.")
        return
    iq.use_test(my_tests[0]["id"])

    try:
        rows = iq.query(definition=RAW_DEFINITION_JSON, timeout=60)
    except IQQueryError as e:
        print("Not valid JSON, or not a recognized query shape: %s" % e)
        return
    except IQRequestError as e:
        print("Query failed or timed out: %s" % e)
        return

    print("%d row(s) from a definition=<JSON string> query:" % len(rows))
    for row in rows[:10]:
        print(" ", row)

    # filters=/sort=/group_by=/time_range=/limit= all still layer on top
    # of a JSON-string definition= exactly the same way as a dict one --
    # they're parsed into a dict internally before any of that happens.
    # The one thing that does NOT work here: display-name resolution
    # (e.g. filtering by "Rx Count" instead of its raw alias) -- that
    # needs a view to resolve names against, which a bare definition=
    # doesn't have. Use the query's own alias names directly instead.
    rows = iq.query(
        definition=RAW_DEFINITION_JSON,
        filters=[("rx_stream_stats_frame_count", "gt", 0)],
        sort="rx_stream_stats_frame_count DESC",
        limit=10,
        timeout=60,
    )
    print("\n%d row(s) with filters=/sort=/limit= layered on top:" % (
        len(rows)))
    for row in rows[:10]:
        print(" ", row)


if __name__ == "__main__":
    main()
