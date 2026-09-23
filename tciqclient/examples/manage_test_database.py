"""Database lifecycle management -- IQ-PYTHON-010: rename_test()/
delete_test(), so CI/CD pipelines and lab management scripts can clean up
the IQ database store without any manual GUI interaction.

*** DANGER: both operations are real and irreversible against a real
*** server. delete_test() permanently removes a test's stored results;
*** there is no undo, no trash/recycle bin, no confirmation from the
*** server itself. This script will NOT run against anything until you
*** deliberately edit TARGET_DATABASE_ID below to a disposable test
*** database's id -- never point this at anything you (or anyone else)
*** still need. It also requires typing a literal confirmation phrase
*** before either operation actually runs, on top of that.

Get a database id to test with from list_tests_by_owner.py's output, or
create a throwaway test on your server specifically for trying this out.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQError, IQRequestError

#: Set this to a REAL, DISPOSABLE test database's id before running this
#: script at all -- see the module docstring. Left as None on purpose so
#: this can't accidentally run against anything by default.
TARGET_DATABASE_ID = None

#: What you must type back, verbatim, to actually proceed with either
#: destructive step below -- a deliberate extra speed bump beyond just
#: editing TARGET_DATABASE_ID.
CONFIRM_PHRASE = "yes delete this test database"


def _confirm(action_description):
    print("\n*** %s ***" % action_description)
    print("Type %r to proceed, anything else to skip:" % CONFIRM_PHRASE)
    return input("> ").strip() == CONFIRM_PHRASE


def main():
    if not TARGET_DATABASE_ID:
        print(
            "TARGET_DATABASE_ID is not set -- edit this script and set it "
            "to a real, disposable test database's id first. Refusing to "
            "run against anything by default. See list_tests_by_owner.py "
            "to find a database id.")
        return

    iq = IQClient()

    try:
        before = iq.get_test(database_id=TARGET_DATABASE_ID)
    except IQRequestError as e:
        print("Couldn't find database %r: %s" % (TARGET_DATABASE_ID, e))
        return
    print("Target database: %s (%s)" % (before["name"], TARGET_DATABASE_ID))

    new_name = before["name"] + " (renamed by tciqrestclient example)"
    if _confirm("About to RENAME %r to %r" % (before["name"], new_name)):
        updated = iq.rename_test(new_name, database_id=TARGET_DATABASE_ID)
        print("Renamed. Server now reports: %s" % updated.get(
            "name", "(name not present in response -- check get_test())"))
    else:
        print("Skipped rename.")

    if _confirm(
            "About to PERMANENTLY DELETE database %r (%s) and all its "
            "results" % (before["name"], TARGET_DATABASE_ID)):
        try:
            iq.delete_test(database_id=TARGET_DATABASE_ID)
            print("Deleted.")
        except IQError as e:
            print("Delete failed: %s" % e)
    else:
        print("Skipped delete.")


if __name__ == "__main__":
    main()
