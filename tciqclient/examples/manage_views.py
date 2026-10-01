"""Named view CRUD from code -- IQ-PYTHON-003 (Named Views): list system
views, and save/reuse/delete a custom one, exactly as a user would do
from the TestCenter IQ GUI's own view manager.

This script is self-contained: it creates its own throwaway view, reads
it back, then deletes it -- safe to run against a real server, since it
only ever touches the one view it made (named EXAMPLE_VIEW_NAME below).
The delete always runs (see the try/finally in main()) even if something
in between fails -- an earlier version of this script could leave the
throwaway view behind on a real server if a later step raised.

It does NOT create a view from scratch (there's no supported way to build
a view's `details` GUI-table-spec out of thin air -- see the module
docstring in tciqrestclient/views.py); instead it clones an existing view's own
`details`, renames the clone, and saves that.

A view created this way used to be unusable afterward -- CONFIRMED
2026-09-03 (see HANDOVER.md section 9): the server never populates a
freshly saved view's own effective_details.system_data.query_providers,
so list_view_columns()/query(name=...) would raise IQViewError against
it. That's now handled transparently inside IQClient itself (it searches
other views on the server for a matching provider by name) -- this
example just calls list_view_columns()/query(name=...) normally below,
no workaround needed.

See run_view_query.py for querying a view once you have its name, and
list_view_columns() there for discovering what a view's columns are
actually called.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQError

#: A distinctive name so this script's cleanup can find (and not
#: accidentally collide with) anything else on the server.
EXAMPLE_VIEW_NAME = "tciqrestclient_example_view (safe to delete)"

#: Clone this existing view's `details` as the starting point -- edit to
#: a real view name on your server if "Detailed Stream Results" doesn't
#: exist there.
SOURCE_VIEW_NAME = "Detailed Stream Results"


def main():
    # timeout=60: a server with hundreds of views (GET /views returns
    # every one's full effective_details) can take longer than the 10s
    # default to list them all -- confirmed 2026-09-03 against a real
    # 500+-view server (see HANDOVER.md section 9).
    iq = IQClient(timeout=180)
    my_tests = iq.list_tests(owner="test-owner")
    if my_tests:
        iq.use_test(my_tests[0]["id"])
    else:
        print("No tests found for that owner -- the query(name=...) "
              "step below will need a real database_id= or use_test() "
              "call to work; edit the owner above.")

    # list_views() -- every view the server knows about. Can be slow: the
    # full effective_details.system_data.query_providers templates are
    # included per view by default (see HANDOVER.md section 4) -- pass
    # timeout= to give this specific call more time on a server with many
    # views, rather than raising the client's default globally.
    views = iq.list_views(timeout=120)
    print("%d view(s) on this server. First 10:" % len(views))
    for v in views[:10]:
        print("  %-40s view_type=%s" % (
            v["name"], v.get("details", {}).get("view_type")))

    source = iq.find_view(SOURCE_VIEW_NAME, timeout=60)
    if not source:
        print("\nNo view named %r to clone from -- edit SOURCE_VIEW_NAME "
              "to a real view on your server." % SOURCE_VIEW_NAME)
        return

    # Clean up a previous run's leftover first, if any -- makes this
    # script safe to re-run without accumulating duplicate example views.
    existing = iq.find_view(EXAMPLE_VIEW_NAME, timeout=60)
    if existing:
        print("\nFound a leftover %r from a previous run -- deleting it "
              "first." % EXAMPLE_VIEW_NAME)
        iq.delete_view(view_id=existing["id"])

    print("\nCloning %r's details as %r ..." % (
        SOURCE_VIEW_NAME, EXAMPLE_VIEW_NAME))
    created = iq.save_view(
        name=EXAMPLE_VIEW_NAME,
        details=source["details"],
        description="Created by tciqrestclient's manage_views.py example -- safe to delete.",
    )
    print("Saved. Server response id: %s" % created.get("id", "(not in response)"))

    # save_view()'s response shape isn't guaranteed to include the new
    # view_id directly (depends on the server version) -- look it up by
    # name to be sure, the same way a caller without that response would.
    saved = iq.find_view(EXAMPLE_VIEW_NAME, timeout=60)
    if not saved:
        print("Couldn't find the view back by name after saving -- check "
              "the server response above for what actually happened.")
        return
    print("Confirmed saved: id=%s" % saved["id"])

    # Everything from here on touches a real, now-existing view on the
    # server -- guarantee cleanup runs even if a step below raises.
    try:
        # Reuse it, exactly as saved -- no workaround needed (see the
        # module docstring for what used to be required here).
        columns = iq.list_view_columns(
            EXAMPLE_VIEW_NAME, active_only=True, timeout=60)
        print("\n%d active column(s) on the clone (showing display_name):"
              % len(columns))
        for c in columns[:5]:
            print("  %s" % c["display_name"])

        try:
            rows = iq.query(name=EXAMPLE_VIEW_NAME, data_type="eot", limit=5)
            print("\n%d row(s) queried back from the clone:" % len(rows))
            for row in rows[:3]:
                print(" ", row)
        except IQError as e:
            print("\nCouldn't query the clone back: %s" % e)
    finally:
        # delete_view(name=...) would re-run the same full, possibly-slow
        # GET /views lookup as above just to find this same id again --
        # we already have it from find_view() a few lines up, so delete
        # by id directly instead.
        print("\nDeleting %r (id=%s) ..." % (EXAMPLE_VIEW_NAME, saved["id"]))
        iq.delete_view(view_id=saved["id"])
        print("Deleted.")


if __name__ == "__main__":
    main()
