"""Tipos de coluna da API, usados pelas migrações e pelos repositórios."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.engine import Dialect
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine, UserDefinedType


class _UUIDDoMariaDB(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "UUID"


class UUIDNativo(TypeDecorator[uuid.UUID]):
    """UUID nativo (16 bytes) no MariaDB 10.7+; CHAR(36) nos demais bancos (SQLite do CI).

    Ver docs/adr/010. Na aplicação o valor é sempre `uuid.UUID`; no banco, o texto canônico.
    """

    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if getattr(dialect, "is_mariadb", False):
            return dialect.type_descriptor(_UUIDDoMariaDB())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect: Dialect) -> uuid.UUID | None:
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
