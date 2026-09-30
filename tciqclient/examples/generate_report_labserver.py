"""Generate and download a PDF report against a specific database on a
lab-hosted TestCenter IQ deployment ("labserver") -- see
list_databases_labserver.py for that connection mode in isolation, and
generate_report.py for the local-server version of this same walkthrough
(async completion, excluded_sections=, etc. -- all identical here, only
the connection differs).

CONFIRMED against a real labserver 2026-09-22 (iqteam03.es.cal.viavi.io:
9199): HTTPS with a self-signed certificate (see
list_databases_labserver.py's own docstring for the full story) -- so
this uses the same host/port/use_https/verify settings as that example.

TEMPLATE_ID/database_name=/snapshot_filter=/page_layout below all come
straight from a real GUI-captured POST /reports body for this exact
database (2026-09-22), not guesses:

    {"report_template_id": "1ec10b591a114cd08d36e80c0e85ebac",
     "database": {"id": "edhkcay4a5bctdhy", "name": "Untitled"},
     "title": "Untitled Report", "format": "pdf",
     "page_layout": {"paper_size": "us-letter", "orientation": "landscape"},
     "parameters": {..., "excluded_sections": "[]",
                     "test_snapshot_filter": "[\"is_all_included\"]"}, ...}

Two things worth calling out about that real capture:
  - The GUI picked "Traffic Test Report (tmp)" by id, not the canonical
    "Traffic Test Report" by name -- template selection is evidently
    per-database/context, not a single fixed default (this database's
    own test.type metadata is "rfc2544,throughput,traffic"). Looked up
    directly: same 3-section structure as the canonical template
    (section/section_1 = tables, section_2 = the same "Port Frame Rate
    Chart"/"Stream Frame Rate Chart" pair) -- a "(tmp)" template is
    evidently a full clone, not a stripped-down variant.
  - The real capture's own excluded_sections is "[]" -- the GUI itself
    does NOT proactively exclude section_2 here, even though it's the
    exact same crash-inducing chart section already confirmed broken
    for the canonical template (see generate_report.py/HANDOVER.md).
    This script excludes it anyway via find_unsupported_report_sections()
    -- deliberately diverging from the literal real capture, because
    that field is user/GUI-controlled, not an automatic crash-avoidance
    mechanism, and reproducing the crash on purpose here wouldn't
    demonstrate anything new.
"""
import os
import time

from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQError, IQRequestError
from tciqrestclient.reports import REPORT_ALL_SNAPSHOTS_FILTER

#: Same labserver as list_databases_labserver.py -- see that file's
#: docstring for why HTTPS + verify=False are both needed here.
LABSERVER_HOST = "iqteam03.es.cal.viavi.io"
LABSERVER_PORT = 9199
LABSERVER_USE_HTTPS = True
LABSERVER_VERIFY_SSL = False

if LABSERVER_VERIFY_SSL is False:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#: The specific database to report on. Edit this to any real database id
#: on your own labserver (see list_databases_labserver.py to find one).
DATABASE_ID = "edhkcay4a5bctdhy"

#: The exact template a real GUI capture used for THIS database (see the
#: module docstring) -- "Traffic Test Report (tmp)", found by id, not
#: name. Falls back to TEMPLATE_NAME below if this id doesn't exist on
#: your server (e.g. you changed DATABASE_ID to a different database).
TEMPLATE_ID = "1ec10b591a114cd08d36e80c0e85ebac"
TEMPLATE_NAME = "Traffic Test Report"

#: Statuses meaning "still working" -- see generate_report.py's module
#: docstring for the full, real-server-confirmed story on these.
IN_PROGRESS_STATUSES = ("queued", "generating")
POLL_INTERVAL_SEC = 10
MAX_POLLS = 24  # 24 x 5s = 2 minutes


def wait_for_report(iq, report_id):
    """Poll get_report() until its status leaves IN_PROGRESS_STATUSES, or
    MAX_POLLS is reached. A single poll's IQRequestError doesn't abort the
    whole wait -- see generate_report.py's own version of this for why.

    Return:
    (report, timed_out) -- report is the last get_report() response seen
    (None if every single poll failed); timed_out is True if MAX_POLLS
    was reached without a terminal status.
    """
    report = None
    for attempt in range(MAX_POLLS):
        try:
            report = iq.get_report(report_id)
        except IQRequestError as e:
            print("  [poll %d/%d] failed (%s) -- retrying" % (
                attempt + 1, MAX_POLLS, e))
        else:
            status = report.get("status")
            print("  [poll %d/%d] status=%s progress=%s" % (
                attempt + 1, MAX_POLLS, status, report.get("progress")))
            if status not in IN_PROGRESS_STATUSES:
                return report, False
        time.sleep(POLL_INTERVAL_SEC)
    return report, True


def main():
    iq = IQClient(
        host=LABSERVER_HOST, port=LABSERVER_PORT,
        use_https=LABSERVER_USE_HTTPS, verify=LABSERVER_VERIFY_SSL,
        timeout=60)
    print("Connected: base_url=%s" % iq.base_url)

    try:
        db = iq.get_test(DATABASE_ID)
    except IQRequestError as e:
        print("Couldn't find database %r: %s" % (DATABASE_ID, e))
        return
    print("Database: %r (%s), owner=%s" % (
        db.get("name"), DATABASE_ID,
        db.get("metadata", {}).get("test.owner", "?")))

    templates = iq.list_report_templates()
    if not templates:
        print("No report templates available on this server.")
        return
    template = next(
        (t for t in templates if t.get("id") == TEMPLATE_ID), None)
    if not template:
        template = next(
            (t for t in templates if t.get("name") == TEMPLATE_NAME), None)
    if not template:
        print("Neither TEMPLATE_ID nor TEMPLATE_NAME matched anything on "
              "this server -- falling back to the first available "
              "template.")
        template = templates[0]
    print("Using template: %r (%s)" % (
        template.get("name", template["id"]), template["id"]))

    # excluded_sections= -- CONFIRMED real fix for a real report-rendering
    # crash (see generate_report.py's module docstring and HANDOVER.md).
    # find_unsupported_report_sections() finds which sections to exclude
    # generically, without needing to already know a template's layout.
    unsupported = iq.find_unsupported_report_sections(template["id"])
    if unsupported:
        print("Template has %d section(s) not safe to render: %s -- "
              "excluding them." % (len(unsupported), unsupported))
    else:
        print("Every section in this template is safe to render -- "
              "nothing to exclude.")

    print("\nGenerating report...")
    report = iq.generate_report(
        template["id"], title="tciqrestclient labserver example report",
        database_id=DATABASE_ID, database_name=db.get("name"),
        format="pdf", excluded_sections=unsupported,
        snapshot_filter=REPORT_ALL_SNAPSHOTS_FILTER,
        page_layout={"paper_size": "us-letter", "orientation": "landscape"})
    print("Created: id=%s status=%s" % (report["id"], report.get("status")))

    print("\nWaiting for it to finish (up to %ds)..." % (
        POLL_INTERVAL_SEC * MAX_POLLS))
    final_report, timed_out = wait_for_report(iq, report["id"])

    if timed_out:
        last_status = final_report.get("status") if final_report else (
            "unknown -- every poll failed, see above")
        print("\nStill %r after %ds -- giving up rather than downloading "
              "an incomplete file." % (
                  last_status, POLL_INTERVAL_SEC * MAX_POLLS))
        return

    status = final_report.get("status")
    if status not in ("done", "complete", "completed", "success"):
        print("\nReached terminal status %r (not a success status) -- "
              "not attempting to download." % status)
        return

    output_path = "labserver_report.pdf"
    try:
        iq.download_report(final_report["id"], save_as=output_path)
    except IQError as e:
        print("\nDownload failed: %s" % e)
        return
    size = os.path.getsize(output_path)
    print("\nDownloaded %d byte(s) to %s%s" % (
        size, output_path,
        " (0 bytes -- something's wrong even though status looked done)"
        if size == 0 else ""))


if __name__ == "__main__":
    main()
