"""Bulk database cleanup -- delete every database over a storage-size
threshold, or older than a given age (review feedback: "delete databases
> size" / "delete database older than x days").

*** DANGER: this can delete MANY databases in one run, permanently and
*** irreversibly -- there is no undo, no trash/recycle bin, no server-side
*** confirmation. Both list_databases_over_size()/list_databases_older_
*** than() and their delete_* counterparts default to dry_run=True: they
*** always return the full list of what matches, but only delete_*
*** with dry_run=False explicitly given actually deletes anything. This
*** script mirrors that: it always previews first, and -- like
*** manage_test_database.py -- requires typing a literal confirmation
*** phrase before passing dry_run=False for real.

"Size" is total storage (get_database_summary()'s value_storage_kb +
index_storage_kb, in KB -- CONFIRMED real fields, see
tests/fixtures.py). "Age" is metadata["test.started"] (also confirmed
real) compared against now.

Edit MIN_SIZE_KB/MAX_AGE_DAYS below -- both start disabled (None) so this
can't accidentally delete anything just by being run.
"""
from tciqrestclient import IQClient

#: Delete databases at or over this many KB of total storage
#: (value_storage_kb + index_storage_kb). None (default): skip this check
#: entirely.
MIN_SIZE_KB = None

#: Delete databases whose metadata["test.started"] is more than this many
#: days old. None (default): skip this check entirely.
MAX_AGE_DAYS = None

#: What you must type back, verbatim, to actually delete anything --
#: same speed bump as manage_test_database.py's CONFIRM_PHRASE.
CONFIRM_PHRASE = "yes delete these databases"


def _confirm(matches, action_description):
    print("\n%d database(s) %s:" % (len(matches), action_description))
    for t in matches:
        summary = t.get("summary") or {}
        print("  %-20s %-40s started=%s size_kb=%s" % (
            t["id"], t.get("name", "?"),
            (t.get("metadata") or {}).get("test.started", "?"),
            summary.get("value_storage_kb", 0) + summary.get(
                "index_storage_kb", 0)))
    if not matches:
        return False
    print("\n*** About to PERMANENTLY DELETE the %d database(s) above ***"
          % len(matches))
    print("Type %r to proceed, anything else to skip:" % CONFIRM_PHRASE)
    return input("> ").strip() == CONFIRM_PHRASE


def main():
    if MIN_SIZE_KB is None and MAX_AGE_DAYS is None:
        print(
            "MIN_SIZE_KB and MAX_AGE_DAYS are both unset -- edit this "
            "script and set at least one before running it. Refusing to "
            "list/delete anything by default.")
        return

    iq = IQClient(timeout=60)

    if MIN_SIZE_KB is not None:
        matches = iq.list_databases_over_size(MIN_SIZE_KB)
        if _confirm(matches, "at or over %d KB total storage" % MIN_SIZE_KB):
            iq.delete_databases_over_size(MIN_SIZE_KB, dry_run=False)
            print("Deleted.")
        else:
            print("Skipped size-based cleanup.")

    if MAX_AGE_DAYS is not None:
        matches = iq.list_databases_older_than(MAX_AGE_DAYS)
        if _confirm(matches, "older than %d day(s)" % MAX_AGE_DAYS):
            iq.delete_databases_older_than(MAX_AGE_DAYS, dry_run=False)
            print("Deleted.")
        else:
            print("Skipped age-based cleanup.")


if __name__ == "__main__":
    main()
