"""
PostgreSQL Operations
Part of SOVEREIGN PYTHON LLM ENGINE

PostgreSQL database operations using asyncpg.
"""

from typing import Any
from dataclasses import dataclass

from ...core.evidence import WORMLedger


@dataclass
class PostgresQueryResult:
    """Postgres query result"""
    rows: list[dict[str, Any]]
    row_count: int
    columns: list[str]


class PostgresOperations:
    """
    PostgreSQL database operations.

    Uses asyncpg for async native Postgres protocol.
    """

    def __init__(
        self,
        connection_string: str,
        worm_ledger: WORMLedger | None = None
    ):
        """
        Initialize Postgres operations.

        Args:
            connection_string: Postgres connection string
            worm_ledger: Optional WORM ledger
        """
        self.connection_string = connection_string
        self.worm_ledger = worm_ledger

    async def query(self, sql: str, *params) -> PostgresQueryResult:
        """
        Execute SELECT query.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            PostgresQueryResult with rows
        """
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg is required. Install: pip install asyncpg")

        conn = await asyncpg.connect(self.connection_string)

        try:
            rows = await conn.fetch(sql, *params)

            # Convert to dicts
            columns = list(rows[0].keys()) if rows else []
            row_dicts = [dict(row) for row in rows]

            result = PostgresQueryResult(
                rows=row_dicts,
                row_count=len(row_dicts),
                columns=columns
            )

            # Log to WORM
            if self.worm_ledger:
                await self.worm_ledger.append({
                    "event": "postgres_query",
                    "sql": sql,
                    "row_count": result.row_count
                })

            return result

        finally:
            await conn.close()

    async def execute(self, sql: str, *params) -> str:
        """
        Execute INSERT/UPDATE/DELETE.

        Args:
            sql: SQL statement
            params: Parameters

        Returns:
            Status string (e.g., "INSERT 0 1")
        """
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg is required")

        conn = await asyncpg.connect(self.connection_string)

        try:
            status = await conn.execute(sql, *params)

            # Log to WORM
            if self.worm_ledger:
                await self.worm_ledger.append({
                    "event": "postgres_execute",
                    "sql": sql,
                    "status": status
                })

            return status

        finally:
            await conn.close()

    async def transaction(self, statements: list[tuple[str, tuple]]) -> None:
        """
        Execute multiple statements in transaction.

        Args:
            statements: List of (sql, params) tuples
        """
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg is required")

        conn = await asyncpg.connect(self.connection_string)

        try:
            async with conn.transaction():
                for sql, params in statements:
                    await conn.execute(sql, *params)

        finally:
            await conn.close()


# Tool registration helpers
async def postgres_query_tool(connection_string: str, sql: str, params: list | None = None) -> dict:
    """Execute Postgres query"""
    ops = PostgresOperations(connection_string)
    result = await ops.query(sql, *(params or []))

    return {
        "rows": result.rows,
        "row_count": result.row_count,
        "columns": result.columns
    }


async def postgres_execute_tool(connection_string: str, sql: str, params: list | None = None) -> dict:
    """Execute Postgres statement"""
    ops = PostgresOperations(connection_string)
    status = await ops.execute(sql, *(params or []))

    return {
        "status": status
    }
