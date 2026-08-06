"""
Tool Loader
Part of SOVEREIGN PYTHON LLM ENGINE

Auto-registers all available tools into the registry.
"""

from pathlib import Path
from .registry import ToolRegistry, ToolDefinition, RiskClass, ApprovalPolicy


# ==========================================
# FILESYSTEM TOOLS
# ==========================================

def register_filesystem_tools(registry: ToolRegistry) -> None:

    async def read_file(params: dict) -> dict:
        path = Path(params["path"])
        if not path.exists():
            return {"error": f"File not found: {path}"}
        try:
            content = path.read_text(encoding='utf-8')
            return {"content": content, "path": str(path), "size": len(content)}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="filesystem.read",
        version="1.0.0",
        title="Read File",
        description="Read contents of a file",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=5000,
        handler=read_file,
        tags=["filesystem", "read"]
    ))

    async def write_file(params: dict) -> dict:
        path = Path(params["path"])
        content = params["content"]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return {"success": True, "path": str(path), "bytes_written": len(content)}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="filesystem.write",
        version="1.0.0",
        title="Write File",
        description="Write content to a file",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=10000,
        handler=write_file,
        tags=["filesystem", "write"]
    ))

    async def list_directory(params: dict) -> dict:
        path = Path(params["path"])
        if not path.exists():
            return {"error": f"Path not found: {path}"}
        if not path.is_dir():
            return {"error": f"Not a directory: {path}"}
        try:
            files = []
            for item in path.iterdir():
                files.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "is_file": item.is_file(),
                    "size": item.stat().st_size if item.is_file() else 0
                })
            return {"files": files, "count": len(files), "path": str(path)}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="filesystem.list",
        version="1.0.0",
        title="List Directory",
        description="List files in a directory",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=5000,
        handler=list_directory,
        tags=["filesystem", "read"]
    ))

    async def delete_file(params: dict) -> dict:
        path = Path(params["path"])
        if not path.exists():
            return {"error": f"File not found: {path}"}
        try:
            path.unlink()
            return {"success": True, "path": str(path)}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="filesystem.delete",
        version="1.0.0",
        title="Delete File",
        description="Delete a file (irreversible)",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        output_schema=None,
        risk_class=RiskClass.DESTRUCTIVE_LOCAL,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=5000,
        handler=delete_file,
        tags=["filesystem", "delete"]
    ))

    async def move_file(params: dict) -> dict:
        import shutil
        src = Path(params["source"])
        dst = Path(params["destination"])
        if not src.exists():
            return {"error": f"Source not found: {src}"}
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {"success": True, "source": str(src), "destination": str(dst)}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="filesystem.move",
        version="1.0.0",
        title="Move File",
        description="Move or rename a file",
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"}
            },
            "required": ["source", "destination"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=5000,
        handler=move_file,
        tags=["filesystem", "write"]
    ))

    async def search_files(params: dict) -> dict:
        import fnmatch
        root = Path(params["path"])
        pattern = params["pattern"]
        recursive = params.get("recursive", True)

        if not root.exists():
            return {"error": f"Path not found: {root}"}

        try:
            matches = []
            glob_pattern = f"**/{pattern}" if recursive else pattern
            for match in root.glob(glob_pattern):
                matches.append({
                    "path": str(match),
                    "name": match.name,
                    "size": match.stat().st_size if match.is_file() else 0
                })
            return {"matches": matches, "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="filesystem.search",
        version="1.0.0",
        title="Search Files",
        description="Search for files by pattern (e.g. '*.py', '*.json')",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string"},
                "recursive": {"type": "boolean", "default": True}
            },
            "required": ["path", "pattern"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=search_files,
        tags=["filesystem", "search"]
    ))


# ==========================================
# CODE TOOLS
# ==========================================

def register_code_tools(registry: ToolRegistry) -> None:

    async def execute_python(params: dict) -> dict:
        code = params["code"]
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="code.execute_python",
        version="1.0.0",
        title="Execute Python",
        description="Execute Python code in subprocess",
        input_schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"]
        },
        output_schema=None,
        risk_class=RiskClass.DESTRUCTIVE_LOCAL,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=True,
        timeout_ms=30000,
        handler=execute_python,
        tags=["code", "execution"]
    ))

    async def run_shell(params: dict) -> dict:
        import subprocess
        command = params["command"]
        cwd = params.get("cwd", None)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=cwd
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="code.shell",
        version="1.0.0",
        title="Run Shell Command",
        description="Run a shell command",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"}
            },
            "required": ["command"]
        },
        output_schema=None,
        risk_class=RiskClass.DESTRUCTIVE_LOCAL,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=True,
        timeout_ms=60000,
        handler=run_shell,
        tags=["code", "shell", "execution"]
    ))


# ==========================================
# GIT TOOLS
# ==========================================

def register_git_tools(registry: ToolRegistry) -> None:
    from .git.operations import (
        git_status_tool, git_commit_tool,
        git_push_tool, git_log_tool
    )
    from .git.operations import GitOperations

    async def git_status(params: dict) -> dict:
        try:
            return await git_status_tool(params["repo_path"])
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.status",
        version="1.0.0",
        title="Git Status",
        description="Get git repository status (branch, modified, untracked files)",
        input_schema={
            "type": "object",
            "properties": {"repo_path": {"type": "string"}},
            "required": ["repo_path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=git_status,
        tags=["git", "read"]
    ))

    async def git_diff(params: dict) -> dict:
        try:
            git = GitOperations(Path(params["repo_path"]))
            diff = await git.diff(params.get("file_path"))
            return {"diff": diff}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.diff",
        version="1.0.0",
        title="Git Diff",
        description="Show changes in working directory",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "file_path": {"type": "string"}
            },
            "required": ["repo_path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=git_diff,
        tags=["git", "read"]
    ))

    async def git_log(params: dict) -> dict:
        try:
            return await git_log_tool(params["repo_path"], params.get("max_count", 10))
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.log",
        version="1.0.0",
        title="Git Log",
        description="Get commit history",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "max_count": {"type": "integer", "default": 10}
            },
            "required": ["repo_path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=git_log,
        tags=["git", "read"]
    ))

    async def git_commit(params: dict) -> dict:
        try:
            return await git_commit_tool(
                params["repo_path"],
                params["message"],
                params.get("files")
            )
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.commit",
        version="1.0.0",
        title="Git Commit",
        description="Stage files and create a commit",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "message": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["repo_path", "message"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=15000,
        handler=git_commit,
        tags=["git", "write"]
    ))

    async def git_push(params: dict) -> dict:
        try:
            return await git_push_tool(params["repo_path"], params.get("remote", "origin"))
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.push",
        version="1.0.0",
        title="Git Push",
        description="Push commits to remote repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "remote": {"type": "string", "default": "origin"}
            },
            "required": ["repo_path"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_REMOTE_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=30000,
        handler=git_push,
        tags=["git", "write", "remote"]
    ))

    async def git_pull(params: dict) -> dict:
        try:
            git = GitOperations(Path(params["repo_path"]))
            await git.pull(params.get("remote", "origin"), params.get("branch"))
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.pull",
        version="1.0.0",
        title="Git Pull",
        description="Pull commits from remote repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "remote": {"type": "string", "default": "origin"},
                "branch": {"type": "string"}
            },
            "required": ["repo_path"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=30000,
        handler=git_pull,
        tags=["git", "write", "remote"]
    ))

    async def git_branch_list(params: dict) -> dict:
        try:
            git = GitOperations(Path(params["repo_path"]))
            branches = await git.branch_list()
            return {"branches": branches}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.branch_list",
        version="1.0.0",
        title="List Git Branches",
        description="List all branches in repository",
        input_schema={
            "type": "object",
            "properties": {"repo_path": {"type": "string"}},
            "required": ["repo_path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=git_branch_list,
        tags=["git", "read"]
    ))

    async def git_branch_create(params: dict) -> dict:
        try:
            git = GitOperations(Path(params["repo_path"]))
            await git.branch_create(params["name"], params.get("checkout", False))
            return {"success": True, "branch": params["name"]}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.branch_create",
        version="1.0.0",
        title="Create Git Branch",
        description="Create a new branch",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "name": {"type": "string"},
                "checkout": {"type": "boolean", "default": False}
            },
            "required": ["repo_path", "name"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=git_branch_create,
        tags=["git", "write"]
    ))

    async def git_checkout(params: dict) -> dict:
        try:
            git = GitOperations(Path(params["repo_path"]))
            await git.checkout(params["branch"])
            return {"success": True, "branch": params["branch"]}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.checkout",
        version="1.0.0",
        title="Git Checkout",
        description="Checkout a branch",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "branch": {"type": "string"}
            },
            "required": ["repo_path", "branch"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=10000,
        handler=git_checkout,
        tags=["git", "write"]
    ))

    async def git_clone(params: dict) -> dict:
        try:
            from git import Repo
            import asyncio
            target = Path(params["target_path"])
            target.mkdir(parents=True, exist_ok=True)

            def _clone():
                Repo.clone_from(params["url"], target)

            await asyncio.to_thread(_clone)
            return {"success": True, "path": str(target)}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="git.clone",
        version="1.0.0",
        title="Git Clone",
        description="Clone a remote repository",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "target_path": {"type": "string"}
            },
            "required": ["url", "target_path"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=60000,
        handler=git_clone,
        tags=["git", "write", "remote"]
    ))


# ==========================================
# DATABASE TOOLS
# ==========================================

def register_database_tools(registry: ToolRegistry) -> None:
    from .database.sqlite import sqlite_query_tool, sqlite_execute_tool

    async def sqlite_query(params: dict) -> dict:
        try:
            return await sqlite_query_tool(
                params["db_path"],
                params["sql"],
                params.get("params")
            )
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="database.sqlite_query",
        version="1.0.0",
        title="SQLite Query",
        description="Execute a SELECT query on a SQLite database",
        input_schema={
            "type": "object",
            "properties": {
                "db_path": {"type": "string"},
                "sql": {"type": "string"},
                "params": {"type": "array"}
            },
            "required": ["db_path", "sql"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=15000,
        handler=sqlite_query,
        tags=["database", "sqlite", "read"]
    ))

    async def sqlite_execute(params: dict) -> dict:
        try:
            return await sqlite_execute_tool(
                params["db_path"],
                params["sql"],
                params.get("params")
            )
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="database.sqlite_execute",
        version="1.0.0",
        title="SQLite Execute",
        description="Execute an INSERT/UPDATE/DELETE on a SQLite database",
        input_schema={
            "type": "object",
            "properties": {
                "db_path": {"type": "string"},
                "sql": {"type": "string"},
                "params": {"type": "array"}
            },
            "required": ["db_path", "sql"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_LOCAL_WRITE,
        approval_policy=ApprovalPolicy.USER_CONFIRMATION,
        sandbox_required=False,
        timeout_ms=15000,
        handler=sqlite_execute,
        tags=["database", "sqlite", "write"]
    ))

    async def sqlite_list_tables(params: dict) -> dict:
        try:
            from .database.sqlite import SQLiteOperations
            ops = SQLiteOperations(Path(params["db_path"]))
            tables = await ops.list_tables()
            return {"tables": tables}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="database.sqlite_list_tables",
        version="1.0.0",
        title="SQLite List Tables",
        description="List all tables in a SQLite database",
        input_schema={
            "type": "object",
            "properties": {"db_path": {"type": "string"}},
            "required": ["db_path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=5000,
        handler=sqlite_list_tables,
        tags=["database", "sqlite", "read"]
    ))


# ==========================================
# DOCUMENT TOOLS
# ==========================================

def register_document_tools(registry: ToolRegistry) -> None:

    async def parse_pdf(params: dict) -> dict:
        try:
            from .documents.pdf import PDFParser
            parser = PDFParser()
            doc = await parser.parse(Path(params["path"]))
            return {
                "text": doc.text,
                "pages": doc.pages,
                "metadata": doc.metadata
            }
        except ImportError:
            return {"error": "pypdf not installed. Run: pip install pypdf"}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="documents.parse_pdf",
        version="1.0.0",
        title="Parse PDF",
        description="Extract text and metadata from a PDF file",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=30000,
        handler=parse_pdf,
        tags=["documents", "pdf", "read"]
    ))

    async def parse_docx(params: dict) -> dict:
        try:
            from .documents.docx import DOCXParser
            parser = DOCXParser()
            doc = await parser.parse(Path(params["path"]))
            return {
                "text": doc.text,
                "paragraphs": doc.paragraphs,
                "metadata": doc.metadata
            }
        except ImportError:
            return {"error": "python-docx not installed. Run: pip install python-docx"}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="documents.parse_docx",
        version="1.0.0",
        title="Parse DOCX",
        description="Extract text from a Microsoft Word document",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=15000,
        handler=parse_docx,
        tags=["documents", "docx", "read"]
    ))

    async def parse_markdown(params: dict) -> dict:
        try:
            from .documents.markdown import MarkdownParser
            parser = MarkdownParser()
            doc = await parser.parse(Path(params["path"]))
            return {
                "text": doc.text,
                "sections": doc.sections,
                "links": doc.links,
                "code_blocks": doc.code_blocks,
                "metadata": doc.metadata
            }
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="documents.parse_markdown",
        version="1.0.0",
        title="Parse Markdown",
        description="Parse a Markdown file and extract sections, links, code blocks",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=parse_markdown,
        tags=["documents", "markdown", "read"]
    ))

    async def parse_html(params: dict) -> dict:
        try:
            from .documents.html import HTMLParser
            parser = HTMLParser()
            doc = await parser.parse(Path(params["path"]))
            return {
                "text": doc.text,
                "title": doc.title,
                "links": doc.links,
                "metadata": doc.metadata
            }
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="documents.parse_html",
        version="1.0.0",
        title="Parse HTML",
        description="Extract text and links from an HTML file",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=parse_html,
        tags=["documents", "html", "read"]
    ))


# ==========================================
# WEB TOOLS (decorator-based, auto-register on import)
# ==========================================

def register_web_tools(registry: ToolRegistry) -> None:
    # web.search, web.fetch, web.extract use @tool decorator
    # importing the module auto-registers them into the global registry
    # we then copy them into the provided registry
    try:
        import src.tools.web.search as _  # noqa: F401
        from .registry import get_global_registry
        global_reg = get_global_registry()
        for tool_id in ["web.search", "web.fetch", "web.extract"]:
            if global_reg.has(tool_id) and not registry.has(tool_id):
                registry.register(global_reg.get(tool_id))
    except ImportError as e:
        print(f"Note: web tools require httpx + beautifulsoup4: {e}")
    except Exception as e:
        print(f"Note: web tools skipped: {e}")


# ==========================================
# EMBEDDINGS TOOLS (decorator-based)
# ==========================================

def register_embeddings_tools(registry: ToolRegistry) -> None:
    try:
        import src.tools.embeddings.encode as _  # noqa: F401
        from .registry import get_global_registry
        global_reg = get_global_registry()
        for tool_id in ["embeddings.encode_text", "embeddings.similarity"]:
            if global_reg.has(tool_id) and not registry.has(tool_id):
                registry.register(global_reg.get(tool_id))
    except Exception as e:
        print(f"Note: embeddings tools skipped: {e}")


# ==========================================
# AUDIO TOOLS
# ==========================================

def register_audio_tools(registry: ToolRegistry) -> None:

    async def transcribe_audio(params: dict) -> dict:
        try:
            from .audio.transcribe import AudioTranscriber
            transcriber = AudioTranscriber(
                provider=params.get("provider", "openai"),
                model=params.get("model", "whisper-1")
            )
            result = await transcriber.transcribe(
                Path(params["audio_path"]),
                language=params.get("language")
            )
            return {
                "text": result.text,
                "language": result.language,
                "duration": result.duration
            }
        except ImportError:
            return {"error": "openai not installed. Run: pip install openai"}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="audio.transcribe",
        version="1.0.0",
        title="Transcribe Audio",
        description="Transcribe audio file to text using Whisper",
        input_schema={
            "type": "object",
            "properties": {
                "audio_path": {"type": "string"},
                "language": {"type": "string"},
                "provider": {"type": "string", "default": "openai"},
                "model": {"type": "string", "default": "whisper-1"}
            },
            "required": ["audio_path"]
        },
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_REMOTE,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=120000,
        handler=transcribe_audio,
        tags=["audio", "transcribe", "whisper"]
    ))

    async def synthesize_speech(params: dict) -> dict:
        try:
            from .audio.synthesize import AudioSynthesizer
            synth = AudioSynthesizer(provider=params.get("provider", "openai"))
            result = await synth.synthesize(
                text=params["text"],
                voice=params.get("voice", "alloy"),
                speed=params.get("speed", 1.0)
            )
            output_path = params.get("output_path", "output.mp3")
            Path(output_path).write_bytes(result.audio_bytes)
            return {"success": True, "output_path": output_path, "format": result.format}
        except ImportError:
            return {"error": "openai not installed. Run: pip install openai"}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        tool_id="audio.synthesize",
        version="1.0.0",
        title="Synthesize Speech",
        description="Convert text to speech (TTS)",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "voice": {"type": "string", "default": "alloy"},
                "speed": {"type": "number", "default": 1.0},
                "output_path": {"type": "string"},
                "provider": {"type": "string", "default": "openai"}
            },
            "required": ["text"]
        },
        output_schema=None,
        risk_class=RiskClass.REVERSIBLE_REMOTE_WRITE,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=60000,
        handler=synthesize_speech,
        tags=["audio", "tts", "speech"]
    ))


# ==========================================
# PYTORCH TOOLS
# ==========================================

def register_pytorch_tools(registry: ToolRegistry) -> None:
    from .ml.pytorch import tensor_operation, check_cuda

    async def pytorch_tensor_op(params: dict) -> dict:
        return await tensor_operation(params)

    registry.register(ToolDefinition(
        tool_id="pytorch.tensor_operation",
        version="1.0.0",
        title="PyTorch Tensor Operation",
        description="Execute PyTorch tensor operations (add, matmul, softmax, relu, etc)",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {"type": "string"},
                "tensor_a": {"type": "array"},
                "tensor_b": {"type": "array"},
                "dim": {"type": "integer"}
            },
            "required": ["operation", "tensor_a"]
        },
        output_schema=None,
        risk_class=RiskClass.PURE_COMPUTATION,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=10000,
        handler=pytorch_tensor_op,
        tags=["pytorch", "ml", "tensor"]
    ))

    async def pytorch_cuda_check(params: dict) -> dict:
        return await check_cuda(params)

    registry.register(ToolDefinition(
        tool_id="pytorch.check_cuda",
        version="1.0.0",
        title="Check CUDA Availability",
        description="Check if CUDA is available and list GPU devices",
        input_schema={"type": "object", "properties": {}},
        output_schema=None,
        risk_class=RiskClass.READ_ONLY_LOCAL,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False,
        timeout_ms=5000,
        handler=pytorch_cuda_check,
        tags=["pytorch", "ml", "cuda"]
    ))


# ==========================================
# MASTER LOADER
# ==========================================

def load_all_tools(registry: ToolRegistry) -> int:
    """
    Load all available tools into registry.

    Returns:
        Number of tools loaded
    """
    count_before = len(registry.tools)

    # Core tools — always available
    register_filesystem_tools(registry)
    register_code_tools(registry)

    # Git tools (requires gitpython)
    try:
        register_git_tools(registry)
    except ImportError:
        print("Note: gitpython not installed, skipping git.* tools. Run: pip install gitpython")

    # Database tools (stdlib sqlite3, always available)
    register_database_tools(registry)

    # Document tools (optional deps)
    register_document_tools(registry)

    # Web tools (requires httpx + beautifulsoup4)
    register_web_tools(registry)

    # Embeddings tools (optional)
    register_embeddings_tools(registry)

    # Audio tools (requires openai)
    register_audio_tools(registry)

    # PyTorch tools (optional)
    try:
        register_pytorch_tools(registry)
    except ImportError:
        print("Note: torch not installed, skipping pytorch.* tools. Run: pip install torch")

    count_after = len(registry.tools)
    loaded = count_after - count_before

    print(f"OK: Loaded {loaded} tools into registry")
    return loaded
