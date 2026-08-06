"""
MCP Transport Layers
Part of SOVEREIGN PYTHON LLM ENGINE

Transport implementations for MCP server (stdio, HTTP).
"""

import sys
import asyncio
from typing import AsyncIterator
from pathlib import Path
import json

from .server import MCPServer


class StdioTransport:
    """
    Stdio transport for MCP server.

    Reads JSON-RPC from stdin, writes responses to stdout.
    """

    def __init__(self, server: MCPServer):
        self.server = server

    async def run(self) -> None:
        """Run stdio server loop"""
        while True:
            try:
                # Read line from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None,
                    sys.stdin.readline
                )

                if not line:
                    break  # EOF

                line = line.strip()
                if not line:
                    continue

                # Handle request
                response = await self.server.handle_request(line)

                # Write response to stdout
                if response:
                    sys.stdout.write(response + "\n")
                    sys.stdout.flush()

            except KeyboardInterrupt:
                break
            except Exception as e:
                # Write error to stderr
                sys.stderr.write(f"Error: {str(e)}\n")
                sys.stderr.flush()


class HTTPTransport:
    """
    HTTP transport for MCP server.

    Exposes server over HTTP with Server-Sent Events for streaming.
    """

    def __init__(self, server: MCPServer, host: str = "127.0.0.1", port: int = 8000):
        self.server = server
        self.host = host
        self.port = port

    async def run(self) -> None:
        """Run HTTP server"""
        try:
            from aiohttp import web
        except ImportError:
            raise ImportError("aiohttp is required for HTTP transport")

        app = web.Application()
        app.router.add_post("/rpc", self._handle_rpc)
        app.router.add_get("/health", self._handle_health)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        print(f"MCP server listening on http://{self.host}:{self.port}")

        # Keep running
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    async def _handle_rpc(self, request: "web.Request") -> "web.Response":
        """Handle JSON-RPC request"""
        from aiohttp import web

        try:
            # Read request body
            body = await request.text()

            # Handle request
            response = await self.server.handle_request(body)

            # Return response
            if response:
                return web.Response(
                    text=response,
                    content_type="application/json"
                )
            else:
                # Notification (no response)
                return web.Response(status=204)

        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                "id": None
            }
            return web.Response(
                text=json.dumps(error_response),
                content_type="application/json",
                status=500
            )

    async def _handle_health(self, request: "web.Request") -> "web.Response":
        """Health check endpoint"""
        from aiohttp import web

        return web.json_response({
            "status": "ok",
            "server": "sovereign-engine-mcp",
            "version": "1.0.0"
        })


class WebSocketTransport:
    """
    WebSocket transport for MCP server.

    Real-time bidirectional communication.
    """

    def __init__(self, server: MCPServer, host: str = "127.0.0.1", port: int = 8001):
        self.server = server
        self.host = host
        self.port = port

    async def run(self) -> None:
        """Run WebSocket server"""
        try:
            from aiohttp import web
        except ImportError:
            raise ImportError("aiohttp is required for WebSocket transport")

        app = web.Application()
        app.router.add_get("/ws", self._handle_websocket)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        print(f"MCP WebSocket server listening on ws://{self.host}:{self.port}/ws")

        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    async def _handle_websocket(self, request: "web.Request") -> "web.WebSocketResponse":
        """Handle WebSocket connection"""
        from aiohttp import web

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Handle request
                response = await self.server.handle_request(msg.data)

                # Send response
                if response:
                    await ws.send_str(response)

            elif msg.type == web.WSMsgType.ERROR:
                print(f"WebSocket error: {ws.exception()}")

        return ws
