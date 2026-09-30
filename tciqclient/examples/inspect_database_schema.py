"""Discover a test's schema programmatically -- IQ-PYTHON-006 (Database
Metadata Retrieval): what tables and fields a database has, without
reading internal documentation or reverse-engineering the GUI.

get_database_schema()/list_table_names()/list_fields() all call the same
GET /databases/<id>?detail=full endpoint under the hood -- list_table_
names()/list_fields() just extract the relevant part of that response for
you. Useful for building a query dynamically (e.g. deciding which
columns to project) without hardcoding a view name the way
run_view_query.py does.

Response shape CONFIRMED against a real server 2026-09-03 (see
HANDOVER.md section 9): each table descriptor has 'name' and 'kind'
('result_set' or 'dimension_set'); each field descriptor has 'name' and,
when reported, 'type', 'display_name', 'description', and 'unit'.

Also covers three thin convenience methods added on top of the above:
get_database_tables() (an alias for list_table_names(), under the name
requested in review feedback), get_table_schema(table_name) (one table's
own descriptor, instead of every table's), and get_database_summary()
(just the row-count/storage-size "summary" dict -- see
bulk_cleanup_databases.py for what that's actually useful for).
"""
from tciqrestclient import IQClient


def main():
    iq = IQClient(timeout=120)

    my_tests = iq.list_tests(owner="test-owner")
    if not my_tests:
        print("No tests found for that owner.")
        return
    test = my_tests[0]
    print("Inspecting schema for: %s (%s)" % (test["name"], test["id"]))

    tables = iq.list_table_names(database_id=test["id"])
    if not tables:
        print(
            "\nNo tables reported -- this database genuinely has none. "
            "Falling back to the raw schema record:")
        schema = iq.get_database_schema(database_id=test["id"])
        print(" ", schema)
        return

    print("\nTables:")
    for table in tables:
        print("  %s (%s)" % (table.get("name", "?"), table.get("kind", "?")))

    # Fields across all tables, then narrowed to just the first table --
    # list_fields(table_name=None) returns everything; pass a specific
    # table's name to scope it.
    all_fields = iq.list_fields(database_id=test["id"])
    print("\n%d field(s) total across all tables. First 10:" % len(all_fields))
    for field in all_fields[:10]:
        print("  %s (%s)" % (field.get("name", field), field.get("type", "?")))

    first_table_name = tables[0].get("name")
    if first_table_name:
        scoped_fields = iq.list_fields(
            table_name=first_table_name, database_id=test["id"])
        print("\n%d field(s) in table %r:" % (
            len(scoped_fields), first_table_name))
        for field in scoped_fields[:10]:
            print("  %s (%s)" % (field.get("name", field), field.get("type", "?")))

        # get_table_schema() -- the one table's own descriptor (kind +
        # facts/attributes), instead of list_table_names()'s full list.
        one_table = iq.get_table_schema(
            first_table_name, database_id=test["id"])
        print("\nget_table_schema(%r) -- kind=%s, %d field(s):" % (
            first_table_name, one_table.get("kind", "?"),
            len(one_table.get("facts") or one_table.get("attributes") or [])))

    # get_database_tables() -- same data as list_table_names() above,
    # under the name requested in review feedback.
    assert iq.get_database_tables(database_id=test["id"]) == tables

    # get_database_summary() -- row count and storage size, without the
    # rest of the schema. See bulk_cleanup_databases.py for what this is
    # used for.
    summary = iq.get_database_summary(database_id=test["id"])
    print("\nSummary: %s" % summary)


if __name__ == "__main__":
    main()
