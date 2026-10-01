"""Named view CRUD, against the real captured view/definition shape."""
import copy
import json
import os

import pytest
import responses as responses_lib

import fixtures
from tciqrestclient import views
from tciqrestclient.exceptions import IQViewError
from tciqrestclient.transport import Transport

BASE = "http://fake:9200"
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_data(filename):
    path = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(
            "tests/data/%s is a real orion-res capture that isn't checked "
            "into this repo -- see HANDOVER.md section 9" % filename)
    with open(path) as f:
        return json.load(f)


def test_list_views(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/views", json=[fixtures.VIEW])
    result = views.list_views(Transport(BASE))
    assert result == [fixtures.VIEW]


def test_list_views_empty(mocked_responses):
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=None)
    assert views.list_views(Transport(BASE)) == []


def test_get_view(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/views/view-1", json=fixtures.VIEW)
    result = views.get_view(Transport(BASE), "view-1")
    assert result["name"] == "Detailed Stream Results"


def test_list_views_timeout_override_reaches_transport(mocked_responses):
    from unittest import mock
    mocked_responses.add(responses_lib.GET, BASE + "/views", json=[])
    transport = Transport(BASE)
    with mock.patch.object(
            transport, "get", wraps=transport.get) as spy:
        views.list_views(transport, timeout=45)
    assert spy.call_args.kwargs["timeout"] == 45


def test_get_view_requires_id():
    try:
        views.get_view(Transport(BASE), None)
        assert False, "expected IQViewError"
    except IQViewError:
        pass


def test_find_view_by_name_match(mocked_responses):
    other = copy.deepcopy(fixtures.VIEW)
    other["id"] = "view-2"
    other["name"] = "Some Other View"
    mocked_responses.add(
        responses_lib.GET, BASE + "/views", json=[other, fixtures.VIEW])
    result = views.find_view_by_name(
        Transport(BASE), "Detailed Stream Results")
    assert result["id"] == "view-1"


def test_find_view_by_name_no_match(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/views", json=[fixtures.VIEW])
    assert views.find_view_by_name(Transport(BASE), "Nonexistent") is None


def test_find_view_by_name_timeout_override_reaches_transport(
        mocked_responses):
    from unittest import mock
    mocked_responses.add(
        responses_lib.GET, BASE + "/views", json=[fixtures.VIEW])
    transport = Transport(BASE)
    with mock.patch.object(
            transport, "get", wraps=transport.get) as spy:
        views.find_view_by_name(
            transport, "Detailed Stream Results", timeout=45)
    assert spy.call_args.kwargs["timeout"] == 45


def test_get_view_definition_raises_without_effective_details():
    # fixtures.VIEW is a real (trimmed) `details` shape, but was captured
    # without effective_details.system_data.query_providers -- the
    # templates get_view_definition() needs to build an executable query.
    # See test_get_view_definition_builds_real_query below for the happy
    # path against a real export that does include them.
    try:
        views.get_view_definition(fixtures.VIEW)
        assert False, "expected IQViewError"
    except IQViewError as e:
        assert "Detailed Stream Results" in str(e)
        assert "query_provider" in str(e)


def test_get_view_definition_requires_view():
    try:
        views.get_view_definition(None)
        assert False, "expected IQViewError"
    except IQViewError:
        pass


def test_get_view_definition_builds_real_query():
    # CONFIRMED byte-for-byte against a real captured POST /queries body
    # -- see tciqrestclient.view_query_builder module docstring and
    # tests/test_view_query_builder.py for the full validation.
    view = _load_data("view_detailed_stream_results.json")
    expected = _load_data("dsr_query_unfiltered.json")["definition"]
    from tciqrestclient.query import merge_modifiers
    built = views.get_view_definition(view, data_type="eot")
    assert built["kind"] == "single"
    assert merge_modifiers(built["definition"], limit=120) == expected


def _synthetic_view_with_tables(*data_types):
    return {
        "name": "Synthetic",
        "details": {"user_data": {"tables": [
            {"data_type": dt} for dt in data_types
        ]}},
    }


# -- IQ-PYTHON-004: default-to-snapshot table resolution -- CONFIRMED  --
# -- necessary 2026-09-03 against a real server (see HANDOVER.md §9)  --

def test_resolve_table_index_defaults_to_eot_when_live_listed_first():
    view = _synthetic_view_with_tables("live", "eot")
    assert views._resolve_table_index(view, None, None) == 1


def test_resolve_table_index_defaults_to_eot_when_eot_listed_first():
    # Not just "index 1 happens to work" -- genuinely type-aware.
    view = _synthetic_view_with_tables("eot", "live")
    assert views._resolve_table_index(view, None, None) == 0


def test_resolve_table_index_falls_back_to_zero_with_no_eot_table():
    view = _synthetic_view_with_tables("live")
    assert views._resolve_table_index(view, None, None) == 0


def test_resolve_table_index_explicit_index_still_honored():
    # An explicit table_index=0 must NOT be overridden by the new
    # default-to-eot logic, even though eot is at index 1 here.
    view = _synthetic_view_with_tables("live", "eot")
    assert views._resolve_table_index(view, 0, None) == 0


def test_resolve_table_index_data_type_still_takes_priority():
    view = _synthetic_view_with_tables("eot", "live")
    assert views._resolve_table_index(view, None, "live") == 1


def test_resolve_table_index_data_type_matching_is_case_insensitive():
    # Real user complaint: data_type="EOT" silently failed -- every real
    # table's own data_type value is lowercase, but a caller's
    # differently-cased string should still match, not raise.
    view = _synthetic_view_with_tables("live", "eot")
    assert views._resolve_table_index(view, None, "EOT") == 1
    assert views._resolve_table_index(view, None, "Live") == 0


def test_get_view_definition_unknown_data_type_raises():
    view = _load_data("view_detailed_stream_results.json")
    try:
        views.get_view_definition(view, data_type="nope")
        assert False, "expected IQViewError"
    except IQViewError as e:
        assert "nope" in str(e)


def test_save_view_creates_when_no_id(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/views", json={"id": "new-1"})
    result = views.save_view(
        Transport(BASE), "My View", fixtures.VIEW["details"])
    assert result == {"id": "new-1"}
    sent = mocked_responses.calls[0].request
    assert sent.method == "POST"


def test_save_view_sends_details_verbatim(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/views", json={"id": "new-1"})
    views.save_view(Transport(BASE), "My View", fixtures.VIEW["details"])

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["details"] == fixtures.VIEW["details"]


def test_save_view_updates_when_id_given(mocked_responses):
    mocked_responses.add(
        responses_lib.PUT, BASE + "/views/view-1", json={"id": "view-1"})
    views.save_view(
        Transport(BASE), "My View", fixtures.VIEW["details"],
        view_id="view-1")
    sent = mocked_responses.calls[0].request
    assert sent.method == "PUT"


def test_save_view_requires_name():
    try:
        views.save_view(Transport(BASE), "", fixtures.VIEW["details"])
        assert False, "expected IQViewError"
    except IQViewError:
        pass


# -- IQ-PYTHON-003: a view saved via save_view() has no usable          --
# -- effective_details.system_data of its own -- CONFIRMED 2026-09-03   --
# -- against a real server (see HANDOVER.md §9). The client-side        --
# -- fallback: borrow a matching query_provider from any OTHER view on  --
# -- the server that has it, since provider definitions are shared      --
# -- globally by name, not view-specific.                               --

_WORKING_PROVIDER = {
    "name": "synthetic_provider",
    "base_query": {"multi_result": {
        "subqueries": [{"alias": "view", "subqueries": []}]}},
    "attribute_query_updates": [
        {"name": "col_a", "alias_name": "col_a", "display_name": "Col A",
         "query_updates": [{"key": "multi_result/subqueries/0/projections",
                             "values": ["raw.col_a as col_a"]}]},
    ],
    "fact_query_updates": [],
    "derived_fact_query_updates": [],
    "default_order_updates": {},
}

_VIEW_WITH_PROVIDER = {
    "id": "view-source", "name": "Source View",
    "details": {"view_type": "single_level_table", "user_data": {"tables": [
        {"data_type": "eot", "query_provider": "synthetic_provider",
         "columns": ["col_a"], "primary_dimension_attributes": []},
    ]}},
    "effective_details": {"system_data": {
        "query_providers": [_WORKING_PROVIDER]}},
}

_CUSTOM_VIEW_MISSING_PROVIDER = {
    "id": "view-custom", "name": "My CI View",
    "details": {"view_type": "single_level_table", "user_data": {"tables": [
        {"data_type": "eot", "query_provider": "synthetic_provider",
         "columns": ["col_a"], "primary_dimension_attributes": []},
    ]}},
    # No effective_details at all -- exactly what a real save_view()
    # response/re-fetch looks like, confirmed 2026-09-03.
}


def test_get_view_definition_finds_provider_from_another_view(
        mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/views",
        json=[_VIEW_WITH_PROVIDER, _CUSTOM_VIEW_MISSING_PROVIDER])
    built = views.get_view_definition(
        _CUSTOM_VIEW_MISSING_PROVIDER, data_type="eot",
        transport=Transport(BASE))
    assert built["kind"] == "single"
    assert "raw.col_a as col_a" in (
        built["definition"]["multi_result"]["subqueries"][0]["projections"])


def test_get_view_definition_without_transport_keeps_old_behavior(
        mocked_responses):
    # No transport= given (the default) -- no fallback attempted, exact
    # pre-fix behavior: raises, even though a fix-up would have been
    # findable if transport had been passed (nothing should even be
    # requested from the server in this case).
    try:
        views.get_view_definition(
            _CUSTOM_VIEW_MISSING_PROVIDER, data_type="eot")
        assert False, "expected IQViewError"
    except IQViewError as e:
        assert "synthetic_provider" in str(e)
    assert len(mocked_responses.calls) == 0


def test_get_view_definition_prefers_provider_with_default_order(
        mocked_responses):
    # CONFIRMED 2026-09-03 against a real server: default_order_updates
    # is NOT globally shared across views with the same provider name --
    # of 5 real views sharing one provider, 4 had an empty
    # order_updates. Naively using whichever match is found first can
    # silently pick one with no default order, which then 400s on any
    # paginated/limited query ("pagination requires at least one order
    # expression") -- the fallback must prefer a match that actually has
    # one, even if it's not literally the first view found.
    provider_no_order = copy.deepcopy(_WORKING_PROVIDER)
    provider_no_order["default_order_updates"] = {"order_updates": []}
    view_no_order = {
        "id": "view-no-order", "name": "Some Other View With No Order",
        "details": {"view_type": "single_level_table", "user_data": {
            "tables": [{"data_type": "eot",
                        "query_provider": "synthetic_provider"}]}},
        "effective_details": {"system_data": {
            "query_providers": [provider_no_order]}},
    }
    provider_with_order = copy.deepcopy(_WORKING_PROVIDER)
    provider_with_order["default_order_updates"] = {"order_updates": [
        {"type": "attribute", "name": "col_a", "order": "ASC"}]}
    view_with_order = {
        "id": "view-with-order", "name": "Source View",
        "details": {"view_type": "single_level_table", "user_data": {
            "tables": [{"data_type": "eot",
                        "query_provider": "synthetic_provider"}]}},
        "effective_details": {"system_data": {
            "query_providers": [provider_with_order]}},
    }
    # view_no_order is listed FIRST -- proves this isn't "just take the
    # first match".
    mocked_responses.add(
        responses_lib.GET, BASE + "/views",
        json=[view_no_order, view_with_order, _CUSTOM_VIEW_MISSING_PROVIDER])
    built = views.get_view_definition(
        _CUSTOM_VIEW_MISSING_PROVIDER, data_type="eot",
        transport=Transport(BASE))
    assert "view.col_a ASC" in built["definition"]["multi_result"]["orders"]


def test_get_view_definition_provider_not_found_anywhere_still_raises(
        mocked_responses):
    # transport IS given, but no other view on the server has this
    # provider either -- must still raise, not silently produce a
    # broken/empty query.
    other_view = copy.deepcopy(_VIEW_WITH_PROVIDER)
    other_view["effective_details"]["system_data"]["query_providers"] = []
    mocked_responses.add(
        responses_lib.GET, BASE + "/views",
        json=[other_view, _CUSTOM_VIEW_MISSING_PROVIDER])
    try:
        views.get_view_definition(
            _CUSTOM_VIEW_MISSING_PROVIDER, data_type="eot",
            transport=Transport(BASE))
        assert False, "expected IQViewError"
    except IQViewError as e:
        assert "synthetic_provider" in str(e)


def test_delete_view(mocked_responses):
    mocked_responses.add(
        responses_lib.DELETE, BASE + "/views/view-1", status=204)
    views.delete_view(Transport(BASE), "view-1")


def test_delete_view_requires_id():
    try:
        views.delete_view(Transport(BASE), None)
        assert False, "expected IQViewError"
    except IQViewError:
        pass
