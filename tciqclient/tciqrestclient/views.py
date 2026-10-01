"""Named view CRUD (/views) -- PLAN.md, section 2.4.

CONFIRMED from a real server export (449 views): a view's `details` is a
GUI table spec, NOT itself a `multi_result` query definition -- an
earlier version of this docstring assumed the latter and was wrong. The
real shape (trimmed):

    {
      "view_type": "single_level_table",   # or chart/gauge/histogram/...
      "user_data": {
        "refresh_rate_in_msec": 1000,
        "tables": [
          {
            "data_type": "live",           # or "eot", "history", ...
            "query_provider": "live_table_stream_traffic",
            "columns": [...], "filters": [...], "orders": [...],
            "primary_dimension_attributes": [...],
          },
          ...
        ],
      },
    }

`query_provider` names one of ~449 distinct server-side query templates
seen across a real server's views. There's no *documented* endpoint that
does the (query_provider, columns) -> `multi_result` translation, but the
GUI clearly does it somehow -- and it turns out the templates it uses are
themselves shipped on the view: `effective_details.system_data.
query_providers[]` (present on every view returned by GET /views).
get_view_definition() below (tciqrestclient.view_query_builder under the hood)
reverse-engineers that same translation, confirmed byte-for-byte against
two real captures (unfiltered and filtered) of "Detailed Stream Results".
See tests/fixtures.py's VIEW constant for a (still GUI-table-spec-only,
no templates) real trimmed example of `details`, and
tests/data/view_detailed_stream_results.json for one with
`effective_details` intact.
"""
import copy

from . import view_query_builder
from .exceptions import IQViewError


def list_views(transport, timeout=None):
    """List all views known to the server.

    Each view's `effective_details.system_data.query_providers` (needed
    by get_view_definition()) is included by default -- on a server with
    many views this can make the response body large and slow; pass
    timeout= to override the client's default HTTP timeout for just this
    call rather than raising it globally.
    """
    return transport.get("/views", timeout=timeout) or []


def get_view(transport, view_id, timeout=None):
    """Get one view by id."""
    if not view_id:
        raise IQViewError("view_id is required")
    return transport.get("/views/%s" % view_id, timeout=timeout)


def find_view_by_name(transport, name, timeout=None):
    """Find a view by its display name. Client-side match -- no
    server-side name filter has been confirmed. See list_views() re:
    timeout= -- fetching every view's full details/effective_details to
    search client-side can be slow on a server with many views."""
    for view in list_views(transport, timeout=timeout):
        if view.get("name") == name:
            return view
    return None


def _resolve_table_index(view, table_index, data_type):
    """Shared by get_view_definition()/list_view_columns()/
    build_field_resolver(): translate data_type= (e.g. "eot") to the
    matching table_index, if given.

    IQ-PYTHON-004 requires query() to default to snapshot data, not live
    -- CONFIRMED broken 2026-09-03 (see HANDOVER.md section 9):
    unconditionally returning table_index (whose own default was 0)
    silently picked whichever table a view happened to list *first* --
    "live" for the real "Detailed Stream Results" view -- when neither
    table_index= nor data_type= was given at all. When both are
    unspecified (table_index is None, not just defaulted to 0 by the
    caller -- see get_view_definition()'s own default), prefer a table
    with data_type == "eot" over whatever is first; fall back to index 0
    only if the view has no eot table at all (e.g. a live-only view for
    a still-running test). An explicit table_index= (including
    table_index=0) is still honored exactly as given either way -- this
    only changes what happens when the caller asks for nothing specific.

    data_type= matching is case-insensitive (a real user reported
    data_type="EOT" silently failing -- every table's own data_type
    value is lowercase, e.g. "eot"/"live", but there's no reason a
    caller's differently-cased string should be rejected instead of
    matched).
    """
    if not view:
        raise IQViewError("view is required")
    tables = (view.get("details") or {}).get(
        "user_data", {}).get("tables") or []
    if data_type is not None:
        wanted = data_type.lower() if isinstance(data_type, str) else data_type
        for i, table in enumerate(tables):
            table_data_type = table.get("data_type")
            if (table_data_type == data_type or
                    (isinstance(table_data_type, str) and
                     isinstance(wanted, str) and
                     table_data_type.lower() == wanted)):
                return i
        raise IQViewError(
            "view %r has no table with data_type=%r (available: %s)" %
            (view.get("name"), data_type,
             [t.get("data_type") for t in tables]))
    if table_index is not None:
        return table_index
    for i, table in enumerate(tables):
        if table.get("data_type") == "eot":
            return i
    return 0


def _find_provider_elsewhere(transport, provider_name, timeout=None):
    """IQ-PYTHON-003 requires saved custom views to be reusable via
    query(name=...) -- CONFIRMED broken 2026-09-03 (see HANDOVER.md
    section 9): a view created via save_view() never gets its own
    effective_details.system_data.query_providers populated by the
    server, even though its details.user_data.tables[].query_provider
    names are copied verbatim from whatever view it was cloned from.
    Most of a query_provider's definition (base_query, attribute/fact/
    derived_fact_query_updates) is genuinely shared by name across every
    view that references it -- any other view carrying it can supply
    that part. Returns the best matching provider dict found, or None if
    no view on the server has one by this name.

    ONE FIELD IS NOT GLOBAL, CONFIRMED 2026-09-03: `default_order_updates`
    varies per-view even for providers sharing the same name (of 5 real
    views sharing "eot_table_stream_traffic" checked against a real
    server, 4 had an empty default_order_updates.order_updates and only
    1 -- "Stream Results" -- had the same 3 entries "Detailed Stream
    Results" itself does). Naively using the *first* matching view found
    can silently return a provider with no default order at all, which
    then makes any paginated/limited query (query()'s own default)
    against the fixed-up view 400 with "pagination requires at least one
    order expression" -- confirmed via this exact failure before this
    preference was added. Prefer a match whose default_order_updates has
    at least one order_updates entry; only fall back to whichever match
    was found first if none do (still better than raising outright, and
    matches the original, simpler behavior for a provider that
    genuinely doesn't have a default order at all)."""
    first_match = None
    for view in list_views(transport, timeout=timeout):
        providers = (
            (view.get("effective_details") or {}).get("system_data") or {}
        ).get("query_providers") or []
        for provider in providers:
            if provider.get("name") != provider_name:
                continue
            if first_match is None:
                first_match = provider
            order_updates = (
                provider.get("default_order_updates") or {}
            ).get("order_updates") or []
            if order_updates:
                return provider
    return first_match


def _ensure_provider_available(transport, view, table_index, timeout=None):
    """Return `view`, or a patched deep copy of it, guaranteed to carry
    (if findable at all -- see _find_provider_elsewhere()) the specific
    query_provider its `table_index`'th table needs in its own
    effective_details.system_data.query_providers -- see
    _find_provider_elsewhere()'s docstring for why this is needed at
    all. `table_index` must already be a resolved concrete index (call
    _resolve_table_index() first) -- this does not itself handle
    data_type=/None resolution.

    transport=None (the default for any caller that doesn't have one,
    e.g. a direct views.get_view_definition(view) call with no client)
    disables the fallback entirely, returning `view` unchanged --
    preserves the exact pre-fix behavior (the original IQViewError from
    view_query_builder surfaces normally) for any such caller.
    """
    if transport is None:
        return view
    tables = (view.get("details") or {}).get(
        "user_data", {}).get("tables") or []
    if not 0 <= table_index < len(tables):
        return view  # out-of-range -- let the usual error surface downstream
    provider_name = tables[table_index].get("query_provider")
    if not provider_name:
        return view
    existing = (
        (view.get("effective_details") or {}).get("system_data") or {}
    ).get("query_providers") or []
    if any(p.get("name") == provider_name for p in existing):
        return view  # view already has it -- nothing to do
    found = _find_provider_elsewhere(transport, provider_name, timeout=timeout)
    if found is None:
        return view  # not found anywhere -- let the usual error surface
    patched = copy.deepcopy(view)
    effective_details = patched.setdefault("effective_details", {})
    system_data = effective_details.setdefault("system_data", {})
    system_data.setdefault("query_providers", []).append(found)
    return patched


def get_view_definition(view, table_index=None, data_type=None,
                         snapshot_name=None, transport=None, timeout=None):
    """Build an executable query (or queries) from a saved view, using
    its own effective_details.system_data.query_providers templates (see
    tciqrestclient.view_query_builder for the full mechanism).

    Table (single_level_table/paged_single_level_table) is confirmed
    byte-for-byte against real captures; x_y_chart/pie_chart/histogram/
    boxplot are also supported but reverse-engineered from
    magellan-frontend's TS source rather than a capture -- see
    tciqrestclient.view_query_builder's module docstring and WIDGET_QUERY_PLAN.md
    for what's confirmed vs. assumed. Any other view_type raises
    IQViewError, since its result shape (if any) hasn't been checked.

    Arguments:
    view       -- A view object, as returned by get_view()/
                 find_view_by_name()/list_views() -- must include
                 effective_details (present by default on a real
                 server's response).
    table_index -- Which of the view's details.user_data.tables entries
                  to build a query for. Most views have exactly one;
                  some (e.g. "Detailed Stream Results") have more than
                  one -- typically split by data_type ("live" while a
                  test runs, "eot" for its finished snapshot). Ignored
                  if data_type is given. None (default) -- along with
                  data_type also None -- means "no preference given";
                  see _resolve_table_index() for the resulting default
                  (IQ-PYTHON-004: prefers a table with data_type="eot"
                  over whatever the view lists first, confirmed
                  necessary 2026-09-03 -- see HANDOVER.md section 9).
    data_type  -- Select the table by its data_type field (e.g. "eot")
                 instead of by index -- convenient for the common
                 live/eot split. Raises IQViewError if no table has
                 this data_type.
    snapshot_name -- Restrict results to one specific named snapshot --
                 only valid against a table whose data_type is "eot" --
                 see tciqrestclient.view_query_builder.build_query_definition().
    transport  -- Optional Transport, used only to look elsewhere on the
                 server for a query_provider this view's own
                 effective_details is missing (see
                 _ensure_provider_available()'s docstring for why a
                 view can legitimately be missing one -- confirmed
                 2026-09-03, IQ-PYTHON-003). None (default): no such
                 fallback is attempted, matching pre-fix behavior
                 exactly.
    timeout    -- Passed through to the fallback lookup above, if
                 transport is given.

    Return:
    {"kind": "single", "definition": <multi_result dict>} for a
    view_type that's genuinely one query, or {"kind": "multi",
    "definitions": {<name>: <multi_result dict>, ...}} for one that
    isn't -- see tciqrestclient.view_query_builder.build_query_definition()'s
    docstring.

    Raises:
    IQViewError -- unsupported view_type, table_index/data_type doesn't
                  match a table, or the view's query_provider/
                  effective_details are missing/don't match the expected
                  shape (e.g. the view was fetched without
                  effective_details, or transport= wasn't given/didn't
                  find a substitute either).
    """
    table_index = _resolve_table_index(view, table_index, data_type)
    view = _ensure_provider_available(
        transport, view, table_index, timeout=timeout)
    return view_query_builder.build_query_definition(
        view, table_index=table_index, snapshot_name=snapshot_name)


def list_view_columns(view, table_index=None, data_type=None,
                       active_only=False, transport=None, timeout=None):
    """List every column-like attribute a view's table can reference --
    including its GUI display_name (e.g. "Rx Count"), for discovering what
    query(name=..., filters=/sort=/group_by=) accepts. See
    tciqrestclient.view_query_builder.list_view_columns() for the return shape and
    active_only=.

    table_index/data_type/transport/timeout: same as get_view_definition().
    """
    table_index = _resolve_table_index(view, table_index, data_type)
    view = _ensure_provider_available(
        transport, view, table_index, timeout=timeout)
    return view_query_builder.list_view_columns(
        view, table_index=table_index, active_only=active_only)


def build_field_resolver(view, table_index=None, data_type=None,
                          transport=None, timeout=None):
    """Return a function resolving a column's GUI display_name, raw
    attribute path, or alias_name to the alias_name query(name=...)'s
    filters=/sort=/group_by= need -- see
    tciqrestclient.view_query_builder.build_field_resolver().

    table_index/data_type/transport/timeout: same as get_view_definition().
    """
    table_index = _resolve_table_index(view, table_index, data_type)
    view = _ensure_provider_available(
        transport, view, table_index, timeout=timeout)
    return view_query_builder.build_field_resolver(
        view, table_index=table_index)


def save_view(transport, name, details=None, description="", view_id=None,
              definition=None):
    """Create a new view, or update an existing one when view_id is given.

    Arguments:
    details / definition -- The view's GUI table spec, exactly as `details`
              appears on an existing view (see the module docstring) -- e.g.
              read via get_view()/find_view_by_name(), modify, and pass back.
              ``definition`` is accepted as an alias for ``details`` so both
              parameter names work: ``save_view(name=..., definition={...})``
              and ``save_view(name=..., details={...})`` are equivalent. This
              is NOT a ``multi_result`` query definition; there's no supported
              way to build one of these from scratch or from a query definition
              (see get_view_definition()).
    """
    if not name:
        raise IQViewError("view name is required")
    resolved_details = definition if definition is not None else details
    body = {
        "name": name,
        "description": description,
        "details": resolved_details,
    }
    if view_id:
        return transport.put("/views/%s" % view_id, json_body=body)
    return transport.post("/views", json_body=body)


def delete_view(transport, view_id):
    """Delete a view by id."""
    if not view_id:
        raise IQViewError("view_id is required")
    transport.delete("/views/%s" % view_id)
