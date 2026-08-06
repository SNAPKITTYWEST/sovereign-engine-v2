"""
Layer 3: Pure Transformations
Part of SOVEREIGN PYTHON LLM ENGINE

Pure functions for data transformation.
No side effects, no I/O, deterministic outputs.
"""

import re
import json
from typing import Any
from datetime import datetime, timezone


# ==========================================
# JSON Parsing & Extraction
# ==========================================

def extract_json_schema(text: str) -> dict[str, Any] | None:
    """
    Extract and validate JSON from LLM output.

    Handles common LLM formatting issues:
    - Markdown code blocks (```json ... ```)
    - Extra whitespace
    - Trailing commas (attempts to fix)

    Args:
        text: Raw LLM response text

    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    # Strip markdown code block markers
    clean = re.sub(r'^```json\s*', '', text.strip(), flags=re.MULTILINE)
    clean = re.sub(r'\s*```$', '', clean, flags=re.MULTILINE)
    clean = clean.strip()

    # Attempt to fix trailing commas (common LLM error)
    clean = re.sub(r',\s*}', '}', clean)
    clean = re.sub(r',\s*]', ']', clean)

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return None


def extract_tag_content(text: str, tag: str) -> str | None:
    """
    Extract content from XML-style tags.

    Example:
        extract_tag_content("<thinking>foo</thinking>", "thinking") -> "foo"

    Args:
        text: Text containing tags
        tag: Tag name (without angle brackets)

    Returns:
        Tag content, or None if tag not found
    """
    pattern = f'<{tag}>(.*?)</{tag}>'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_all_tags(text: str, tag: str) -> list[str]:
    """
    Extract all occurrences of a tag.

    Args:
        text: Text containing tags
        tag: Tag name

    Returns:
        List of tag contents
    """
    pattern = f'<{tag}>(.*?)</{tag}>'
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches]


# ==========================================
# Tool Call Parsing
# ==========================================

def parse_tool_call(response: str) -> tuple[str, dict[str, Any]] | None:
    """
    Parse tool call from LLM response.

    Expected format:
        <tool_call name="function_name">
        {"param1": "value1", "param2": "value2"}
        </tool_call>

    Args:
        response: LLM response text

    Returns:
        (tool_name, parameters) tuple, or None if no tool call found
    """
    # Extract tool_call tag content
    match = re.search(
        r'<tool_call\s+name="([^"]+)">(.*?)</tool_call>',
        response,
        re.DOTALL
    )

    if not match:
        return None

    tool_name = match.group(1)
    params_json = match.group(2).strip()

    try:
        params = json.loads(params_json)
        return (tool_name, params)
    except json.JSONDecodeError:
        return None


def parse_multiple_tool_calls(response: str) -> list[tuple[str, dict[str, Any]]]:
    """
    Parse multiple tool calls from response.

    Returns:
        List of (tool_name, parameters) tuples
    """
    pattern = r'<tool_call\s+name="([^"]+)">(.*?)</tool_call>'
    matches = re.findall(pattern, response, re.DOTALL)

    tool_calls = []
    for tool_name, params_json in matches:
        try:
            params = json.loads(params_json.strip())
            tool_calls.append((tool_name, params))
        except json.JSONDecodeError:
            continue

    return tool_calls


# ==========================================
# Text Normalization
# ==========================================

def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    - Collapses multiple spaces to single space
    - Removes leading/trailing whitespace
    - Normalizes line endings to \n
    """
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)

    # Collapse multiple newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to max length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to append when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    truncate_at = max_length - len(suffix)
    return text[:truncate_at] + suffix


# ==========================================
# Code Extraction
# ==========================================

def extract_code_blocks(text: str, language: str | None = None) -> list[str]:
    """
    Extract code blocks from markdown.

    Args:
        text: Markdown text
        language: Filter by language (e.g., "python", "bash")

    Returns:
        List of code block contents
    """
    if language:
        pattern = f'```{language}\n(.*?)```'
    else:
        pattern = r'```(?:\w+)?\n(.*?)```'

    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches]


def extract_inline_code(text: str) -> list[str]:
    """
    Extract inline code (backtick-wrapped).

    Args:
        text: Text containing inline code

    Returns:
        List of inline code snippets
    """
    matches = re.findall(r'`([^`]+)`', text)
    return matches


# ==========================================
# Number Extraction & Parsing
# ==========================================

def extract_numbers(text: str) -> list[float]:
    """
    Extract all numbers from text.

    Handles:
    - Integers: 42
    - Floats: 3.14
    - Negative: -5
    - Scientific notation: 1e-5
    """
    pattern = r'-?\d+\.?\d*(?:[eE][+-]?\d+)?'
    matches = re.findall(pattern, text)
    return [float(m) for m in matches]


def parse_percentage(text: str) -> float | None:
    """
    Parse percentage from text.

    Example:
        "25%" -> 0.25
        "3.5%" -> 0.035

    Returns:
        Decimal percentage, or None if not found
    """
    match = re.search(r'(\d+\.?\d*)%', text)
    if match:
        return float(match.group(1)) / 100.0
    return None


# ==========================================
# Binary Encoding/Decoding
# ==========================================

def int_to_binary(value: int, bit_width: int = 16) -> str:
    """
    Convert integer to binary string.

    Args:
        value: Integer value
        bit_width: Number of bits (zero-padded)

    Returns:
        Binary string (e.g., "0000000000101010")
    """
    return bin(value)[2:].zfill(bit_width)


def binary_to_int(binary_str: str) -> int:
    """
    Convert binary string to integer.

    Args:
        binary_str: Binary string (e.g., "101010")

    Returns:
        Integer value
    """
    return int(binary_str, 2)


def hide_binary_in_phase(binary_str: str) -> list[float]:
    """
    Convert binary string to phase angles for quantum encoding.

    0 -> 0.0 (phase = 0)
    1 -> π (phase = 180°)

    Args:
        binary_str: Binary string

    Returns:
        List of phase angles in radians
    """
    import math
    return [0.0 if bit == '0' else math.pi for bit in binary_str]


# ==========================================
# Message Format Transformations
# ==========================================

def messages_to_prompt(messages: list[dict[str, str]]) -> str:
    """
    Convert message list to single prompt string.

    Format:
        System: <system message>

        User: <user message>

        Assistant: <assistant message>

    Args:
        messages: List of {role, content} dicts

    Returns:
        Formatted prompt string
    """
    lines = []
    for msg in messages:
        role = msg['role'].capitalize()
        content = msg['content']
        lines.append(f"{role}: {content}")

    return "\n\n".join(lines)


def prompt_to_messages(prompt: str) -> list[dict[str, str]]:
    """
    Parse prompt string back to message list.

    Inverse of messages_to_prompt.
    """
    messages = []
    current_role = None
    current_content = []

    for line in prompt.split('\n'):
        # Check if line starts with role indicator
        match = re.match(r'^(System|User|Assistant):\s*(.*)$', line)
        if match:
            # Save previous message
            if current_role:
                messages.append({
                    'role': current_role.lower(),
                    'content': '\n'.join(current_content).strip()
                })

            # Start new message
            current_role = match.group(1)
            current_content = [match.group(2)]
        else:
            # Continuation of current message
            if current_role:
                current_content.append(line)

    # Save last message
    if current_role:
        messages.append({
            'role': current_role.lower(),
            'content': '\n'.join(current_content).strip()
        })

    return messages


# ==========================================
# List/Dict Transformations
# ==========================================

def flatten_dict(d: dict[str, Any], parent_key: str = '', sep: str = '.') -> dict[str, Any]:
    """
    Flatten nested dictionary.

    Example:
        {"a": {"b": 1}} -> {"a.b": 1}

    Args:
        d: Nested dictionary
        parent_key: Parent key prefix
        sep: Separator for keys

    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: dict[str, Any], sep: str = '.') -> dict[str, Any]:
    """
    Unflatten dictionary (inverse of flatten_dict).

    Example:
        {"a.b": 1} -> {"a": {"b": 1}}
    """
    result: dict[str, Any] = {}
    for key, value in d.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def deduplicate_list(items: list[Any]) -> list[Any]:
    """
    Remove duplicates while preserving order.

    Args:
        items: List with potential duplicates

    Returns:
        Deduplicated list
    """
    seen = set()
    result = []
    for item in items:
        # Use string representation for hashability
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ==========================================
# Token Counting (Estimation)
# ==========================================

def estimate_token_count(text: str, chars_per_token: float = 4.0) -> int:
    """
    Estimate token count from text.

    This is a rough approximation. For exact counts, use tiktoken.

    Args:
        text: Input text
        chars_per_token: Average characters per token (4 for English)

    Returns:
        Estimated token count
    """
    return int(len(text) / chars_per_token)


# ==========================================
# Hash & ID Generation
# ==========================================

def generate_short_id(data: str, length: int = 8) -> str:
    """
    Generate short ID from data.

    Args:
        data: Input data
        length: ID length

    Returns:
        Hex ID string
    """
    from hashlib import sha256
    hash_digest = sha256(data.encode()).hexdigest()
    return hash_digest[:length]


# ==========================================
# Timestamp Formatting
# ==========================================

def format_timestamp(dt: datetime) -> str:
    """
    Format datetime as ISO 8601 UTC.

    Args:
        dt: Datetime object

    Returns:
        ISO 8601 string
    """
    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat()


def parse_timestamp(iso_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp.

    Args:
        iso_str: ISO 8601 string

    Returns:
        Datetime object (UTC)
    """
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ==========================================
# Validation Helpers
# ==========================================

def is_valid_json(text: str) -> bool:
    """Check if text is valid JSON"""
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def is_valid_url(text: str) -> bool:
    """Check if text is a valid URL"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(text) is not None


def is_valid_email(text: str) -> bool:
    """Check if text is a valid email"""
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return email_pattern.match(text) is not None
