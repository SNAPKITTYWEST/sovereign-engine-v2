"""
HTTP Bridge Server
Part of SOVEREIGN PYTHON LLM ENGINE

HTTP-based bridge for C frontend communication.
Simpler alternative to stdio for local communication.
"""

from typing import Any
from datetime import datetime, timezone
from pathlib import Path
import json

from ..agents.react import ReActAgent, ReActConfig
from ..tools.registry import ToolRegistry
from ..tools.loader import load_all_tools
from ..tools.approval import ApprovalEngine
from ..core.evidence import WORMLedger
from ..core.crypto import generate_signing_key
from ..runtime.providers.multi import MultiProvider
from ..models.entities import Task
from .key_manager import KeyManager


class HTTPBridge:
    """
    HTTP bridge server.

    Exposes REST endpoints for C frontend:
    - POST /agent/run - Run agent task
    - POST /tool/execute - Execute tool
    - GET /tools - List tools
    - POST /chat - Chat message
    - GET /health - Health check
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 19000):
        self.host = host
        self.port = port

        # Initialize components
        signing_key = generate_signing_key()
        self.ledger = WORMLedger(Path("bridge_evidence.jsonl"), signing_key)
        self.registry = ToolRegistry()
        load_all_tools(self.registry)  # Load filesystem, code, etc tools
        self.approval = ApprovalEngine(self.ledger)
        self.key_manager = KeyManager()
        self.model = MultiProvider(key_manager=self.key_manager)  # MoE routing with key manager

        # Initialize agent
        config = ReActConfig(max_steps=15, log_to_worm=True)
        self.agent = ReActAgent(
            self.model,
            self.registry,
            self.approval,
            self.ledger,
            config
        )

    async def run(self):
        """Run HTTP bridge server"""
        try:
            from aiohttp import web
        except ImportError:
            raise ImportError("aiohttp required. Install: pip install aiohttp")

        app = web.Application()

        # Register routes
        app.router.add_post("/agent/run", self._handle_agent_run)
        app.router.add_post("/tool/execute", self._handle_tool_execute)
        app.router.add_get("/tools", self._handle_tools_list)
        app.router.add_post("/chat", self._handle_chat)
        app.router.add_get("/health", self._handle_health)

        # API Key management routes
        app.router.add_post("/keys/set", self._handle_keys_set)
        app.router.add_get("/keys/status", self._handle_keys_status)
        app.router.add_delete("/keys/{provider}", self._handle_keys_delete)

        # CORS middleware for local dev
        @web.middleware
        async def cors_middleware(request, handler):
            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return response

        app.middlewares.append(cors_middleware)

        # Log startup
        startup_data = json.dumps({
            "event": "http_bridge_startup",
            "host": self.host,
            "port": self.port,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }).encode('utf-8')
        self.ledger.append("bridge_startup", startup_data, {"host": self.host, "port": self.port})

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        print(f"HTTP Bridge listening on http://{self.host}:{self.port}")

        # Keep running
        try:
            import asyncio
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    async def _handle_agent_run(self, request):
        """Handle POST /agent/run"""
        from aiohttp import web

        data = await request.json()
        task_description = data.get("task")

        if not task_description:
            return web.json_response(
                {"error": "task parameter required"},
                status=400
            )

        # Create task
        task = Task(
            task_id=f"bridge-{datetime.utcnow().timestamp()}",
            description=task_description
        )

        # Run agent
        result = await self.agent.run(task)

        return web.json_response({
            "result": result,
            "task_id": task.task_id
        })

    async def _handle_tool_execute(self, request):
        """Handle POST /tool/execute"""
        from aiohttp import web

        data = await request.json()
        tool_name = data.get("tool")
        tool_args = data.get("args", {})

        if not tool_name:
            return web.json_response(
                {"error": "tool parameter required"},
                status=400
            )

        # Get tool
        tool = self.registry.get(tool_name)
        if not tool:
            return web.json_response(
                {"error": f"Tool not found: {tool_name}"},
                status=404
            )

        # Execute
        try:
            result = await tool.handler(tool_args)  # Pass dict, not kwargs
            return web.json_response({
                "tool": tool_name,
                "result": str(result)
            })
        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def _handle_tools_list(self, request):
        """Handle GET /tools"""
        from aiohttp import web

        tools = self.registry.list_all()

        return web.json_response({
            "tools": [
                {
                    "id": tool.tool_id,
                    "description": tool.description,
                    "risk_class": tool.risk_class.value
                }
                for tool in tools[:50]
            ]
        })

    async def _handle_chat(self, request):
        """Handle POST /chat"""
        from aiohttp import web

        data = await request.json()
        message_text = data.get("message")

        if not message_text:
            return web.json_response(
                {"error": "message parameter required"},
                status=400
            )

        # Generate response
        messages = [
            {
                "role": "user",
                "content": message_text
            }
        ]

        response = await self.model.invoke_model(
            model_id=None,  # Use default: Nemotron if available, else Llama 3.2
            messages=messages,
            max_tokens=2048,
            temperature=0.7
        )

        reply = response["content"][0]["text"]

        return web.json_response({
            "reply": reply
        })

    async def _handle_health(self, request):
        """Handle GET /health"""
        from aiohttp import web

        return web.json_response({
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def _handle_keys_set(self, request):
        """Handle POST /keys/set - Set API key"""
        from aiohttp import web

        try:
            data = await request.json()
            provider = data.get("provider")  # "openrouter" or "ollama"
            api_key = data.get("key")

            if not provider or not api_key:
                return web.json_response(
                    {"error": "provider and key required"},
                    status=400
                )

            # Set key
            self.key_manager.set_key(provider, api_key)

            # Reload provider with new key
            import os
            os.environ[f"{provider.upper()}_API_KEY"] = api_key
            self.model = MultiProvider(key_manager=self.key_manager)  # Reinitialize with new key

            return web.json_response({
                "success": True,
                "provider": provider,
                "expires_in_hours": 24
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def _handle_keys_status(self, request):
        """Handle GET /keys/status - Get key status"""
        from aiohttp import web

        status = self.key_manager.get_status()

        return web.json_response({
            "keys": status,
            "providers": {
                "openrouter": {
                    "name": "OpenRouter",
                    "models": ["Nemotron 70B", "Mistral 7B"],
                    "cost": "Free (daily rotation)"
                },
                "ollama": {
                    "name": "Ollama",
                    "models": ["Llama 3.2", "CodeLlama", "Muse 1.0"],
                    "cost": "Free (local)"
                }
            }
        })

    async def _handle_keys_delete(self, request):
        """Handle DELETE /keys/{provider} - Remove API key"""
        from aiohttp import web

        provider = request.match_info.get("provider")

        if not provider:
            return web.json_response(
                {"error": "provider required"},
                status=400
            )

        self.key_manager.remove_key(provider)

        return web.json_response({
            "success": True,
            "provider": provider
        })


def main():
    """Entry point for HTTP bridge"""
    import asyncio

    bridge = HTTPBridge()
    asyncio.run(bridge.run())


if __name__ == "__main__":
    main()
