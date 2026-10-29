"""MCP server: vault operations routed through Obsidian, so links get updated.

Agents (Cowork, Claude Code) must not `mv` files inside the vault: only Obsidian
knows how to rewrite links. This server runs on macOS and drives the running
app through its official CLI. The tool list is deliberately closed.
"""

import json
import os
import subprocess
from pathlib import PurePosixPath

from mcp.server.mcpserver import MCPServer
# ToolError (not ValueError…): the only type whose message the SDK passes on to the agent.
from mcp.server.mcpserver.exceptions import ToolError

OBSIDIAN_BIN = os.environ.get(
    "OBSIDIAN_BIN", "/Applications/Obsidian.app/Contents/MacOS/Obsidian"
)
# Target vault name (e.g. "MyVault"); otherwise the CLI uses the active vault.
VAULT = os.environ.get("OBSIDIAN_VAULT")
TIMEOUT_S = 20

mcp = MCPServer(
    "obsidian-vault",
    instructions=(
        "To move or rename a note or folder in the Obsidian vault, use these tools, "
        "never mv/cp/rm: they update links. Paths are relative to the vault root "
        "(e.g. 'Projects/X/Note.md'). Obsidian must be running."
    ),
)


def _check_rel_path(path: str) -> str:
    """Reject absolute paths and paths escaping the vault."""
    p = PurePosixPath(path.strip())
    if not path.strip() or p.is_absolute() or ".." in p.parts:
        raise ToolError(f"Invalid path (must be relative to the vault): {path!r}")
    return str(p)


def _obsidian_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Obsidian"], capture_output=True).returncode == 0


def _cli(command: str, **params: str) -> str:
    if not _obsidian_running():
        raise ToolError("Obsidian is not running: open it and retry.")
    args = [OBSIDIAN_BIN, command] + [f"{k}={v}" for k, v in params.items()]
    if VAULT:
        args.append(f"vault={VAULT}")
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise ToolError(f"The Obsidian CLI did not answer within {TIMEOUT_S} s ({command}).")
    out = (res.stdout + res.stderr).strip()
    if res.returncode != 0 or out.startswith("Error"):
        raise ToolError(out or f"`obsidian {command}` failed (exit code {res.returncode}).")
    return out


@mcp.tool()
def vault_move_file(source: str, destination: str) -> str:
    """Move (and/or rename) a file in the vault, updating links.

    source: file path, e.g. 'Projects/X/Note.md'.
    destination: target folder ending with '/' (e.g. 'Areas/Y/')
    or the new full file path (e.g. 'Areas/Y/Note.md').
    """
    return _cli("move", path=_check_rel_path(source), to=_check_rel_path(destination)
                + ("/" if destination.strip().endswith("/") else ""))


@mcp.tool()
def vault_rename(source: str, new_name: str) -> str:
    """Rename a file in place (same folder), updating links.

    source: file path. new_name: new file name, without folder.
    """
    if "/" in new_name:
        raise ToolError("new_name must not contain '/': use vault_move_file.")
    return _cli("rename", path=_check_rel_path(source), name=new_name)


# The CLI cannot move folders: call the internal API used by drag-and-drop.
# Fixed JS code, only the paths (JSON-serialized) vary.
_MOVE_FOLDER_JS = """(async () => {
  const src = %s, dst = %s;
  const f = app.vault.getAbstractFileByPath(src);
  if (!f || f.children === undefined) return 'Error: folder not found: ' + src;
  if (app.vault.getAbstractFileByPath(dst)) return 'Error: destination already exists: ' + dst;
  const parent = dst.includes('/') ? dst.slice(0, dst.lastIndexOf('/')) : '';
  if (parent && !app.vault.getAbstractFileByPath(parent)) await app.vault.createFolder(parent);
  await app.fileManager.renameFile(f, dst);
  return 'Moved: ' + src + ' -> ' + dst;
})()"""


@mcp.tool()
def vault_move_folder(source: str, destination: str) -> str:
    """Move and/or rename a folder in the vault, updating links.

    source: folder path, e.g. 'Projects/X'.
    destination: the folder's NEW full path, e.g. 'Archives/X'
    (missing parent folders are created).
    """
    src = _check_rel_path(source).rstrip("/")
    dst = _check_rel_path(destination).rstrip("/")
    out = _cli("eval", code=_MOVE_FOLDER_JS % (json.dumps(src), json.dumps(dst)))
    out = out.removeprefix("=>").strip()
    if out.startswith("Error"):
        raise ToolError(out)
    return out


@mcp.tool()
def vault_backlinks(path: str) -> str:
    """List the notes linking to a file (to check before/after a move)."""
    return _cli("backlinks", path=_check_rel_path(path)) or "(no backlinks)"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
