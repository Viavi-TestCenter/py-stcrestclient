"""Tests for tciqrestclient.view_query_builder, validated against real captures.

`tests/data/view_detailed_stream_results.json` and
`dsr_query_unfiltered.json` are a real "Detailed Stream Results" view
export and its real, unfiltered `POST /queries` request body -- captured
fresh from a live orion-res server on 2026-09-03 (the original captures
these were reverse-engineered against were lost -- see HANDOVER.md
section 0/9 for that whole story). `test_matches_real_unfiltered_capture`
below passing against these is a genuine, independent re-confirmation
that view_query_builder.py's algorithm is still correct.

`dsr_query_filtered_min_latency.json` is currently NOT a real GUI
capture -- the REST API alone can't produce the GUI's own "push-down"
filter placement (see build_query_definition()'s module docstring), and
no browser was available to capture one from. It was instead constructed
programmatically, by applying the exact transform this file's own
`test_matches_real_filtered_capture_gui_pushdown_shape` describes, to the
same real view above -- then confirmed to be a valid, real-server-
executable query (after stripping the same schema-dependent columns
`test_matches_real_unfiltered_capture`'s capture needed). That's a
real, working query shape, but it is NOT independent confirmation that
it's byte-identical to what the GUI's own JavaScript actually sends --
the two tests using it (`test_matches_real_filtered_capture_gui_pushdown_
shape`, `test_merge_modifiers_filter_shape_differs_from_gui_capture`) are
consequently checking self-consistency, not ground truth, until someone
replaces this file with an actual browser DevTools capture (open
"Detailed Stream Results", type `rx_stream_stats.min_latency < 0.17`
into its filter box, copy the POST /queries request body) to compare
against -- update this docstring once that happens, whichever way the
comparison goes.
"""
import copy
import json
import os

import pytest

from tciqrestclient.exceptions import IQViewError
from tciqrestclient.query import merge_modifiers
from tciqrestclient.view_query_builder import (
    build_chart_duration_probe_definitions, build_chart_query_definitions,
    build_field_resolver, build_histogram_query_definitions,
    build_query_definition, build_xy_chart_filter_dropdown_query,
    build_xy_chart_query_definitions, chart_numeric_series, list_view_columns,
    parse_unknown_attribute_error, strip_unknown_attribute)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load(filename):
    path = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(
            "tests/data/%s is a real orion-res capture that isn't checked "
            "into this repo -- see HANDOVER.md section 9" % filename)
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def view():
    return _load("view_detailed_stream_results.json")


@pytest.fixture
def unfiltered_capture():
    return _load("dsr_query_unfiltered.json")["definition"]


@pytest.fixture
def filtered_capture():
    return _load("dsr_query_filtered_min_latency.json")["definition"]


# table_index 0 is "live", 1 is "eot" -- the real captures were both taken
# against the eot table (a finished snapshot, not a running test).
_EOT_TABLE_INDEX = 1


def test_matches_real_unfiltered_capture(view, unfiltered_capture):
    built = build_query_definition(view, table_index=_EOT_TABLE_INDEX)
    assert built["kind"] == "single"
    # The captured request has limit/pagination set -- those are request
    # modifiers, not part of the provider template, so apply them the same
    # way a caller would (see tciqrestclient.query.merge_modifiers).
    result = merge_modifiers(built["definition"], limit=120)
    assert result == unfiltered_capture


def test_matches_real_filtered_capture_gui_pushdown_shape(
        view, filtered_capture):
    """The GUI pushes an ad-hoc filter down into the specific inner
    subquery where the raw column lives, rather than qualifying it against
    the outermost alias. Confirms the *base* tree this module builds is
    byte-for-byte what the GUI itself would filter -- i.e. the reverse-
    engineered algorithm is correct, independent of how a caller chooses to
    attach filters afterwards (see the "NOTE" in the module docstring about
    merge_modifiers producing a different, non-byte-identical shape)."""
    built = build_query_definition(view, table_index=_EOT_TABLE_INDEX)
    filtered = copy.deepcopy(built["definition"])
    node = filtered["multi_result"]
    rxss = node["subqueries"][0]["subqueries"][0]
    assert rxss["alias"] == "rxss"
    rxss["filters"].append("(rx_stream_stats.min_latency) < 0.17")
    node["limit"] = 120
    node["pagination"] = {"mode": "forward"}
    assert filtered == filtered_capture


def test_merge_modifiers_filter_shape_differs_from_gui_capture(
        view, filtered_capture):
    """Document (not just assert away) the known divergence: filtering a
    builder-produced definition via the normal tciqrestclient.query.merge_modifiers
    mechanism qualifies against the outermost alias, not the GUI's
    push-down style -- so the result is a different (structurally valid,
    but not real-server-confirmed) shape from what the GUI itself sends."""
    built = build_query_definition(view, table_index=_EOT_TABLE_INDEX)
    result = merge_modifiers(
        built["definition"],
        filters=[("rx_stream_stats_min_latency", "lt", 0.17)],
        limit=120)
    assert result["multi_result"]["filters"] == [
        "view.rx_stream_stats_min_latency<0.17"]
    assert result != filtered_capture


def test_live_table_builds_without_error(view):
    # No real capture exists for the "live" table (data_type == "live"),
    # so this only checks the algorithm runs and produces a well-formed
    # tree, not exact content.
    built = build_query_definition(view, table_index=0)
    node = built["definition"]["multi_result"]
    assert node["subqueries"][0]["alias"] == "view"
    assert {sq["alias"] for sq in node["subqueries"][0]["subqueries"]} == {
        "rxss", "txss"}
    assert node["projections"]


def test_unsupported_view_type_raises(view):
    bad_view = copy.deepcopy(view)
    bad_view["details"]["view_type"] = "chart"
    with pytest.raises(IQViewError, match="chart"):
        build_query_definition(bad_view)


def test_table_index_out_of_range_raises(view):
    with pytest.raises(IQViewError, match="table_index"):
        build_query_definition(view, table_index=5)


def test_unknown_query_provider_raises(view):
    bad_view = copy.deepcopy(view)
    bad_view["details"]["user_data"]["tables"][0]["query_provider"] = (
        "no_such_provider")
    with pytest.raises(IQViewError, match="no_such_provider"):
        build_query_definition(bad_view, table_index=0)


def test_no_tables_raises(view):
    bad_view = copy.deepcopy(view)
    bad_view["details"]["user_data"]["tables"] = []
    with pytest.raises(IQViewError, match="no tables"):
        build_query_definition(bad_view)


def test_unknown_column_name_is_skipped_not_fatal(view):
    bad_view = copy.deepcopy(view)
    bad_view["details"]["user_data"]["tables"][1]["columns"].append(
        "made_up.column_that_does_not_exist")
    # Should not raise -- unknown columns are skipped (see module
    # docstring/build_query_definition's "unknown/renamed column" comment).
    build_query_definition(bad_view, table_index=1)


# -- auto-repair: a database's schema can lack an attribute the view's ---
# -- query_provider template references (real 400, reported by Vinod) ----

# The exact VALIDATION_FAILED response body orion-res returned for a real
# database whose test config didn't have a "dual IP config" stream setup,
# even though "Detailed Stream Results"'s eot table's columns include it.
_REAL_ERROR_BODY = (
    '{"code":"VALIDATION_FAILED","message":"Validation failed: name '
    'error; unknown attribute name: tx_stream_config.ipv4_2_source_addr '
    'as tx_stream_config_ipv4_2_source_addr"}')
_REAL_RAW_PROJECTION = (
    "tx_stream_config.ipv4_2_source_addr as "
    "tx_stream_config_ipv4_2_source_addr")


def test_parse_unknown_attribute_error_from_real_response_body():
    # As it actually appears wrapped in transport.py's IQRequestError
    # message: "<method> <url> returned <status>: <resp.text>".
    full_message = ("POST http://127.0.0.1:9200/queries returned 400: "
                     + _REAL_ERROR_BODY)
    assert (parse_unknown_attribute_error(full_message) ==
            _REAL_RAW_PROJECTION)


# A second, differently-worded real 400 -- CONFIRMED 2026-09-16 against a
# real AION-managed orion-res server/view ("NFVi Advanced Kubernetes
# Platform Deployment Summary" on 10.109.143.126). Same underlying
# schema-mismatch failure as _REAL_ERROR_BODY above, but orion-res phrased
# it as "unknown dimension or result set name" instead of "unknown
# attribute name" -- the original regex only matched the first phrasing,
# so auto_repair gave up immediately on this one instead of stripping the
# bad column and retrying (a real, reproducible gap, not a guess).
_REAL_ERROR_BODY_DIMENSION_PHRASING = (
    '{"code":"VALIDATION_FAILED","message":"Validation failed: name '
    'error; unknown dimension or result set name: '
    'nfv_adv_k8s_instance_group_instance.instance_kind as instance_kind"}')
_REAL_RAW_PROJECTION_DIMENSION_PHRASING = (
    "nfv_adv_k8s_instance_group_instance.instance_kind as instance_kind")


def test_parse_unknown_attribute_error_dimension_phrasing():
    full_message = (
        "POST http://10.109.143.126:64012/api/res/queries returned 400: "
        + _REAL_ERROR_BODY_DIMENSION_PHRASING)
    assert (parse_unknown_attribute_error(full_message) ==
            _REAL_RAW_PROJECTION_DIMENSION_PHRASING)


def test_parse_unknown_attribute_error_no_match_returns_none():
    assert parse_unknown_attribute_error("some other error") is None
    assert parse_unknown_attribute_error("") is None
    assert parse_unknown_attribute_error(None) is None


def test_strip_unknown_attribute_removes_alias_at_every_level(view):
    built = build_query_definition(
        view, table_index=_EOT_TABLE_INDEX)["definition"]
    alias = "tx_stream_config_ipv4_2_source_addr"

    def count(tree):
        n = [0]

        def walk(node):
            for p in node.get("projections", []):
                if p.endswith("as %s" % alias):
                    n[0] += 1
            for c in node.get("subqueries", []):
                walk(c)

        walk(tree["multi_result"])
        return n[0]

    assert count(built) > 0  # sanity: the column is really there first
    changed = strip_unknown_attribute(built, _REAL_RAW_PROJECTION)
    assert changed is True
    assert count(built) == 0


def test_strip_unknown_attribute_no_alias_match_returns_false(view):
    built = build_query_definition(
        view, table_index=_EOT_TABLE_INDEX)["definition"]
    assert strip_unknown_attribute(built, "not a projection string") is False


# -- display_name resolution: filter/sort by GUI column label, not just --
# -- the internal alias (Vinod: "filter should take 'Rx Frame count' not --
# -- 'rx_stream_stats_frame_count'") -------------------------------------

def test_list_view_columns_includes_display_names(view):
    columns = list_view_columns(view, table_index=_EOT_TABLE_INDEX)
    by_name = {c["name"]: c for c in columns}
    entry = by_name["rx_stream_stats.frame_count"]
    assert entry["alias_name"] == "rx_stream_stats_frame_count"
    assert entry["display_name"] == "Rx Count"


def test_list_view_columns_active_only_restricts_to_table_columns(view):
    # This fixture was pre-trimmed to only the columns already active on
    # its tables (see the module docstring), so active_only=True/False
    # happen to match here -- shrink the table's own declared columns to
    # exercise the actual filtering behavior instead.
    narrowed_view = copy.deepcopy(view)
    table = narrowed_view["details"]["user_data"]["tables"][_EOT_TABLE_INDEX]
    table["columns"] = ["rx_stream_stats.frame_count"]
    table["primary_dimension_attributes"] = ["stream_block.name"]

    all_columns = list_view_columns(narrowed_view, table_index=_EOT_TABLE_INDEX)
    active_columns = list_view_columns(
        narrowed_view, table_index=_EOT_TABLE_INDEX, active_only=True)
    assert len(active_columns) < len(all_columns)
    assert {c["name"] for c in active_columns} == {
        "rx_stream_stats.frame_count", "stream_block.name"}


def test_build_field_resolver_resolves_display_name_case_insensitively(
        view):
    resolve = build_field_resolver(view, table_index=_EOT_TABLE_INDEX)
    assert resolve("Rx Count") == "rx_stream_stats_frame_count"
    assert resolve("rx count") == "rx_stream_stats_frame_count"
    assert resolve("RX COUNT") == "rx_stream_stats_frame_count"


def test_build_field_resolver_resolves_raw_attribute_path(view):
    resolve = build_field_resolver(view, table_index=_EOT_TABLE_INDEX)
    assert resolve("rx_stream_stats.frame_count") == (
        "rx_stream_stats_frame_count")


def test_build_field_resolver_passes_through_unknown_names(view):
    resolve = build_field_resolver(view, table_index=_EOT_TABLE_INDEX)
    assert resolve("rx_stream_stats_frame_count") == (
        "rx_stream_stats_frame_count")  # already the alias -- unchanged
    assert resolve("view.some_alias") == "view.some_alias"  # untouched
    assert resolve("nonexistent column") == "nonexistent column"


def test_build_field_resolver_resolves_unambiguous_bare_column_name(view):
    # A real user complaint: filters=[("frame_count", ...)] didn't work,
    # only the full "rx_stream_stats.frame_count" or the GUI label did.
    # "min_latency" only ever appears as "rx_stream_stats.min_latency" on
    # this real view -- unambiguous, so the bare name should now resolve.
    resolve = build_field_resolver(view, table_index=_EOT_TABLE_INDEX)
    assert resolve("min_latency") == "rx_stream_stats_min_latency"
    assert resolve("MIN_LATENCY") == "rx_stream_stats_min_latency"


def test_build_field_resolver_leaves_ambiguous_bare_column_name_unresolved(
        view):
    # This real view has BOTH "tx_stream_stats.frame_count" and
    # "rx_stream_stats.frame_count" -- bare "frame_count" must NOT
    # silently guess one of them; qualify it (or use the GUI display
    # name) instead.
    resolve = build_field_resolver(view, table_index=_EOT_TABLE_INDEX)
    assert resolve("frame_count") == "frame_count"  # unresolved, unchanged
    # The fully-qualified forms for either side still work fine.
    assert resolve("rx_stream_stats.frame_count") == (
        "rx_stream_stats_frame_count")
    assert resolve("tx_stream_stats.frame_count") == (
        "tx_stream_stats_frame_count")


def test_filter_by_display_name_produces_same_expression_as_alias(
        view):
    built = build_query_definition(
        view, table_index=_EOT_TABLE_INDEX)["definition"]
    resolve = build_field_resolver(view, table_index=_EOT_TABLE_INDEX)

    by_display_name = merge_modifiers(
        built, filters=[("Rx Count", "gt", 100000)],
        resolve_field=resolve)
    by_alias = merge_modifiers(
        built, filters=[("rx_stream_stats_frame_count", "gt", 100000)])

    assert (by_display_name["multi_result"]["filters"] ==
            by_alias["multi_result"]["filters"] ==
            ["view.rx_stream_stats_frame_count>100000"])


def test_sort_by_display_name_produces_same_expression_as_alias(view):
    built = build_query_definition(
        view, table_index=_EOT_TABLE_INDEX)["definition"]
    resolve = build_field_resolver(view, table_index=_EOT_TABLE_INDEX)

    by_display_name = merge_modifiers(
        built, sort="Rx Count DESC", resolve_field=resolve)
    assert (by_display_name["multi_result"]["orders"][-1] ==
            "view.rx_stream_stats_frame_count DESC")


# -- synthetic fixtures for the widget-type work below --------------------
#
# Unlike "Detailed Stream Results" above, none of view_query_builder's
# x_y_chart/pie_chart/histogram/boxplot builders (or the default-order
# projection-injection fix) have a real capture to validate against yet
# (see WIDGET_QUERY_PLAN.md) -- these fixtures are hand-built, just large
# enough to exercise the algorithm, not real server data.

def _synthetic_provider(**overrides):
    provider = {
        "name": "synthetic_provider",
        "base_query": {
            "multi_result": {
                "subqueries": [{"alias": "view", "subqueries": []}],
            }
        },
        "attribute_query_updates": [
            {
                "name": "col_a", "alias_name": "col_a",
                "display_name": "Col A",
                "query_updates": [
                    {"key": "multi_result/subqueries/0/projections",
                     "values": ["raw.col_a as col_a"]},
                ],
            },
            {
                "name": "col_b", "alias_name": "col_b",
                "display_name": "Col B",
                "query_updates": [
                    {"key": "multi_result/subqueries/0/projections",
                     "values": ["raw.col_b as col_b"]},
                ],
            },
        ],
        "fact_query_updates": [],
        "derived_fact_query_updates": [],
        "default_order_updates": {},
    }
    provider.update(overrides)
    return provider


def _synthetic_view(view_type, provider=None, table_overrides=None):
    provider = provider if provider is not None else _synthetic_provider()
    table = {
        "data_type": "eot",
        "query_provider": provider["name"],
        "columns": ["col_a"],
        "primary_dimension_attributes": [],
    }
    if table_overrides:
        table.update(table_overrides)
    return {
        "name": "Synthetic View",
        "details": {
            "view_type": view_type,
            "user_data": {"tables": [table]},
        },
        "effective_details": {
            "system_data": {"query_providers": [provider]}},
    }


# -- default-order projection injection (Phase 0, gap #1 in ---------------
# -- WIDGET_QUERY_PLAN.md section 1) ---------------------------------------

def test_default_order_on_inactive_column_injects_its_own_projection():
    # col_b is the default order but is NOT in the table's active columns
    # (only col_a is) -- without the fix, "view.col_b ASC" would be
    # emitted with no matching projection ever having been added.
    provider = _synthetic_provider(default_order_updates={
        "order_updates": [
            {"type": "attribute", "name": "col_b", "order": "ASC"},
        ],
    })
    view = _synthetic_view("single_level_table", provider=provider)
    built = build_query_definition(view)["definition"]
    node = built["multi_result"]
    assert "raw.col_b as col_b" in node["subqueries"][0]["projections"]
    assert "view.col_b ASC" in node["orders"]


def test_default_order_on_active_column_does_not_duplicate_projection():
    # col_a IS already active -- the fix must not re-add its projection a
    # second time (dedup already handled by _append_at_path, but this
    # pins the observable behavior).
    provider = _synthetic_provider(default_order_updates={
        "order_updates": [
            {"type": "attribute", "name": "col_a", "order": "DESC"},
        ],
    })
    view = _synthetic_view("single_level_table", provider=provider)
    built = build_query_definition(view)["definition"]
    node = built["multi_result"]
    assert node["subqueries"][0]["projections"].count(
        "raw.col_a as col_a") == 1
    assert "view.col_a DESC" in node["orders"]


# -- snapshot filter (Phase 0/1, gap #2 + shared primitive) ----------------

def test_snapshot_filter_falls_back_to_alias_qualified_snapshot_name():
    # CONFIRMED against a real server 2026-09-03 (see HANDOVER.md
    # section 9): the fallback must qualify with the outermost "view"
    # alias -- a raw "test.snapshot_name = ..." 400s as an unrecognized
    # sub-query result name at that scope.
    view = _synthetic_view("single_level_table")
    built = build_query_definition(view, snapshot_name="Snap1")["definition"]
    assert "view.test_snapshot_name = 'Snap1'" in (
        built["multi_result"]["filters"])


def test_snapshot_filter_uses_provider_template_with_value_substitution():
    provider = _synthetic_provider(snapshot_filter_provider={
        "interactive_query_updates": [
            {
                "action": "filters",
                "query_updates": [
                    {"key": "multi_result/filters",
                     "values": ["test.snapshot_name = '$(value)'"]},
                ],
            },
        ],
    })
    view = _synthetic_view("single_level_table", provider=provider)
    built = build_query_definition(
        view, snapshot_name="Snap2")["definition"]
    assert "test.snapshot_name = 'Snap2'" in built["multi_result"]["filters"]


def test_no_snapshot_name_means_no_filter_added():
    view = _synthetic_view("single_level_table")
    built = build_query_definition(view)["definition"]
    assert built["multi_result"]["filters"] == []


def test_snapshot_name_against_live_table_raises():
    # "test.snapshot_name" is a finished-test concept -- a still-running
    # test's live table has no completed snapshots to filter by.
    view = _synthetic_view(
        "single_level_table", table_overrides={"data_type": "live"})
    with pytest.raises(IQViewError, match="live"):
        build_query_definition(view, snapshot_name="Snap1")


def test_snapshot_name_against_table_without_data_type_raises():
    view = _synthetic_view(
        "single_level_table", table_overrides={"data_type": None})
    with pytest.raises(IQViewError, match="eot"):
        build_query_definition(view, snapshot_name="Snap1")


def test_snapshot_name_none_is_fine_against_live_table():
    # The restriction is specifically about *passing* snapshot_name=,
    # not about building a query for a live table at all.
    view = _synthetic_view(
        "single_level_table", table_overrides={"data_type": "live"})
    built = build_query_definition(view)  # snapshot_name=None (default)
    assert built["kind"] == "single"


# -- other view_types: dispatch + kind tagging -----------------------------

def _synthetic_xy_chart_view(series=None, providers=None):
    """A minimal but real-shaped "x_y_chart" view -- no `tables` list at
    all (CONFIRMED real shape, see HANDOVER.md section 9's "x_y_chart"
    entry): `details.user_data.series[]` instead, each entry naming a
    single `query_provider` directly (no `system_data.statistics[]`
    lookup indirection, unlike histogram)."""
    provider = _synthetic_provider(attribute_query_updates=[
        {"name": "col_a", "alias_name": "col_a",
         "query_updates": [
             {"key": "multi_result/subqueries/0/projections",
              "values": ["raw.col_a as col_a"]}]},
        {"name": "col_b", "alias_name": "col_b",
         "query_updates": [
             {"key": "multi_result/subqueries/0/projections",
              "values": ["raw.col_b as col_b"]}]},
    ])
    providers = providers if providers is not None else [provider]
    series = series if series is not None else [
        {"query_provider": "synthetic_provider",
         "h_axis": {"values": ["col_a"]}, "v_axis": {"values": ["col_b"]},
         "filter_columns": []},
    ]
    return {
        "name": "Synthetic XY Chart",
        "details": {"view_type": "x_y_chart", "user_data": {"series": series}},
        "effective_details": {"system_data": {"query_providers": providers}},
    }


def test_xy_chart_returns_multi_kind_keyed_by_provider_name():
    view = _synthetic_xy_chart_view()
    built = build_xy_chart_query_definitions(view)
    assert built["kind"] == "multi"
    assert set(built["definitions"]) == {"synthetic_provider"}
    tree = built["definitions"]["synthetic_provider"]
    node = tree["multi_result"]["subqueries"][0]
    assert "raw.col_a as col_a" in node["projections"]
    assert "raw.col_b as col_b" in node["projections"]


def test_xy_chart_includes_filter_columns_as_active_names():
    # CONFIRMED against a real server 2026-09-24: filter_columns[].name
    # names a column by its query-safe ALIAS ("test_snapshot_name"),
    # not the raw dotted attribute name _find_update_entry() actually
    # keys on ("test.snapshot_name") -- unlike h_axis/v_axis, which
    # both already use the raw dotted form. Silently no-ops without
    # translating it first (see _resolve_alias_to_name()).
    provider = _synthetic_provider(attribute_query_updates=[
        {"name": "col_a", "alias_name": "col_a",
         "query_updates": [
             {"key": "multi_result/subqueries/0/projections",
              "values": ["raw.col_a as col_a"]}]},
        {"name": "test.snapshot_name", "alias_name": "test_snapshot_name",
         "query_updates": [
             {"key": "multi_result/subqueries/0/projections",
              "values": ["raw.snapshot as test_snapshot_name"]}]},
    ])
    view = _synthetic_xy_chart_view(series=[
        {"query_provider": "synthetic_provider",
         "h_axis": {"values": ["col_a"]}, "v_axis": {"values": []},
         "filter_columns": [{"name": "test_snapshot_name", "values": []}]},
    ], providers=[provider])
    built = build_xy_chart_query_definitions(view)
    tree = built["definitions"]["synthetic_provider"]
    assert "raw.snapshot as test_snapshot_name" in (
        tree["multi_result"]["subqueries"][0]["projections"])


def test_xy_chart_applies_snapshot_filter_via_bare_attribute():
    # CONFIRMED against a real server 2026-09-24: snapshot_filter_provider
    # can be entirely unset (None) while "test.snapshot_name" still has
    # its own usable interactive_query_updates -- and that's what the
    # real capture confirms actually gets used.
    provider = _synthetic_provider(attribute_query_updates=[
        {"name": "col_a", "alias_name": "col_a",
         "query_updates": [
             {"key": "multi_result/subqueries/0/projections",
              "values": ["raw.col_a as col_a"]}]},
        {"name": "test.snapshot_name", "alias_name": "test_snapshot_name",
         "interactive_query_updates": [
             {"action": "filters", "query_updates": [
                 {"key": "multi_result/subqueries/0/filters",
                  "values": ["raw.snapshot = '$(value)'"]},
             ]},
         ]},
    ])
    view = _synthetic_xy_chart_view(series=[
        {"query_provider": "synthetic_provider",
         "h_axis": {"values": ["col_a"]}, "v_axis": {"values": []},
         "filter_columns": []},
    ], providers=[provider])
    built = build_xy_chart_query_definitions(view, snapshot_name="Snap1")
    tree = built["definitions"]["synthetic_provider"]
    assert "raw.snapshot = 'Snap1'" in (
        tree["multi_result"]["subqueries"][0]["filters"])


def test_xy_chart_raises_when_no_series():
    view = _synthetic_xy_chart_view(series=[])
    with pytest.raises(IQViewError, match="no series"):
        build_xy_chart_query_definitions(view)


def test_xy_chart_raises_on_unknown_provider():
    view = _synthetic_xy_chart_view(series=[
        {"query_provider": "nonexistent",
         "h_axis": {"values": ["col_a"]}, "v_axis": {"values": []},
         "filter_columns": []},
    ])
    with pytest.raises(IQViewError, match="nonexistent"):
        build_xy_chart_query_definitions(view)


def test_build_xy_chart_filter_dropdown_query_returns_providers_own_copy():
    provider = _synthetic_provider(
        filter_dropdown_query={"multi_result": {"projections": ["x"]}})
    view = _synthetic_xy_chart_view(providers=[provider])
    query = build_xy_chart_filter_dropdown_query(view)
    assert query == {"multi_result": {"projections": ["x"]}}
    # A real, independent copy -- mutating it doesn't touch the provider.
    query["multi_result"]["projections"].append("y")
    assert provider["filter_dropdown_query"]["multi_result"]["projections"] == ["x"]


def test_build_xy_chart_filter_dropdown_query_raises_when_absent():
    view = _synthetic_xy_chart_view()
    with pytest.raises(IQViewError, match="filter_dropdown_query"):
        build_xy_chart_filter_dropdown_query(view)


def test_pie_chart_projects_group_by_and_total_fields():
    provider = _synthetic_provider(group_by="col_b", total="col_a")
    view = _synthetic_view(
        "pie_chart", provider=provider,
        table_overrides={"columns": []})  # no active columns at all
    built = build_query_definition(view)["definition"]
    node = built["multi_result"]["subqueries"][0]
    # Both the mandatory group_by and total columns get projected even
    # though the table itself declares no active columns.
    assert "raw.col_a as col_a" in node["projections"]
    assert "raw.col_b as col_b" in node["projections"]


def test_pie_chart_applies_snapshot_filter():
    view = _synthetic_view("pie_chart")
    built = build_query_definition(view, snapshot_name="Snap1")["definition"]
    assert "view.test_snapshot_name = 'Snap1'" in (
        built["multi_result"]["filters"])


def _synthetic_histogram_view(statistics=None, group_by="col_b",
                               providers=None):
    """A minimal but real-shaped "histogram" view -- no `tables` list at
    all (confirmed real shape, see HANDOVER.md section 9's "histogram"
    entry), `details.user_data.statistics`/`group_by` instead, plus a
    matching `effective_details.system_data.statistics` lookup table
    alongside the usual `query_providers`."""
    providers = providers if providers is not None else [_synthetic_provider()]
    statistics = statistics if statistics is not None else [
        {"statistics": "synthetic_provider.col_a", "group_by": group_by},
    ]
    return {
        "name": "Synthetic Histogram",
        "details": {
            "view_type": "histogram",
            "user_data": {"statistics": statistics, "group_by": group_by},
        },
        "effective_details": {"system_data": {
            "query_providers": providers,
            "statistics": [
                {"name": "%s.%s" % (p["name"], attr["name"]),
                 "query_provider": p["name"], "stat_name": attr["name"]}
                for p in providers
                for attr in p.get("attribute_query_updates") or []
            ],
        }},
    }


def test_histogram_returns_multi_kind_keyed_by_provider_name():
    view = _synthetic_histogram_view()
    built = build_histogram_query_definitions(view)
    assert built["kind"] == "multi"
    assert set(built["definitions"]) == {"synthetic_provider"}
    tree = built["definitions"]["synthetic_provider"]
    assert "raw.col_a as col_a" in (
        tree["multi_result"]["subqueries"][0]["projections"])
    # The view's own group_by ("col_b") is applied too, unlike the
    # replaced v1's wrong provider["group_by"]/["default_group"] guess.
    assert "raw.col_b as col_b" in (
        tree["multi_result"]["subqueries"][0]["projections"])


def test_histogram_splits_into_one_query_per_distinct_provider():
    provider_a = _synthetic_provider(name="provider_a")
    provider_b = _synthetic_provider(name="provider_b")
    view = _synthetic_histogram_view(
        statistics=[
            {"statistics": "provider_a.col_a", "group_by": "col_b"},
            {"statistics": "provider_b.col_b", "group_by": "col_b"},
        ],
        providers=[provider_a, provider_b])
    built = build_histogram_query_definitions(view)
    assert set(built["definitions"]) == {"provider_a", "provider_b"}


def test_histogram_applies_snapshot_filter():
    provider = _synthetic_provider(attribute_query_updates=[
        {"name": "col_a", "alias_name": "col_a",
         "query_updates": [
             {"key": "multi_result/subqueries/0/projections",
              "values": ["raw.col_a as col_a"]}]},
        {"name": "test.snapshot_name", "alias_name": "test_snapshot_name",
         "query_updates": [
             {"key": "multi_result/subqueries/0/projections",
              "values": ["raw.snapshot as test_snapshot_name"]}]},
    ])
    view = _synthetic_histogram_view(providers=[provider])
    built = build_histogram_query_definitions(view, snapshot_name="Snap1")
    tree = built["definitions"]["synthetic_provider"]
    assert "view.test_snapshot_name = 'Snap1'" in (
        tree["multi_result"]["filters"])


def test_histogram_skips_snapshot_filter_for_provider_without_it():
    # CONFIRMED against a real server 2026-09-24: not every histogram
    # provider has a "test.snapshot_name" attribute at all -- forcing
    # the filter anyway 400s with "unknown sub-query result name".
    # snapshot_name= should just have no effect for such a provider,
    # matching x_y_chart's own "ignored where not applicable" precedent.
    view = _synthetic_histogram_view()  # default provider has no snapshot attr
    built = build_histogram_query_definitions(view, snapshot_name="Snap1")
    tree = built["definitions"]["synthetic_provider"]
    assert tree["multi_result"]["filters"] == []


def test_histogram_string_snapshot_filter_provider_resolves_via_attribute():
    # CONFIRMED against a real server 2026-09-24: snapshot_filter_provider
    # can be a bare string naming an attribute (with its own
    # interactive_query_updates), not just an inline dict template.
    provider = _synthetic_provider(
        snapshot_filter_provider="test.snapshot_name",
        attribute_query_updates=[
            {"name": "col_a", "alias_name": "col_a",
             "query_updates": [
                 {"key": "multi_result/subqueries/0/projections",
                  "values": ["raw.col_a as col_a"]}]},
            {"name": "test.snapshot_name", "alias_name": "test_snapshot_name",
             "interactive_query_updates": [
                 {"action": "filters", "query_updates": [
                     {"key": "multi_result/subqueries/0/filters",
                      "values": ["raw.snapshot = '$(value)'"]},
                 ]},
             ]},
        ])
    view = _synthetic_histogram_view(providers=[provider])
    built = build_histogram_query_definitions(view, snapshot_name="Snap1")
    tree = built["definitions"]["synthetic_provider"]
    assert "raw.snapshot = 'Snap1'" in (
        tree["multi_result"]["subqueries"][0]["filters"])


def test_histogram_raises_when_no_statistics_selected():
    view = _synthetic_histogram_view(statistics=[])
    with pytest.raises(IQViewError, match="no statistics selected"):
        build_histogram_query_definitions(view)


def test_histogram_raises_on_unknown_statistic():
    view = _synthetic_histogram_view(statistics=[
        {"statistics": "synthetic_provider.nonexistent", "group_by": "col_b"},
    ])
    with pytest.raises(IQViewError, match="nonexistent"):
        build_histogram_query_definitions(view)


def test_boxplot_returns_multi_kind_one_per_group():
    view = _synthetic_view(
        "boxplot", table_overrides={"groups": ["latency", "jitter"]})
    built = build_query_definition(view)
    assert built["kind"] == "multi"
    assert set(built["definitions"]) == {"latency", "jitter"}
    for tree in built["definitions"].values():
        assert "raw.col_a as col_a" in (
            tree["multi_result"]["subqueries"][0]["projections"])


def test_boxplot_falls_back_to_single_definition_keyed_by_provider_name():
    view = _synthetic_view("boxplot")  # no "groups" declared on the table
    built = build_query_definition(view)
    assert built["kind"] == "multi"
    assert set(built["definitions"]) == {"synthetic_provider"}


def test_health_indicator_and_ts_chart_still_unsupported():
    # health_indicator: deliberately deprioritized/out of scope for now
    # (see WIDGET_QUERY_PLAN.md section 3) -- must keep raising
    # IQViewError, not silently misbuild something.
    #
    # "chart" IS now supported by IQClient.query() (confirmed against a
    # real server 2026-09-24) -- but via a genuinely different, separate
    # mechanism (build_chart_duration_probe_definitions()/
    # build_chart_query_definitions() below, dispatched to directly from
    # client.py, NOT through this function) -- see this module's own
    # docstring's "chart" section for why. build_query_definition()
    # itself correctly still raises for it unchanged, since "chart" was
    # deliberately never added to _BUILDERS/SUPPORTED_VIEW_TYPES.
    for view_type in ("health_indicator", "chart"):
        view = _synthetic_view(view_type)
        with pytest.raises(IQViewError, match=view_type):
            build_query_definition(view)


# -- "chart" view_type: build_chart_duration_probe_definitions() /
# build_chart_query_definitions() -- see module docstring -----------------

def _synthetic_chart_view(series_overrides=None):
    """A minimal but real-shaped "chart" view -- one numeric series
    ("rate", sharing provider "duration_provider") plus the "Test
    Events" plotlines marker series every real chart view also carries
    -- matching effective_details.system_data.series[].query_details/
    series_query_providers and system_data.sampling_duration_providers/
    base_queries as captured from a real server (see HANDOVER.md
    section 9's "chart" entry)."""
    user_data_series = [
        {"name": "rate", "chart_type": "spline", "display_name": "Rate"},
        {"name": "events.name", "chart_type": "plotlines",
         "display_name": "Test Events"},
    ]
    if series_overrides is not None:
        user_data_series = series_overrides

    system_series = {
        "name": "rate",
        "query_details": [{
            "sampling_duration_provider": "duration_provider",
            "series_query_provider": "aggregate",
            "sampling_duration_multiplier": 1.1,
        }],
        "series_query_providers": [{
            "name": "aggregate",
            "completed_data": {
                "base_query_name": "base_completed",
                "query_updates": [
                    {"key": "multi_result/subqueries/0/projections",
                     "values": ["avg(raw.rate) as rate",
                                "interval(raw.ts, '{duration}') as interval"]},
                    {"key": "multi_result/projections",
                     "values": ["sum(leaf.rate) as value"]},
                ],
            },
            "live_data": {
                "base_query_name": "base_live",
                "query_updates": [
                    {"key": "single_result/projections",
                     "values": ["max(raw.ts) as timestamp",
                                "sum(raw.rate) as value"]},
                ],
            },
        }],
    }
    return {
        "name": "Synthetic Chart",
        "details": {"view_type": "chart",
                     "user_data": {"series": user_data_series}},
        "effective_details": {"system_data": {
            "series": [system_series],
            "base_queries": [
                {"name": "base_completed", "query": {"multi_result": {
                    "filters": [], "groups": ["leaf.interval"],
                    "orders": ["leaf.interval ASC"],
                    "projections": ["leaf.interval as timestamp"],
                    "subqueries": [{"alias": "leaf", "projections": [],
                                     "groups": [], "orders": [],
                                     "filters": []}],
                }}},
                {"name": "base_live", "query": {"single_result": {
                    "filters": [], "groups": [], "orders": [],
                    "projections": [],
                }}},
                {"name": "base_duration_probe", "query": {"multi_result": {
                    "filters": [], "groups": [], "orders": [],
                    "projections": ["max(leaf.avg) as sampling_duration"],
                    "subqueries": [{"alias": "leaf", "projections": [],
                                     "groups": [], "orders": [],
                                     "filters": []}],
                }}},
            ],
            "sampling_duration_providers": [{
                "name": "duration_provider",
                "base_query_name": "base_duration_probe",
                "query_updates": [
                    {"key": "multi_result/subqueries/0/projections",
                     "values": ["avg(raw.ts) as avg"]},
                ],
            }],
        }},
    }


def test_chart_numeric_series_excludes_plotlines():
    view = _synthetic_chart_view()
    series = chart_numeric_series(view)
    assert [s["name"] for s in series] == ["rate"]


def test_build_chart_duration_probe_definitions_returns_empty_when_live():
    view = _synthetic_chart_view()
    assert build_chart_duration_probe_definitions(view, is_live=True) == {}


def test_build_chart_duration_probe_definitions_builds_patched_probe():
    view = _synthetic_chart_view()
    probes = build_chart_duration_probe_definitions(view, is_live=False)
    assert set(probes) == {"duration_provider"}
    tree = probes["duration_provider"]["multi_result"]
    assert tree["subqueries"][0]["projections"] == ["avg(raw.ts) as avg"]


def test_build_chart_duration_probe_definitions_dedups_shared_provider():
    # Two series sharing the same sampling_duration_provider should
    # only be probed once.
    view = _synthetic_chart_view(series_overrides=[
        {"name": "rate", "chart_type": "spline"},
        {"name": "rate2", "chart_type": "spline"},
    ])
    view["effective_details"]["system_data"]["series"].append(
        dict(view["effective_details"]["system_data"]["series"][0],
             name="rate2"))
    probes = build_chart_duration_probe_definitions(view, is_live=False)
    assert set(probes) == {"duration_provider"}


def test_build_chart_duration_probe_definitions_raises_on_missing_provider():
    view = _synthetic_chart_view()
    view["effective_details"]["system_data"]["series"][0][
        "query_details"][0]["sampling_duration_provider"] = "nonexistent"
    with pytest.raises(IQViewError, match="nonexistent"):
        build_chart_duration_probe_definitions(view, is_live=False)


def test_build_chart_duration_probe_definitions_raises_when_no_numeric_series():
    view = _synthetic_chart_view(series_overrides=[
        {"name": "events.name", "chart_type": "plotlines"},
    ])
    with pytest.raises(IQViewError, match="no numeric series"):
        build_chart_duration_probe_definitions(view, is_live=False)


def test_build_chart_query_definitions_completed_substitutes_duration():
    view = _synthetic_chart_view()
    built = build_chart_query_definitions(
        view, is_live=False, duration_by_provider={"duration_provider": 0.9})
    assert built["kind"] == "multi"
    assert set(built["definitions"]) == {"rate"}
    node = built["definitions"]["rate"]["multi_result"]
    # avg_sampling_time=0.9 * multiplier=1.1 = 0.99 -> ceil -> 1 second.
    assert "interval(raw.ts, 'PT1S') as interval" in (
        node["subqueries"][0]["projections"])
    assert "sum(leaf.rate) as value" in node["projections"]


def test_build_chart_query_definitions_live_ignores_duration_by_provider():
    view = _synthetic_chart_view()
    built = build_chart_query_definitions(
        view, is_live=True, duration_by_provider={})
    node = built["definitions"]["rate"]["single_result"]
    assert node["projections"] == ["max(raw.ts) as timestamp",
                                    "sum(raw.rate) as value"]


def test_build_chart_query_definitions_raises_when_duration_missing():
    view = _synthetic_chart_view()
    with pytest.raises(IQViewError, match="duration_provider"):
        build_chart_query_definitions(
            view, is_live=False, duration_by_provider={})
