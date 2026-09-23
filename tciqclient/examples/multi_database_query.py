"""Multi-database support -- IQ-PYTHON-007: query any test's results,
not just whichever one is "current", without switching back and forth.
This matters most for post-test processing pipelines that analyze
several finished tests' results after the fact, potentially in the same
run.

Two ways to point a call at a specific database:
  - use_test(database_id) sets the *default* for every call afterwards
    (what run_view_query.py and friends use) -- convenient for a script
    that mostly works with one test at a time.
  - database_id=<id> on an individual query()/get_test()/etc. call
    overrides the default for just that one call, without changing it
    for anything else -- this is what a pipeline iterating over several
    tests actually wants, demonstrated below.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError

VIEW_NAME = "Detailed Stream Results"


def main():
    iq = IQClient()

    my_tests = iq.list_tests(owner="she83111")
    if len(my_tests) < 2:
        print(
            "Need at least 2 tests for this example to be meaningful "
            "(found %d) -- it'll still run against just one, but won't "
            "demonstrate anything multi-database-specific." % len(my_tests))
    if not my_tests:
        return

    # Set a default (e.g. for whatever "primary" test a script is mostly
    # about) -- calls with no database_id= fall back to this one.
    iq.use_test(my_tests[0]["id"])
    print("Default test: %s (%s)" % (my_tests[0]["name"], my_tests[0]["id"]))

    default_test = iq.get_test()  # no database_id= -- uses the default
    print("get_test() with no database_id= returns the default: %s" % (
        default_test["name"]))

    # Now iterate over every test's results *without* touching the
    # default -- each call below explicitly names its own database_id=.
    print("\nPulling a few rows from each test's own database_id=, "
          "without changing the default:")
    for test in my_tests[:5]:
        try:
            rows = iq.query(
                name=VIEW_NAME, data_type="eot",
                database_id=test["id"], limit=5, timeout=30)
            print("  %-40s -> %d row(s)" % (test["name"], len(rows)))
        except IQViewError as e:
            print("  %-40s -> no matching view/table: %s" % (
                test["name"], e))
        except IQRequestError as e:
            print("  %-40s -> query failed: %s" % (test["name"], e))

    # Confirm the default really didn't change.
    still_default = iq.get_test()
    print("\nDefault test after the loop is still: %s" % (
        still_default["name"]))
    assert still_default["id"] == my_tests[0]["id"]


if __name__ == "__main__":
    main()
