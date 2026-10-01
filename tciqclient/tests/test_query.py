"""Query definition composition, exercised against the real captured
multi_result definition (fixtures.QUERY_DEFINITION) -- not an invented
shape."""
import datetime

import pytest

import fixtures
from tciqrestclient.exceptions import IQQueryError
from tciqrestclient.query import merge_modifiers, rows_to_dicts


def test_no_modifiers_returns_equivalent_definition():
    result = merge_modifiers(fixtures.QUERY_DEFINITION)
    assert result == fixtures.QUERY_DEFINITION


def test_does_not_mutate_input():
    original = fixtures.QUERY_DEFINITION
    merge_modifiers(original, filters=[("frame_count", "gt", 0)])
    assert original == fixtures.QUERY_DEFINITION  # unchanged


def test_filter_qualified_with_single_child_alias():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION, filters=[("frame_count", "gt", 0)])
    node = result["multi_result"]
    assert node["filters"][-1] == "view.frame_count>0"


def test_filter_shorthand_field_value():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION, filters=[("frame_count", 42)])
    assert result["multi_result"]["filters"][-1] == "view.frame_count=42"


def test_filter_string_operators():
    cases = [
        (("a", "eq", 1), "view.a=1"),
        (("a", "ne", 1), "view.a!=1"),
        (("a", "lt", 1), "view.a<1"),
        (("a", "lte", 1), "view.a<=1"),
        (("a", "gt", 1), "view.a>1"),
        (("a", "gte", 1), "view.a>=1"),
    ]
    for filt, expected in cases:
        result = merge_modifiers(fixtures.QUERY_DEFINITION, filters=[filt])
        assert result["multi_result"]["filters"][-1] == expected


def test_filter_contains_uses_like():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        filters=[("stream_block_name", "contains", "Block")])
    assert result["multi_result"]["filters"][-1] == (
        "view.stream_block_name LIKE '%Block%'")


def test_filter_in_uses_in_clause():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        filters=[("port", "in", ["1/1", "1/2"])])
    assert result["multi_result"]["filters"][-1] == (
        "view.port IN ('1/1', '1/2')")


def test_filter_string_value_is_quoted_and_escaped():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        filters=[("name", "eq", "O'Brien")])
    assert result["multi_result"]["filters"][-1] == "view.name='O''Brien'"


def test_filter_dict_form():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        filters=[{"field": "frame_count", "op": "gt", "value": 0}])
    assert result["multi_result"]["filters"][-1] == "view.frame_count>0"


def test_filter_raw_string_passthrough():
    raw = "view.frame_count>0 AND view.other<10"
    result = merge_modifiers(fixtures.QUERY_DEFINITION, filters=[raw])
    assert result["multi_result"]["filters"][-1] == raw


def test_filter_already_qualified_not_re_qualified():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION, filters=[("txss.frame_count", 0)])
    assert result["multi_result"]["filters"][-1] == "txss.frame_count=0"


def test_filter_rejects_unknown_op():
    with pytest.raises(IQQueryError):
        merge_modifiers(fixtures.QUERY_DEFINITION, filters=[("a", "wat", 1)])


def test_filter_rejects_bad_tuple_shape():
    with pytest.raises(IQQueryError):
        merge_modifiers(fixtures.QUERY_DEFINITION, filters=[("a", "b", "c", "d")])


def test_sort_single_field_defaults_asc():
    result = merge_modifiers(fixtures.QUERY_DEFINITION, sort="frame_count")
    assert result["multi_result"]["orders"][-1] == "view.frame_count ASC"


def test_sort_field_and_direction_tuple():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION, sort=("frame_count", "desc"))
    assert result["multi_result"]["orders"][-1] == "view.frame_count DESC"


def test_sort_raw_string_with_direction_passthrough():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION, sort="view.frame_count DESC")
    assert result["multi_result"]["orders"][-1] == "view.frame_count DESC"


def test_sort_multi_column():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION, sort=[("a", "asc"), ("b", "desc")])
    orders = result["multi_result"]["orders"]
    assert orders[-2:] == ["view.a ASC", "view.b DESC"]


def test_sort_rejects_bad_direction():
    with pytest.raises(IQQueryError):
        merge_modifiers(fixtures.QUERY_DEFINITION, sort=("a", "sideways"))


def test_group_by_single_field():
    result = merge_modifiers(fixtures.QUERY_DEFINITION, group_by="stream_block_name")
    assert result["multi_result"]["groups"][-1] == "view.stream_block_name"


def test_group_by_list():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION, group_by=["a", "b"])
    assert result["multi_result"]["groups"][-2:] == ["view.a", "view.b"]


def test_time_range_both_bounds():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        time_range=("started", "2026-01-01", "2026-01-02"))
    filters = result["multi_result"]["filters"]
    assert filters[-2] == "view.started>='2026-01-01'"
    assert filters[-1] == "view.started<='2026-01-02'"


def test_time_range_open_ended_start_only():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        time_range={"field": "started", "start": "2026-01-01"})
    filters = result["multi_result"]["filters"]
    assert filters[-1] == "view.started>='2026-01-01'"


def test_time_range_accepts_datetime():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        time_range=("started", datetime.datetime(2026, 1, 1), None))
    filters = result["multi_result"]["filters"]
    assert filters[-1] == "view.started>='2026-01-01T00:00:00'"


def test_time_range_requires_field():
    with pytest.raises(IQQueryError):
        merge_modifiers(fixtures.QUERY_DEFINITION, time_range=("a", "b"))


def test_all_modifiers_composable_together():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        filters=[("frame_count", "gt", 0)],
        sort=("frame_count", "desc"),
        group_by="stream_block_name",
        time_range=("started", "2026-01-01", "2026-01-02"),
    )
    node = result["multi_result"]
    assert node["filters"][-3:] == [
        "view.frame_count>0",
        "view.started>='2026-01-01'",
        "view.started<='2026-01-02'",
    ]
    assert node["orders"][-1] == "view.frame_count DESC"
    assert node["groups"][-1] == "view.stream_block_name"
    # original tree structure and limit/pagination untouched
    assert node["limit"] == 120
    assert node["pagination"] == {"mode": "forward"}
    assert len(node["subqueries"]) == 1


def test_limit_overrides_existing_value():
    result = merge_modifiers(fixtures.QUERY_DEFINITION, limit=50)
    assert result["multi_result"]["limit"] == 50


def test_limit_none_leaves_existing_value_untouched():
    result = merge_modifiers(fixtures.QUERY_DEFINITION, limit=None)
    assert result["multi_result"]["limit"] == 120  # the view's own default


def test_limit_sets_when_absent():
    definition = {
        "multi_result": {
            "subqueries": [],
            "projections": [], "filters": [], "groups": [], "orders": [],
        }
    }
    result = merge_modifiers(definition, limit=1000)
    assert result["multi_result"]["limit"] == 1000


def test_limit_composes_with_other_modifiers():
    result = merge_modifiers(
        fixtures.QUERY_DEFINITION,
        filters=[("frame_count", "gt", 0)],
        limit=25,
    )
    node = result["multi_result"]
    assert node["limit"] == 25
    assert node["filters"][-1] == "view.frame_count>0"


def test_flat_definition_no_prefix_when_multiple_children():
    definition = {
        "multi_result": {
            "subqueries": [
                {"alias": "a", "subqueries": [], "projections": [], "filters": [], "groups": [], "orders": []},
                {"alias": "b", "subqueries": [], "projections": [], "filters": [], "groups": [], "orders": []},
            ],
            "projections": [], "filters": [], "groups": [], "orders": [],
        }
    }
    result = merge_modifiers(definition, filters=[("x", 1)])
    assert result["multi_result"]["filters"][-1] == "x=1"


def test_unrecognized_definition_raises():
    with pytest.raises(IQQueryError):
        merge_modifiers({"nonsense": {}}, filters=[("a", 1)])


def test_rows_to_dicts_zips_columns_and_rows():
    dicts = rows_to_dicts(fixtures.QUERY_RESPONSE["result"])
    assert dicts[0] == {
        "test_snapshot_name": "Snapshot_4Kstreams",
        "tx_stream_stats_frame_count": "44841",
        "rx_stream_stats_frame_count": "43227",
    }
    assert len(dicts) == 3


def test_rows_to_dicts_empty_result():
    assert rows_to_dicts({}) == []
    assert rows_to_dicts(None) == []
