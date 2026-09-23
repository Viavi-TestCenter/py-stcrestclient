"""List every database (test) on an AION-hosted TestCenter IQ deployment.

Same idea as list_tests_by_owner.py, but connects via AION discovery
specifically (see discover_aion.py for that half in isolation) and lists
every database rather than filtering to one owner.

Configure via TCIQ_AION_URL/TCIQ_AION_USERNAME/TCIQ_AION_PASSWORD (and
optionally TCIQ_AION_NODE_NAME/TCIQ_AION_PORT_NAME) in the environment or
a .env file -- see .env.example. Nothing is hardcoded here.

*** A real AION organization can have many candidate orion-res instances
*** (product-instances entries whose ports include one named "iq", the
*** default aion_port_name=) -- discovery with no aion_node_name= just
*** picks whichever comes first, which is not necessarily the instance
*** that actually has the data you're after. If the list below comes
*** back empty, that's a strong sign discovery landed on the wrong
*** instance, not that there are no databases anywhere -- try setting
*** TCIQ_AION_NODE_NAME to a specific node (see discover_aion.py), or ask
*** whoever administers your AION org which node/instance to use.
"""
from tciqrestclient import IQClient
from tciqrestclient.exceptions import IQConfigError, IQConnectionError


def main():
    try:
        iq = IQClient(timeout=60)
    except IQConfigError as e:
        print("Not configured for AION: %s" % e)
        print("Set TCIQ_AION_URL/TCIQ_AION_USERNAME/TCIQ_AION_PASSWORD "
              "(see .env.example) and try again.")
        return
    except IQConnectionError as e:
        print("AION discovery failed: %s" % e)
        return

    print("Connected: base_url=%s\n" % iq.base_url)

    databases = iq.list_tests()
    if not databases:
        print("No databases found on this instance -- see the module "
              "docstring above: this usually means AION discovery landed "
              "on the wrong instance, not that the deployment is empty.")
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
