"""auto_repair -- see HANDOVER.md section 4 and client.py's query()
docstring. A view's query_provider template references every column that
view type supports, but a specific test's database may not have all of
them (e.g. a view with dual-IP/MAC/VLAN/IPv6 config columns, queried
against a single-stack test's database that never used that config).
Without auto_repair, that 400s with VALIDATION_FAILED "unknown attribute
name: ...". query(name=..., auto_repair=True) (the default) catches
exactly that error, strips the offending column, and retries -- silently,
up to MAX_AUTO_REPAIR_ATTEMPTS times -- so an automation script doesn't
need to know in advance which optional columns a particular test's
database happens to have.

This is easiest to actually observe against a real single-stack test's
database and a view with several optional protocol-specific columns
(dual-IP/VLAN/IPv6/MPLS/TCP/UDP config, etc.) -- a real case was observed
missing ~21 such columns at once. If your test server's databases all
have every column every view expects, iq.last_dropped_columns will just
come back empty below -- that's a correct result, not a broken example.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_NAME = "Detailed Stream Results"


def main():
    iq = IQClient()

    my_tests = iq.list_tests(owner="test-owner")
    if not my_tests:
        print("No tests found for that owner.")
        return
    iq.use_test(my_tests[0]["id"])
    print("Querying test: %s" % my_tests[0]["name"])

    # auto_repair=True (the default) -- succeeds even if this database
    # is missing some of the view's optional columns.
    try:
        rows = iq.query(name=VIEW_NAME, data_type="eot", limit=50, timeout=60)
    except IQViewError as e:
        # CONFIRMED 2026-09-08: not every orion-res deployment has a view
        # named "Detailed Stream Results" -- view availability is
        # per-deployment, not tied to the test database itself (a real
        # AION-managed instance with the exact same test data had a much
        # smaller view set and didn't include this one).
        print("Couldn't find that view on this server: %s" % e)
        print("Edit VIEW_NAME to a real table view on your server.")
        return
    print("\n%d row(s) returned with auto_repair=True (the default)." % (
        len(rows)))
    if iq.last_dropped_columns:
        print("Columns silently dropped to make this query succeed:")
        for col in iq.last_dropped_columns:
            print("  %s" % col)
        print(
            "(the returned rows above are missing whatever these columns "
            "would have shown)")
    else:
        print("Nothing was dropped -- this database has every column "
              "the view's template references.")

    # auto_repair=False -- see the original error instead of a silent
    # retry. Only worth showing if the call above actually dropped
    # something; otherwise there's nothing to reproduce.
    if iq.last_dropped_columns:
        print("\nRe-running with auto_repair=False to show the original "
              "error instead:")
        try:
            iq.query(
                name=VIEW_NAME, data_type="eot", limit=50, timeout=60,
                auto_repair=False)
            print("(expected this to raise IQRequestError -- it didn't; "
                  "the server may have started reporting a schema "
                  "mismatch differently)")
        except IQRequestError as e:
            print("  %s" % e)


if __name__ == "__main__":
    main()
