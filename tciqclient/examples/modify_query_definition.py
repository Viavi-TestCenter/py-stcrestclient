"""Modify a query definition directly, then run it -- for when
filters=/sort=/group_by=/time_range= (query_modifiers.py, IQ-PYTHON-005)
aren't expressive enough. Those all go through tciqrestclient.query.
merge_modifiers() under the hood, which only ever *appends* structured,
AND-ed conditions to a definition's outermost node -- it can't express
an OR across two conditions, and it can't remove or replace anything
already on the definition. This file is about the definition itself: a
plain Python dict (see tciqrestclient/query.py's module docstring for its real
shape), free to edit however a dict allows, before handing it to
query(definition=...).

Where does the starting definition come from? tciqrestclient.views.
get_view_definition() -- the same function query(name=...) calls
internally -- builds one from an existing view's own query_provider
templates, so there's no need to hand-write one from scratch or capture
one from the GUI (see run_view_query.py's RAW_DEFINITION / run_json_
definition_query.py's RAW_DEFINITION_JSON for that alternative starting
point -- either works equally well as something to modify).

Three modifications demonstrated below, each something merge_modifiers()
genuinely cannot do:
  1. An OR-combined filter -- merge_modifiers()'s filters= are always
     AND-ed together as separate array entries; a single raw expression
     string with OR inside parens is the only way to express "either"
     instead.
  2. Removing a projection -- merge_modifiers() only ever appends;
     there's no "drop this column" equivalent for any of its modifiers.
  3. Overwriting (not appending to) the orders list.

"Detailed Stream Results" (like every real single_level_table capture
seen so far) has exactly one top-level child subquery, aliased "view" --
that's why every outer-node field reference below is qualified
"view.<field>". This isn't a fixed rule for every view's definition,
just this one's own tree shape -- _outer_prefix() below determines it
the same way tciqrestclient.query._resolve_prefix() does internally, rather than
hardcoding "view." blindly, so this still does the right thing (or says
so) against a view whose definition is shaped differently.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError, IQViewError
from tciqrestclient import view_query_builder
from tciqrestclient import views as views_mod

VIEW_NAME = "Detailed Stream Results"

#: query(name=..., auto_repair=True)'s retry-and-strip trick (see
#: auto_repair_demo.py) only applies to name= queries -- a raw
#: definition= bypasses it entirely, so the same "unknown attribute"
#: error a database missing some of the view's optional columns can
#: raise (real, confirmed -- see HANDOVER.md section 4) resurfaces here
#: uncaught. Cap how many columns this example will strip itself, the
#: same way IQClient's own MAX_AUTO_REPAIR_ATTEMPTS does.
MAX_REPAIR_ATTEMPTS = 100


def _run_with_manual_repair(iq, definition, **query_kwargs):
    """query(definition=...) with the same strip-and-retry auto_repair
    does for name= queries, applied by hand -- using tciqrestclient.
    view_query_builder's own public helpers directly, since definition=
    doesn't get this for free. Mutates `definition` in place (removing
    whatever got stripped) so every modification demonstrated after this
    call starts from an already-clean definition, not just this one
    call."""
    attempts_left = MAX_REPAIR_ATTEMPTS
    while True:
        try:
            return iq.query(definition=definition, **query_kwargs)
        except IQRequestError as e:
            raw_projection = view_query_builder.parse_unknown_attribute_error(
                str(e))
            if not raw_projection or attempts_left <= 0:
                raise
            if not view_query_builder.strip_unknown_attribute(
                    definition, raw_projection):
                raise
            print("  (stripped unsupported column: %s)" % raw_projection)
            attempts_left -= 1


def _outer_prefix(node):
    """The alias to qualify a bare field name with, e.g. "view" in
    "view.frame_count" -- only unambiguous when the node has exactly one
    child subquery. None otherwise (a flat node, or more than one
    child) -- same rule tciqrestclient.query._resolve_prefix() applies internally
    for filters=/sort=/group_by=."""
    subqueries = node.get("subqueries") or []
    if len(subqueries) == 1:
        return subqueries[0].get("alias")
    return None


def main():
    iq = IQClient(timeout=60)

    my_tests = iq.list_tests(owner="she83111")
    if not my_tests:
        print("No tests found for that owner.")
        return
    iq.use_test(my_tests[0]["id"])

    view = iq.find_view(VIEW_NAME, timeout=60)
    if not view:
        print("No view named %r -- edit VIEW_NAME to a real table view "
              "on your server." % (VIEW_NAME,))
        return

    # Same idiom run_view_query.py/query_modifiers.py use to discover a
    # real column name before hardcoding one -- avoids guessing an alias
    # that doesn't exist on this particular view/database pair.
    columns = iq.list_view_columns(
        VIEW_NAME, test_live=False, active_only=True, timeout=60)
    if not columns:
        print("No active columns on %r -- nothing to filter/sort by."
              % VIEW_NAME)
        return
    column = columns[0]["alias_name"]
    # A second, different column for the OR-filter demo below -- falls
    # back to the same column (with a different bound) if the view only
    # has one active column.
    column2 = columns[1]["alias_name"] if len(columns) > 1 else column
    print("Using columns %r/%r for the filter/order modifications below."
          % (column, column2))

    built = views_mod.get_view_definition(view, data_type="eot")
    if built["kind"] != "single":
        print(
            "%r is a %r-kind view_type (histogram/boxplot build more "
            "than one query) -- this example only covers the single-"
            "definition case; see run_histogram_query.py/"
            "run_boxplot_query.py for those." % (VIEW_NAME, built["kind"]))
        return
    definition = built["definition"]
    node = definition["multi_result"]  # this view's one outermost node
    prefix = _outer_prefix(node)
    if not prefix:
        print(
            "Can't unambiguously qualify %r's field names (its outermost "
            "node has zero or multiple child subqueries) -- qualify them "
            "as 'alias.%s' yourself below instead of relying on prefix="
            % (VIEW_NAME, column))
        return

    try:
        baseline = _run_with_manual_repair(
            iq, definition, limit=100, timeout=60)
        print("\nBaseline (unmodified) -- %d row(s):" % len(baseline))
        for row in baseline[:3]:
            print(" ", row)
    except (IQViewError, IQRequestError) as e:
        print("Baseline query failed: %s" % e)
        return

    # 1. OR-combined filter -- filters=[(a, "gt", 0), (b, "gt", 0)] on
    # query() would AND these together; only a single raw expression
    # string with OR inside parens can express "either" instead. (Tried
    # "x>0 OR x IS NOT NULL" here first -- CONFIRMED against a real
    # server 2026-09-11 that IS NOT NULL is rejected outright for a
    # numeric column: "null checks are only valid for columns" -- so
    # this ORs two plain numeric comparisons instead, across two
    # different columns when the view has them.)
    or_filter = "(%s.%s>0 OR %s.%s>0)" % (prefix, column, prefix, column2)
    node["filters"].append(or_filter)
    try:
        rows = iq.query(definition=definition, limit=100, timeout=60)
        print("\nWith an OR-combined filter appended directly -- %d "
              "row(s):" % len(rows))
    except IQRequestError as e:
        print("\nOR-filter query didn't work here: %s" % e)
    node["filters"].pop()  # undo -- keep the next modification isolated

    # 2. Remove a projection -- drop whichever column was projected last,
    # rather than assuming a specific one exists on every deployment.
    if len(node["projections"]) > 1:
        dropped = node["projections"].pop()
        try:
            rows = iq.query(definition=definition, limit=10, timeout=60)
            got_columns = len(rows[0]) if rows else 0
            print("\nAfter removing projection %r -- %d row(s), %d "
                  "column(s) each (was %d):" % (
                      dropped, len(rows), got_columns,
                      len(node["projections"]) + 1))
        except IQRequestError as e:
            print("\nQuery after removing a projection didn't work here: "
                  "%s" % e)
        node["projections"].append(dropped)  # restore

    # 3. Overwrite (not append to) orders -- merge_modifiers()'s sort=
    # always appends another order entry after the definition's own
    # existing ones (e.g. "Detailed Stream Results"' default
    # test_snapshot_name/tx_stream_stream_id order -- see
    # tciqrestclient/views.py's _find_provider_elsewhere() docstring), so it only
    # ever breaks ties, rather than actually taking effect as the
    # primary sort -- CONFIRMED 2026-09-11: sort="<column> DESC" and
    # sort="<column> ASC" produced byte-identical row order on a real
    # server for exactly this reason. This replaces orders outright, so
    # the new key genuinely is the primary (only) sort this time.
    node["orders"] = ["%s.%s DESC" % (prefix, column)]
    try:
        # A bigger limit than the other demos above -- large enough to
        # show this column's real (non-null) values as well as any
        # nulls, since a null-valued row can legitimately sort before
        # every real value under some DESC null-ordering conventions
        # (CONFIRMED against a real server 2026-09-11 -- a limit=5 here
        # showed 5/5 None, which looked broken until raising the limit
        # showed real values further down the same DESC-sorted list).
        rows = iq.query(definition=definition, limit=30, timeout=60)
        print("\nWith orders= overwritten to sort by %r DESC -- %d "
              "row(s), first 10 values:" % (column, len(rows)))
        for row in rows[:10]:
            print("  %s = %s" % (column, row.get(column)))
    except IQRequestError as e:
        print("\nQuery with overwritten orders= didn't work here: %s" % e)


if __name__ == "__main__":
    main()
