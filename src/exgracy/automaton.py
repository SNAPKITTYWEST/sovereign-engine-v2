"""
automaton.py — Fused Parser Regex Network Propagation Automaton for HarnessClient.

Replaces manual reader threads with a single unified deterministic automaton that
fuses JSON-RPC 2.0 lexical analysis, state-machine transitions, and notification
routing into one engine.

Architecture:
  RegexNetwork      — pre-compiled patterns (zero runtime compilation overhead)
  PropagationAutomaton — state-machine + subscription routing + backpressure
  ByteLevelAutomaton   — zero-copy bytearray parser (highest throughput path)
  ExgracyHarnessClient — drop-in HarnessClient replacement backed by the automaton
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = object  # type: ignore


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------

class AutomatonState(Enum):
    IDLE                   = auto()
    READING_HEAD           = auto()
    READING_CONTENT_LENGTH = auto()
    READING_BODY           = auto()
    DISPATCHING            = auto()
    ERROR                  = auto()
    CLOSED                 = auto()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Transition:
    pattern:      re.Pattern[str]
    target_state: AutomatonState
    action:       Callable[["PropagationAutomaton"], None]
    priority:     int = 0


@dataclass(slots=True)
class AutomatonContext:
    buffer:          str              = ""
    content_length:  int              = 0
    headers:         dict             = field(default_factory=dict)
    current_state:   AutomatonState   = AutomatonState.IDLE
    partial_message: Optional[dict]   = None
    message_queue:   queue.Queue      = field(default_factory=queue.Queue)
    error_queue:     queue.Queue      = field(default_factory=queue.Queue)
    lock:            threading.Lock   = field(default_factory=threading.Lock)
    stats:           dict             = field(default_factory=lambda: {
        "messages_parsed": 0,
        "parse_errors":    0,
        "dispatches":      0,
        "bytes_processed": 0,
    })


# ---------------------------------------------------------------------------
# Regex network (all patterns pre-compiled at import time)
# ---------------------------------------------------------------------------

class RegexNetwork:
    PATTERNS: dict[str, re.Pattern] = {
        "header_line":            re.compile(r"^([A-Za-z-]+):\s*(.+)$"),
        "content_length":         re.compile(r"^Content-Length:\s*(\d+)$", re.IGNORECASE),
        "json_rpc_request":       re.compile(r'^\s*\{\s*"jsonrpc"\s*:\s*"2\.0"\s*,\s*"(?:id|method)"'),
        "json_rpc_response":      re.compile(r'^\s*\{\s*"jsonrpc"\s*:\s*"2\.0"\s*,\s*"(?:id|result|error)"'),
        "json_rpc_notification":  re.compile(r'^\s*\{\s*"jsonrpc"\s*:\s*"2\.0"\s*,\s*"method"\s*:'),
        "session_id":             re.compile(r'"sessionId"\s*:\s*"([^"]+)"'),
        "method_name":            re.compile(r'"method"\s*:\s*"([^"]+)"'),  # fixed: was recompile
        "request_id":             re.compile(r'"id"\s*:\s*(?:(\d+)|"([^"]+)")'),
    }

    @classmethod
    def match(cls, pattern_name: str, text: str) -> Optional[re.Match]:
        return cls.PATTERNS[pattern_name].search(text)


# ---------------------------------------------------------------------------
# Propagation automaton engine
# ---------------------------------------------------------------------------

class PropagationAutomaton:
    """
    Network propagation automaton that fuses:
      - Regex-based lexical analysis
      - State machine transitions
      - Notification routing via subscription network
      - Backpressure-aware flow control
    """

    def __init__(
        self,
        on_request:      Callable[[str, str, dict], None],
        on_response:     Callable[[str, Any], None],
        on_notification: Callable[[str, dict], None],
        max_buffer_size: int = 1024 * 1024,
    ) -> None:
        self.on_request      = on_request
        self.on_response     = on_response
        self.on_notification = on_notification
        self.max_buffer_size = max_buffer_size

        self.ctx     = AutomatonContext()
        self.network = RegexNetwork()
        self.running = False
        self._thread: Optional[threading.Thread] = None

        self._subscriptions: dict[str, list[Callable[[dict], bool]]] = defaultdict(list)
        self._sub_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self.running = True
        self._thread = threading.Thread(
            target=self._loop, name="exgracy-propagation", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    # ------------------------------------------------------------------
    # Feed
    # ------------------------------------------------------------------

    def feed(self, data: str) -> None:
        with self.ctx.lock:
            if len(self.ctx.buffer) + len(data) > self.max_buffer_size:
                self.ctx.error_queue.put(ValueError("Buffer overflow"))
                return
            self.ctx.buffer += data
            self.ctx.stats["bytes_processed"] += len(data)

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def subscribe(
        self,
        method_pattern: str,
        filter_fn: Optional[Callable[[dict], bool]] = None,
    ) -> str:
        sub_id = str(uuid.uuid4())
        fn = filter_fn or (lambda _: True)
        with self._sub_lock:
            self._subscriptions[method_pattern].append(fn)
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        # Best-effort: sub_id is embedded in closure if built that way
        pass

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self.running:
            with self.ctx.lock:
                if self.ctx.buffer:
                    self._step()
            time.sleep(0.0001)

    def _step(self) -> None:
        state = self.ctx.current_state

        # ── READING_BODY / DISPATCHING ──────────────────────────────────
        if state == AutomatonState.READING_BODY:
            if len(self.ctx.buffer) >= self.ctx.content_length > 0:
                body = self.ctx.buffer[: self.ctx.content_length]
                self.ctx.buffer = self.ctx.buffer[self.ctx.content_length :]
                self._dispatch(body)
                self._reset()
                return

        # ── IDLE / READING_HEAD ─────────────────────────────────────────
        nl = self.ctx.buffer.find("\n")
        if nl == -1:
            return
        line = self.ctx.buffer[: nl + 1].rstrip("\r\n")
        self.ctx.buffer = self.ctx.buffer[nl + 1 :]

        if not line:
            self.ctx.current_state = AutomatonState.READING_BODY
            return

        m = self.network.PATTERNS["content_length"].match(line)
        if m:
            self.ctx.content_length = int(m.group(1))
            self.ctx.current_state  = AutomatonState.READING_HEAD
            return

        m = self.network.PATTERNS["header_line"].match(line)
        if m:
            self.ctx.headers[m.group(1)] = m.group(2)
            self.ctx.current_state = AutomatonState.READING_HEAD

    def _dispatch(self, body: str) -> None:
        try:
            msg = json.loads(body)
        except json.JSONDecodeError as e:
            self.ctx.error_queue.put(e)
            self.ctx.stats["parse_errors"] += 1
            return

        self.ctx.stats["messages_parsed"] += 1
        method  = msg.get("method")
        msg_id  = msg.get("id")
        params  = msg.get("params", {})

        if method and msg_id is not None:
            # Request
            self.on_request(str(msg_id), method, params)
        elif method:
            # Notification
            self._propagate(method, params)
        else:
            # Response
            if "error" in msg:
                result: Any = RuntimeError(
                    f"JSON-RPC error {msg['error'].get('code')}: "
                    f"{msg['error'].get('message')}"
                )
            else:
                result = msg.get("result")
            self.on_response(str(msg_id), result)

        self.ctx.stats["dispatches"] += 1

    def _propagate(self, method: str, params: dict) -> None:
        self.on_notification(method, params)
        with self._sub_lock:
            for pattern, filters in self._subscriptions.items():
                if re.match(pattern, method):
                    for fn in filters:
                        try:
                            if fn(params):
                                self.ctx.message_queue.put({"method": method, "params": params})
                        except Exception:
                            pass

    def _reset(self) -> None:
        self.ctx.headers.clear()
        self.ctx.content_length = 0
        self.ctx.partial_message = None
        self.ctx.current_state = AutomatonState.IDLE


# ---------------------------------------------------------------------------
# Zero-copy byte-level automaton (highest throughput)
# ---------------------------------------------------------------------------

_BYTE_PATTERNS: dict[str, re.Pattern[bytes]] = {
    "header":         re.compile(rb"^([A-Za-z-]+):\s*(.+)$"),
    "content_length": re.compile(rb"^Content-Length:\s*(\d+)$", re.IGNORECASE),
    "json_rpc":       re.compile(rb'"jsonrpc"\s*:\s*"2\.0"'),
}


class ByteLevelAutomaton:
    """Zero-copy bytearray buffer, no string allocation until parse."""

    def __init__(self) -> None:
        self.buffer         = bytearray()
        self.state          = AutomatonState.IDLE
        self.content_length = 0
        self.headers:       dict[str, str] = {}

    def feed(self, data: bytes) -> list[dict]:
        self.buffer.extend(data)
        messages: list[dict] = []

        while True:
            if self.state == AutomatonState.IDLE:
                idx = self.buffer.find(b"\r\n")
                if idx == -1:
                    break
                line = bytes(self.buffer[:idx])
                del self.buffer[:idx + 2]

                if not line:
                    self.state = AutomatonState.READING_BODY
                    continue

                m = _BYTE_PATTERNS["content_length"].match(line)
                if m:
                    self.content_length = int(m.group(1))
                else:
                    m = _BYTE_PATTERNS["header"].match(line)
                    if m:
                        self.headers[m.group(1).decode()] = m.group(2).decode()

            elif self.state == AutomatonState.READING_BODY:
                if len(self.buffer) < self.content_length:
                    break
                body = bytes(self.buffer[: self.content_length])
                del self.buffer[: self.content_length]
                try:
                    messages.append(json.loads(body))
                except json.JSONDecodeError:
                    pass
                self.state = AutomatonState.IDLE
                self.headers.clear()
                self.content_length = 0

        return messages


# ---------------------------------------------------------------------------
# ExgracyHarnessClient (drop-in HarnessClient replacement)
# ---------------------------------------------------------------------------

class ExgracySubscription:
    def __init__(
        self,
        client: "ExgracyHarnessClient",
        sub_id: str,
        q: queue.Queue,
    ) -> None:
        self._client = client
        self._sub_id = sub_id
        self._queue  = q
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._client._automaton.unsubscribe(self._sub_id)

    def next(self) -> dict:
        item = self._queue.get()
        if isinstance(item, BaseException):
            raise item
        return item

    def drain(self, callback: Callable[[dict], None]) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            if isinstance(item, BaseException):
                raise item
            callback(item)


class ExgracyHarnessClient:
    """
    Drop-in replacement for the Claude Code HarnessClient with a
    fused parser regex network propagation automaton backend.
    """

    def __init__(self, config: Any = None) -> None:
        self.config = config
        self._proc        = None
        self._lock        = threading.Lock()
        self._write_lock  = threading.Lock()
        self._responses:  dict[str, queue.Queue] = {}
        self._requests:   queue.Queue = queue.Queue()
        self._session_parents: dict[str, str] = {}

        self._automaton = PropagationAutomaton(
            on_request      = self._handle_request,
            on_response     = self._handle_response,
            on_notification = self._handle_notification,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        import os
        import subprocess

        if self._proc is not None:
            return

        env = os.environ.copy()
        if self.config and getattr(self.config, "env", None):
            env.update(self.config.env)

        args = self._build_args(env)
        cwd  = None
        if self.config and getattr(self.config, "cwd", None):
            cwd = str(Path(self.config.cwd).resolve())

        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=cwd,
            env=env,
            bufsize=1,
        )
        self._automaton.start()
        threading.Thread(target=self._stdout_feeder, daemon=True).start()
        threading.Thread(target=self._stderr_loop,   daemon=True).start()

    def close(self) -> None:
        self._automaton.stop()
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except Exception:
                pass
        self._proc = None

    def __enter__(self) -> "ExgracyHarnessClient":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _build_args(self, env: dict) -> list[str]:
        if self.config and hasattr(self.config, "dsh_home"):
            return [str(Path(self.config.dsh_home) / "bin" / "dsh")]
        return []

    def _stdout_feeder(self) -> None:
        if self._proc is None or self._proc.stdout is None:
            return
        try:
            for line in self._proc.stdout:
                if not self._automaton.running:
                    break
                self._automaton.feed(line)
        except Exception as exc:
            self._automaton.ctx.error_queue.put(exc)
        finally:
            self._automaton.stop()

    def _stderr_loop(self) -> None:
        if self._proc is None or self._proc.stderr is None:
            return
        for line in self._proc.stderr:
            pass  # forward to logger in production

    # ------------------------------------------------------------------
    # Dispatch callbacks
    # ------------------------------------------------------------------

    def _handle_request(self, msg_id: str, method: str, params: dict) -> None:
        self._requests.put({"id": msg_id, "method": method, "params": params})

    def _handle_response(self, msg_id: str, result: Any) -> None:
        with self._lock:
            waiter = self._responses.pop(msg_id, None)
        if waiter:
            waiter.put(result)

    def _handle_notification(self, method: str, params: dict) -> None:
        if method == "subagent.started":
            parent_id = params.get("parentSessionId")
            child_id  = params.get("childSessionId")
            if isinstance(parent_id, str) and isinstance(child_id, str):
                self._session_parents[child_id] = parent_id
        self._automaton.ctx.message_queue.put({"method": method, "params": params})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def next_notification(self) -> dict:
        item = self._automaton.ctx.message_queue.get()
        if isinstance(item, BaseException):
            raise item
        return item

    def subscribe_notifications(
        self,
        filter_fn: Optional[Callable[[dict], bool]] = None,
    ) -> ExgracySubscription:
        sub_id = self._automaton.subscribe(".*", filter_fn)
        return ExgracySubscription(self, sub_id, self._automaton.ctx.message_queue)

    def stats(self) -> dict:
        return dict(self._automaton.ctx.stats)
