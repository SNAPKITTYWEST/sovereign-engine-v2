"""
Sovereign Engine direct runner — bypasses sovereign.py draft wiring,
invokes the actual working subsystems directly.
Bedrock backend wired until Ahmad's sovereign SDK ships.
"""
import asyncio
import sys
import json
sys.path.insert(0, ".")

from src.tools.registry import ToolRegistry
from src.tools.loader import load_all_tools
from src.routing.pipeline import RoutingPipeline, build_default_routing_nodes
from src.agents.react import ReActAgent, ReActConfig
from src.inference.bedrock_backend import BedrockBackend
from src.models.entities import Task


async def main():
    print("Booting Sovereign Engine...")

    # Tools
    registry = ToolRegistry()
    load_all_tools(registry)

    # Model — Bedrock (temporary until Ahmad's SDK)
    model = BedrockBackend()

    # Routing pipeline — Jordan algebra MoE
    expert_names = ["coder", "reasoner", "query", "constraint", "general"]
    routing_nodes = build_default_routing_nodes(expert_names)
    routing = RoutingPipeline(
        experts={name: lambda t, n=name: {"expert": n, "result": t} for name in expert_names},
        routing_nodes=routing_nodes,
    )

    # Agent
    agent = ReActAgent(
        model=model,
        tool_registry=registry,
        config=ReActConfig(max_steps=10),
        agent_id="sovereign_main",
    )

    task = "Write a fibonacci function in Python"
    print(f"\nTask: {task}\n")
    print("Running through Jordan algebra routing pipeline...")

    # Route first — returns DispatchResult
    dispatch = await routing.route(task, {})
    print(f"Routing: active experts = {dispatch.active_count}, "
          f"success = {dispatch.success_count}")
    print()

    # Run agent — wrap task string in Task entity
    task_obj = Task(id="task-001", description=task)
    result = await agent.run(task_obj)
    print("=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
