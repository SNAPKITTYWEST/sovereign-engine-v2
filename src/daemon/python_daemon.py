"""
Sovereign LLM Engine — Python Asyncio Daemon
Part of SOVEREIGN PYTHON LLM ENGINE

Persistent background daemon that exposes a TCP socket for IPC (port 19002).
Receives JSON task messages, routes them to registered handlers, and responds
with JSON results. Supports graceful shutdown and health-check ping.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Protocol

# ==========================================
# Logging
# ==========================================

logger = logging.getLogger("sovereign.daemon")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ==========================================
# Data Types
# ==========================================

@dataclass
class DaemonTask:
    """Inbound task received from a client."""
    task_id: str
    type: str
    payload: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DaemonResponse:
    """Outbound response sent back to a client."""
    task_id: str
    result: dict[str, Any]
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps({
            "task_id": self.task_id,
            "result": self.result,
            "error": self.error,
        })


# ==========================================
# Handler Protocol
# ==========================================

class DaemonHandler(Protocol):
    """
    Handler protocol for daemon tasks.

    Every registered handler must implement this interface.
    async handle(task) must return a plain dict result.
    """

    async def handle(self, task: DaemonTask) -> dict[str, Any]:
        """Process a task and return a result dict."""
        ...


# ==========================================
# Built-in Handlers
# ==========================================

class EchoHandler:
    """Built-in echo handler for testing; returns payload as-is."""

    async def handle(self, task: DaemonTask) -> dict[str, Any]:
        return {"echo": task.payload, "task_id": task.task_id}


class StatusHandler:
    """Built-in status handler; reports daemon uptime and registered types."""

    def __init__(self, daemon: "PythonDaemon") -> None:
        self._daemon = daemon

    async def handle(self, task: DaemonTask) -> dict[str, Any]:
        return {
            "status": "running",
            "registered_types": list(self._daemon._handlers.keys()),
            "started_at": self._daemon._started_at,
        }


# ==========================================
# Client Connection
# ==========================================

class _ClientConnection:
    """
    Manages a single connected client.

    Reads newline-delimited JSON messages from the reader and writes
    newline-delimited JSON responses back to the writer. The special
    plain-text message "PING\\n" is answered with "PONG\\n" without
    deserialising as JSON.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        dispatch: Callable[[DaemonTask], Coroutine[Any, Any, DaemonResponse]],
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._dispatch = dispatch

    async def run(self) -> None:
        peer = self._writer.get_extra_info("peername", "<unknown>")
        logger.debug("Client connected: %s", peer)
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break  # EOF — client disconnected

                raw = line.strip()

                # Health-check fast path
                if raw == b"PING":
                    self._writer.write(b"PONG\n")
                    await self._writer.drain()
                    continue

                # Parse JSON task
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError as exc:
                    error_resp = json.dumps({
                        "task_id": "unknown",
                        "result": {},
                        "error": f"JSON parse error: {exc}",
                    })
                    self._writer.write((error_resp + "\n").encode())
                    await self._writer.drain()
                    continue

                # Validate required fields
                task_id = msg.get("task_id", "")
                task_type = msg.get("type", "")
                payload = msg.get("payload", {})

                if not task_id or not task_type:
                    error_resp = json.dumps({
                        "task_id": task_id or "unknown",
                        "result": {},
                        "error": "Missing required fields: task_id, type",
                    })
                    self._writer.write((error_resp + "\n").encode())
                    await self._writer.drain()
                    continue

                task = DaemonTask(
                    task_id=task_id,
                    type=task_type,
                    payload=payload if isinstance(payload, dict) else {},
                )

                response = await self._dispatch(task)
                self._writer.write((response.to_json() + "\n").encode())
                await self._writer.drain()

        except asyncio.CancelledError:
            pass
        except ConnectionResetError:
            pass
        except Exception as exc:
            logger.warning("Error in client connection from %s: %s", peer, exc)
        finally:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            logger.debug("Client disconnected: %s", peer)


# ==========================================
# Main Daemon
# ==========================================

class PythonDaemon:
    """
    Persistent asyncio daemon.

    Usage:
        daemon = PythonDaemon(host="127.0.0.1", port=19002)
        daemon.register_handler("my_task", MyHandler())
        asyncio.run(daemon.start())

    The daemon listens on TCP (host, port) and processes newline-delimited
    JSON task messages. Send "PING\\n" to receive "PONG\\n".
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 19002

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._host = host
        self._port = port
        self._handlers: dict[str, DaemonHandler] = {}
        self._server: asyncio.Server | None = None
        self._stop_event: asyncio.Event | None = None
        self._started_at: str | None = None
        self._active_connections: set[asyncio.Task[None]] = set()

        # Register built-in handlers
        self.register_handler("echo", EchoHandler())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_handler(self, task_type: str, handler: DaemonHandler) -> None:
        """
        Register a handler for a specific task type.

        Overwrites any existing handler for that type.
        """
        if task_type in self._handlers:
            logger.warning("Overwriting existing handler for task type '%s'", task_type)
        self._handlers[task_type] = handler
        logger.info("Registered handler for task type '%s'", task_type)

    def unregister_handler(self, task_type: str) -> None:
        """Remove handler for a task type."""
        self._handlers.pop(task_type, None)

    async def start(self) -> None:
        """
        Start the daemon and block until shutdown is requested.

        Installs SIGTERM/SIGINT handlers for graceful shutdown.
        """
        self._stop_event = asyncio.Event()
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Register status handler (needs reference to self)
        self.register_handler("status", StatusHandler(self))

        # Install signal handlers (Unix only; skip on Windows)
        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._request_shutdown)
        else:
            # On Windows use a KeyboardInterrupt task wrapper instead
            loop.run_until_complete  # no-op reference; signal handled via exception

        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._host,
            port=self._port,
        )

        addr = self._server.sockets[0].getsockname()
        logger.info("Sovereign daemon listening on %s:%s", addr[0], addr[1])

        async with self._server:
            try:
                await self._stop_event.wait()
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass

        await self.stop()

    async def stop(self) -> None:
        """Graceful shutdown: close server and drain active connections."""
        logger.info("Daemon shutting down…")

        if self._server is not None:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

        # Cancel and await all active connection tasks
        if self._active_connections:
            for task in list(self._active_connections):
                task.cancel()
            await asyncio.gather(*self._active_connections, return_exceptions=True)
            self._active_connections.clear()

        logger.info("Daemon stopped.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request_shutdown(self) -> None:
        """Signal handler callback — sets the stop event."""
        logger.info("Shutdown signal received.")
        if self._stop_event is not None:
            self._stop_event.set()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Called by asyncio.start_server for each new connection."""
        conn = _ClientConnection(reader, writer, self._dispatch)
        task = asyncio.current_task()
        if task is not None:
            self._active_connections.add(task)
        try:
            await conn.run()
        finally:
            if task is not None:
                self._active_connections.discard(task)

    async def _dispatch(self, task: DaemonTask) -> DaemonResponse:
        """Route a task to its registered handler."""
        handler = self._handlers.get(task.type)
        if handler is None:
            return DaemonResponse(
                task_id=task.task_id,
                result={},
                error=f"No handler registered for task type '{task.type}'",
            )

        try:
            result = await handler.handle(task)
            return DaemonResponse(task_id=task.task_id, result=result)
        except Exception as exc:
            logger.exception("Handler error for task %s (type=%s)", task.task_id, task.type)
            return DaemonResponse(
                task_id=task.task_id,
                result={},
                error=f"Handler raised {type(exc).__name__}: {exc}",
            )


# ==========================================
# Convenience: send a single task from client code
# ==========================================

async def send_task(
    task_id: str,
    task_type: str,
    payload: dict[str, Any],
    host: str = PythonDaemon.DEFAULT_HOST,
    port: int = PythonDaemon.DEFAULT_PORT,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Send a single task to a running daemon and return the response dict.

    Raises:
        asyncio.TimeoutError if the daemon does not respond within timeout seconds.
        ConnectionRefusedError if the daemon is not running.
        ValueError if the daemon returns an error in the response envelope.
    """
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=timeout
    )
    try:
        msg = json.dumps({"task_id": task_id, "type": task_type, "payload": payload})
        writer.write((msg + "\n").encode())
        await writer.drain()

        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        response = json.loads(raw)
        if response.get("error"):
            raise ValueError(f"Daemon error: {response['error']}")
        return response["result"]
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def ping_daemon(
    host: str = PythonDaemon.DEFAULT_HOST,
    port: int = PythonDaemon.DEFAULT_PORT,
    timeout: float = 5.0,
) -> bool:
    """
    Send PING to daemon. Returns True if daemon responds PONG.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.write(b"PING\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return raw.strip() == b"PONG"
    except Exception:
        return False


# ==========================================
# Entry point (run daemon directly)
# ==========================================

if __name__ == "__main__":
    daemon = PythonDaemon()
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        pass
