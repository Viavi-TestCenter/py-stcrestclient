"""Generate a report from an existing template and download it to disk.

Closes the automation loop: run a test, then produce a report from code
without touching the GUI.

format= is lowercase ('pdf', not 'PDF') -- CONFIRMED against a real
server 2026-09-03 (see HANDOVER.md section 9); the uppercase form 400s
with "unknown report format". title= is also required -- confirmed the
same day; omitting it 400s with "missing report title".

snapshot_filter= picks what data the report covers -- CONFIRMED against
two real GUI-captured requests 2026-09-11 (see tciqrestclient/reports.py's module
docstring): the GUI itself always sends a list of filter flags in
parameters.test_snapshot_filter, not a single "eot vs. live" toggle.
REPORT_ALL_SNAPSHOTS_FILTER ("is_all_included") alone is a snapshot-only
report -- what the first real capture showed; adding
REPORT_LIVE_INCLUDED_FILTER ("is_live_included") to that same list is
what a real "live and snapshot" report generation request looked like in
the second capture.

*** KNOWN GAP, NOT YET FIXED (see HANDOVER.md section 9): report
*** generation is asynchronous on the real server (a freshly created
*** report's status is "queued", not immediately ready) -- but
*** generate_report(output_path=...) downloads immediately after
*** creating it, with no wait/poll for completion. Confirmed against a
*** real server: this can produce a 0-byte file. Until that's fixed,
*** either don't pass output_path= here (call get_report(report["id"])
*** yourself in a loop until its status is a completed/terminal one,
*** then download_report()), or treat this example's downloaded file as
*** unreliable and check its size before trusting it. The
*** snapshot_filter= demonstrations below deliberately skip
*** output_path= for exactly this reason -- they just show the created
*** report object (status "queued") rather than a possibly-truncated
*** download.
***
*** wait_for_report() below is that recommended poll-then-download
*** pattern -- CONFIRMED real statuses seen along the way: "queued",
*** "generating" (both still in progress -- keep polling), and
*** "canceled" (terminal, but not success -- confirmed 2026-09-11 when
*** a real server restarted mid-generation and swept the in-flight job
*** rather than resuming it).

*** SECOND, SEPARATE BUG -- CONFIRMED ROOT-CAUSED AND FIXED HERE
*** 2026-09-16: for a long stretch every report created against this
*** environment either sat "generating" forever or crashed outright.
*** Root-caused (not guessed) against the real orion-res and
*** magellan-frontend source (both read-only -- nothing there was
*** changed; see HANDOVER.md for the full trace) down to two
*** independent bugs:
***   1. A Go concurrency bug in orion-res's report worker
***      (renderingState()) that can abandon its own completion signal,
***      leaking the render goroutine and leaving the report stuck
***      "generating" instead of ever reaching an error/done status.
***   2. A real, 100%-reproducible TypeError in the report-rendering
***      frontend JS when a report template includes a chart-type
***      section (e.g. an x_y_chart view like "Port Frame Rate Chart")
***      -- confirmed live via Chrome DevTools Protocol (a debugger
***      breakpoint on the uncaught exception, not just log-watching).
*** Both bugs live in orion-res/magellan-frontend, which this project
*** was explicitly told not to touch. The fix below is entirely
*** client-side: the real POST /reports body supports a
*** parameters.excluded_sections field (a JSON-encoded list of a
*** template's own section names) that skips a section during
*** rendering. Excluding just the chart section from the real
*** "Traffic Test Report" template avoided bug #2 entirely and
*** produced a genuine, complete, correctly-paginated report --
*** confirmed by inspecting the rendered report's DOM directly (4 real
*** pages, real column headers and row data). find_unsupported_
*** report_sections() below finds which sections to exclude
*** generically (by checking each section's view_type against
*** REPORT_SAFE_VIEW_TYPES in tciqrestclient/reports.py), so this doesn't
*** require already knowing a template's layout.
*** No report has ever been observed reaching an actual completed/
*** success status in this environment even with chart sections
*** excluded, likely due to bug #1 above (still unfixed, since it's on
*** the Go side) -- wait_for_report() times out and gives up after
*** MAX_POLLS attempts rather than waiting forever, since "still
*** generating" past that point has, in practice, meant "never going
*** to finish here" rather than "nearly done" -- raise MAX_POLLS
*** yourself against a server where reports genuinely complete.
"""
import os
import time

from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError
from tciqrestclient.reports import REPORT_ALL_SNAPSHOTS_FILTER, REPORT_LIVE_INCLUDED_FILTER

#: Report template to use, by exact name. "Traffic Test Report" is the
#: general-purpose template both real captures this file's
#: snapshot_filter= behavior is based on actually used -- CONFIRMED
#: 2026-09-11. A server can have more than one template with a similar
#: name (e.g. several "Traffic Test Report (tmp)" duplicates alongside
#: this one) -- match the exact name, not a substring, so this doesn't
#: silently pick a "(tmp)" one instead.
TEMPLATE_NAME = "Traffic Test Report"

#: Statuses meaning "still working" -- CONFIRMED real values (see module
#: docstring). Anything else is treated as terminal, whether that's an
#: eventual success status this environment has just never produced, or
#: a real failure/cancellation like "canceled".
IN_PROGRESS_STATUSES = ("queued", "generating")

#: How long wait_for_report() polls before giving up -- 12 x 5s = 60s,
#: matching what's actually been observed: a report here either leaves
#: "queued"/"generating" within the first few polls (if it's ever going
#: to) or never does at all.
POLL_INTERVAL_SEC = 5
MAX_POLLS = 12


def wait_for_report(iq, report_id):
    """Poll get_report() until its status leaves IN_PROGRESS_STATUSES,
    or MAX_POLLS is reached. This is the fix for the KNOWN GAP in the
    module docstring above -- use this (or your own version of it)
    instead of generate_report(output_path=...)'s immediate, unwaited
    download for anything you actually need the file to be complete.

    A single poll's IQRequestError (e.g. a transient connection drop --
    CONFIRMED happening mid-poll against a real server twice in one
    session, 2026-09-11, each time recovering within a few seconds on
    its own) doesn't abort the whole wait -- it's logged and counted as
    one of the MAX_POLLS attempts, same as an in-progress status would
    be, rather than propagating and losing everything already waited
    for. A poll failing every single time still exhausts MAX_POLLS and
    returns a timeout, same as if the report just never finished.

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

    my_tests = iq.list_tests(owner="bha83166")
    if not my_tests:
        print("No tests found for that owner.")
        return
    test = my_tests[0]
    iq.use_test(test["id"])

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
    print("Generating '%s' report from template %r ..." % (
        template.get("name", template["id"]), template["id"]))

    # excluded_sections= -- the confirmed fix described in the module
    # docstring above (SECOND, SEPARATE BUG). find_unsupported_report_
    # sections() inspects the template's own sections/views and returns
    # which ones aren't safe to render (chart-type views like "Port
    # Frame Rate Chart"); pass that straight to generate_report()
    # throughout this example. Against the real "Traffic Test Report"
    # template this returns ["section_2"] and the resulting report
    # renders completely instead of crashing the report-rendering
    # frontend.
    unsupported = iq.find_unsupported_report_sections(template["id"])
    if unsupported:
        print("Template has %d section(s) not safe to render: %s -- "
              "excluding them from every report below." % (
                  len(unsupported), unsupported))
    else:
        print("Every section in this template is safe to render -- "
              "nothing to exclude.")

    output_path = "report.pdf"
    iq.generate_report(
        template["id"], title="tciqrestclient example report", format="pdf",
        database_name=test["name"], output_path=output_path,
        excluded_sections=unsupported)
    print("Saved to %s" % output_path)

    # snapshot_filter= -- explicit snapshot-only report, matching the
    # first real capture (the GUI's own default when no specific
    # snapshot is chosen).
    report = iq.generate_report(
        template["id"], title="tciqrestclient example -- snapshot only",
        database_name=test["name"], excluded_sections=unsupported,
        snapshot_filter=REPORT_ALL_SNAPSHOTS_FILTER)
    print("\nSnapshot-only report created: id=%s status=%s" % (
        report["id"], report.get("status")))

    # Combine both flags for a "live and snapshot" report -- matching
    # the second real capture. Only meaningful while a test is actually
    # running; harmless either way (the flag just has nothing live to
    # add if the test has already finished).
    report = iq.generate_report(
        template["id"], title="tciqrestclient example -- live and snapshot",
        database_name=test["name"], excluded_sections=unsupported,
        snapshot_filter=[REPORT_ALL_SNAPSHOTS_FILTER,
                         REPORT_LIVE_INCLUDED_FILTER])
    print("Live+snapshot report created: id=%s status=%s" % (
        report["id"], report.get("status")))

    # The recommended fix for the KNOWN GAP above: create the report
    # with no output_path= (so nothing gets downloaded prematurely),
    # then poll with wait_for_report() and only download once it's
    # actually left "queued"/"generating".
    print("\nWaiting for a report to finish (up to %ds) before "
          "downloading it..." % (POLL_INTERVAL_SEC * MAX_POLLS))
    report = iq.generate_report(
        template["id"], title="tciqrestclient example -- wait then download",
        database_name=test["name"], excluded_sections=unsupported)
    final_report, timed_out = wait_for_report(iq, report["id"])
    if timed_out:
        last_status = final_report.get("status") if final_report else (
            "unknown -- every poll failed, see above")
        print("  Still %r after %ds -- giving up rather than downloading "
              "an incomplete file (see the module docstring: no report "
              "has ever been observed completing in this environment)."
              % (last_status, POLL_INTERVAL_SEC * MAX_POLLS))
    else:
        waited_path = "report_waited.pdf"
        iq.download_report(final_report["id"], save_as=waited_path)
        size = os.path.getsize(waited_path)
        print("  Reached terminal status %r; downloaded %d byte(s) to %s%s"
              % (final_report.get("status"), size, waited_path,
                 " (0 bytes -- terminal but not a success status, e.g. "
                 "\"canceled\")" if size == 0 else ""))


if __name__ == "__main__":
    main()
