"""End-to-end example for an AION-hosted deployment -- IQ-PYTHON-002 (the
AION half), taken all the way through to real queries instead of stopping
at discovery. See discover_aion.py for AION *discovery* edge cases in
isolation (aion_node_name=/aion_port_name=/wrong credentials/env-based
config) -- this file assumes discovery already works and focuses on what
comes after: is everything downstream (list_tests/list_views/
query(name=...)/live vs eot/filters/auto_repair/multi-database) really
identical to local mode once connected?

Short answer: yes -- AION only changes *how* IQClient resolves base_url=
and picks up its auth token (see tciqrestclient/aion_discovery.py); every method
called below is the exact same call as its local-mode counterpart in
run_view_query.py/run_live_query.py/query_modifiers.py/
multi_database_query.py/auto_repair_demo.py. What genuinely differs
between deployments is server *content*, not client behavior -- CONFIRMED
2026-09-08 against a real AION org sharing the exact same underlying test
data as this repo's local dev server: it exposed only 33 views vs. the
local server's 507, and didn't have "Detailed Stream Results" (the view
every other example hardcodes) at all (see HANDOVER.md section 0g).

So rather than hardcoding one view name and bailing if it's missing like
the local examples do, this script discovers a *usable* table view at
runtime -- VIEW_NAME below is tried first, then it falls back to any
single_level_table/paged_single_level_table view the server actually has
(see SUPPORTED_VIEW_TYPES). The point of this file is to actually exercise
real query traffic against whatever AION deployment you point it at,
covering the same edge cases the local-mode examples each cover
individually -- eot vs. live data, filters=/sort=/group_by=/
snapshot_name=, auto_repair, and database_id= across multiple tests --
each wrapped in its own try/except so one deployment quirk (a missing
table, no currently-running test, an unfilterable column) doesn't stop
the rest of the walkthrough from running.

Configure via TCIQ_AION_URL/TCIQ_AION_USERNAME/TCIQ_AION_PASSWORD (and
optionally TCIQ_AION_NODE_NAME/TCIQ_AION_PORT_NAME) in the environment or
a .env file -- see .env.example. Nothing is hardcoded here; if AION isn't
configured, this exits with a clear message instead of a traceback.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import (
    IQConfigError, IQConnectionError, IQQueryError, IQRequestError,
    IQViewError,
)
from tciqrestclient.view_query_builder import SUPPORTED_VIEW_TYPES

OWNER = "owner-name"
VIEW_NAME = "Detailed Stream Results"


def _first_queryable_view(views):
    """VIEW_NAME if it exists, else the first single_level_table/
    paged_single_level_table view on the server -- see the module
    docstring for why this doesn't just hardcode one name and bail like
    the local-mode examples do."""
    by_name = {v["name"]: v for v in views}
    if VIEW_NAME in by_name:
        return by_name[VIEW_NAME]
    for v in views:
        if v.get("details", {}).get("view_type") in SUPPORTED_VIEW_TYPES:
            return v
    return None


def main():
    print("Connecting via AION (TCIQ_AION_URL/TCIQ_AION_USERNAME/"
          "TCIQ_AION_PASSWORD from the environment/.env) ...")
    try:
        iq = IQClient(timeout=60)
    except IQConfigError as e:
        print("  Not configured for AION (or anything else): %s" % e)
        print("  Set TCIQ_AION_URL/TCIQ_AION_USERNAME/TCIQ_AION_PASSWORD "
              "(see .env.example) to run this for real.")
        return
    except IQConnectionError as e:
        print("  AION discovery failed: %s" % e)
        return
    print("  connected: base_url=%s" % iq.base_url)

    # --- tests -----------------------------------------------------------
    my_tests = iq.list_tests(owner=OWNER)
    if not my_tests:
        print("\nNo tests found for owner=%r on this deployment -- edit "
              "OWNER to a real user, or seed test data first." % OWNER)
        return
    iq.use_test(my_tests[0]["id"])
    print("\n%d test(s) for %r; using: %s (%s)" % (
        len(my_tests), OWNER, my_tests[0]["name"], my_tests[0]["id"]))

    # --- views -------------------------------------------------------------
    # timeout=60: GET /views can be slow on a server with hundreds of views
    # -- true on AION too, not just local (see run_view_query.py).
    views = iq.list_views(timeout=60)
    print("\n%d view(s) on this deployment (a real AION org tested "
          "2026-09-08 had only 33 vs. a local dev server's 507 -- view "
          "catalogs are per-deployment, not tied to the test data)."
          % len(views))

    view = _first_queryable_view(views)
    if not view:
        print("No queryable (%s) view found on this deployment -- nothing "
              "left to demonstrate." % ", ".join(SUPPORTED_VIEW_TYPES))
        return
    fallback_note = (
        "" if view["name"] == VIEW_NAME else
        " -- VIEW_NAME=%r not found here, fell back to this one"
        % VIEW_NAME)
    print("Using view: %r (view_type=%s)%s" % (
        view["name"], view["details"].get("view_type"), fallback_note))

    # --- eot/snapshot query ------------------------------------------------
    rows = []
    try:
        rows = iq.query(view["name"], False, limit=50, timeout=60)
        print("\n%d snapshot (eot) row(s):" % len(rows))
        for row in rows[:3]:
            print(" ", row)
    except IQViewError as e:
        print("\nCouldn't build a snapshot query from %r: %s" % (
            view["name"], e))
    except IQRequestError as e:
        print("\nSnapshot query failed: %s" % e)

    # --- auto_repair ---------------------------------------------------
    # last_dropped_columns reflects whichever query() call above touched
    # it most recently -- only meaningful if that query actually ran.
    if rows:
        if iq.last_dropped_columns:
            print("\nColumns auto_repair=True (the default) silently "
                  "dropped to make that query succeed:")
            for col in iq.last_dropped_columns:
                print("  %s" % col)
            print("Re-running with auto_repair=False to show the original "
                  "error instead:")
            try:
                iq.query(view["name"], False, limit=50, timeout=60,
                         auto_repair=False)
                print("  (expected this to raise IQRequestError -- it "
                      "didn't)")
            except IQRequestError as e:
                print("  %s" % e)
        else:
            print("\nNothing was dropped by auto_repair -- this "
                  "deployment's database has every column %r's template "
                  "references." % view["name"])

    # --- filters=/sort=/group_by= -------------------------------------
    try:
        columns = iq.list_view_columns(
            view["name"], test_live=False, active_only=True, timeout=60)
    except (IQViewError, IQRequestError) as e:
        print("\nCouldn't list %r's columns: %s" % (view["name"], e))
        columns = []

    # Column dicts are {"name", "alias_name", "display_name"} -- no type
    # info, so this doesn't try to guess "numeric" like a schema-aware
    # example could; it just attempts a filter/sort and reports whatever
    # happens, same as the rest of this script's "try it, report the
    # outcome either way" approach.
    candidates = [c["alias_name"] for c in columns
                  if "snapshot" not in c["alias_name"]] or [
        c["alias_name"] for c in columns]
    if candidates:
        col = candidates[0]
        try:
            filtered = iq.query(
                view["name"], False, filters=[(col, "gte", 0)],
                sort="%s DESC" % col, limit=10, timeout=60)
            print("\nfilters=/sort= on %r -- %d row(s):" % (
                col, len(filtered)))
            for row in filtered[:3]:
                print(" ", row)
        except (IQViewError, IQQueryError, IQRequestError) as e:
            print("\nfilters=/sort= on %r didn't work here (%s) -- "
                  "expected for a non-numeric or unfilterable column; "
                  "pick a different one from list_view_columns() above."
                  % (col, e))

        try:
            grouped = iq.query(
                view["name"], False, group_by=[col], limit=50, timeout=60)
            print("\nGrouped by %r -- %d row(s)." % (col, len(grouped)))
        except (IQViewError, IQQueryError, IQRequestError) as e:
            print("\ngroup_by=%r didn't work here: %s" % (col, e))
    else:
        print("\nNo active column found on %r to demonstrate filters=/"
              "sort=/group_by= against." % view["name"])

    # --- snapshot_name= ------------------------------------------------
    snapshot_col = next(
        (c["alias_name"] for c in columns if "snapshot_name" in c["alias_name"]),
        None)
    if rows and snapshot_col and rows[0].get(snapshot_col):
        snap = rows[0][snapshot_col]
        try:
            snap_rows = iq.query(
                view["name"], False, snapshot_name=snap, limit=5, timeout=60)
            print("\n%d row(s) restricted to snapshot %r:" % (
                len(snap_rows), snap))
        except (IQViewError, IQRequestError) as e:
            print("\nsnapshot_name=%r didn't work here: %s" % (snap, e))
    else:
        print("\nNo snapshot-name column found on these rows -- skipping "
              "snapshot_name= (see run_view_query.py for that in "
              "isolation against a view confirmed to have one).")

    # --- live data -------------------------------------------------------
    print("\nLive (test_live=True) data for %r's currently-running test, "
          "if any:" % OWNER)
    try:
        live_rows = iq.query(
            view["name"], True, user=OWNER, limit=10, timeout=30)
        print("  %d row(s)" % len(live_rows))
    except IQViewError as e:
        print("  Couldn't build a live query from %r: %s" % (
            view["name"], e))
    except IQQueryError as e:
        print("  No test owned by %r is currently running: %s" % (OWNER, e))
    except IQRequestError as e:
        print("  Live query failed: %s" % e)

    # --- multi-database: database_id= override --------------------------
    if len(my_tests) > 1:
        print("\nSame view, queried per-test via database_id= (not "
              "use_test()) across the first few tests:")
        for t in my_tests[:3]:
            try:
                per_test_rows = iq.query(
                    view["name"], False, database_id=t["id"],
                    limit=5, timeout=30)
                print("  %-40s -> %d row(s)" % (
                    t["name"], len(per_test_rows)))
            except IQViewError as e:
                print("  %-40s -> no matching view/table: %s" % (
                    t["name"], e))
            except IQRequestError as e:
                print("  %-40s -> query failed: %s" % (t["name"], e))
    else:
        print("\nOnly one test found for %r -- can't demonstrate "
              "database_id= across multiple tests (see "
              "multi_database_query.py for that in isolation)." % OWNER)


if __name__ == "__main__":
    main()
