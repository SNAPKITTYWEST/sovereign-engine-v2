"""
Stdio Bridge Server
Part of SOVEREIGN PYTHON LLM ENGINE

Stdio-based bridge for C frontend communication.
Uses JSON-RPC 2.0 over stdin/stdout.
"""

import sys
import asyncio
import json
from typing import Any
from datetime import datetime

from ..agents.react import ReActAgent, ReActConfig
from ..tools.registry import ToolRegistry
from ..tools.approval import ApprovalEngine
from ..core.evidence import WORMLedger
from ..core.crypto import generate_signing_key
from ..runtime.providers.multi import MultiProvider
from ..models.entities import Task, Message, MessageRole
from pathlib import Path


class StdioBridge:
    """
    Stdio bridge server.

    Protocol:
    - C frontend writes JSON-RPC requests to our stdin
    - We write JSON-RPC responses to stdout
    - All messages are newline-delimited JSON
    """

    def __init__(self):
        # Initialize components
        signing_key = generate_signing_key()
        self.ledger = WORMLedger(Path("bridge_evidence.worm"), signing_key)
        self.registry = ToolRegistry()
        self.approval = ApprovalEngine(self.ledger)
        self.model = MultiProvider()  # OpenRouter → Ollama fallback

        # Initialize agent
        config = ReActConfig(max_steps=15, log_to_worm=True)
        self.agent = ReActAgent(
            self.model,
            self.registry,
            self.approval,
            self.ledger,
            config
        )

        # Request handlers
        self.handlers = {
            "agent.run": self._handle_agent_run,
            "agent.stream": self._handle_agent_stream,
            "tool.execute": self._handle_tool_execute,
            "tool.list": self._handle_tool_list,
            "chat.message": self._handle_chat_message,
            "health": self._handle_health,
        }

    async def run(self):
        """Run stdio bridge server"""
        # Log startup
        await self.ledger.append({
            "event": "bridge_startup",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Write ready signal
        self._write_response({
            "jsonrpc": "2.0",
            "method": "bridge.ready",
            "params": {
                "version": "1.0.0",
                "capabilities": ["agent.run", "agent.stream", "tool.execute", "chat.message"]
            }
        })

        # Read loop
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

                # Parse request
                request = json.loads(line)

                # Handle request
                response = await self._handle_request(request)

                # Write response
                if response:
                    self._write_response(response)

            except KeyboardInterrupt:
                break
            except Exception as e:
                # Write error response
                self._write_response({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    },
                    "id": None
                })

        # Log shutdown
        await self.ledger.append({
            "event": "bridge_shutdown",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def _handle_request(self, request: dict) -> dict | None:
        """Handle JSON-RPC request"""
        # Validate
        if request.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request"
                },
                "id": request.get("id")
            }

        method = request.get("method")
        if not method:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Method required"
                },
                "id": request.get("id")
            }

        params = request.get("params", {})
        request_id = request.get("id")

        # Find handler
        handler = self.handlers.get(method)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                "id": request_id
            }

        # Execute
        try:
            result = await handler(params)

            # Don't send response for notifications
            if request_id is None:
                return None

            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": "Handler error",
                    "data": str(e)
                },
                "id": request_id
            }

    async def _handle_agent_run(self, params: dict) -> dict:
        """Handle agent.run request"""
        task_description = params.get("task")
        if not task_description:
            raise ValueError("task parameter required")

        # Create task
        task = Task(
            task_id=f"bridge-{datetime.utcnow().timestamp()}",
            description=task_description
        )

        # Run agent
        result = await self.agent.run(task)

        return {
            "result": result,
            "task_id": task.task_id
        }

    async def _handle_agent_stream(self, params: dict) -> dict:
        """Handle agent.stream request"""
        # Streaming would require SSE or WebSocket
        # For now, fall back to non-streaming
        return await self._handle_agent_run(params)

    async def _handle_tool_execute(self, params: dict) -> dict:
        """Handle tool.execute request"""
        tool_name = params.get("tool")
        tool_args = params.get("args", {})

        if not tool_name:
            raise ValueError("tool parameter required")

        # Get tool
        tool = self.registry.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Execute
        result = await tool.handler(**tool_args)

        return {
            "tool": tool_name,
            "result": str(result)
        }

    async def _handle_tool_list(self, params: dict) -> dict:
        """Handle tool.list request"""
        tools = self.registry.list_all()

        return {
            "tools": [
                {
                    "id": tool.tool_id,
                    "description": tool.description,
                    "risk_class": tool.risk_class.value
                }
                for tool in tools[:50]  # Limit to 50
            ]
        }

    async def _handle_chat_message(self, params: dict) -> dict:
        """Handle chat.message request"""
        message_text = params.get("message")
        if not message_text:
            raise ValueError("message parameter required")

        # Generate response using model
        messages = [
            {
                "role": "user",
                "content": message_text
            }
        ]

        response = await self.model.invoke_model(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            messages=messages,
            max_tokens=2048
        )

        # Extract text
        reply = response["content"][0]["text"]

        return {
            "reply": reply
        }

    async def _handle_health(self, params: dict) -> dict:
        """Handle health check"""
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat()
        }

    def _write_response(self, response: dict) -> None:
        """Write JSON response to stdout"""
        json_str = json.dumps(response)
        sys.stdout.write(json_str + "\n")
        sys.stdout.flush()


def main():
    """Entry point for stdio bridge"""
    bridge = StdioBridge()
    asyncio.run(bridge.run())


if __name__ == "__main__":
    main()
