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
