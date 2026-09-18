"""
CLI Main Entry Point
Part of SOVEREIGN PYTHON LLM ENGINE

Command-line interface for running agents, tools, and MCP server.
"""

import asyncio
import sys
from pathlib import Path
import argparse


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="sovereign-engine",
        description="Sovereign Python LLM Engine - Provider-neutral agent runtime"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Run ReAct or MCTS agent")
    agent_parser.add_argument("--type", choices=["react", "mcts"], default="react", help="Agent type")
    agent_parser.add_argument("--task", required=True, help="Task description")
    agent_parser.add_argument("--model", default="anthropic.claude-3-5-sonnet-20241022-v2:0", help="Model ID")
    agent_parser.add_argument("--max-steps", type=int, default=10, help="Max steps")

    # Tool command
    tool_parser = subparsers.add_parser("tool", help="Execute a tool")
    tool_parser.add_argument("--name", required=True, help="Tool name")
    tool_parser.add_argument("--args", help="Tool arguments (JSON)")

    # MCP server command
    mcp_parser = subparsers.add_parser("mcp", help="Run MCP server")
    mcp_parser.add_argument("--transport", choices=["stdio", "http", "ws"], default="stdio", help="Transport")
    mcp_parser.add_argument("--host", default="127.0.0.1", help="Host (HTTP/WS only)")
    mcp_parser.add_argument("--port", type=int, default=8000, help="Port (HTTP/WS only)")

    # RAG command
    rag_parser = subparsers.add_parser("rag", help="Run RAG query")
    rag_parser.add_argument("--query", required=True, help="Query string")
    rag_parser.add_argument("--top-k", type=int, default=5, help="Top K results")

    # Version command
    version_parser = subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "agent":
        asyncio.run(run_agent(args))
    elif args.command == "tool":
        asyncio.run(run_tool(args))
    elif args.command == "mcp":
        asyncio.run(run_mcp(args))
    elif args.command == "rag":
        asyncio.run(run_rag(args))
    elif args.command == "version":
        print("Sovereign Engine v1.0.0")
    else:
        parser.print_help()


async def run_agent(args):
    """Run agent"""
    from ..agents.react import ReActAgent, ReActConfig
    from ..tools.registry import ToolRegistry
    from ..tools.approval import ApprovalEngine
    from ..core.evidence import WORMLedger
    from ..runtime.providers.bedrock import BedrockProvider
    from ..models.entities import Task

    print(f"Running {args.type} agent...")
    print(f"Task: {args.task}")
    print(f"Model: {args.model}")

    # Initialize components
    registry = ToolRegistry()
    approval = ApprovalEngine()
    ledger = WORMLedger(Path("evidence.worm"))

    # Initialize model
    model = BedrockProvider(region="us-east-1")

    # Create agent
    if args.type == "react":
        config = ReActConfig(max_steps=args.max_steps)
        agent = ReActAgent(model, registry, approval, ledger, config)

        # Run task
        task = Task(task_id="cli-task", description=args.task)
        result = await agent.run(task)

        print("\n=== RESULT ===")
        print(result)
    else:
        print("MCTS agent not yet wired to CLI")


async def run_tool(args):
    """Execute tool"""
    import json
    from ..tools.registry import ToolRegistry

    print(f"Executing tool: {args.name}")

    registry = ToolRegistry()
    tool = registry.get(args.name)

    if not tool:
        print(f"Error: Tool not found: {args.name}")
        sys.exit(1)

    # Parse arguments
    if args.args:
        tool_args = json.loads(args.args)
    else:
        tool_args = {}

    # Execute
    result = await tool.handler(**tool_args)

    print("\n=== RESULT ===")
    print(result)


async def run_mcp(args):
    """Run MCP server"""
    from ..mcp.server import MCPServer
    from ..mcp.transport import StdioTransport, HTTPTransport, WebSocketTransport
    from ..tools.registry import ToolRegistry
    from ..tools.approval import ApprovalEngine

    print(f"Starting MCP server ({args.transport} transport)...")

    # Initialize components
    registry = ToolRegistry()
    approval = ApprovalEngine()

    # Create server
    server = MCPServer(registry, approval)

    # Select transport
    if args.transport == "stdio":
        transport = StdioTransport(server)
        await transport.run()
    elif args.transport == "http":
        transport = HTTPTransport(server, args.host, args.port)
        await transport.run()
    elif args.transport == "ws":
        transport = WebSocketTransport(server, args.host, args.port)
        await transport.run()


async def run_rag(args):
    """Run RAG query"""
    from ..retrieval.rag import RAGPipeline, RAGConfig
    from ..retrieval.parallel import ParallelRetriever, ParallelRetrieverConfig
    from ..tools.embeddings.encode import EmbeddingsTool
    from ..runtime.providers.bedrock import BedrockProvider

    print(f"RAG Query: {args.query}")

    # Initialize components
    model = BedrockProvider()
    embeddings = EmbeddingsTool(provider="openai")

    # Create retriever (would need vector store)
    retriever_config = ParallelRetrieverConfig()
    retriever = ParallelRetriever({}, config=retriever_config)

    # Create RAG pipeline
    rag_config = RAGConfig(top_k=args.top_k)
    pipeline = RAGPipeline(model, retriever, embeddings, config=rag_config)

    # Query
    result = await pipeline.query(args.query)

    print("\n=== ANSWER ===")
    print(result)


if __name__ == "__main__":
    main()
