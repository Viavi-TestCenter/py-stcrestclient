"""Report templates + reports (/report-templates, /reports)."""
import responses as responses_lib

from tciqrestclient import reports
from tciqrestclient.exceptions import IQReportError
from tciqrestclient.transport import Transport

BASE = "http://fake:9200"


def test_list_report_templates(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/report-templates",
        json=[{"id": "t1"}])
    assert reports.list_report_templates(Transport(BASE)) == [{"id": "t1"}]


def test_list_report_templates_empty(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/report-templates", json=None)
    assert reports.list_report_templates(Transport(BASE)) == []


def test_get_report_template(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/report-templates/t1", json={"id": "t1"})
    assert reports.get_report_template(Transport(BASE), "t1") == {"id": "t1"}


def test_get_report_template_requires_id():
    try:
        reports.get_report_template(Transport(BASE), None)
        assert False, "expected IQReportError"
    except IQReportError:
        pass


def test_create_report_posts_expected_body(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    result = reports.create_report(Transport(BASE), "t1", "db-1", "My Report")
    assert result == {"id": "r1"}

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["report_template_id"] == "t1"
    assert sent_body["database"] == {"id": "db-1"}
    assert sent_body["title"] == "My Report"
    # CONFIRMED against a real server 2026-09-03 (see HANDOVER.md section
    # 9): the format value must be lowercase -- "PDF" 400s with "unknown
    # report format".
    assert sent_body["format"] == "pdf"


def test_create_report_requires_title():
    try:
        reports.create_report(Transport(BASE), "t1", "db-1", "")
        assert False, "expected IQReportError"
    except IQReportError:
        pass


def test_create_report_passes_extra_fields(mocked_responses):
    mocked_responses.add(
        responses_lib.POST, BASE + "/reports", json={"id": "r1"})
    reports.create_report(
        Transport(BASE), "t1", "db-1", format="HTML", title="My Report")

    import json
    sent_body = json.loads(mocked_responses.calls[0].request.body)
    assert sent_body["format"] == "HTML"
    assert sent_body["title"] == "My Report"


def test_create_report_requires_template_id():
    try:
        reports.create_report(Transport(BASE), "", "db-1", "My Report")
        assert False, "expected IQReportError"
    except IQReportError:
        pass


def test_create_report_requires_database_id():
    try:
        reports.create_report(Transport(BASE), "t1", "", "My Report")
        assert False, "expected IQReportError"
    except IQReportError:
        pass


def test_get_report(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/reports/r1", json={"id": "r1"})
    assert reports.get_report(Transport(BASE), "r1") == {"id": "r1"}


def test_list_reports(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/reports", json=[{"id": "r1"}])
    assert reports.list_reports(Transport(BASE)) == [{"id": "r1"}]


def test_download_report_file_returns_bytes(mocked_responses):
    mocked_responses.add(
        responses_lib.GET, BASE + "/reports/r1/download",
        body=b"%PDF-fake", content_type="application/pdf")
    result = reports.download_report_file(Transport(BASE), "r1")
    assert result == b"%PDF-fake"


def test_download_report_file_writes_to_disk(mocked_responses, tmp_path):
    mocked_responses.add(
        responses_lib.GET, BASE + "/reports/r1/download",
        body=b"%PDF-fake", content_type="application/pdf")
    save_as = str(tmp_path / "report.pdf")
    result = reports.download_report_file(
        Transport(BASE), "r1", save_as=save_as)
    assert result == save_as
    with open(save_as, "rb") as f:
        assert f.read() == b"%PDF-fake"


def test_download_report_file_requires_id():
    try:
        reports.download_report_file(Transport(BASE), None)
        assert False, "expected IQReportError"
    except IQReportError:
        pass


# ---------------------------------------------------------------------------
# find_unsupported_sections() -- CONFIRMED 2026-09-16 fix for a real
# report-generation crash (see module docstring/HANDOVER.md). Fixture
# below mirrors the real "Traffic Test Report" template's shape: two
# table sections and one chart section. view_type strings are the real
# ones ("drill_down_table"/"chart"), re-checked live 2026-09-16 against
# the real server -- an earlier pass through this same investigation had
# wrongly recorded these as "single_level_table"/"x_y_chart" instead
# (see reports.py's module docstring "CORRECTION" note); this fixture
# was updated to match reality, not the other way around.
# ---------------------------------------------------------------------------

TEMPLATE_WITH_CHART_SECTION = {
    "id": "tmpl-1",
    "details": {
        "sections": [
            {"name": "section", "views": [{"name": "Table View One"}]},
            {"name": "section_1", "views": [{"name": "Table View Two"}]},
            {"name": "section_2", "views": [
                {"name": "Port Frame Rate Chart"},
                {"name": "Stream Frame Rate Chart"},
            ]},
        ],
    },
}

VIEWS_BY_NAME = {
    "Table View One": {"name": "Table View One",
                        "details": {"view_type": "drill_down_table"}},
    "Table View Two": {"name": "Table View Two",
                        "details": {"view_type": "drill_down_table"}},
    "Port Frame Rate Chart": {"name": "Port Frame Rate Chart",
                               "details": {"view_type": "chart"}},
    "Stream Frame Rate Chart": {"name": "Stream Frame Rate Chart",
                                 "details": {"view_type": "chart"}},
}


def _views_list_response(request):
    import json as _json
    return (200, {}, _json.dumps(list(VIEWS_BY_NAME.values())))


def test_find_unsupported_sections_flags_only_the_chart_section(
        mocked_responses):
    mocked_responses.add_callback(
        responses_lib.GET, BASE + "/views",
        callback=_views_list_response, content_type="application/json")
    result = reports.find_unsupported_sections(
        Transport(BASE), TEMPLATE_WITH_CHART_SECTION)
    assert result == ["section_2"]


def test_find_unsupported_sections_all_table_returns_empty(
        mocked_responses):
    mocked_responses.add_callback(
        responses_lib.GET, BASE + "/views",
        callback=_views_list_response, content_type="application/json")
    all_table_template = {
        "details": {"sections": [
            {"name": "section", "views": [{"name": "Table View One"}]},
        ]},
    }
    assert reports.find_unsupported_sections(
        Transport(BASE), all_table_template) == []


def test_find_unsupported_sections_missing_view_counts_as_unsupported(
        mocked_responses):
    mocked_responses.add_callback(
        responses_lib.GET, BASE + "/views",
        callback=_views_list_response, content_type="application/json")
    template = {
        "details": {"sections": [
            {"name": "section", "views": [{"name": "Does Not Exist"}]},
        ]},
    }
    assert reports.find_unsupported_sections(Transport(BASE), template) == (
        ["section"])


def test_find_unsupported_sections_no_details_returns_empty():
    assert reports.find_unsupported_sections(Transport(BASE), {}) == []
