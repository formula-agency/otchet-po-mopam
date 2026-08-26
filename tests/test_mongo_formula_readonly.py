from __future__ import annotations

import unittest
from typing import Any

from scripts.mongo_formula_readonly import (
    FORMULA_TENANT_TAG,
    FormulaMongoError,
    ReadOnlyCollection,
    _role_scope_violations,
    _write_capabilities,
    override_mongo_endpoint,
    resolve_formula_tenant,
)


class EndpointOverrideTests(unittest.TestCase):
    def test_replaces_only_host_and_keeps_credentials_and_options(self) -> None:
        uri = "mongodb://reader:secret@mongo.internal:27017/mongo_calls?authSource=admin"

        rewritten = override_mongo_endpoint(uri, "127.0.0.1:27018")

        self.assertEqual(
            rewritten,
            "mongodb://reader:secret@127.0.0.1:27018/mongo_calls?authSource=admin",
        )

    def test_leaves_uri_unchanged_without_override(self) -> None:
        uri = "mongodb://mongo.internal:27017/mongo_calls"

        self.assertEqual(override_mongo_endpoint(uri, ""), uri)


class FakeCustomers:
    def __init__(self, document: dict[str, Any] | None) -> None:
        self.document = document
        self.query: dict[str, Any] | None = None

    def find_one(self, query: dict[str, Any], projection: dict[str, Any]) -> dict[str, Any] | None:
        self.query = query
        return self.document


class FakeCollection:
    name = "calls"

    def __init__(self) -> None:
        self.pipeline: Any = None

    def aggregate(self, pipeline: Any, **kwargs: Any) -> list[Any]:
        self.pipeline = pipeline
        return []


class FormulaTenantResolutionTests(unittest.TestCase):
    def test_query_is_pinned_to_active_formula_tenant(self) -> None:
        customers = FakeCustomers(
            {
                "tenant_tag": "formula",
                "display_name": "Формула",
                "db_connection": {
                    "connection_string": "mongodb://hidden",
                    "database_name": "formula_db",
                },
                "data_sources": {"calls_collection": "calls"},
            }
        )

        tenant = resolve_formula_tenant(customers)  # type: ignore[arg-type]

        self.assertEqual(
            customers.query,
            {"tenant_tag": FORMULA_TENANT_TAG, "is_active": True},
        )
        self.assertEqual(tenant.database_name, "formula_db")
        self.assertEqual(tenant.data_sources["calls_collection"], "calls")

    def test_rejects_any_non_formula_document(self) -> None:
        customers = FakeCustomers(
            {
                "tenant_tag": "another-tenant",
                "db_connection": {
                    "connection_string": "mongodb://hidden",
                    "database_name": "another_db",
                },
            }
        )

        with self.assertRaises(FormulaMongoError):
            resolve_formula_tenant(customers)  # type: ignore[arg-type]


class ReadOnlyCollectionTests(unittest.TestCase):
    def test_allows_read_only_aggregation(self) -> None:
        collection = FakeCollection()
        reader = ReadOnlyCollection(collection)  # type: ignore[arg-type]
        pipeline = [{"$match": {"user_name": "Иван"}}, {"$count": "calls"}]

        self.assertEqual(reader.aggregate(pipeline), [])
        self.assertEqual(collection.pipeline, pipeline)

    def test_blocks_out_and_merge_stages(self) -> None:
        reader = ReadOnlyCollection(FakeCollection())  # type: ignore[arg-type]

        for stage in ({"$out": "copy"}, {"$merge": "summary"}):
            with self.subTest(stage=stage):
                with self.assertRaises(FormulaMongoError):
                    reader.aggregate([stage])


class CapabilityTests(unittest.TestCase):
    def test_detects_server_side_write_permissions(self) -> None:
        status = {
            "authInfo": {
                "authenticatedUserRoles": [{"role": "readWrite", "db": "formula"}],
                "authenticatedUserPrivileges": [
                    {"resource": {"db": "formula", "collection": ""}, "actions": ["find", "insert"]}
                ],
            }
        }

        roles, actions = _write_capabilities(status)

        self.assertEqual(roles, {"readWrite"})
        self.assertEqual(actions, {"insert"})

    def test_accepts_read_role_scoped_to_formula_database(self) -> None:
        status = {
            "authInfo": {
                "authenticatedUserRoles": [{"role": "read", "db": "mongo_calls"}],
            }
        }

        self.assertEqual(_role_scope_violations(status, "mongo_calls"), set())

    def test_rejects_read_role_on_another_database(self) -> None:
        status = {
            "authInfo": {
                "authenticatedUserRoles": [{"role": "read", "db": "another_tenant"}],
            }
        }

        self.assertEqual(
            _role_scope_violations(status, "mongo_calls"),
            {"another_tenant:read"},
        )


if __name__ == "__main__":
    unittest.main()
