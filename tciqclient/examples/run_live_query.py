"""Query a view's "live" data -- results for a test that's still
running, as opposed to a finished test's "eot" (end-of-test) snapshot
data (see run_view_query.py for that case).

There's no separate live-subscription API here: "live" is just
test_live=True (or the string "live") on the same query(name=...) call
-- orion-res resolves it to a different query_provider template (a
different join/projection shape) than snapshot data does. To get fresh
numbers while a test keeps running, re-run the same query() call again;
this file does that a few times in a short polling loop to show what
that looks like, rather than opening any kind of persistent connection.

user= lets you skip looking up a database_id yourself: pass the owner's
username and, for live data specifically, tciqrestclient finds the one test they
currently have running (metadata["test.running"] == "true") for you --
there's no such shortcut for snapshot/eot data, since a user can have
many *completed* tests with no way to tell which one you mean (pass
database_id= explicitly for that -- see run_view_query.py).

snapshot_name= is the one thing that does NOT carry over from eot to
live: a still-running test has no *completed* snapshot to filter by, so
passing snapshot_name= alongside test_live=True raises IQViewError
outright (demonstrated below) rather than silently returning nothing or
ignoring it.

This uses "Detailed Stream Results" -- a single_level_table view with
separate live/snapshot tables, confirmed against real captures for the
snapshot side (see WIDGET_QUERY_PLAN.md and tciqrestclient/view_query_builder.py
for what's confirmed vs. not) -- pick a different table view name if
that one doesn't exist on your server, or better, one for a test you
know is currently running (a finished test's live table is simply
empty).
"""
import time

from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQQueryError, IQRequestError, IQViewError

VIEW_NAME = "Detailed Stream Results"
OWNER = "she83111"

#: How many times to re-run the query, and how long to wait between
#: polls -- purely for this example's demo loop; there's no minimum/
#: maximum poll interval enforced by tciqrestclient or orion-res itself.
POLL_COUNT = 3
POLL_INTERVAL_SEC = 2


def main():
    # timeout=60: a server with hundreds of views (GET /views returns
    # every one's full effective_details) can take longer than the 10s
    # default to list them all -- confirmed 2026-09-03 against a real
    # 500+-view server (see HANDOVER.md section 9). Set once here rather
    # than per-call, since every find_view()/query(name=...) call below
    # hits that same listing internally.
    iq = IQClient(debug=False, timeout=60)

    view = iq.find_view(VIEW_NAME, timeout=60)
    if not view:
        print("No view named %r -- edit VIEW_NAME to match a real "
              "table view on your server." % (VIEW_NAME,))
        return

    # snapshot_name= against live data always raises -- there's no
    # completed snapshot yet for a test that's still running. This is a
    # property of test_live=True, not of any particular snapshot_name=
    # value -- try/except around just the resolution step, before ever
    # touching a real (or missing) running test.
    try:
        iq.query(
            VIEW_NAME, True, user=OWNER,
            snapshot_name="doesn't matter -- always rejected")
        print("(expected this to raise IQViewError -- it didn't; check "
              "whether this view's live table is really named "
              "data_type=\"live\")")
    except IQViewError as e:
        print("snapshot_name= against live data correctly raises:")
        print(" ", e)
    except IQQueryError as e:
        # No test owned by OWNER is currently running -- see the note
        # printed below the polling attempt for how to fix that.
        print("Couldn't even resolve a running test for %r: %s" % (OWNER, e))

    # Poll the live table a few times -- each call is a fresh, independent
    # request/response; nothing is cached or subscribed between calls.
    # user= re-resolves OWNER's currently-running test on every call (in
    # case a different test started running between polls); pass
    # database_id= instead of user= if you already know which test.
    print("\nPolling %r's live data for %r, %d time(s), %ds apart:" % (
        VIEW_NAME, OWNER, POLL_COUNT, POLL_INTERVAL_SEC))
    for i in range(POLL_COUNT):
        try:
            rows = iq.query(
                VIEW_NAME, "live", user=OWNER, limit=10, timeout=30)
        except IQViewError as e:
            print("Couldn't build a query from that view's live table: "
                  "%s" % e)
            return
        except IQQueryError as e:
            print(
                "No test owned by %r is currently running -- point OWNER "
                "at a user with a live test, or pass database_id= "
                "directly instead of user=: %s" % (OWNER, e))
            return
        except IQRequestError as e:
            print("Query failed or timed out: %s" % e)
            return

        print("\n[poll %d/%d] %d row(s):" % (i + 1, POLL_COUNT, len(rows)))
        for row in rows[:5]:
            print(" ", row)

        if i < POLL_COUNT - 1:
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
