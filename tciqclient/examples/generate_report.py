"""Generate a report from an existing template and download it once it
has actually finished rendering -- the confirmed-working pattern from
generate_report_labserver.py, adapted for a local/standalone orion-res
connection (see that file for the labserver version; the two differ
only in how IQClient() connects and which database/template they use).

format= is lowercase ('pdf', not 'PDF') and title= is required --
CONFIRMED against a real server 2026-09-03 (see HANDOVER.md section 9):
the uppercase form 400s with "unknown report format", and an omitted
title 400s with "missing report title".

Report generation is asynchronous: a freshly created report's status
starts as "queued", not immediately ready, and orion-res's own report
worker has been observed leaving a report stuck "queued"/"generating"
indefinitely instead of ever reaching a terminal status (see
HANDOVER.md section 9). This script never downloads until
wait_for_report() has confirmed a real success status, so it either
produces a genuine, complete file or explains clearly why it didn't --
unlike generate_report(output_path=...)'s immediate, unwaited download,
it never writes a truncated/0-byte report.pdf.

excluded_sections= (via find_unsupported_report_sections()) skips any
section whose view isn't confirmed safe for report rendering -- at
least one real chart-type view_type is known to crash the
report-rendering frontend if included.
"""
import os
import time

from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQError, IQRequestError
from tciqrestclient.reports import REPORT_ALL_SNAPSHOTS_FILTER

#: Report template to use, by exact name. A server can have more than one
#: template with a similar name (e.g. "Traffic Test Report (tmp)"
#: duplicates alongside this one) -- match the exact name, not a
#: substring, so this doesn't silently pick a "(tmp)" one instead.
TEMPLATE_NAME = "Traffic Test Report"

#: Statuses meaning "still working". Anything else is treated as
#: terminal, whether that's a real success status or a real failure/
#: cancellation like "canceled".
IN_PROGRESS_STATUSES = ("queued", "generating")

#: Statuses meaning the report actually finished successfully -- only one
#: of these is safe to download. A report can reach a terminal status
#: that ISN'T one of these (e.g. "canceled"), which is exactly the case
#: the old immediate-download approach could silently turn into a 0-byte
#: file instead of a clear message.
SUCCESS_STATUSES = ("done", "complete", "completed", "success")

#: How long wait_for_report() polls before giving up -- 10s x 24 = 4
#: minutes, matching generate_report_labserver.py's own patient timeout.
#: A local report queue has been observed still busy well past the
#: older, shorter windows this file used to use.
POLL_INTERVAL_SEC = 10
MAX_POLLS = 24


def wait_for_report(iq, report_id):
    """Poll get_report() until its status leaves IN_PROGRESS_STATUSES, or
    MAX_POLLS is reached.

    A single poll's IQRequestError (e.g. a transient connection drop)
    doesn't abort the whole wait -- it's logged and counted as one of
    the MAX_POLLS attempts, same as an in-progress status would be,
    rather than propagating and losing everything already waited for.

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
    iq = IQClient()

    my_tests = iq.list_tests(owner="owner-name")
    if not my_tests:
        print("No tests found for that owner.")
        return
    test = my_tests[0]
    iq.use_test(test["id"])
    print("Test: %r (%s)" % (test["name"], test["id"]))

    templates = iq.list_report_templates()
    if not templates:
        print("No report templates available on this server.")
        return
    template = next(
        (t for t in templates if t.get("name") == TEMPLATE_NAME), None)
    if not template:
        print("No template named %r on this server -- edit TEMPLATE_NAME "
              "to a real one (see the names list_report_templates() "
              "returns). Falling back to the first available template."
              % TEMPLATE_NAME)
        template = templates[0]
    print("Using template: %r (%s)" % (
        template.get("name", template["id"]), template["id"]))

    unsupported = iq.find_unsupported_report_sections(template["id"])
    if unsupported:
        print("Template has %d section(s) not safe to render: %s -- "
              "excluding them." % (len(unsupported), unsupported))
    else:
        print("Every section in this template is safe to render -- "
              "nothing to exclude.")

    print("\nGenerating report...")
    report = iq.generate_report(
        template["id"], title="tciqrestclient example report",
        database_name=test["name"], format="pdf",
        excluded_sections=unsupported,
        snapshot_filter=REPORT_ALL_SNAPSHOTS_FILTER)
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
    if status not in SUCCESS_STATUSES:
        print("\nReached terminal status %r (not a success status) -- "
              "not attempting to download." % status)
        return

    output_path = "report.pdf"
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
