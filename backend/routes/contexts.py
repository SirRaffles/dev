"""
Context folder management API routes.
Browse, create, edit context folders and markdown files on iCloud Drive.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import ICLOUD_BASE_PATH

logger = logging.getLogger(__name__)
router = APIRouter(tags=["contexts"])

CONTEXTS_DIR = ICLOUD_BASE_PATH / "contexts"


class FolderCreateRequest(BaseModel):
    path: str
    description: str = ""


class FileWriteRequest(BaseModel):
    content: str


def _safe_path(user_path: str) -> Path:
    """Resolve a user-provided path safely within CONTEXTS_DIR."""
    # Reject raw `..` before resolving (audit #4)
    if ".." in user_path.split("/") or ".." in user_path.split("\\"):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    resolved = (CONTEXTS_DIR / user_path).resolve()
    if not str(resolved).startswith(str(CONTEXTS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return resolved


def _folder_to_dict(folder: Path, base: Path) -> dict:
    """Convert a folder Path to a response dict."""
    rel = str(folder.relative_to(base))
    meta_path = folder / "_meta.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    children = [f for f in folder.iterdir() if f.is_dir() and not f.name.startswith(".")]
    files = [f for f in folder.iterdir() if f.is_file() and f.name != "_meta.json"]

    return {
        "name": folder.name,
        "path": rel,
        "description": meta.get("description", ""),
        "created_at": meta.get("created_at", ""),
        "children_count": len(children),
        "files_count": len(files),
    }


def _build_tree(folder: Path, base: Path) -> dict:
    """Recursively build a folder tree."""
    node = _folder_to_dict(folder, base)
    children = sorted(
        [f for f in folder.iterdir() if f.is_dir() and not f.name.startswith(".")],
        key=lambda f: f.name.lower(),
    )
    node["children"] = [_build_tree(c, base) for c in children]
    return node


@router.get("/contexts")
async def list_contexts(path: str = ""):
    """List context folders and files at a given path."""
    target = _safe_path(path) if path else CONTEXTS_DIR
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    folders = sorted(
        [f for f in target.iterdir() if f.is_dir() and not f.name.startswith(".")],
        key=lambda f: f.name.lower(),
    )
    files = sorted(
        [f for f in target.iterdir() if f.is_file() and f.name != "_meta.json"],
        key=lambda f: f.name.lower(),
    )

    return {
        "current_path": path,
        "folders": [_folder_to_dict(f, CONTEXTS_DIR) for f in folders],
        "files": [
            {
                "name": f.name,
                "path": str(f.relative_to(CONTEXTS_DIR)),
                "size_bytes": f.stat().st_size,
                "modified_at": f.stat().st_mtime,
            }
            for f in files
        ],
    }


@router.get("/contexts/tree")
async def get_context_tree():
    """Return the full nested tree of all context folders."""
    if not CONTEXTS_DIR.exists():
        return {"tree": {"name": "contexts", "path": "", "children": []}}

    tree = _build_tree(CONTEXTS_DIR, CONTEXTS_DIR)
    tree["name"] = "contexts"
    tree["path"] = ""
    return {"tree": tree}


@router.post("/contexts/folders")
async def create_context_folder(req: FolderCreateRequest):
    """Create a new context folder."""
    path = req.path.strip().strip("/")
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")

    target = _safe_path(path)
    if target.exists():
        raise HTTPException(status_code=409, detail="Folder already exists")

    target.mkdir(parents=True, exist_ok=True)

    # Create _meta.json
    from datetime import datetime
    meta = {
        "created_at": datetime.now().isoformat(),
        "description": req.description,
        "tags": [],
    }
    (target / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Create empty context.md
    (target / "context.md").write_text(
        f"# {target.name}\n\n*Add context notes here.*\n",
        encoding="utf-8",
    )

    return {"path": path, "created": True}


@router.delete("/contexts/folders/{path:path}")
async def delete_context_folder(path: str):
    """Delete a context folder."""
    target = _safe_path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Folder not found")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    import shutil
    try:
        shutil.rmtree(target)
    except OSError:
        logger.error("Could not delete context folder %s", target, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"status": "deleted", "path": path}


@router.get("/contexts/files/{path:path}")
async def read_context_file(path: str):
    """Read a markdown file from a context folder."""
    target = _safe_path(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    content = target.read_text(encoding="utf-8")
    return {"content": content, "path": path}


@router.put("/contexts/files/{path:path}")
async def write_context_file(path: str, req: FileWriteRequest):
    """Write/update a markdown file in a context folder."""
    target = _safe_path(path)

    # Audit #4: only allow markdown files under /contexts/files.
    if target.suffix != ".md":
        raise HTTPException(status_code=400, detail="Only .md files are allowed")

    # Ensure parent directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(req.content, encoding="utf-8")
    return {"status": "saved", "path": path}


@router.get("/contexts/_global")
async def read_global_glossary():
    """Read the global glossary file. Returns empty body if missing."""
    target = CONTEXTS_DIR / "_global.md"
    if not target.is_file():
        return {"content": "", "exists": False}
    try:
        return {
            "content": target.read_text(encoding="utf-8"),
            "exists": True,
            "modified_at": target.stat().st_mtime,
        }
    except OSError as exc:
        logger.warning("Failed to read _global.md: %s", exc)
        raise HTTPException(status_code=500, detail="Could not read global glossary")


@router.put("/contexts/_global")
async def write_global_glossary(req: FileWriteRequest):
    """Atomically write the global glossary file."""
    target = CONTEXTS_DIR / "_global.md"
    CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".md.tmp")
    try:
        tmp.write_text(req.content, encoding="utf-8")
        tmp.replace(target)
        return {"status": "saved", "path": "_global.md"}
    except OSError as exc:
        logger.error("Failed to write _global.md: %s", exc)
        raise HTTPException(status_code=500, detail="Could not write global glossary")
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


@router.get("/contexts/search")
async def search_contexts(q: str = ""):
    """Search across all context and insight files."""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    if not CONTEXTS_DIR.exists():
        return {"results": []}

    results = []
    query_lower = q.lower()

    for md_file in CONTEXTS_DIR.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    results.append({
                        "path": str(md_file.relative_to(CONTEXTS_DIR)),
                        "filename": md_file.name,
                        "line_number": i + 1,
                        "snippet": line.strip()[:200],
                    })
                    if len(results) >= 50:
                        return {"results": results, "truncated": True}
        except (OSError, UnicodeDecodeError):
            continue

    return {"results": results, "truncated": False}
