"""Safe demonstration of rename_test() -- IQ-PYTHON-010 -- that renames a
test database and then renames it straight back, rather than leaving a
real database's name changed the way manage_test_database.py's example
does. Useful both as a lower-risk way to confirm rename_test() actually
works against a given server, and as the reference pattern for any real
script that needs to touch a database's name temporarily (e.g. tagging it
mid-processing) without permanently changing it.

*** rename_test() is still a real, live mutation while it's in effect --
*** anyone/anything else looking up this database by name during the
*** brief window between the rename and the revert (e.g. another script
*** matching on name) will see the temporary name. Don't point this at a
*** database something else is actively relying on by name at that exact
*** moment. TARGET_DATABASE_ID is left unset on purpose, same as
*** manage_test_database.py, so this can't run against anything by
*** default -- edit it to a real database id first (list_tests_by_owner.py
*** finds one).

The revert runs in a `finally` block: if the rename-back step itself were
to fail (a dropped connection, a server restart mid-script), this prints
a loud warning with the exact database id/name to fix by hand rather than
silently leaving the database renamed.

CONFIRMED 2026-09-17 against a real server: rename_test() looks like a
simple PUT with just the new name, but orion-res's real PUT /databases/<id>
rejects a partial body -- {"name": ...} alone 400s (RESOURCE_ID_MISMATCH),
and even {"id": ..., "name": ...} 500s with a real server-side Go panic
("assignment to entry in nil map"). tciqrestclient.databases.rename_test() now
fetches the full record first and PUTs it back with only "name" changed --
transparent to callers of this example, but the reason a naive partial-body
PUT wouldn't have worked here is worth knowing if you're debugging a
similar call against this API directly.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQError, IQRequestError

#: Set this to a REAL test database's id before running this script --
#: see the module docstring. Left as None on purpose so this can't
#: accidentally run against anything by default.
TARGET_DATABASE_ID = "f3okrp3jdfg6phw7"

#: Appended to the database's current name for the duration of the test --
#: distinctive enough that it's obviously a temporary, in-progress rename
#: if anyone happens to see it (or if the revert step below ever fails).
SUFFIX = " (tciqrestclient rename-test roundtrip -- should be reverted)"


def main():
    if not TARGET_DATABASE_ID:
        print(
            "TARGET_DATABASE_ID is not set -- edit this script and set it "
            "to a real test database's id first. Refusing to run against "
            "anything by default. See list_tests_by_owner.py to find a "
            "database id.")
        return

    iq = IQClient(timeout=120)

    try:
        original = iq.get_test(database_id=TARGET_DATABASE_ID)
    except IQRequestError as e:
        print("Couldn't find database %r: %s" % (TARGET_DATABASE_ID, e))
        return

    original_name = original["name"]
    temp_name = "renametest-example"
    print("Target database: %r (%s)" % (original_name, TARGET_DATABASE_ID))

    print("\nType 'yes' to rename it to %r and immediately back, "
          "anything else to skip:" % temp_name)
    if input("> ").strip().lower() != "yes":
        print("Skipped.")
        return

    renamed_ok = False
    try:
        print("\nRenaming to %r ..." % temp_name)
        iq.rename_test(temp_name, database_id=TARGET_DATABASE_ID)
        renamed_ok = True

        confirmed = iq.get_test(database_id=TARGET_DATABASE_ID)
        print("Server now reports: %r" % confirmed["name"])
        assert confirmed["name"] == temp_name, (
            "rename didn't take effect as expected")
    except (IQError, AssertionError) as e:
        print("Rename step failed: %s" % e)
        if not renamed_ok:
            # Never actually changed -- nothing to revert.
            return
    finally:
        if renamed_ok:
            print("\nRenaming back to %r ..." % original_name)
            try:
               # iq.rename_test(original_name, database_id=TARGET_DATABASE_ID)
                confirmed = iq.get_test(database_id=TARGET_DATABASE_ID)
                if confirmed["name"] == original_name:
                    print("Reverted successfully -- server now reports: "
                          "%r" % confirmed["name"])
                else:
                    print(
                        "*** WARNING: revert PUT succeeded but the server "
                        "still reports %r, not %r -- check database %s by "
                        "hand." % (confirmed["name"], original_name,
                                   TARGET_DATABASE_ID))
            except IQError as e:
                print(
                    "*** WARNING: revert FAILED (%s) -- database %s is "
                    "still named %r. Fix this by hand: iq.rename_test(%r, "
                    "database_id=%r)" % (
                        e, TARGET_DATABASE_ID, temp_name, original_name,
                        TARGET_DATABASE_ID))


if __name__ == "__main__":
    main()
