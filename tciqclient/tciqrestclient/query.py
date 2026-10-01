"""Query definition composition and result shaping (PLAN.md, section 2.3).

orion-res's query `definition` is a tree of subquery nodes -- confirmed
from a real captured request/response, not guessed:

    {
      "multi_result": {
        "subqueries": [ {"alias": "view", "subqueries": [...], ...} ],
        "projections": [...], "filters": [...], "groups": [...],
        "orders": [...], "limit": 120, "pagination": {"mode": "forward"}
      }
    }

Projections/filters/orders are literal SQL-ish expression strings (e.g.
``"view.frame_count>1000"``), not a structured {field, op, value} shape --
that's simply how the real API works, not a design choice made here. This
module's job is to let callers pass plain Python values (tuples, dicts,
strings) and never hand-build those expression strings themselves, by
appending to the *outermost* node of an existing definition (typically one
already stored on a view).

single_result's exact shape has not been directly observed (no real
example captured yet) -- by strong analogy with multi_result's leaf nodes
(identical fields, minus `subqueries`), it's treated here as
{alias?, projections, filters, groups, orders, limit, pagination}. This
assumption is isolated to _OUTERMOST_KEYS below; correct it there if a
real single_result example shows otherwise.
"""
import copy
import datetime

from .exceptions import IQQueryError

#: Query-definition keys recognized as "the query type" -- exactly one of
#: these is present in a real `definition` object. Order matters only for
#: _outermost_node()'s error message.
_OUTERMOST_KEYS = (
    "multi_result", "single_result", "single_dimension", "raw",
    "delete_result",
)

_OPS = {"eq": "=", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}


def merge_modifiers(definition, filters=None, sort=None, group_by=None,
                     time_range=None, limit=None, resolve_field=None):
    """Return a copy of `definition` with filters/sort/group_by/time_range
    appended to its outermost node's filters/orders/groups arrays, and
    limit set on it directly.

    Arguments:
    definition -- An existing query definition (e.g. from a saved view).
    filters    -- List of filter entries. Each is a literal SQL-ish
                 expression string (passed through as-is), a (field,
                 value) or (field, op, value) tuple, or a
                 {'field','op','value'} dict. op defaults to 'eq' and
                 must be one of: eq, ne, lt, lte, gt, gte, contains, in.
    sort       -- Field name, "field ASC"/"field DESC" string, a (field,
                 order) tuple, or a list of those for multi-column sort.
    group_by   -- Field name, or list of field names.
    time_range -- (field, start, end) tuple, or {'field','start','end'}
                 dict. `field` is required -- there's no universal
                 timestamp column name across all query types. start/end
                 may be omitted individually for an open-ended range.
    limit      -- Max rows to return. Unlike filters/sort/group_by (which
                 append to the outermost node's arrays), this *replaces*
                 whatever limit the definition already carries (e.g. a
                 saved view's own default) -- there's only ever one limit
                 per query, not a list of them. None (default) leaves the
                 definition's existing limit untouched. Every real capture
                 with a limit also carries a `pagination` sibling
                 ({"mode": "forward"}); if the definition doesn't already
                 have one, setting limit adds that default too.
    resolve_field -- Optional function(field_name) -> field_name, applied
                 to every field name in filters=/sort=/group_by=/
                 time_range= before qualifying it (see
                 tciqrestclient.view_query_builder.build_field_resolver() -- lets
                 e.g. a view's GUI column label "Rx Count" resolve to its
                 actual query alias "rx_stream_stats_frame_count" before
                 qualification). None (default): no resolution, field
                 names are used exactly as given.

    Field names are qualified automatically with the outermost node's
    single child alias (e.g. "view.") when the definition has exactly one
    top-level subquery, matching how real queries reference their inner
    projections. Already-qualified names ("alias.field") and raw
    expression strings are left untouched.

    Return:
    A new definition dict; the input is not mutated.
    """
    definition = copy.deepcopy(definition)
    _query_type, node = _outermost_node(definition)
    prefix = _resolve_prefix(node)

    if filters:
        node.setdefault("filters", []).extend(
            _format_filter(f, prefix, resolve_field) for f in filters)

    if sort:
        node.setdefault("orders", []).extend(
            _format_sort(s, prefix, resolve_field)
            for s in _normalize_sort_list(sort))

    if group_by:
        fields = [group_by] if isinstance(group_by, str) else list(group_by)
        node.setdefault("groups", []).extend(
            _qualify(f, prefix, resolve_field) for f in fields)

    if time_range:
        node.setdefault("filters", []).extend(
            _format_time_range(time_range, prefix, resolve_field))

    if limit is not None:
        node["limit"] = limit
        node.setdefault("pagination", {"mode": "forward"})

    return definition


def rows_to_dicts(result):
    """Zip a query result's positional `rows` against its `columns` into
    a list of row dicts. `result` is the `result` object from a
    run_query() response (or an empty/missing one, tolerated)."""
    columns = (result or {}).get("columns") or []
    rows = (result or {}).get("rows") or []
    return [dict(zip(columns, row)) for row in rows]


# -- internals ----------------------------------------------------------


def _outermost_node(definition):
    for key in _OUTERMOST_KEYS:
        if key in definition:
            return key, definition[key]
    raise IQQueryError(
        "definition has none of the recognized query types: %s" %
        ", ".join(_OUTERMOST_KEYS))


def _resolve_prefix(node):
    """The alias to qualify bare field names with, inferred from the
    outermost node's own subqueries. None (no qualification) when the
    node is flat or has more than one child -- ambiguous cases are left
    to the caller to qualify explicitly as "alias.field"."""
    subqueries = node.get("subqueries") or []
    if len(subqueries) == 1:
        return subqueries[0].get("alias")
    return None


def _qualify(field, prefix, resolve_field=None):
    if resolve_field:
        field = resolve_field(field)
    if prefix and "." not in field and " " not in field:
        return "%s.%s" % (prefix, field)
    return field


def _quote(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return "'%s'" % value.isoformat()
    escaped = str(value).replace("'", "''")
    return "'%s'" % escaped


def _format_filter(f, prefix, resolve_field=None):
    if isinstance(f, str):
        return f  # already a raw expression -- passed through as-is.

    if isinstance(f, dict):
        field, op, value = f["field"], f.get("op", "eq"), f.get("value")
    elif isinstance(f, (list, tuple)):
        if len(f) == 3:
            field, op, value = f
        elif len(f) == 2:
            field, value = f
            op = "eq"
        else:
            raise IQQueryError(
                "filter tuple must be (field, value) or (field, op, "
                "value): got %r" % (f,))
    else:
        raise IQQueryError(
            "filter must be a str, dict, or tuple, got %r" % (f,))

    qualified = _qualify(field, prefix, resolve_field)

    if op == "contains":
        return "%s LIKE %s" % (qualified, _quote("%" + str(value) + "%"))
    if op == "in":
        values = ", ".join(_quote(v) for v in value)
        return "%s IN (%s)" % (qualified, values)
    if op not in _OPS:
        raise IQQueryError(
            "unsupported filter operator %r; must be one of: contains, "
            "in, %s" % (op, ", ".join(_OPS)))
    return "%s%s%s" % (qualified, _OPS[op], _quote(value))


def _normalize_sort_list(sort):
    if isinstance(sort, str):
        return [sort]
    if (isinstance(sort, tuple) and len(sort) == 2 and
            isinstance(sort[1], str) and sort[1].upper() in ("ASC", "DESC")):
        return [sort]
    if isinstance(sort, list):
        return sort
    raise IQQueryError(
        "sort must be a str, a (field, order) tuple, or a list of those, "
        "got %r" % (sort,))


def _format_sort(s, prefix, resolve_field=None):
    if isinstance(s, str):
        parts = s.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].upper() in ("ASC", "DESC"):
            field, order = parts
        else:
            field, order = s, "ASC"
    elif isinstance(s, (list, tuple)) and len(s) == 2:
        field, order = s
    else:
        raise IQQueryError(
            "sort entry must be a str or (field, order) tuple, got %r" %
            (s,))

    order = order.upper()
    if order not in ("ASC", "DESC"):
        raise IQQueryError(
            "sort order must be ASC or DESC, got %r" % (order,))
    return "%s %s" % (_qualify(field, prefix, resolve_field), order)


def _format_time_range(tr, prefix, resolve_field=None):
    if isinstance(tr, dict):
        field, start, end = tr["field"], tr.get("start"), tr.get("end")
    elif isinstance(tr, (list, tuple)) and len(tr) == 3:
        field, start, end = tr
    else:
        raise IQQueryError(
            "time_range must be (field, start, end) or "
            "{'field', 'start', 'end'}, got %r" % (tr,))

    qualified = _qualify(field, prefix, resolve_field)
    exprs = []
    if start is not None:
        exprs.append("%s>=%s" % (qualified, _quote(start)))
    if end is not None:
        exprs.append("%s<=%s" % (qualified, _quote(end)))
    return exprs
