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
