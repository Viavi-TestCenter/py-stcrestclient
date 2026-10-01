"""Connect to an AION-hosted TestCenter IQ deployment -- IQ-PYTHON-002
(Auto-Discovery), the AION half. See discover_local.py for a standalone/
on-prem TestCenter deployment instead -- this is the other one PRD Goal
#3 ("Support both standalone TestCenter and AION deployments
transparently") calls out.

Unlike file-based discovery, AION discovery is a real network handshake:
  1. Authenticate to AION's IAM (username/password -> bearer access
     token).
  2. Query /api/inv/product-instances for every product instance AION
     knows about.
  3. Find the one whose ports include an entry named "iq" (or whatever
     aion_port_name= says instead), and extract its host/port.
The same access token is then injected as `Authorization: Bearer` on
every subsequent request this client makes -- no separate login step
needed for actual queries afterwards.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQConfigError, IQConnectionError

# Edit these to real AION credentials to exercise this for real -- as
# written, aion.example.com doesn't resolve, so this raises
# IQConnectionError below rather than silently succeeding. Never commit
# real credentials here -- use environment variables/.env instead (see
# the bottom of main() below) for anything beyond a one-off local test.
AION_URL = "https://aion.example.com"
AION_USERNAME = "username"
AION_PASSWORD = "password"


def main():
    print("Basic AION discovery (aion_url=/aion_username=/aion_password=):")
    try:
        iq = IQClient(
            aion_url=AION_URL,
            aion_username=AION_USERNAME,
            aion_password=AION_PASSWORD,
        )
        print("  resolved base_url: %s" % iq.base_url)
    except IQConnectionError as e:
        print("  AION discovery failed: %s" % e)

    # aion_node_name= -- restrict discovery to one specific node when
    # AION hosts more than one product instance (useful in a shared lab
    # where several TestCenter IQ instances run across different nodes).
    print("\nRestricted to a specific node (aion_node_name=):")
    try:
        iq = IQClient(
            aion_url=AION_URL, aion_username=AION_USERNAME,
            aion_password=AION_PASSWORD, aion_node_name="10.109.143.126",
        )
        print("  resolved base_url: %s" % iq.base_url)
    except IQConnectionError as e:
        print("  AION discovery failed: %s" % e)

    # aion_port_name= -- override if your AION deployment labels the
    # orion-res port entry under a different name in product-instances
    # (default: "iq" -- confirmed against a real AION org 2026-09-08).
    print("\nCustom port label (aion_port_name=):")
    try:
        iq = IQClient(
            aion_url=AION_URL, aion_username=AION_USERNAME,
            aion_password=AION_PASSWORD, aion_port_name="iq-results",
        )
        print("  resolved base_url: %s" % iq.base_url)
    except IQConnectionError as e:
        print("  AION discovery failed: %s" % e)

    # aion_ca_cert= -- path to a CA certificate, only needed if AION's
    # own platform HTTPS endpoint uses a self-signed/internal cert.
    # print("\nWith a custom CA cert (aion_ca_cert=):")
    # iq = IQClient(
    #     aion_url=AION_URL, aion_username=AION_USERNAME,
    #     aion_password=AION_PASSWORD, aion_ca_cert="/path/to/aion_ca.pem",
    # )

    # A deliberately wrong password -- confirm this fails loudly
    # (IQConnectionError) rather than silently falling back to some
    # stale/cached address.
    print("\nWrong credentials (should fail, not silently succeed):")
    try:
        IQClient(
            aion_url=AION_URL, aion_username=AION_USERNAME,
            aion_password="definitely-wrong",
        )
        print("  (unexpected: this should have raised IQConnectionError)")
    except IQConnectionError as e:
        print("  correctly failed: %s" % e)

    # What you'll actually use day to day: nothing hardcoded, everything
    # from .env / the environment (TCIQ_AION_URL, TCIQ_AION_USERNAME,
    # TCIQ_AION_PASSWORD, and optionally TCIQ_AION_NODE_NAME/
    # TCIQ_AION_PORT_NAME/TCIQ_AION_CA_CERT -- see .env.example).
    print("\nYour actual .env/environment configuration:")
    try:
        iq = IQClient()
        print("  resolved base_url: %s" % iq.base_url)
    except IQConfigError as e:
        print("  could not resolve an address from .env/environment: %s" % e)
    except IQConnectionError as e:
        print("  AION discovery failed: %s" % e)


if __name__ == "__main__":
    main()
