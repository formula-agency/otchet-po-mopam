from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.read_preferences import SecondaryPreferred


FORMULA_TENANT_TAG = "formula"
DEFAULT_CONFIG_DATABASE = "mongo_calls"
DEFAULT_CONFIG_COLLECTION = "customers"
DEFAULT_TIMEOUT_MS = 10_000
WRITE_PIPELINE_STAGES = {"$merge", "$out"}
WRITE_ROLES = {
    "dbAdmin",
    "dbAdminAnyDatabase",
    "dbOwner",
    "hostManager",
    "readWrite",
    "readWriteAnyDatabase",
    "restore",
    "root",
    "userAdmin",
    "userAdminAnyDatabase",
}
WRITE_ACTIONS = {
    "bypassDocumentValidation",
    "collMod",
    "compact",
    "convertToCapped",
    "createCollection",
    "createIndex",
    "createRole",
    "createUser",
    "dropCollection",
    "dropDatabase",
    "dropIndex",
    "dropRole",
    "dropUser",
    "enableSharding",
    "grantPrivilegesToRole",
    "grantRole",
    "insert",
    "moveChunk",
    "remove",
    "renameCollectionSameDB",
    "revokePrivilegesFromRole",
    "revokeRole",
    "update",
    "updateRole",
    "updateUser",
}


class FormulaMongoError(RuntimeError):
    """A safe, non-secret-bearing MongoDB access error."""


@dataclass(frozen=True)
class FormulaTenantConfig:
    database_name: str
    connection_string: str = field(repr=False)
    display_name: str = "Формула"
    data_sources: Mapping[str, str] = field(default_factory=dict)


def _formula_query() -> dict[str, Any]:
    # This value is deliberately not configurable: the connector must never
    # select another customer from the shared configuration database.
    return {"tenant_tag": FORMULA_TENANT_TAG, "is_active": True}


def override_mongo_endpoint(uri: str, endpoint: str) -> str:
    endpoint = endpoint.strip()
    if not endpoint:
        return uri
    if not re.fullmatch(r"[A-Za-z0-9_.-]+:\d{1,5}", endpoint):
        raise FormulaMongoError(
            "MONGO_CALLS_ENDPOINT_OVERRIDE должен иметь формат host:port."
        )
    match = re.match(r"^(mongodb://)([^/]+)(/.*)?$", uri)
    if not match:
        raise FormulaMongoError(
            "MONGO_CALLS_ENDPOINT_OVERRIDE поддерживает только mongodb:// URI."
        )
    authority = match.group(2)
    credentials = authority.rsplit("@", 1)[0] + "@" if "@" in authority else ""
    return f"{match.group(1)}{credentials}{endpoint}{match.group(3) or ''}"


def resolve_formula_tenant(customers: Collection[Mapping[str, Any]]) -> FormulaTenantConfig:
    document = customers.find_one(
        _formula_query(),
        {
            "_id": 0,
            "tenant_tag": 1,
            "display_name": 1,
            "db_connection.connection_string": 1,
            "db_connection.database_name": 1,
            "data_sources": 1,
        },
    )
    if document is None:
        raise FormulaMongoError("Активный tenant formula не найден в конфигурации MongoDB.")
    if document.get("tenant_tag") != FORMULA_TENANT_TAG:
        raise FormulaMongoError("Конфигурация вернула tenant, отличный от formula.")

    db_connection = document.get("db_connection")
    if not isinstance(db_connection, Mapping):
        raise FormulaMongoError("У tenant formula отсутствует db_connection.")
    connection_string = db_connection.get("connection_string")
    database_name = db_connection.get("database_name")
    if not isinstance(connection_string, str) or not connection_string:
        raise FormulaMongoError("У tenant formula отсутствует строка подключения.")
    if not isinstance(database_name, str) or not database_name:
        raise FormulaMongoError("У tenant formula не указана база данных.")

    raw_sources = document.get("data_sources")
    data_sources = {
        str(key): value
        for key, value in (raw_sources.items() if isinstance(raw_sources, Mapping) else [])
        if isinstance(value, str) and value
    }
    return FormulaTenantConfig(
        database_name=database_name,
        connection_string=connection_string,
        display_name=str(document.get("display_name") or "Формула"),
        data_sources=data_sources,
    )


def _write_capabilities(status: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    auth_info = status.get("authInfo")
    if not isinstance(auth_info, Mapping):
        return set(), set()

    roles: set[str] = set()
    for item in auth_info.get("authenticatedUserRoles", []):
        if isinstance(item, Mapping) and isinstance(item.get("role"), str):
            roles.add(item["role"])

    actions: set[str] = set()
    for privilege in auth_info.get("authenticatedUserPrivileges", []):
        if not isinstance(privilege, Mapping):
            continue
        privilege_actions = privilege.get("actions", [])
        if isinstance(privilege_actions, Iterable) and not isinstance(privilege_actions, (str, bytes)):
            actions.update(str(action) for action in privilege_actions)
    return roles & WRITE_ROLES, actions & WRITE_ACTIONS


def _role_scope_violations(status: Mapping[str, Any], database_name: str) -> set[str]:
    auth_info = status.get("authInfo")
    if not isinstance(auth_info, Mapping):
        return {"unverified"}
    authenticated_roles = auth_info.get("authenticatedUserRoles")
    if not isinstance(authenticated_roles, list) or not authenticated_roles:
        return {"unverified"}

    violations: set[str] = set()
    for item in authenticated_roles:
        if not isinstance(item, Mapping):
            violations.add("unverified")
            continue
        role = item.get("role")
        role_database = item.get("db")
        if role != "read" or role_database != database_name:
            violations.add(f"{role_database}:{role}")
    return violations


class ReadOnlyCollection:
    """Narrow PyMongo facade that exposes query operations only."""

    __slots__ = ("__collection",)

    def __init__(self, collection: Collection[Any]) -> None:
        self.__collection = collection

    @property
    def name(self) -> str:
        return self.__collection.name

    def find(self, *args: Any, **kwargs: Any) -> Any:
        return self.__collection.find(*args, **kwargs)

    def find_one(self, *args: Any, **kwargs: Any) -> Any:
        return self.__collection.find_one(*args, **kwargs)

    def aggregate(self, pipeline: Sequence[Mapping[str, Any]], **kwargs: Any) -> Any:
        for stage in pipeline:
            if not isinstance(stage, Mapping):
                raise FormulaMongoError("Каждый этап aggregation pipeline должен быть объектом.")
            if WRITE_PIPELINE_STAGES.intersection(stage):
                raise FormulaMongoError("Aggregation pipeline с $out/$merge запрещен в read-only режиме.")
        return self.__collection.aggregate(pipeline, **kwargs)

    def count_documents(self, *args: Any, **kwargs: Any) -> int:
        return self.__collection.count_documents(*args, **kwargs)

    def estimated_document_count(self, *args: Any, **kwargs: Any) -> int:
        return self.__collection.estimated_document_count(*args, **kwargs)

    def distinct(self, *args: Any, **kwargs: Any) -> list[Any]:
        return self.__collection.distinct(*args, **kwargs)


class FormulaMongoReader:
    """Read-only access to the database selected by customers.tenant_tag=formula."""

    def __init__(self, client: MongoClient[Any], tenant: FormulaTenantConfig) -> None:
        self.__client = client
        self.__tenant = tenant
        self.__database: Database[Any] = client[tenant.database_name]
        self.__verified = False
        self.__server_read_only = False

    @classmethod
    def from_env(
        cls,
        env_file: str | Path | None = ".env",
        *,
        require_server_read_only: bool = True,
    ) -> "FormulaMongoReader":
        if env_file is not None:
            load_dotenv(dotenv_path=env_file, override=False)
        config_uri = os.getenv("MONGO_CALLS_CONFIG_URI", "").strip()
        if not config_uri:
            raise FormulaMongoError("Не задан MONGO_CALLS_CONFIG_URI.")
        config_database = os.getenv("MONGO_CALLS_CONFIG_DATABASE", DEFAULT_CONFIG_DATABASE).strip()
        config_collection = os.getenv("MONGO_CALLS_CONFIG_COLLECTION", DEFAULT_CONFIG_COLLECTION).strip()
        if not config_database or not config_collection:
            raise FormulaMongoError("Не заданы база или коллекция центральной конфигурации MongoDB.")
        endpoint_override = os.getenv("MONGO_CALLS_ENDPOINT_OVERRIDE", "").strip()
        config_uri = override_mongo_endpoint(config_uri, endpoint_override)
        try:
            timeout_ms = max(
                1_000,
                int(os.getenv("MONGO_CALLS_CONNECT_TIMEOUT_MS", str(DEFAULT_TIMEOUT_MS))),
            )
        except ValueError as exc:
            raise FormulaMongoError("MONGO_CALLS_CONNECT_TIMEOUT_MS должен быть целым числом.") from exc

        config_client: MongoClient[Any] = MongoClient(
            config_uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms * 2,
            read_preference=SecondaryPreferred(),
            appname="formula-report-config-reader",
        )
        try:
            config_client.admin.command("ping")
            tenant = resolve_formula_tenant(config_client[config_database][config_collection])
        except FormulaMongoError:
            raise
        except Exception as exc:
            raise FormulaMongoError(
                f"Не удалось прочитать конфигурацию tenant formula: {type(exc).__name__}."
            ) from exc
        finally:
            config_client.close()

        tenant_uri = override_mongo_endpoint(tenant.connection_string, endpoint_override)
        tenant_client: MongoClient[Any] = MongoClient(
            tenant_uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms * 2,
            read_preference=SecondaryPreferred(),
            appname="formula-report-readonly",
        )
        reader = cls(tenant_client, tenant)
        try:
            reader.verify(require_server_read_only=require_server_read_only)
        except Exception:
            reader.close()
            raise
        return reader

    @property
    def tenant_tag(self) -> str:
        return FORMULA_TENANT_TAG

    @property
    def display_name(self) -> str:
        return self.__tenant.display_name

    @property
    def database_name(self) -> str:
        return self.__tenant.database_name

    @property
    def data_sources(self) -> Mapping[str, str]:
        return dict(self.__tenant.data_sources)

    @property
    def server_read_only(self) -> bool:
        self.__require_verified()
        return self.__server_read_only

    def verify(self, *, require_server_read_only: bool = True) -> None:
        try:
            self.__client.admin.command("ping")
            status = self.__database.command({"connectionStatus": 1, "showPrivileges": True})
        except Exception as exc:
            raise FormulaMongoError(
                f"Не удалось подключиться к БД tenant formula: {type(exc).__name__}."
            ) from exc
        write_roles, write_actions = _write_capabilities(status)
        scope_violations = _role_scope_violations(status, self.database_name)
        self.__server_read_only = not (write_roles or write_actions or scope_violations)
        if require_server_read_only and not self.__server_read_only:
            details = ", ".join(sorted(write_roles | write_actions | scope_violations))
            raise FormulaMongoError(
                "Учетная запись tenant formula не ограничена ролью read только на его БД; "
                f"подключение отклонено ({details})."
            )
        self.__verified = True

    def __require_verified(self) -> None:
        if not self.__verified:
            raise FormulaMongoError("Серверные read-only права tenant formula еще не проверены.")

    def collection(self, name: str) -> ReadOnlyCollection:
        self.__require_verified()
        if not isinstance(name, str) or not name or "\x00" in name:
            raise FormulaMongoError("Некорректное имя коллекции.")
        return ReadOnlyCollection(self.__database[name])

    def collection_names(self) -> list[str]:
        self.__require_verified()
        return self.__database.list_collection_names()

    def close(self) -> None:
        self.__client.close()

    def __enter__(self) -> "FormulaMongoReader":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Проверяет read-only подключение к MongoDB tenant formula.",
    )
    parser.add_argument("--env-file", default=".env", help="Путь к env-файлу (по умолчанию .env).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with FormulaMongoReader.from_env(args.env_file) as reader:
            print(f"MongoDB: tenant={reader.tenant_tag}, database={reader.database_name}, access=read-only")
            print("Data sources: " + ", ".join(sorted(reader.data_sources)))
        return 0
    except FormulaMongoError as exc:
        print(f"MongoDB access error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
