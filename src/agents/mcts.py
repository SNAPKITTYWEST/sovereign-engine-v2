"""
MCTS Agent Implementation
Part of SOVEREIGN PYTHON LLM ENGINE

Monte Carlo Tree Search for code generation and problem solving.
Uses PUCT algorithm for node selection.
"""

from typing import Any
from dataclasses import dataclass, field
import math
import asyncio
from datetime import datetime
import hashlib

from ..models.entities import MCTSNodeState, MCTSSearchResult, CodeExecutionResult
from ..models.state_machines import MCTSState, MCTSStateMachine
from ..engine.rules import mcts_should_terminate, mcts_should_expand
from ..core.protocols import Model
from ..runtime.sandbox import CodeSandbox
from ..core.evidence import WORMLedger


@dataclass
class MCTSNode:
    """
    MCTS tree node.

    Each node represents a code solution candidate.
    """
    node_id: str
    parent_id: str | None
    code: str
    test_assertion: str | None
    visit_count: int = 0
    total_reward: float = 0.0
    children: list[str] = field(default_factory=list)
    is_terminal: bool = False
    test_passed: bool = False

    @property
    def average_reward(self) -> float:
        """Average reward (Q-value)"""
        if self.visit_count == 0:
            return 0.0
        return self.total_reward / self.visit_count


@dataclass
class MCTSConfig:
    """Configuration for MCTS agent"""
    max_iterations: int = 100
    exploration_constant: float = 1.414  # sqrt(2) for PUCT
    num_children_per_expansion: int = 3
    temperature: float = 0.8
    timeout_per_execution: float = 10.0
    log_to_worm: bool = True


class MCTSAgent:
    """
    MCTS agent for code generation with test-driven search.

    Algorithm:
    1. Selection: Traverse tree using PUCT
    2. Expansion: Generate N child nodes (code candidates)
    3. Evaluation: Execute code and evaluate with test
    4. Backpropagation: Update Q-values up the tree
    """

    def __init__(
        self,
        model: Model,
        sandbox: CodeSandbox,
        worm_ledger: WORMLedger | None = None,
        config: MCTSConfig | None = None
    ):
        self.model = model
        self.sandbox = sandbox
        self.worm_ledger = worm_ledger
        self.config = config or MCTSConfig()

        self.state_machine = MCTSStateMachine()
        self.nodes: dict[str, MCTSNode] = {}

    async def search(
        self,
        problem: str,
        test_assertion: str,
        initial_code: str | None = None
    ) -> MCTSSearchResult:
        """
        Run MCTS search to find best code solution.

        Args:
            problem: Problem description
            test_assertion: Test assertion to verify solution
            initial_code: Optional starting code

        Returns:
            MCTSSearchResult with best solution
        """
        # Initialize root node
        root_code = initial_code or self._generate_initial_code(problem)
        root_id = self._hash_code(root_code)

        root_node = MCTSNode(
            node_id=root_id,
            parent_id=None,
            code=root_code,
            test_assertion=test_assertion
        )
        self.nodes[root_id] = root_node

        # Initialize state
        state = self.state_machine.initial_state(
            root_node_id=root_id,
            max_iterations=self.config.max_iterations
        )

        # Evaluate root
        root_reward = await self._evaluate_node(root_node)
        root_node.total_reward = root_reward
        root_node.visit_count = 1

        best_node = root_node
        best_reward = root_reward

        # Main search loop
        while not mcts_should_terminate(state):
            # 1. Selection
            state = self.state_machine.set_phase(state, "selection")
            selected_node = self._select_node(root_id, state)

            # 2. Expansion
            if mcts_should_expand(state, selected_node.visit_count):
                state = self.state_machine.set_phase(state, "expansion")
                children = await self._expand_node(selected_node, problem, state)
            else:
                children = [selected_node]

            # 3. Evaluation
            state = self.state_machine.set_phase(state, "evaluation")
            for child in children:
                reward = await self._evaluate_node(child)

                # Track best
                if reward > best_reward:
                    best_reward = reward
                    best_node = child
                    state = self.state_machine.update_best(state, best_reward, child.node_id)

            # 4. Backpropagation
            state = self.state_machine.set_phase(state, "backpropagation")
            for child in children:
                self._backpropagate(child, child.total_reward / max(child.visit_count, 1))

            # Increment iteration
            state = self.state_machine.increment_iteration(state)

        # Log to WORM
        if self.config.log_to_worm and self.worm_ledger:
            await self._log_to_worm(problem, state, best_node)

        # Return result
        return MCTSSearchResult(
            best_code=best_node.code,
            best_score=best_reward,
            iterations=state["iteration"],
            nodes_explored=len(self.nodes),
            test_passed=best_node.test_passed
        )

    def _select_node(self, root_id: str, state: MCTSState) -> MCTSNode:
        """
        Select leaf node using PUCT (Predictor + Upper Confidence Bound).

        PUCT = Q + c * P * sqrt(N_parent) / (1 + N_child)

        Where:
        - Q = average reward
        - c = exploration constant
        - P = prior probability (uniform for now)
        - N = visit count
        """
        current_id = root_id
        current_node = self.nodes[current_id]

        while current_node.children:
            # Compute PUCT scores for children
            best_child_id = None
            best_score = -float('inf')

            parent_visits = current_node.visit_count

            for child_id in current_node.children:
                child = self.nodes[child_id]

                # Q-value (exploitation)
                q_value = child.average_reward

                # UCB (exploration)
                prior = 1.0 / len(current_node.children)  # Uniform prior
                ucb = self.config.exploration_constant * prior * math.sqrt(parent_visits) / (1 + child.visit_count)

                # PUCT score
                puct_score = q_value + ucb

                if puct_score > best_score:
                    best_score = puct_score
                    best_child_id = child_id

            # Traverse to best child
            current_id = best_child_id
            current_node = self.nodes[current_id]

        return current_node

    async def _expand_node(
        self,
        node: MCTSNode,
        problem: str,
        state: MCTSState
    ) -> list[MCTSNode]:
        """
        Expand node by generating N child code candidates.

        Args:
            node: Parent node to expand
            problem: Problem description
            state: MCTS state

        Returns:
            List of child nodes
        """
        children = []

        # Generate N variations
        for i in range(self.config.num_children_per_expansion):
            # Build prompt
            prompt = self._build_expansion_prompt(node, problem, i)

            # Generate code
            try:
                code = await self.model.generate(
                    messages=[
                        {"role": "system", "content": "You are a code generation expert."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=1024
                )

                # Clean code
                code = self._extract_code(code)

                # Create child node
                child_id = self._hash_code(code)

                # Skip if duplicate
                if child_id in self.nodes:
                    continue

                child = MCTSNode(
                    node_id=child_id,
                    parent_id=node.node_id,
                    code=code,
                    test_assertion=node.test_assertion
                )

                self.nodes[child_id] = child
                node.children.append(child_id)
                children.append(child)

            except Exception as e:
                # Log error but continue
                if self.worm_ledger and self.config.log_to_worm:
                    await self.worm_ledger.append({
                        "event": "mcts_expansion_error",
                        "node_id": node.node_id,
                        "error": str(e),
                        "iteration": state["iteration"]
                    })

        return children

    async def _evaluate_node(self, node: MCTSNode) -> float:
        """
        Evaluate node by executing code with test assertion.

        Args:
            node: Node to evaluate

        Returns:
            Reward in [0.0, 1.0]
        """
        # Build code with test
        full_code = f"{node.code}\n\n{node.test_assertion}\nprint('TESTS_PASSED')"

        # Execute in sandbox
        try:
            result: CodeExecutionResult = await self.sandbox.execute_python(full_code)

            # Check if tests passed
            if result.success and "TESTS_PASSED" in result.output:
                node.test_passed = True
                node.is_terminal = True
                reward = 1.0  # Perfect score
            elif result.success:
                # Code ran but tests didn't pass
                reward = 0.3
            else:
                # Execution failed
                reward = 0.1

            # Update node
            node.visit_count += 1
            node.total_reward += reward

            return reward

        except Exception:
            # Execution error
            node.visit_count += 1
            node.total_reward += 0.0
            return 0.0

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        """
        Backpropagate reward up the tree.

        Args:
            node: Starting node
            reward: Reward to propagate
        """
        current_id = node.node_id

        while current_id:
            current_node = self.nodes[current_id]

            # Update stats
            current_node.visit_count += 1
            current_node.total_reward += reward

            # Move to parent
            current_id = current_node.parent_id

    def _build_expansion_prompt(
        self,
        node: MCTSNode,
        problem: str,
        variation_index: int
    ) -> str:
        """Build prompt for expanding node"""

        if node.parent_id is None:
            # Expanding root
            return f"""Problem: {problem}

Generate a Python solution. Return only the code, no explanations.

Variation #{variation_index + 1} - Try a different approach."""

        else:
            # Expanding non-root
            parent = self.nodes[node.parent_id]

            return f"""Problem: {problem}

Previous solution:
```python
{parent.code}
```

This solution scored {parent.average_reward:.2f}.

Generate an IMPROVED solution. Try a different approach or fix issues.
Return only the code, no explanations.

Variation #{variation_index + 1}"""

    def _extract_code(self, text: str) -> str:
        """Extract code from markdown or plain text"""
        import re

        # Try to extract from ```python block
        match = re.search(r'```python\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to extract from ``` block
        match = re.search(r'```\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Return as-is
        return text.strip()

    def _generate_initial_code(self, problem: str) -> str:
        """Generate initial code stub"""
        return f"# Solution for: {problem}\n# TODO: Implement\n"

    def _hash_code(self, code: str) -> str:
        """Hash code to generate node ID"""
        return hashlib.sha256(code.encode()).hexdigest()[:16]

    async def _log_to_worm(
        self,
        problem: str,
        state: MCTSState,
        best_node: MCTSNode
    ) -> None:
        """Log MCTS search to WORM ledger"""
        if not self.worm_ledger:
            return

        await self.worm_ledger.append({
            "event": "mcts_search_complete",
            "problem": problem,
            "iterations": state["iteration"],
            "nodes_explored": len(self.nodes),
            "best_score": state["best_score"],
            "best_code": best_node.code,
            "test_passed": best_node.test_passed,
            "timestamp": datetime.utcnow().isoformat()
        })
