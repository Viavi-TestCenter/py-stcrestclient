"""Report templates + reports (/report-templates, /reports).

Closes the test-and-report automation loop: generate a report from an
existing template, then download the resulting file, entirely from code.

POST /reports body CONFIRMED against two real captures of the GUI's own
report-generation request (2026-09-11, both real requests the GUI
actually sent, not a guess) -- one an eot-only report, the other for
"live and snapshot" generation:

    {"id": "", "report_template_id": "...", "database": {"id": "...",
     "name": "..."}, "title": "...", "format": "pdf",
     "page_layout": {"paper_size": "us-letter", "orientation": "landscape"},
     "parameters": {"application.id": "...", "application.name": "...",
                     "application.version": "...", "company_name": "",
                     "custom_logo": "", "description": "",
                     "dut.details": "[]", "excluded_sections": "[]",
                     "owner": "...", "report_preferences": "{...}",
                     "test.type": "traffic",
                     "test_snapshot_filter": "[\"is_all_included\"]"},
     "metadata": {"aftViewIds": "{}"}}

The second (live+snapshot) capture is byte-identical except for one
field: `test_snapshot_filter` was `"[\"is_all_included\",
\"is_live_included\"]"` instead. This confirms `test_snapshot_filter`
is a list of independent filter flags, not a single mode -- CONFIRMED
real values so far: "is_all_included" (every snapshot) and
"is_live_included" (also include the test's live/in-progress data);
combining both in the same list is what "live and snapshot" report
generation actually looks like on the wire. See
REPORT_ALL_SNAPSHOTS_FILTER/REPORT_LIVE_INCLUDED_FILTER below.

This also superseded an earlier, wrong guess: there is no top-level
"live"/"snapshot_name" field anywhere in a real request -- live vs.
snapshot selection for a report is NOT a separate boolean the way
query()'s test_live= is; it's expressed entirely through which flags
are present in this one list.

Most of the rest of `parameters` (application.id/name/version,
company_name, dut.details, description, owner, test.type,
report_preferences) looks GUI-populated from the target database's own
metadata/preferences for display purposes, not something this module
tries to reproduce automatically -- pass any of it through **extra (as
parameters={...}) if you need exact fidelity for a specific real
request.

`excluded_sections` is the one `parameters` field this module DOES help
with directly (generate_report()'s own `excluded_sections=`, plus
find_unsupported_sections() below) -- CONFIRMED 2026-09-16, root-caused
against the actual orion-res/magellan-frontend source (not just
observed as a black box): a report template's chart-type sections
crash the report-rendering frontend with a real, 100%-reproducible
`TypeError` in its own JS (confirmed via Chrome DevTools protocol
inspection of the live report tab -- universal across every database
tried, not data-specific -- see HANDOVER.md for the full trace).
Excluding that one section via `excluded_sections=["section_2"]` made
the *exact same* template ("Traffic Test Report",
295049e881f74b458244a3adb60a7c28 -- two table sections, one chart
section with "Port Frame Rate Chart"/"Stream Frame Rate Chart")
generate a real, complete, correctly-paginated report with real data.
find_unsupported_sections() below finds which sections to exclude
generically, without needing to already know a template's section
names/layout.

CORRECTION 2026-09-16 (same day, later re-verification): the *real*
`view_type` strings for that same template's sections were re-checked
live against the actual server (`iq.find_view()` on each section's own
view name, with each name confirmed unique -- no ambiguity) and turned
out to be `"drill_down_table"` for both table sections and `"chart"`
for both chart-type views -- NOT `"single_level_table"`/`"x_y_chart"`
as an earlier pass through this same investigation had recorded and
shipped into REPORT_SAFE_VIEW_TYPES below. That was a real bug in this
library's own code (wrong safe-list entries), not a data change on the
server: as originally shipped, find_unsupported_sections() would have
flagged *every* section of this template (including the two working
table sections) as unsupported, rather than surgically flagging just
the two chart ones. Fixed by adding "drill_down_table" to
REPORT_SAFE_VIEW_TYPES below. A live Chrome-DevTools DOM re-check of
the *corrected* exclusion list (matching the original "exclude only
the chart section" case) was attempted the same day but blocked by an
unrelated, real problem on this server: Chrome itself was failing to
launch for *any* report generation attempt ("exit status 21" / "Chrome
early termination" in orion-res's own log), traced to a stale lock on
its shared `--user-data-dir` profile folder held by ~30+ accumulated
chrome.exe processes from earlier testing this session -- see
HANDOVER.md. So: the general mechanism (excluding crash-inducing
chart-type sections works) remains confirmed from the original DOM
inspection; the exact safe/unsafe view_type strings are now corrected
to match live reality, but re-confirming the corrected list end-to-end
via a fresh DOM inspection is still pending a Chrome/process cleanup on
this machine.
"""
from .exceptions import IQReportError

#: CONFIRMED real filter flag for parameters.test_snapshot_filter
#: meaning "include every (snapshot/eot) test result" -- what the real
#: GUI sends by default (see module docstring). Pass to generate_report(
#: snapshot_filter=REPORT_ALL_SNAPSHOTS_FILTER) to match that exactly.
REPORT_ALL_SNAPSHOTS_FILTER = "is_all_included"

#: CONFIRMED real filter flag for parameters.test_snapshot_filter
#: meaning "also include the test's live/in-progress data" -- combine
#: with REPORT_ALL_SNAPSHOTS_FILTER (as a list) for "live and snapshot"
#: report generation, confirmed against a real GUI capture 2026-09-11:
#: generate_report(snapshot_filter=[REPORT_ALL_SNAPSHOTS_FILTER,
#: REPORT_LIVE_INCLUDED_FILTER]).
REPORT_LIVE_INCLUDED_FILTER = "is_live_included"

#: view_types CONFIRMED safe for report generation specifically --
#: narrower than tciqrestclient.view_query_builder.SUPPORTED_VIEW_TYPES (which is
#: about what query() can build a definition for, a different concern).
#: "drill_down_table" is the one directly CONFIRMED-safe entry, checked
#: live 2026-09-16 against the real "Traffic Test Report" template's own
#: two table-section views (see the module docstring's "CORRECTION" note
#: -- an earlier pass had wrongly recorded these as "single_level_table"
#: instead). "single_level_table"/"paged_single_level_table" are carried
#: over from query()'s own confirmed-safe types (view_query_builder.
#: SUPPORTED_VIEW_TYPES) as a reasonable but NOT report-section-confirmed
#: assumption -- harmless to list even if never actually matched by a
#: report section, since the risk here is only ever from omitting a
#: real safe type (causing needless over-exclusion), not from listing
#: one that doesn't come up. Everything else (chart/pie_chart/histogram/
#: boxplot/gauge/health_indicator/...) is unconfirmed for reports --
#: "chart" specifically is now CONFIRMED to crash it (see module
#: docstring) -- treated the same as truly-unknown types here rather
#: than assumed safe.
REPORT_SAFE_VIEW_TYPES = ("single_level_table", "paged_single_level_table",
                           "drill_down_table")


def list_report_templates(transport):
    return transport.get("/report-templates") or []


def get_report_template(transport, template_id):
    if not template_id:
        raise IQReportError("template_id is required")
    return transport.get("/report-templates/%s" % template_id)


def find_unsupported_sections(transport, template, timeout=None):
    """Find which of a report template's sections reference a view
    whose real view_type isn't confirmed safe for report generation
    (see REPORT_SAFE_VIEW_TYPES and the module docstring for why this
    exists -- a real, confirmed crash in the report-rendering frontend,
    not a guess).

    Arguments:
    template -- A report template record, as returned by
               get_report_template().
    timeout  -- Passed through to the view lookup for each view a
               section references.

    Return:
    List of section names (the same "name" field generate_report(
    excluded_sections=...) expects) that reference at least one view
    whose view_type isn't in REPORT_SAFE_VIEW_TYPES -- including a view
    that couldn't be found on the server at all, treated as unsupported
    rather than silently skipped. Order matches the template's own
    section order; a template with no such sections returns [].
    """
    from . import views as views_mod

    sections = (template.get("details") or {}).get("sections") or []
    unsupported = []
    for section in sections:
        name = section.get("name")
        if not name:
            continue
        for v in section.get("views") or []:
            view_name = v.get("name")
            view = (views_mod.find_view_by_name(transport, view_name, timeout=timeout)
                    if view_name else None)
            view_type = (view.get("details") or {}).get("view_type") if view else None
            if view_type not in REPORT_SAFE_VIEW_TYPES:
                unsupported.append(name)
                break
    return unsupported


def create_report(transport, report_template_id, database_id, title,
                   format="pdf", database_name=None, **extra):
    """Create (generate) a report from an existing template.

    Arguments:
    report_template_id -- Id of an existing report template.
    database_id         -- Database (test) to report on.
    title               -- Report title. CONFIRMED required by a real
                           server 2026-09-03 (see HANDOVER.md section 9)
                           -- omitting it 400s with "missing report
                           title".
    format               -- Output format. CONFIRMED lowercase 2026-09-03
                           (e.g. 'pdf', not 'PDF') -- 'PDF' 400s with
                           "unknown report format".
    database_name        -- Optional -- the real GUI request also
                           includes database.name alongside database.id
                           (see module docstring). None (default) omits
                           it, matching this method's pre-existing
                           behavior -- CONFIRMED against a real server
                           that omitting it is accepted too (every
                           real-server call this session succeeded
                           without it).
    extra                -- Additional report fields (parameters,
                            page_layout, metadata, etc. -- see module
                            docstring for confirmed real shapes) --
                            passed through as-is.
    """
    if not report_template_id:
        raise IQReportError("report_template_id is required")
    if not database_id:
        raise IQReportError("database_id is required")
    if not title:
        raise IQReportError("title is required")

    database = {"id": database_id}
    if database_name is not None:
        database["name"] = database_name

    body = {
        "report_template_id": report_template_id,
        "database": database,
        "title": title,
        "format": format,
    }
    body.update(extra)
    return transport.post("/reports", json_body=body)


def get_report(transport, report_id):
    if not report_id:
        raise IQReportError("report_id is required")
    return transport.get("/reports/%s" % report_id)


def list_reports(transport):
    return transport.get("/reports") or []


def download_report_file(transport, report_id, save_as=None):
    """Download a generated report's file.

    Arguments:
    save_as -- Local path to write the file to. None to return the raw
              bytes instead of writing to disk.

    Return:
    save_as if given, else the raw file bytes.
    """
    if not report_id:
        raise IQReportError("report_id is required")

    content = transport.get_raw("/reports/%s/download" % report_id)
    if save_as:
        with open(save_as, "wb") as f:
            f.write(content)
        return save_as
    return content
