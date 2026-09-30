"""List the IQ tests (databases) owned by a given user.

Covers PLAN.md step 2: get test ids from the IQ server by username, along
with the metadata needed to identify the right one.

Configure the connection via a .env file (see .env.example) or environment
variables -- nothing is hardcoded here.
"""
from tciqrestclient import IQClient


def main():
    iq = IQClient(timeout=120)

    owner = "test-owner"
    tests = iq.list_tests(owner=owner)

    print("Tests owned by %s:" % owner)
    for test in tests:
        print("  %s  %-40s started=%s" % (
            test["id"],
            test["name"],
            test["metadata"].get("test.started", "?"),
        ))

    if tests:
        detail = iq.get_test(tests[0]["id"])
        print("\nFull metadata for %s:" % tests[0]["name"])
        for key, value in detail["metadata"].items():
            print("  %s = %s" % (key, value))


if __name__ == "__main__":
    main()
