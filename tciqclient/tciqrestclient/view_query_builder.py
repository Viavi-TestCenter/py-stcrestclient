"""Build an executable query definition from a saved view's own
declarative template -- CONFIRMED against two real captured queries (one
unfiltered, one with a filter added), not guessed.

A view's `details` (the GUI-editable spec: `view_type`, and one or more
`tables` entries naming a `query_provider` by string id, plus the active
`columns`/`primary_dimension_attributes`) cannot itself be POSTed to
/queries -- see the module docstring in tciqrestclient/views.py for why that
earlier assumption was wrong. But `effective_details.system_data.
query_providers[]` -- present on every view returned by GET /views --
turns out to hold the *template* the GUI itself uses to build a query
from that spec:

  - `base_query`: the skeleton `multi_result` tree for that provider
    (join conditions already in place; some providers' leaf nodes also
    come with a small pre-populated set of raw projections baked in,
    independent of any active column).
  - `attribute_query_updates` / `fact_query_updates` /
    `derived_fact_query_updates`: one entry per column the provider
    supports, each with `query_updates` -- a list of {key, values} pairs
    where `key` is a '/'-separated path into the tree (numeric segments
    index into lists) and `values` are literal strings to append there.
    When the same name appears in more than one list, derived_fact wins
    over fact wins over attribute -- the derived/computed formula is the
    correct one (e.g. avg_latency is total_latency/frame_count, not a
    plainly-named raw column).
  - `default_order_updates`: the view's default sort, applied
    unconditionally. "attribute"-type entries reuse that column's own
    `orders`-action template if it has one (for a "_order"-suffixed
    sort-helper column), else fall back to sorting on its plain outermost
    alias. "custom"-type entries carry their own query_updates directly.

This module walks a view table's active columns
(primary_dimension_attributes + columns, in order) through that
provider's templates and appends the resulting fragments -- deduplicated,
since a column's supporting raw projection is often shared by another
active column (e.g. duplicate_frame_count backs both its own column and
stream_stats.frame_loss's formula) -- producing the same `multi_result`
tree the GUI's own POST /queries call would use.

Confirmed exact (structural equality, not just "looks right") against
two real captures of "Detailed Stream Results": the unfiltered query, and
the same query with a `rx_stream_stats.min_latency < 0.17` filter added.
One asymmetry observed in that process: a "custom" default_order_updates
entry's own view-level projection also gets mirrored up to an outermost
projection (apparently needed for stable pagination row identity), while
"attribute"-type default orders do not get this. That mirroring is
implemented generically (keyed off appends to the single-child "view"
node's own projections) so it's a harmless no-op for ordinary columns,
which already add their own outermost projection explicitly.

This module does not build ad-hoc filters/sort itself -- once the base
definition is built, filters/sort/group_by/time_range/limit are layered
on the same way as for a hand-built definition=, via
tciqrestclient.query.merge_modifiers() (see tciqrestclient/client.py's query()). That applies
filters against the outermost node's own aliases (e.g.
"view.rx_stream_stats_min_latency<0.17"). NOTE: this is NOT
byte-for-byte what the GUI itself sends -- the GUI pushes a filter down
into the specific inner subquery where the raw column lives (e.g.
"(rx_stream_stats.min_latency) < 0.17" inside the rxss subquery, per
req2.txt). Both shapes are accepted by merge_modifiers()'s general,
already-tested mechanism, and outermost-qualified filtering is
documented elsewhere in this codebase as the supported way to filter any
definition -- but the outermost-style shape specifically applied to a
*builder*-produced definition has not itself been captured/confirmed
against a real server. If a filtered query(name=...) call behaves
unexpectedly, that's the first thing to check with a debug=True capture.

Beyond table (single_level_table/paged_single_level_table -- confirmed as
above), this module also builds x_y_chart/pie_chart/histogram/boxplot
queries, reverse-engineered from magellan-frontend's own widget model
source (the production GUI, not guessed) rather than from a captured
request -- see WIDGET_QUERY_PLAN.md for the per-type findings and which
provider field names are still ASSUMED rather than confirmed. Each of
those builders is flagged in its own docstring; treat them as "should be
structurally correct" rather than "confirmed", until validated against a
real server the same way table was.

Because not every view_type produces exactly one query (histogram is one
query per provider; boxplot is one per statistic), build_query_definition()
returns a tagged dict rather than a bare `multi_result` tree:
{"kind": "single", "definition": <tree>} for the types that are genuinely
one query, or {"kind": "multi", "definitions": {<name>: <tree>, ...}} for
the ones that aren't. This is what lets tciqrestclient.client.IQClient.query()
remain the *only* public query method -- it inspects this tag internally
rather than the caller needing a different method per widget type.

`chart` (a live/time-series line chart widget, e.g. "Port Frame Rate
Chart") is a further step beyond all of the above -- CONFIRMED against a
real local server 2026-09-24, and NOT built via this module's usual
_BUILDERS/_resolve_table_and_provider() path at all (there's no
details.user_data.tables list, and effective_details.system_data has no
query_providers[] -- see IQClient.query()'s SUPPORTED_VIEW_TYPES check,
which routes "chart" to build_chart_duration_probe_definitions()/
build_chart_query_definitions() below instead). Its real system_data
shape is a small query-templating engine: `series[]` (one entry per
plottable measurement, each naming a `base_queries[]` entry plus a list
of {"key": "<path>", "values": [...]} patches -- see
_apply_chart_query_updates() below for the same key/values shape every
other builder's query_updates already use, but WITHOUT that mirror-to-
outermost-projection side effect _apply_query_updates() has, since
chart's own subqueries alias as "leaf", not "view", and its own
templates already include their own outermost-projection update
entries explicitly) and `sampling_duration_providers[]` (a real,
separate query that has to run FIRST for non-live data, to learn how
finely this test's real data is actually sampled -- fed into the
{duration} placeholder every series' own template's non-live query
references). See build_chart_duration_probe_definitions()'s and
build_chart_query_definitions()'s own docstrings for the full two-phase
flow and what's confirmed vs. inferred (in particular: the exact
rounding rule turning a real sampling rate into an ISO-8601 {duration}
string isn't confirmed from a frontend source, just a reasonable
ceil()-based inference against real data).
"""
import copy
import math
import re

from .exceptions import IQViewError

#: view_types confirmed to produce a `multi_result` tree this way via
#: the single-pure-function-per-type _BUILDERS mechanism below. "chart"
#: (CHART_VIEW_TYPE below) is ALSO now supported by IQClient.query(),
#: but deliberately isn't a member of this tuple/of _BUILDERS -- see the
#: module docstring's "chart" section for why it needs a genuinely
#: different, network-involving two-phase build instead. Other view_types
#: (gauge/health_indicator/event_dashboard/etc.) remain unchecked and may
#: use a different result shape entirely (or none -- some view_types
#: aren't backed by a row-returning query at all). Derived from
#: _BUILDERS below (defined at the bottom of this module) so the two can
#: never drift apart.
SUPPORTED_VIEW_TYPES = ()  # set at the bottom of this module


def build_query_definition(view, table_index=0, snapshot_name=None):
    """Build an executable query (or queries) for one of a view's tables,
    from its provider's own declarative template.

    Arguments:
    view        -- A view object as returned by get_view()/
                   find_view_by_name()/list_views() -- must include
                   `effective_details` (present by default on a real
                   server's response).
    table_index -- Index into view["details"]["user_data"]["tables"].
                   Most views have exactly one table; a few (e.g.
                   "Detailed Stream Results") have more than one --
                   typically one per data_type ("live" while a test
                   runs, "eot" for its finished snapshot, etc). Defaults
                   to the first.
    snapshot_name -- Restrict results to one specific named snapshot
                   (mirrors the GUI's own snapshot selector -- see
                   _apply_snapshot_filter()). None (default) applies no
                   such filter, i.e. every snapshot merged together, same
                   as before this argument existed. Only valid against a
                   table whose data_type is "eot" (see Raises below) --
                   "test.snapshot_name" is a finished-test/snapshot
                   concept; a "live" table (a test still running) has no
                   completed snapshots to filter by. Additionally ignored
                   by view_types that don't have a snapshot filter at all
                   even on their eot table (x_y_chart -- confirmed by
                   reading its whole query-building method).

    Return:
    {"kind": "single", "definition": <multi_result dict>} for a
    view_type that's genuinely one query (table, x_y_chart, pie_chart),
    or {"kind": "multi", "definitions": {<name>: <multi_result dict>,
    ...}} for one that isn't (histogram: one per provider; boxplot: one
    per statistic). See tciqrestclient.client.IQClient.query() for how each shape
    gets executed.

    Raises:
    IQViewError -- if the view's view_type isn't one of the confirmed
                  SUPPORTED_VIEW_TYPES, table_index is out of range, the
                  expected system_data/query_provider shape is missing
                  (e.g. the view was fetched without effective_details),
                  or snapshot_name is given for a table whose data_type
                  isn't "eot" (see snapshot_name above) -- e.g. its
                  data_type is "live", or the table doesn't declare a
                  data_type at all. Pass test_live=False (IQClient.
                  query()'s public parameter -- table_index=/data_type=
                  "eot" at this lower level) to select the table that
                  supports it, if this view has one.
    """
    table, provider = _resolve_table_and_provider(view, table_index)
    if snapshot_name and table.get("data_type") != "eot":
        raise IQViewError(
            "snapshot_name=%r was given, but this table's data_type is "
            "%r, not \"eot\" -- a finished-test snapshot is a "
            "'test.snapshot_name'/eot-table concept; a live table (a "
            "test still running) has no completed snapshots to filter "
            "by. Pass test_live=False (or, at this lower level, "
            "table_index=/data_type=\"eot\") to select the table that "
            "supports snapshot_name=, if this view has one." %
            (snapshot_name, table.get("data_type")))
    view_type = _get(view, "details", "view_type")
    builder = _BUILDERS[view_type]
    return builder(table, provider, snapshot_name)


def _resolve_table_and_provider(view, table_index):
    """Shared by build_query_definition()/list_view_columns()/
    build_field_resolver(): validate view_type, look up
    details.user_data.tables[table_index], and find that table's
    query_provider in effective_details.system_data.query_providers.
    Raises IQViewError the same way build_query_definition() documents."""
    name = view.get("name") if view else None
    view_type = _get(view, "details", "view_type")
    if view_type not in SUPPORTED_VIEW_TYPES:
        raise IQViewError(
            "view %r has view_type %r -- only %s are confirmed to build "
            "an executable query this way. Build or capture a "
            "`multi_result` definition directly (see tciqrestclient.query) and "
            "pass it as query(definition=...) instead." %
            (name, view_type, " and ".join(
                repr(t) for t in SUPPORTED_VIEW_TYPES)))

    tables = _get(view, "details", "user_data", "tables") or []
    if not tables:
        raise IQViewError(
            "view %r has no tables in details.user_data" % (name,))
    if not 0 <= table_index < len(tables):
        raise IQViewError(
            "view %r has %d table(s); table_index=%d is out of range" %
            (name, len(tables), table_index))
    table = tables[table_index]

    provider_name = table.get("query_provider")
    providers = _get(view, "effective_details", "system_data",
                      "query_providers") or []
    provider = next(
        (p for p in providers if p.get("name") == provider_name), None)
    if provider is None:
        raise IQViewError(
            "view %r's table references query_provider %r, but no "
            "matching entry was found in effective_details.system_data."
            "query_providers -- was the view fetched with its "
            "effective_details included?" % (name, provider_name))
    return table, provider


def list_view_columns(view, table_index=0, active_only=False):
    """List every column-like attribute a view's table can reference --
    for discovering what's available to filter/sort by (including by its
    GUI display_name, e.g. for query(filters=[("Rx Count", "gt", 0)]) --
    see build_field_resolver()), or just to see what a column is actually
    called internally.

    Arguments:
    view        -- Same as build_query_definition().
    table_index -- Same as build_query_definition().
    active_only -- False (default) lists every column the provider
                  supports (its full attribute/fact/derived_fact_query_
                  updates catalog). True restricts to only the columns
                  actually active on this table (details.user_data.
                  tables[table_index].columns/primary_dimension_
                  attributes) -- what a query for this table actually
                  returns.

    Return:
    List of {"name": <raw attribute path, e.g. "rx_stream_stats.
    frame_count">, "alias_name": <query-safe alias, e.g.
    "rx_stream_stats_frame_count">, "display_name": <GUI label, e.g.
    "Rx Count">} dicts.
    """
    table, provider = _resolve_table_and_provider(view, table_index)
    active_names = None
    if active_only:
        active_names = set(
            list(table.get("primary_dimension_attributes") or []) +
            list(table.get("columns") or []))

    columns = []
    seen_aliases = set()
    for key in ("derived_fact_query_updates", "fact_query_updates",
                "attribute_query_updates"):
        for entry in provider.get(key) or []:
            alias = entry.get("alias_name")
            if not alias or alias in seen_aliases:
                continue  # a name can appear in more than one list --
                          # first hit wins, same priority order as
                          # _find_update_entry().
            if active_names is not None and entry.get("name") not in active_names:
                continue
            seen_aliases.add(alias)
            columns.append({
                "name": entry.get("name"),
                "alias_name": alias,
                "display_name": entry.get("display_name"),
            })
    return columns


def build_field_resolver(view, table_index=0):
    """Return a function that resolves a column reference -- its GUI
    display_name (case-insensitive, e.g. "Rx Count"), raw attribute path
    (e.g. "rx_stream_stats.frame_count"), bare column name (e.g. just
    "frame_count", with no table prefix at all -- see below), or
    already-correct alias_name (e.g. "rx_stream_stats_frame_count") -- to
    the alias_name that tciqrestclient.query.merge_modifiers() needs for
    filters=/sort=/group_by= on a built definition. An unrecognized name
    is passed through unchanged, so an already-qualified name (e.g.
    "view.some_alias") or a name from an expression the resolver doesn't
    need to touch still works.

    Bare column name: a real user complaint was that filters=[("frame_
    count", ...)] didn't work -- only the full "rx_stream_stats.frame_
    count" or the GUI label did. Fixed by also indexing each column by
    the part of its raw attribute path after the last "." -- but ONLY
    when that bare name is unambiguous (exactly one column on this table
    ends in it); a view with both "tx_stream_stats.frame_count" and
    "rx_stream_stats.frame_count" active leaves bare "frame_count"
    unresolved rather than silently guessing which one you meant --
    qualify it (or use the GUI display name) in that case.

    See tciqrestclient.client.IQClient.query()'s resolve_fields= behavior for how
    this gets applied automatically for query(name=...).
    """
    _, provider = _resolve_table_and_provider(view, table_index)
    lookup = {}
    # None once a suffix is seen on two DIFFERENT aliases (ambiguous);
    # the same alias appearing twice (once per override tier -- see the
    # module docstring) doesn't count as a collision.
    suffix_owner = {}
    for key in ("attribute_query_updates", "fact_query_updates",
                "derived_fact_query_updates"):
        for entry in provider.get(key) or []:
            alias = entry.get("alias_name")
            if not alias:
                continue
            for candidate in (entry.get("display_name"), entry.get("name"),
                               alias):
                if candidate:
                    # First hit wins -- matches _find_update_entry()'s
                    # derived > fact > attribute priority, since this
                    # loop visits keys in that same order and never
                    # overwrites an existing lookup entry.
                    lookup.setdefault(candidate.lower(), alias)
            raw_name = entry.get("name")
            if raw_name and "." in raw_name:
                suffix = raw_name.rsplit(".", 1)[-1].lower()
                if suffix in suffix_owner and suffix_owner[suffix] != alias:
                    suffix_owner[suffix] = None
                else:
                    suffix_owner.setdefault(suffix, alias)

    for suffix, alias in suffix_owner.items():
        if alias is not None:
            lookup.setdefault(suffix, alias)

    def resolve(field_name):
        if not isinstance(field_name, str):
            return field_name
        return lookup.get(field_name.lower(), field_name)

    return resolve


#: Matches orion-res's VALIDATION_FAILED response body for a projection
#: that references an attribute the queried database's *own* schema
#: doesn't have -- CONFIRMED from two real 400 responses, worded
#: differently depending on the specific field/deployment:
#:   {"code":"VALIDATION_FAILED","message":"Validation failed: name
#:   error; unknown attribute name: tx_stream_config.ipv4_2_source_addr
#:   as tx_stream_config_ipv4_2_source_addr"}
#:   {"code":"VALIDATION_FAILED","message":"Validation failed: name
#:   error; unknown dimension or result set name:
#:   nfv_adv_k8s_instance_group_instance.instance_kind as instance_kind"}
#: (the second confirmed 2026-09-16 against a real AION-managed orion-res
#: server/view -- "unknown attribute name" and "unknown dimension or
#: result set name" are two distinct phrasings of the same underlying
#: schema-mismatch error, both ending in the same "<raw>.<field> as
#: <alias>" projection fragment auto_repair strips.) This happens even
#: though the view's own query_provider template is valid -- a
#: provider/template is shared across every database that uses that
#: view, but not every database's actual schema has every attribute the
#: template can reference (e.g. a "dual IP/MAC/VLAN config" column only
#: exists for a database whose test used that config -- a single-stack
#: test's database genuinely lacks it). See strip_unknown_attribute()
#: below for the corresponding fix.
_UNKNOWN_ATTRIBUTE_RE = re.compile(
    r"unknown (?:attribute name|dimension or result set name):\s*([^\"]+)")


def parse_unknown_attribute_error(message):
    """Extract the offending raw projection fragment (e.g.
    "tx_stream_config.ipv4_2_source_addr as
    tx_stream_config_ipv4_2_source_addr") from an orion-res
    VALIDATION_FAILED "unknown attribute name: ..." or "unknown
    dimension or result set name: ..." error message/response body, or
    None if it doesn't match either shape.
    """
    if not message:
        return None
    m = _UNKNOWN_ATTRIBUTE_RE.search(message)
    return m.group(1).strip() if m else None


def strip_unknown_attribute(definition, raw_projection):
    """Remove every projection/order referencing the alias a broken
    projection fragment defines (as reported by
    parse_unknown_attribute_error()), from every node of `definition`,
    in place.

    Every level of a built definition re-projects the same alias upward
    (e.g. an inner "(x.y) as z" becomes "rxss.z as z" one level up, then
    "view.z as z" at the outermost level) -- since all of these end in
    "as <alias>", stripping every projection ending that way removes the
    attribute at every level in one pass, not just where it first broke.

    Arguments:
    definition    -- A built query definition (mutated in place).
    raw_projection -- The exact fragment from the error message, e.g.
                     parse_unknown_attribute_error(str(exc)).

    Return:
    True if anything was removed (i.e. this was worth retrying after),
    False if `raw_projection` didn't look like a projection with an
    alias (nothing was changed).
    """
    m = re.search(r"\bas (\w+)$", raw_projection or "")
    if not m:
        return False
    alias = m.group(1)
    removed = [False]

    def strip(node):
        if not isinstance(node, dict):
            return
        projections = node.get("projections")
        if isinstance(projections, list):
            kept = [p for p in projections if not p.endswith("as %s" % alias)]
            if len(kept) != len(projections):
                removed[0] = True
            node["projections"] = kept
        orders = node.get("orders")
        if isinstance(orders, list):
            kept = [o for o in orders
                    if o.rsplit(" ", 1)[0] not in (alias, "view.%s" % alias)]
            if len(kept) != len(orders):
                removed[0] = True
            node["orders"] = kept
        for child in node.get("subqueries") or []:
            strip(child)

    for key in ("multi_result", "single_result"):
        if key in (definition or {}):
            strip(definition[key])
    return removed[0]


# -- internals ------------------------------------------------------------

def _get(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _normalize(node):
    """Real API responses always include subqueries/orders/filters/
    groups/projections on every node; a provider's base_query sometimes
    omits the empty ones on its leaf nodes. Fill them in so appends never
    KeyError, and so the result always has a consistent shape."""
    node.setdefault("subqueries", [])
    node.setdefault("orders", [])
    node.setdefault("filters", [])
    node.setdefault("groups", [])
    node.setdefault("projections", [])
    for child in node["subqueries"]:
        _normalize(child)


def _find_update_entry(provider, name):
    """Look up a column's update template by name. derived_fact takes
    priority over fact over attribute when a name appears in more than
    one -- see module docstring."""
    for key in ("derived_fact_query_updates", "fact_query_updates",
                "attribute_query_updates"):
        for entry in provider.get(key) or []:
            if entry.get("name") == name:
                return entry
    return None


def _resolve_alias_to_name(provider, alias_or_name):
    """CONFIRMED against a real x_y_chart view/capture 2026-09-24: a
    series' own `filter_columns[].name` (e.g. "test_snapshot_name")
    names a column by its query-safe alias, NOT its raw dotted
    attribute name (e.g. "test.snapshot_name") that
    _find_update_entry()/_build_projection_tree() actually key on --
    unlike h_axis/v_axis, which both use the raw dotted form already.
    Passing the alias straight through silently no-ops (see
    _build_projection_tree()'s own "unknown/renamed column -- skip"
    comment) -- confirmed the hard way: the real capture's
    "test_snapshot_name" grouping/projection went missing entirely
    without this. Falls through to `alias_or_name` unresolved (letting
    the caller's own not-found handling decide) if it's already a raw
    name, or doesn't match anything either way."""
    if _find_update_entry(provider, alias_or_name) is not None:
        return alias_or_name
    for key in ("derived_fact_query_updates", "fact_query_updates",
                "attribute_query_updates"):
        for entry in provider.get(key) or []:
            if entry.get("alias_name") == alias_or_name:
                return entry.get("name")
    return alias_or_name


def _get_at_path(tree, path):
    node = tree
    for seg in path.split("/"):
        node = node[int(seg)] if seg.isdigit() else node[seg]
    return node


def _append_at_path(tree, path, values):
    node = _get_at_path(tree, path)
    for v in values:
        if v not in node:  # dedup -- see module docstring
            node.append(v)


def _apply_query_updates(tree, query_updates):
    for upd in query_updates:
        values = upd.get("values")
        if values is None and "value" in upd:
            values = [upd["value"]]
        if values is None:
            continue
        _append_at_path(tree, upd["key"], values)
        if upd["key"] == "multi_result/subqueries/0/projections":
            # Mirror a "view"-level projection's alias up to the
            # outermost projections too. A no-op (deduped) for ordinary
            # columns, which already add their own explicit outermost
            # step -- only has an effect for entries that don't (observed
            # for "custom" default_order_updates entries, e.g.
            # rx_stream.key, needed for stable pagination row identity).
            for v in values:
                m = re.search(r"\bas (\w+)$", v)
                if m:
                    alias = m.group(1)
                    _append_at_path(
                        tree, "multi_result/projections",
                        ["view.%s as %s" % (alias, alias)])


def _apply_default_order_updates(tree, provider, active_names):
    """Apply a provider's default_order_updates. `active_names` is the
    set of column names already walked/projected by the caller (see
    _build_projection_tree()) -- a default-order "attribute"-type entry
    that ISN'T in that set doesn't have a projection for its alias yet,
    so its own projection-producing query_updates have to be applied
    first (mirroring the TS `defaultOrderProjectionIds` ->
    `targetProjections` concat in table.widget.model.ts's
    getQueryDefinition()) -- otherwise the ORDER BY emitted below would
    reference an alias that was never SELECTed. Confirmed missing (real
    bug, not theoretical) by reading that method; harmless no-op for the
    common case where the default-order column is already active, since
    _apply_query_updates()'s per-path dedup makes re-applying the same
    entry's query_updates a no-op."""
    dou = provider.get("default_order_updates") or {}
    for ou in dou.get("order_updates", []):
        if ou.get("type") == "custom":
            _apply_query_updates(tree, ou.get("query_updates") or [])
        elif ou.get("type") == "attribute":
            name = ou.get("name")
            entry = _find_update_entry(provider, name)
            if entry is None:
                continue
            if name not in active_names:
                _apply_query_updates(tree, entry.get("query_updates") or [])
            order_dir = ou.get("order", "ASC")
            interactive = entry.get("interactive_query_updates") or []
            orders_tpl = next(
                (u for u in interactive if u.get("action") == "orders"),
                None)
            if orders_tpl:
                for upd in orders_tpl.get("query_updates") or []:
                    values = upd.get("values") or (
                        [upd["value"]] if "value" in upd else [])
                    values = [v.replace("{order}", order_dir)
                              for v in values]
                    _append_at_path(tree, upd["key"], values)
            else:
                _append_at_path(
                    tree, "multi_result/orders",
                    ["view.%s %s" % (entry.get("alias_name"), order_dir)])


# -- per-view_type builders ------------------------------------------------
#
# Each builder has signature (table, provider, snapshot_name) -> tagged
# dict (see build_query_definition()'s docstring for the {"kind": ...}
# shapes). Registered in _BUILDERS at the bottom of this module, which is
# also where SUPPORTED_VIEW_TYPES is derived from -- the single source of
# truth for "which view_types build_query_definition() accepts".

def _build_projection_tree(provider, active_names):
    """Shared by every builder below: copy a provider's base_query,
    walk `active_names` through its attribute/fact/derived_fact_query_
    updates templates (deduplicated -- see module docstring), and apply
    its default_order_updates. This is the same JSON-path template
    interpreter every widget type in magellan-frontend ultimately uses
    (its `applyUpdates()`/`base.query.provider.ts` equivalent) -- the one
    genuinely shared primitive across all seven widget types, confirmed
    for table and assumed (pending real-capture validation, see
    WIDGET_QUERY_PLAN.md) for the others."""
    base_query = provider.get("base_query")
    provider_name = provider.get("name")
    if not isinstance(base_query, dict) or "multi_result" not in base_query:
        raise IQViewError(
            "provider %r's base_query has no multi_result key -- "
            "unexpected shape, not supported" % (provider_name,))

    tree = copy.deepcopy(base_query)
    _normalize(tree["multi_result"])

    seen = set()
    for column_name in active_names:
        if column_name in seen:
            continue
        seen.add(column_name)
        entry = _find_update_entry(provider, column_name)
        if entry is None:
            continue  # unknown/renamed column -- skip rather than fail
        _apply_query_updates(tree, entry.get("query_updates") or [])

    _apply_default_order_updates(tree, provider, seen)
    return tree


def _active_column_names(table):
    return (list(table.get("primary_dimension_attributes") or []) +
            list(table.get("columns") or []))


def _build_table_query(table, provider, snapshot_name):
    """view_type in ('single_level_table', 'paged_single_level_table') --
    TableWidgetModel.getQueryDefinition() (table.widget.model.ts:305).
    CONFIRMED byte-for-byte against two real captures (see module
    docstring) for the base tree; snapshot_name= is new (not covered by
    either capture, since neither view was snapshot-filtered) -- see
    _apply_snapshot_filter()'s own docstring for its confirmation status.
    """
    tree = _build_projection_tree(provider, _active_column_names(table))
    if snapshot_name:
        _apply_snapshot_filter(tree, provider, snapshot_name)
    return {"kind": "single", "definition": tree}




def _build_pie_chart_query(table, provider, snapshot_name):
    """view_type == 'pie_chart' -- PieChartWidgetModel.
    getQueryDefinition() (pie.chart.widget.model.ts:114). One query.
    NOT yet validated against a real capture (see WIDGET_QUERY_PLAN.md
    section 2.3).

    ASSUMED: the provider declares its mandatory slice-category/
    aggregate-value columns as provider["group_by"]/provider["total"]
    (dedicated fields the GUI always projects regardless of which
    statistics are active, per PieChartWidgetModel) -- the exact JSON key
    names haven't been seen in a real provider export yet; adjust here
    once one is available. Falls back to just the table's own active
    columns if neither field is present, so an unconfirmed guess never
    raises -- it just under-projects instead of failing outright.
    """
    extra = [n for n in (provider.get("group_by"), provider.get("total"))
             if n]
    tree = _build_projection_tree(
        provider, _active_column_names(table) + extra)
    if snapshot_name:
        _apply_snapshot_filter(tree, provider, snapshot_name)
    return {"kind": "single", "definition": tree}


def _build_boxplot_queries(table, provider, snapshot_name):
    """view_type == 'boxplot' -- BoxplotWidgetModel.
    buildQueryDefinitions() (boxplot.widget.model.ts:213), which returns
    one query per selected statistic (a boxplot tile can show several
    independent distributions side by side). NOT yet validated against a
    real capture (see WIDGET_QUERY_PLAN.md section 2.5).

    ASSUMED/INCOMPLETE: the real per-statistic split (v-axis/h-axis/
    groups per BoxplotWidgetModel.getProjections()) isn't derivable from
    a view's own effective_details in any confirmed way yet, so this v1
    treats table["groups"] (if the table declares one) as the list of
    statistic names, each getting an identical query built from the
    table's own active columns -- a placeholder that at least returns the
    right *shape* ({"kind": "multi", ...}) for a boxplot view rather than
    raising, pending a real capture to derive the actual per-statistic
    column split from. Falls back to a single query keyed by the
    provider's name if the table has no "groups" list. Statistic min/max/
    median/quartile/IQR computation is entirely client-side in the GUI --
    not this module's job either way.
    """
    groups = table.get("groups") or [provider.get("name") or "boxplot"]
    definitions = {}
    for stat_name in groups:
        tree = _build_projection_tree(provider, _active_column_names(table))
        if snapshot_name:
            _apply_snapshot_filter(tree, provider, snapshot_name)
        definitions[stat_name] = tree
    return {"kind": "multi", "definitions": definitions}


def _substitute_value_placeholder(value, replacement):
    """Replace the literal "$(value)" placeholder token some
    interactive_query_updates templates use (per magellan-frontend's
    createInteractiveQueryUpdate() and its callers in pie/histogram/
    boxplot) with an actual value at build time. Values without the
    token, or non-string values, pass through unchanged."""
    if isinstance(value, str) and "$(value)" in value:
        return value.replace("$(value)", str(replacement))
    return value


def _apply_snapshot_filter(tree, provider, snapshot_name):
    """Restrict results to one specific named snapshot, mirroring the
    GUI's own snapshot selector (createSnapshotFilters(), confirmed
    present -- by name and by this same two-tier shape -- across table,
    pie, histogram, and boxplot's query-building methods; NOT present in
    xy-chart's).

    Two-tier, matching the GUI: prefer a provider-declared snapshot
    filter template -- provider["snapshot_filter_provider"]'s own
    interactive_query_updates entry with action == "filters", with its
    values' literal "$(value)" placeholder token substituted for
    `snapshot_name` -- and fall back to a "<alias>.test_snapshot_name =
    '<name>'" filter fragment when the provider doesn't declare one.

    CONFIRMED against a real server 2026-09-03 (a real single_level_table
    view whose provider had no snapshot_filter_provider -- see
    HANDOVER.md section 9): the fallback must qualify with the
    outermost node's own alias ("view" -- the same hardcoded alias
    _apply_query_updates() already mirrors projections up to elsewhere
    in this module), not the raw "test.snapshot_name" attribute path a
    prior version of this fallback used. An outermost filter has to
    reference an already-projected alias, the same way merge_modifiers()
    qualifies every other outermost filter (e.g.
    "view.rx_stream_stats_frame_count>100000") -- the raw path is not a
    recognized name at that scope and 400s with "unknown sub-query
    result name: test.snapshot_name = '<name>'".

    The GUI additionally skips this filter entirely when the widget's
    *user-selected* snapshot scope is ALL/LIVE -- not applicable here,
    since tciqrestclient has no such per-call scope concept: omitting
    snapshot_name= already gets the equivalent "no filter" behavior.

    A third shape, CONFIRMED against a real histogram view 2026-09-24:
    `snapshot_filter_provider` can also be a bare string (e.g.
    `"test.snapshot_name"`) instead of the template embedded inline --
    just naming the attribute that serves as the snapshot filter. That
    attribute's own entry (found via _find_update_entry(), same as an
    ordinary active column) is used instead; its own
    interactive_query_updates carry the same action == "filters"
    template shape, unpacked the identical way.

    A fourth case, CONFIRMED against a real x_y_chart view/capture the
    same day: `snapshot_filter_provider` can also just be missing
    (None) even though the "test.snapshot_name" attribute itself still
    has its own interactive_query_updates -- and the real capture
    confirms THAT is what's actually used, not the raw outermost
    fallback below. So None is treated the same as the string case
    above, naming "test.snapshot_name" explicitly -- every provider
    seen so far uses that same canonical name for its snapshot column,
    whether or not it also happens to set snapshot_filter_provider to
    point at it.

    Confirmed real counter-example, same day, that ruled out an even
    simpler version of that fourth case: "Detailed Stream Results"'s
    own real eot provider ALSO has an action == "filters"
    interactive_query_updates entry on "test.snapshot_name" -- but its
    values are the bare literal string "test.snapshot_name", with no
    "$(value)" placeholder token at all (a different template, for
    something else entirely -- not a real, usable filter expression on
    its own). Only a template whose values actually contain "$(value)"
    -- confirmed real for both the histogram and x_y_chart cases above
    -- is treated as a real snapshot-filter template; this table
    provider's own filters-action entry is correctly skipped, falling
    through to the unchanged, already-confirmed outermost fallback.
    """
    def _is_snapshot_filter_action(update):
        if update.get("action") != "filters":
            return False
        updates = update.get("query_updates") or []
        return any("$(value)" in v
                   for upd in updates for v in upd.get("values") or [])

    snapshot_provider = provider.get("snapshot_filter_provider")
    template = None
    if isinstance(snapshot_provider, dict):
        template = next(
            (u for u in
             snapshot_provider.get("interactive_query_updates") or []
             if _is_snapshot_filter_action(u)),
            None)
    else:
        entry = _find_update_entry(
            provider, snapshot_provider or "test.snapshot_name")
        if entry:
            template = next(
                (u for u in entry.get("interactive_query_updates") or []
                 if _is_snapshot_filter_action(u)),
                None)

    if template:
        for upd in template.get("query_updates") or []:
            values = upd.get("values") or (
                [upd["value"]] if "value" in upd else [])
            values = [_substitute_value_placeholder(v, snapshot_name)
                      for v in values]
            _append_at_path(tree, upd["key"], values)
    else:
        _append_at_path(
            tree, "multi_result/filters",
            ["view.test_snapshot_name = '%s'" % snapshot_name])


#: view_type this section applies to. Deliberately NOT a key in
#: _BUILDERS/SUPPORTED_VIEW_TYPES, same reasoning as CHART_VIEW_TYPE
#: below -- see build_histogram_query_definitions()'s own docstring:
#: unlike every _BUILDERS entry, a histogram view has no
#: details.user_data.tables list at all to resolve via
#: _resolve_table_and_provider(), and can genuinely span more than one
#: query_provider in a single call (one query per provider, not one
#: query overall).
HISTOGRAM_VIEW_TYPE = "histogram"


def build_histogram_query_definitions(view, snapshot_name=None):
    """view_type == 'histogram' -- CONFIRMED against a real server
    2026-09-24 (a real "Frame Loss Duration Histogram" view/capture --
    see HANDOVER.md section 9's "histogram" entry), superseding the
    previous NOT-yet-confirmed v1 this replaced.

    Unlike every _BUILDERS entry, histogram's real `details.user_data`
    shape has no `tables` list at all -- it's `{"statistics": [...],
    "group_by", "h_axis", "v_axis", "buckets_config", ...}` instead (one
    entry per selected statistic, e.g. {"statistics":
    "<provider>.<stat>", "group_by": "stream_block.name", ...}), and its
    `effective_details.system_data` carries an extra `statistics[]`
    lookup table (mapping each `"<provider>.<stat>"` full name to its
    `query_provider`/raw `stat_name`) alongside the usual
    `query_providers[]` every _BUILDERS-dispatched type already shares.
    Once a selected statistic is resolved to its provider + raw
    stat_name via that lookup, though, it turns out to need NO new
    templating mechanism at all: `stat_name` (e.g.
    "stream_stats.min_frame_loss_duration") is just an ordinary
    `derived_fact_query_updates` entry on that provider, walked through
    the exact same `_build_projection_tree()`/`_apply_query_updates()`
    primitive every other builder already uses -- confirmed structurally
    identical (byte-for-byte, at every nesting level) to a real captured
    request for it.

    The one genuinely new wrinkle: histogram statistics need grouping,
    unlike a plain table row list. The view's own `details.user_data.
    group_by` (e.g. "stream_block.name") -- NOT `provider["group_by"]`,
    which is a list of every *allowed* choice, not the one actually
    selected, confirmed a wrong assumption in the replaced v1 -- names an
    ordinary attribute whose own `query_updates` already add the right
    `groups` entry at the right nesting level, so it's walked through
    `_build_projection_tree()` exactly like any selected statistic; no
    separate grouping logic is needed.

    A histogram can genuinely span more than one query_provider in a
    single view (see this view_type's own docstring note above) -- each
    distinct provider referenced by the selected statistics gets its own
    query, grouped together the same way the previous v1 already
    returned its result (kept unchanged): {"kind": "multi",
    "definitions": {<provider_name>: <tree>, ...}}.

    Arguments:
    view          -- A view object, as returned by get_view()/
                     find_view_by_name()/list_views() -- must include
                     effective_details.
    snapshot_name -- Same as build_query_definition()'s own -- restricts
                     each provider's query to one named snapshot, but
                     ONLY for a provider that actually has a
                     "test.snapshot_name" attribute of its own --
                     CONFIRMED against a real server that not every
                     provider does ("Stream Latency Histogram View"'s
                     stream_provider_snapshot provider has none at all;
                     unconditionally trying it anyway 400s with "unknown
                     sub-query result name", confirmed the hard way).
                     Silently has no effect on a provider without one,
                     the same "ignored where not applicable" precedent
                     x_y_chart already sets for snapshot_name=. Where a
                     provider does have it, it's included as an active
                     column/grouping dimension whether or not
                     snapshot_name= is actually given (reasonable
                     inference: blending rows across different snapshots
                     into one min/avg/max would otherwise silently
                     produce a meaningless number) -- CONFIRMED only
                     WITH a real snapshot_name given, since the real
                     capture this was built from always had one.

    Raises:
    IQViewError -- the view has no statistics selected, a selected
                  statistic isn't found in system_data.statistics, or
                  its named query_provider isn't found in
                  system_data.query_providers.
    """
    system_data = _get(view, "effective_details", "system_data") or {}
    stat_lookup = {s.get("name"): s for s in system_data.get("statistics") or []}
    providers_by_name = {
        p.get("name"): p for p in system_data.get("query_providers") or []}

    selected = _get(view, "details", "user_data", "statistics") or []
    if not selected:
        raise IQViewError(
            "view %r has no statistics selected" % (view.get("name"),))

    view_group_by = _get(view, "details", "user_data", "group_by")
    groups = {}  # provider_name -> [(stat_name, group_by), ...]
    for stat in selected:
        full_name = stat.get("statistics")
        info = stat_lookup.get(full_name)
        if info is None:
            raise IQViewError(
                "view %r's statistic %r not found in system_data."
                "statistics" % (view.get("name"), full_name))
        provider_name = info.get("query_provider")
        groups.setdefault(provider_name, []).append(
            (info.get("stat_name"), stat.get("group_by")))

    definitions = {}
    for provider_name, stats in groups.items():
        provider = providers_by_name.get(provider_name)
        if provider is None:
            raise IQViewError(
                "view %r references query_provider %r, but no matching "
                "entry was found in effective_details.system_data."
                "query_providers" % (view.get("name"), provider_name))
        group_by_name = (
            next((g for _, g in stats if g), None) or view_group_by)
        # Not every provider supports snapshot-scoping at all -- CONFIRMED
        # against a real server 2026-09-24 ("Stream Latency Histogram
        # View"'s stream_provider_snapshot provider has no
        # snapshot_filter_provider AND no "test.snapshot_name" attribute
        # of its own at all): unconditionally adding it (as the first
        # real capture this was built from needed) 400s with "unknown
        # sub-query result name" for a provider that never projects it.
        # Only add it -- and only attempt snapshot_name= -- when this
        # specific provider actually has it.
        supports_snapshot = _find_update_entry(
            provider, "test.snapshot_name") is not None
        active_names = (
            ([group_by_name] if group_by_name else [])
            + (["test.snapshot_name"] if supports_snapshot else [])
            + [stat_name for stat_name, _ in stats])
        tree = _build_projection_tree(provider, active_names)
        if snapshot_name and supports_snapshot:
            _apply_snapshot_filter(tree, provider, snapshot_name)
        definitions[provider_name] = tree
    return {"kind": "multi", "definitions": definitions}


#: view_type this whole chart-building section below applies to.
#: Deliberately NOT a key in _BUILDERS/SUPPORTED_VIEW_TYPES -- see the
#: module docstring's "chart" section for why it needs a genuinely
#: different two-phase, network-involving build; IQClient.query() checks
#: for this value explicitly before ever consulting SUPPORTED_VIEW_TYPES.
CHART_VIEW_TYPE = "chart"

#: A real DevTools capture of the query the GUI sends for every chart
#: view's "Test Events" plotlines overlay (the marker series every
#: chart view's details.user_data.series ends with, alongside its real
#: numeric series -- see chart_numeric_series() below, which excludes
#: it). Fixed and NOT view-specific -- confirmed 2026-09-24 -- so
#: nothing about this one needed reverse-engineering.
CHART_EVENTS_DEFINITION = {
    "single_result": {
        "projections": [
            "events.name", "events.display_name", "events.category",
            "events.port",
        ],
        "filters": [],
        "groups": [
            "events.name", "events.display_name", "events.category",
            "events.port",
        ],
        "orders": ["events.display_name", "events.port ASC"],
    }
}


def chart_numeric_series(view):
    """The subset of a "chart" view's details.user_data.series that
    carry real queryable data -- excluding the "Test Events" plotlines
    marker series every chart view also lists (see
    CHART_EVENTS_DEFINITION above)."""
    series = _get(view, "details", "user_data", "series") or []
    return [s for s in series if s.get("chart_type") != "plotlines"]


def _find_chart_base_query(system_data, name):
    for entry in system_data.get("base_queries") or []:
        if entry.get("name") == name:
            return entry["query"]
    raise IQViewError(
        "base_query %r not found in system_data.base_queries" % (name,))


def _find_chart_system_series(system_data, name):
    """A user_data series entry (chart_numeric_series()'s own return
    value) only carries display metadata -- its real query_details/
    series_query_providers live on the matching-by-name entry in
    effective_details.system_data.series instead, confirmed against a
    real server."""
    for entry in system_data.get("series") or []:
        if entry.get("name") == name:
            return entry
    return None


def _apply_chart_query_updates(tree, query_updates):
    """Like _apply_query_updates() above (same {"key": "a/b/0/c",
    "values": [...]} shape, same per-path append-with-dedup via
    _append_at_path()) but WITHOUT that function's mirror-to-outermost-
    projection side effect: chart's own subqueries alias as "leaf", not
    "view", so that mirror's hardcoded "view.%s as %s" would emit a
    wrong, unresolvable alias reference here -- confirmed by inspecting
    a real chart view's own templates, which already include their own
    explicit "multi_result/projections" update entries wherever a
    subquery's projection needs to surface at the outer level (e.g.
    "sum(leaf.generator_frame_rate) as value"), so no such mirroring is
    ever needed for this view_type."""
    for upd in query_updates:
        values = upd.get("values")
        if values is None and "value" in upd:
            values = [upd["value"]]
        if values is None:
            continue
        _append_at_path(tree, upd["key"], values)


def build_chart_duration_probe_definitions(view, is_live):
    """Phase 1 of building a "chart" view_type's real queries (see
    build_chart_query_definitions() for phase 2). For non-live/
    "completed" data, every numeric series' template's {duration}
    placeholder needs a real number first -- how finely this specific
    test's real data happens to be sampled, from actually running its
    sampling_duration_provider's own real query. Not needed at all for
    live data -- CONFIRMED against a real server: the live_data variant
    of every series template has no {duration} placeholder anywhere.

    Return:
    {} if is_live. Otherwise {<sampling_duration_provider name>:
    <multi_result dict>} -- one entry per DISTINCT provider referenced
    by this view's numeric series (usually one per series, but two
    series legitimately share the same provider when they come from the
    same measurement table -- deduplicated so it's only probed once).
    IQClient.query() runs each of these for real, then passes the
    resulting {name: avg_sampling_time} into
    build_chart_query_definitions()'s duration_by_provider= argument.

    Raises:
    IQViewError -- the view has no numeric series, a series has no
                  query_details, or a series' own
                  sampling_duration_provider name doesn't match anything
                  in system_data.sampling_duration_providers.
    """
    if is_live:
        return {}

    system_data = _get(view, "effective_details", "system_data") or {}
    series_list = chart_numeric_series(view)
    if not series_list:
        raise IQViewError(
            "view %r has no numeric series to query" % (view.get("name"),))

    probes = {}
    for series in series_list:
        name = series.get("name")
        system_series = _find_chart_system_series(system_data, name)
        query_details = system_series and (
            system_series.get("query_details") or [None])[0]
        if not query_details:
            raise IQViewError(
                "view %r's series %r has no matching entry (with "
                "query_details) in effective_details.system_data.series" %
                (view.get("name"), name))
        provider_name = query_details.get("sampling_duration_provider")
        if not provider_name or provider_name in probes:
            continue
        provider = next(
            (p for p in system_data.get("sampling_duration_providers") or []
             if p.get("name") == provider_name), None)
        if provider is None:
            raise IQViewError(
                "view %r's series %r references sampling_duration_provider "
                "%r, but no matching entry was found in system_data."
                "sampling_duration_providers" %
                (view.get("name"), series.get("name"), provider_name))
        tree = copy.deepcopy(
            _find_chart_base_query(system_data, provider["base_query_name"]))
        _apply_chart_query_updates(tree, provider["query_updates"])
        probes[provider_name] = tree
    return probes


def build_chart_query_definitions(view, is_live, duration_by_provider):
    """Phase 2: the real per-series queries themselves, with each
    non-live series' {duration} placeholder substituted from
    duration_by_provider (IQClient.query()'s real results from running
    build_chart_duration_probe_definitions()'s queries -- see that
    function's docstring; duration_by_provider is ignored entirely when
    is_live).

    The exact rule turning a real avg_sampling_time into the {duration}
    ISO-8601 string every non-live series template references isn't
    confirmed from a frontend source -- ceil() to the next whole second,
    after applying the series' own real sampling_duration_multiplier, is
    a reasonable inference confirmed sensible against real data (a
    steady real generator rate came back correctly, flat and stable, at
    both a 1-second and a 2-second resolved duration on repeat real
    runs), not a byte-for-byte confirmed rounding rule.

    Return:
    {"kind": "multi", "definitions": {<series name>: <multi_result or
    single_result dict>, ...}} -- one entry per numeric series (see
    chart_numeric_series()), keyed by the series' own internal `name`
    (e.g. "tx_port_basic_stats.generator_frame_rate"), same convention
    as histogram/boxplot's own provider-name/statistic-name keys, not
    its GUI display_name.

    Raises:
    IQViewError -- a series/provider reference doesn't match anything
                  in its own series_query_providers or in
                  system_data.base_queries, a series has no live_data/
                  completed_data template for the requested mode, or
                  (non-live only) duration_by_provider is missing a
                  provider this series needs -- meaning
                  build_chart_duration_probe_definitions()'s query for
                  it wasn't run and passed in first.
    """
    system_data = _get(view, "effective_details", "system_data") or {}
    variant_key = "live_data" if is_live else "completed_data"
    definitions = {}
    for series in chart_numeric_series(view):
        name = series.get("name")
        system_series = _find_chart_system_series(system_data, name)
        query_details = system_series and (
            system_series.get("query_details") or [None])[0]
        if not query_details:
            raise IQViewError(
                "view %r's series %r has no matching entry (with "
                "query_details) in effective_details.system_data.series" %
                (view.get("name"), name))
        provider_name = query_details.get("series_query_provider")
        provider = next(
            (p for p in system_series.get("series_query_providers") or []
             if p.get("name") == provider_name), None)
        if provider is None:
            raise IQViewError(
                "view %r's series %r references series_query_provider "
                "%r, but no matching entry was found in its own "
                "series_query_providers" %
                (view.get("name"), name, provider_name))
        variant = provider.get(variant_key)
        if variant is None:
            raise IQViewError(
                "view %r's series %r has no %r query template" %
                (view.get("name"), name, variant_key))

        query_updates = variant["query_updates"]
        if not is_live:
            sampling_provider = query_details.get("sampling_duration_provider")
            avg_sampling_time = duration_by_provider.get(sampling_provider)
            if avg_sampling_time is None:
                raise IQViewError(
                    "no resolved sampling duration for provider %r -- "
                    "run build_chart_duration_probe_definitions()'s real "
                    "query for it and pass the result in first" %
                    (sampling_provider,))
            multiplier = query_details.get("sampling_duration_multiplier", 1.0)
            seconds = max(math.ceil(avg_sampling_time * multiplier), 1)
            duration = "PT%dS" % seconds
            query_updates = [
                {"key": u["key"],
                 "values": [v.replace("{duration}", duration)
                            for v in u.get("values") or []]}
                for u in query_updates
            ]

        tree = copy.deepcopy(
            _find_chart_base_query(system_data, variant["base_query_name"]))
        _apply_chart_query_updates(tree, query_updates)
        definitions[name] = tree
    return {"kind": "multi", "definitions": definitions}


#: view_type this section applies to. Deliberately NOT a key in
#: _BUILDERS/SUPPORTED_VIEW_TYPES -- see build_xy_chart_query_definitions()'s
#: own docstring: like "histogram", it needs no new templating
#: mechanism, but its own `details.user_data.series[]` shape (one
#: `query_provider` string per series, not a `tables` list) means it
#: can't go through `_resolve_table_and_provider()` either.
XY_CHART_VIEW_TYPE = "x_y_chart"


def build_xy_chart_query_definitions(view, snapshot_name=None):
    """view_type == 'x_y_chart' -- CONFIRMED against a real server
    2026-09-24 (a real "StreamBlock Frame Loss Duration Chart" view/
    capture), superseding the previous NOT-yet-confirmed v1 this
    replaced (which unconditionally ignored snapshot_name= and assumed
    a `tables` list that x_y_chart's real shape doesn't have at all --
    dead on arrival for any real view, same story as histogram's
    replaced v1).

    Like histogram, this needs NO new templating mechanism -- once
    resolved, `details.user_data.series[]` (one entry per plotted
    series: `{"query_provider": "<name>", "h_axis": {"values": [...]},
    "v_axis": {"values": [...]}, "filter_columns": [{"name": ...}, ...],
    ...}`) just names ordinary `attribute_query_updates`/
    `derived_fact_query_updates` columns on that ONE named provider,
    walked through the exact same `_build_projection_tree()` primitive
    table/histogram already use -- confirmed structurally identical
    (byte-for-byte, at every nesting level -- this real view's structure
    goes one level deeper than histogram's: outer `multi_result` wraps a
    single `view` subquery, which itself wraps `join` -> `rxss`/`txss`)
    to the query the real GUI actually sends. `filter_columns[].name`
    (typically `"test_snapshot_name"`) is included as an active column
    the same unconditional way histogram includes it -- CONFIRMED
    correct against the real capture, which groups by it even with no
    snapshot_name= filter of its own in play.

    Unlike histogram, each series names exactly one query_provider
    directly (no `system_data.statistics[]` lookup table indirection
    needed) -- but a series has no `name` field of its own to key the
    result by, so (matching histogram's own precedent) the provider
    name is used instead. Two series sharing one provider would collide
    under this key -- not seen in any real view yet, so not specially
    handled; consider table_index=-style disambiguation if a real one
    ever turns up.

    Arguments:
    view          -- A view object, as returned by get_view()/
                     find_view_by_name()/list_views() -- must include
                     effective_details.
    snapshot_name -- Same as build_query_definition()'s own. CONFIRMED
                     working against the real capture this was built
                     from (which did have one) via
                     _apply_snapshot_filter()'s now-generalized
                     resolution (see its own docstring) -- this
                     provider's own `snapshot_filter_provider` is
                     unset, yet its `test.snapshot_name` attribute's
                     own interactive_query_updates is what the real
                     capture confirms actually gets used.

    Return:
    {"kind": "multi", "definitions": {<query_provider name>: <tree>,
    ...}} -- one entry per series (see the collision caveat above).

    Raises:
    IQViewError -- the view has no series, a series has no
                  query_provider, or its named provider isn't found in
                  system_data.query_providers.
    """
    system_data = _get(view, "effective_details", "system_data") or {}
    providers_by_name = {
        p.get("name"): p for p in system_data.get("query_providers") or []}

    series_list = _get(view, "details", "user_data", "series") or []
    if not series_list:
        raise IQViewError(
            "view %r has no series to query" % (view.get("name"),))

    definitions = {}
    for series in series_list:
        provider_name = series.get("query_provider")
        if not provider_name:
            raise IQViewError(
                "view %r has a series with no query_provider" %
                (view.get("name"),))
        provider = providers_by_name.get(provider_name)
        if provider is None:
            raise IQViewError(
                "view %r references query_provider %r, but no matching "
                "entry was found in effective_details.system_data."
                "query_providers" % (view.get("name"), provider_name))

        active_names = (
            list((series.get("h_axis") or {}).get("values") or [])
            + list((series.get("v_axis") or {}).get("values") or [])
            + [_resolve_alias_to_name(provider, f["name"])
               for f in series.get("filter_columns") or []
               if f.get("name")])
        tree = _build_projection_tree(provider, active_names)
        if snapshot_name:
            _apply_snapshot_filter(tree, provider, snapshot_name)
        definitions[provider_name] = tree
    return {"kind": "multi", "definitions": definitions}


def build_xy_chart_filter_dropdown_query(view, series_index=0):
    """The separate, standalone query a real x_y_chart GUI also sends
    alongside its main data query -- CONFIRMED against a real capture
    2026-09-24: the ordered list of real snapshot names available to
    filter/group by (`test.snapshot_name`/`test.snapshot_name_order`),
    used to populate the GUI's own snapshot filter dropdown/axis
    ordering. NOT part of build_xy_chart_query_definitions()'s own
    return value -- like `chart`'s CHART_EVENTS_DEFINITION, it's an
    independent, optional piece of data, not the series data itself.

    Unlike CHART_EVENTS_DEFINITION, this one IS provider-specific --
    it's the named series' own provider["filter_dropdown_query"], a
    complete, ready-to-run definition needing no patching at all
    (confirmed byte-for-byte identical to the real capture as-is).

    Arguments:
    view         -- Same as build_xy_chart_query_definitions().
    series_index -- Which of the view's details.user_data.series[]
                    entries to use (most real views have exactly one).

    Return:
    A `multi_result` dict, ready to pass to query(definition=...)
    directly.

    Raises:
    IQViewError -- series_index is out of range, the series has no
                  query_provider, the provider isn't found, or it has
                  no filter_dropdown_query of its own.
    """
    series_list = _get(view, "details", "user_data", "series") or []
    if not 0 <= series_index < len(series_list):
        raise IQViewError(
            "view %r has %d series; series_index=%d is out of range" %
            (view.get("name"), len(series_list), series_index))
    provider_name = series_list[series_index].get("query_provider")
    system_data = _get(view, "effective_details", "system_data") or {}
    provider = next(
        (p for p in system_data.get("query_providers") or []
         if p.get("name") == provider_name), None)
    if provider is None:
        raise IQViewError(
            "view %r references query_provider %r, but no matching "
            "entry was found in effective_details.system_data."
            "query_providers" % (view.get("name"), provider_name))
    query = provider.get("filter_dropdown_query")
    if query is None:
        raise IQViewError(
            "provider %r has no filter_dropdown_query" % (provider_name,))
    return copy.deepcopy(query)


#: Dispatch table for build_query_definition() -- the single source of
#: truth for which view_types are supported (SUPPORTED_VIEW_TYPES below
#: is derived from this, not maintained separately).
_BUILDERS = {
    "single_level_table": _build_table_query,
    "paged_single_level_table": _build_table_query,
    "pie_chart": _build_pie_chart_query,
    "boxplot": _build_boxplot_queries,
}
SUPPORTED_VIEW_TYPES = tuple(_BUILDERS)
