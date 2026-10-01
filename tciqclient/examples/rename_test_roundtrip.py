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
