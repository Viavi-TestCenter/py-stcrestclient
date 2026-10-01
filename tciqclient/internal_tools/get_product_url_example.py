"""Get a deployed TestCenter+ product instance's URL from AION/Temeva.

Companion to aion_operations_testcenterplus.py -- that file's deploy path
(-d/--deploy) already does this inline, right after creating a brand-new
instance (deploy_prod_instance() calls get_inst_url() on the instance it
just created). This script covers the other, more common case: you
already have a running instance -- deployed by you earlier, by someone
else, or by a CI job -- and just need its URL, with no version
resolution/download/deploy/poll cycle needed.

A product instance's `ports` list carries every service it exposes (iq,
stcapi, api-navigator, telemeter-api, arangodb1-5, ...) as separate
host:port entries. 'testcenterplus' is the one to use: it's TestCenter
Plus's own REST API, and it also proxies TestCenter IQ's results API
under /api/res/* on that same host:port -- confirmed against a real AION
org (see HANDOVER.md).

Configure via TEMEVA_EMAIL/TEMEVA_PASSWORD/TEMEVA_URL (and optionally
TEMEVA_SUBDOMAIN/TEMEVA_INSTANCE_ID) in the environment -- nothing is
hardcoded here.
"""
import os

from utils.Temeva import Temeva

#: Instance to look up, e.g. from deployed_instance_info.txt's
#: INSTANCE_ID= line, or from one of the rows this script itself prints
#: when no id is given. Leave unset to list every TestCenter+ instance's
#: URL instead of just one.
TARGET_INSTANCE_ID = os.environ.get("TEMEVA_INSTANCE_ID") or None


def get_inst_url(inst):
    """host:port (scheme stripped) of an instance's 'testcenterplus'
    port, or None if it doesn't have one -- e.g. an older iq/stcapi-only
    instance with no testcenterplus port at all. (The version of this in
    aion_operations_testcenterplus.py raises UnboundLocalError instead in
    that case -- returning None here so callers can report it cleanly.)
    """
    for port in inst.get("ports", []):
        if port.get("name") == "testcenterplus":
            url = port.get("http", {}).get("url")
            if url:
                return url.split("/")[-1]
    return None


def main():
    temeva = Temeva(
        "username",
        "password",
        os.environ.get("TEMEVA_SUBDOMAIN", "spirent"),
        base_url=os.environ["TEMEVA_URL"],
    )

    if TARGET_INSTANCE_ID:
        inst = temeva.get_product_instance(inst_id=TARGET_INSTANCE_ID)
        host_port = get_inst_url(inst)
        if not host_port:
            print("Instance %s has no 'testcenterplus' port." %
                  TARGET_INSTANCE_ID)
            return
        print("Instance %s -> http://%s" % (TARGET_INSTANCE_ID, host_port))
        return

    # No specific instance given -- list every TestCenter+ instance's URL.
    insts = temeva.list_product_instances()
    found = False
    for inst in insts:
        if inst.get("product", {}).get("name") != "TestCenter+":
            continue
        found = True
        host_port = get_inst_url(inst)
        location = inst.get("location", {}).get("name")
        if host_port:
            print("%-36s %-24s http://%s" % (inst["id"], location, host_port))
        else:
            print("%-36s %-24s (no 'testcenterplus' port)" % (
                inst["id"], location))

    if not found:
        print("No TestCenter+ product instances found.")


if __name__ == "__main__":
    main()
