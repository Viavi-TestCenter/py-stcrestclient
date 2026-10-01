"""Connect to a standalone/on-prem TestCenter IQ deployment -- IQ-PYTHON-002
(Auto-Discovery), the non-AION half. See discover_aion.py for AION
platform deployments instead.

The IQ TCP port `orion-res` listens on is dynamically assigned and can
change between sessions -- this is exactly the "~40 lines of socket
discovery boilerplate" the PRD's problem statement describes. tciqrestclient
collapses all of that into picking one of these options:

  A. base_url=       -- you already know the full address. Skips all
                         discovery outright.
  B. host=/port=      -- you know the address in parts (e.g. host from
                         one config source, port from another).
  C. install_dir=      -- orion-res runs alongside this STC installation
                         (a "local" IQ server); reads
                         <install_dir>/orion-res/etc/orion-res.yaml.
  D. install_dir=      -- orion-res runs on a *different* host (a
                         "remote" IQ server); reads
                         <install_dir>/stcbll.ini's [enhancedResults]
                         section instead. Same argument as C -- tciqrestclient
                         checks stcbll.ini first, falling back to
                         orion-res.yaml (see tciqrestclient/discovery.py).

All of these also work as environment variables / a .env file (see
.env.example) instead of constructor kwargs -- that's how you'd actually
configure a script day to day rather than hardcoding an address in code.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQConfigError, IQConnectionError, IQRequestError


def main():
    # A -- explicit base URL. The fastest, least surprising option for a
    # known deployment; skips host/port composition and file/network
    # discovery entirely.
    iq = IQClient(base_url="http://127.0.0.1:9200")
    print("A) explicit base_url= -> %s" % iq.base_url)

    # B -- explicit host/port, composed into a base URL for you. Useful
    # when the two come from separate config sources (e.g. a hostname
    # from inventory, a port from a job parameter).
    iq = IQClient(host="127.0.0.1", port=9200)
    print("B) explicit host=/port= -> %s" % iq.base_url)

    # C/D -- install_dir= reads whichever of stcbll.ini ([enhancedResults])
    # or orion-res.yaml (service.addr) is present under this directory --
    # see tciqrestclient/discovery.py for the exact lookup order and file formats.
    # Edit this to a real STC install directory to exercise it for real;
    # as written, neither file exists at this path, so it raises
    # IQConnectionError below rather than silently resolving nothing.
    install_dir = r"C:\Program Files\Viavi Solutions\TestCenter"
    try:
        iq = IQClient(install_dir=install_dir)
        print("C/D) install_dir=%r -> %s" % (install_dir, iq.base_url))
    except IQConnectionError as e:
        print("C/D) install_dir=%r -> %s" % (install_dir, e))

    # Discovery has a configurable timeout (default 10s, per IQ-PYTHON-002)
    # -- applies to any network calls discovery itself makes (AION only;
    # file-based discovery here is local disk I/O, not network) as well
    # as every subsequent request this client makes. Pass timeout= to
    # raise or lower it (or TCIQ_TIMEOUT in .env, for the same effect
    # without a code change).
    iq = IQClient(base_url="http://127.0.0.1:9200", timeout=15)
    print("\nConstructed with timeout=15 -- applies to every request this "
          "client makes from here on, including this one:")
    try:
        tests = iq.list_tests()
        print("  %d test(s) found:" % len(tests))
        for t in tests:
            metadata = t.get("metadata", {})
            print("    %s  %-14s owner=%-35s rows=%s" % (
                t["id"], t["name"], metadata.get("test.owner", "-"),
                metadata.get("count", "-")))
    except IQRequestError as e:
        print("  (no server actually listening at that address here: %s)" % e)

    # What you'll actually use day to day: nothing hardcoded, everything
    # from .env / the environment (TCIQ_BASE_URL, TCIQ_HOST/TCIQ_PORT, or
    # TCIQ_INSTALL_DIR -- see .env.example).
    print("\nYour actual .env/environment configuration:")
    try:
        iq = IQClient()
        print("  resolved base_url: %s" % iq.base_url)
    except IQConfigError as e:
        print("  could not resolve an address from .env/environment: %s" % e)
        print("  copy .env.example to .env and fill in at least one "
              "address option.")


if __name__ == "__main__":
    main()
