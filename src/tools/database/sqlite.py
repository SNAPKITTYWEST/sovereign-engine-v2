"""
SQLite Operations
Part of SOVEREIGN PYTHON LLM ENGINE

SQLite database operations.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass
import sqlite3
import asyncio

from ...core.evidence import WORMLedger


@dataclass
class QueryResult:
    """Database query result"""
    rows: list[dict[str, Any]]
    row_count: int
    columns: list[str]


class SQLiteOperations:
    """
    SQLite database operations.

    Provides safe SQL execution with parameter binding.
    """

    def __init__(self, db_path: Path, worm_ledger: WORMLedger | None = None):
        """
        Initialize SQLite operations.

        Args:
            db_path: Path to SQLite database file
            worm_ledger: Optional WORM ledger
        """
        self.db_path = db_path
        self.worm_ledger = worm_ledger

    async def query(self, sql: str, params: tuple | None = None) -> QueryResult:
        """
        Execute SELECT query.

        Args:
            sql: SQL query string
            params: Optional query parameters

        Returns:
            QueryResult with rows
        """
        def _sync_query():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)

                rows = cursor.fetchall()

                # Convert to dicts
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                row_dicts = [dict(row) for row in rows]

                return QueryResult(
                    rows=row_dicts,
                    row_count=len(row_dicts),
                    columns=columns
                )
            finally:
                conn.close()

        result = await asyncio.to_thread(_sync_query)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "sqlite_query",
                "sql": sql,
                "row_count": result.row_count
            })

        return result

    async def execute(self, sql: str, params: tuple | None = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE.

        Args:
            sql: SQL statement
            params: Optional parameters

        Returns:
            Number of affected rows
        """
        def _sync_execute():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)

                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

        row_count = await asyncio.to_thread(_sync_execute)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "sqlite_execute",
                "sql": sql,
                "affected_rows": row_count
            })

        return row_count

    async def execute_many(self, sql: str, params_list: list[tuple]) -> int:
        """
        Execute statement with multiple parameter sets.

        Args:
            sql: SQL statement
            params_list: List of parameter tuples

        Returns:
            Total affected rows
        """
        def _sync_execute_many():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.executemany(sql, params_list)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

        return await asyncio.to_thread(_sync_execute_many)

    async def create_table(self, table_name: str, schema: dict[str, str]) -> None:
        """
        Create table.

        Args:
            table_name: Table name
            schema: Column name -> SQL type mapping
        """
        columns = ", ".join(f"{name} {sql_type}" for name, sql_type in schema.items())
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"

        await self.execute(sql)

    async def insert(self, table_name: str, data: dict[str, Any]) -> int:
        """
        Insert row.

        Args:
            table_name: Table name
            data: Column -> value mapping

        Returns:
            Row ID
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        await self.execute(sql, tuple(data.values()))

        # Get last insert rowid
        result = await self.query("SELECT last_insert_rowid() as id")
        return result.rows[0]["id"]

    async def update(self, table_name: str, data: dict[str, Any], where: str, where_params: tuple) -> int:
        """
        Update rows.

        Args:
            table_name: Table name
            data: Column -> value mapping
            where: WHERE clause
            where_params: WHERE parameters

        Returns:
            Affected rows
        """
        set_clause = ", ".join(f"{col} = ?" for col in data.keys())
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {where}"

        params = tuple(data.values()) + where_params
        return await self.execute(sql, params)

    async def delete(self, table_name: str, where: str, where_params: tuple) -> int:
        """
        Delete rows.

        Args:
            table_name: Table name
            where: WHERE clause
            where_params: WHERE parameters

        Returns:
            Deleted rows
        """
        sql = f"DELETE FROM {table_name} WHERE {where}"
        return await self.execute(sql, where_params)

    async def table_info(self, table_name: str) -> list[dict[str, Any]]:
        """
        Get table schema information.

        Args:
            table_name: Table name

        Returns:
            List of column info dicts
        """
        result = await self.query(f"PRAGMA table_info({table_name})")
        return result.rows

    async def list_tables(self) -> list[str]:
        """
        List all tables.

        Returns:
            List of table names
        """
        result = await self.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [row["name"] for row in result.rows]


# Tool registration helpers
async def sqlite_query_tool(db_path: str, sql: str, params: list | None = None) -> dict:
    """Execute SQLite query"""
    ops = SQLiteOperations(Path(db_path))
    result = await ops.query(sql, tuple(params) if params else None)

    return {
        "rows": result.rows,
        "row_count": result.row_count,
        "columns": result.columns
    }


async def sqlite_execute_tool(db_path: str, sql: str, params: list | None = None) -> dict:
    """Execute SQLite statement"""
    ops = SQLiteOperations(Path(db_path))
    affected = await ops.execute(sql, tuple(params) if params else None)

    return {
        "affected_rows": affected
    }
