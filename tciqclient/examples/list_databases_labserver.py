"""List every database (test) on a lab-hosted TestCenter IQ deployment
("labserver") -- a direct, no-discovery connection: you already know the
exact host and port, so there's no install-dir file to read (like
discover_local.py) and no AION login/instance-lookup (like
discover_aion.py). Just host + port + which scheme it speaks.

CONFIRMED against a real labserver, iqteam03.es.cal.viavi.io:9199 -- and
its own scheme CHANGED between two checks in the same week: on
2026-09-22 (morning) it was plain HTTP, no redirect. By 2026-09-22
(later the same day) an nginx reverse proxy had been put in front of it
that 307-redirects *all* HTTP requests on that same host:port to HTTPS,
and that HTTPS endpoint uses a self-signed certificate. This isn't a
one-time fluke to special-case -- a lab's own TLS setup is real
infrastructure someone else administers and can change out from under
you, and self-signed certs are common for internal-only lab gear. Two
real consequences, both handled below:
  1. `requests` (which tciqrestclient uses internally) follows redirects by
     default, so even the *plain HTTP* request above transparently
     became an HTTPS one -- the SSLError you'd see either way names the
     real problem (certificate verification), not "HTTP doesn't work".
  2. A self-signed cert fails normal verification -- IQClient's own
     verify= parameter (added for exactly this real case) handles it:
     False skips verification entirely (only for a deployment you
     already trust on your own network), or pass a CA bundle file path
     instead if your lab issues certs from an internal CA.

Configure via LABSERVER_HOST/LABSERVER_PORT/LABSERVER_USE_HTTPS/
LABSERVER_VERIFY_SSL below, or TCIQ_HOST/TCIQ_PORT (+ TCIQ_VERIFY_SSL for
verify=) in the environment or a .env file -- see .env.example.
use_https= itself still has no environment-variable equivalent.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQRequestError

#: A labserver's address is just host + a fixed, well-known port -- no
#: install directory, no AION account. Edit these to point at your own
#: deployment, or leave them and set TCIQ_HOST/TCIQ_PORT instead (see
#: the module docstring).
LABSERVER_HOST = "iqteam03.es.cal.viavi.io"
LABSERVER_PORT = 9199

#: CONFIRMED True (HTTPS) for the labserver above as of the second check
#: in the module docstring -- flip to False if your own labserver
#: doesn't redirect to HTTPS. If you get an SSLError on WRONG_VERSION_
#: NUMBER specifically, that means the opposite: the server isn't
#: listening for TLS at all, so flip this to False instead.
LABSERVER_USE_HTTPS = True

#: CONFIRMED needed for the labserver above -- its HTTPS certificate is
#: self-signed, which fails normal verification. False (skip
#: verification entirely) is only appropriate for a lab server you
#: already trust on your own network -- never for anything reachable
#: over the open internet. Set this to a CA bundle file path instead of
#: True/False if your lab issues certs from an internal CA you have the
#: root cert for (a real alternative to disabling verification
#: entirely). True (the library default) verifies normally.
LABSERVER_VERIFY_SSL = False

if LABSERVER_VERIFY_SSL is False:
    # Silence the per-request "Unverified HTTPS request" warning -- this
    # example already made that choice deliberately above, not by accident.
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main():
    iq = IQClient(
        host=LABSERVER_HOST, port=LABSERVER_PORT,
        use_https=LABSERVER_USE_HTTPS, verify=LABSERVER_VERIFY_SSL,
        timeout=30)
    print("Connected: base_url=%s\n" % iq.base_url)

    try:
        databases = iq.list_tests()
    except IQRequestError as e:
        print("Couldn't reach %s: %s" % (iq.base_url, e))
        print("Double-check LABSERVER_HOST/LABSERVER_PORT, and try "
              "flipping LABSERVER_USE_HTTPS if this looks like a "
              "TLS/SSL error.")
        return

    if not databases:
        print("No databases found on this labserver.")
        return

    print("%d database(s):" % len(databases))
    for db in databases:
        meta = db.get("metadata") or {}
        print("  %-20s %-32s owner=%-30s running=%s" % (
            db["id"],
            db["name"],
            meta.get("test.owner", "?"),
            meta.get("test.running", "?"),
        ))


if __name__ == "__main__":
    main()
