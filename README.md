# obsidian-mcp

A local MCP server that lets an AI agent (Claude Cowork, Claude Code, any MCP client)
**move and rename notes and folders in an Obsidian vault while keeping links intact** —
something a plain `mv` cannot do.

It drives the running Obsidian app through its official CLI, so link updates are
performed by Obsidian itself, exactly as with drag-and-drop in the file explorer.

## Why

Agents usually manipulate a vault as plain files. Moving a note with `mv` breaks every
link pointing to it, because only Obsidian maintains the link index. Some agents
(e.g. Claude Cowork) even run their shell in a Linux VM where the Obsidian app is
unreachable. A local MCP server, launched on the host by the desktop client, bridges
that gap.

## Tools

| Tool | Purpose | Implemented with |
|---|---|---|
| `vault_move_file(source, destination)` | move and/or rename a file | `obsidian move` |
| `vault_rename(source, new_name)` | rename a file in place | `obsidian rename` |
| `vault_move_folder(source, destination)` | move and/or rename a folder | `obsidian eval` (fixed JS → `app.fileManager.renameFile`) |
| `vault_backlinks(path)` | list backlinks to a file | `obsidian backlinks` |

Paths are relative to the vault root. The tool list is deliberately closed: no generic
access to `obsidian eval`.

## Requirements

- macOS, Obsidian ≥ 1.12 running, with the CLI enabled:
  Settings → General → *Command line interface*.
- Obsidian setting *Automatically update internal links* enabled.
- Python ≥ 3.12.

## Installation

Install the package into a dedicated environment, so the server clients launch is
independent from the source checkout:

```
conda create -n obsidian-mcp python=3.12
conda run -n obsidian-mcp pip install .      # re-run after each code change
```

Executable: `<env>/bin/obsidian-mcp`.

Environment variables:

- `OBSIDIAN_VAULT`: name of the target vault (defaults to the active vault);
- `OBSIDIAN_BIN`: path to the Obsidian executable
  (defaults to `/Applications/Obsidian.app/Contents/MacOS/Obsidian`).

## Client configuration

Claude Desktop (and therefore Cowork) — `~/Library/Application Support/Claude/claude_desktop_config.json`,
edited while Claude Desktop is closed:

```json
"mcpServers": {
  "obsidian-vault": {
    "command": "/path/to/envs/obsidian-mcp/bin/obsidian-mcp",
    "env": { "OBSIDIAN_VAULT": "MyVault" }
  }
}
```

Claude Code:

```
claude mcp add -s user obsidian-vault -e OBSIDIAN_VAULT=MyVault -- /path/to/envs/obsidian-mcp/bin/obsidian-mcp
```

The client starts the server (stdio subprocess) when it launches and stops it when it quits.

## Making agents actually use it

Having the tools available is not enough: out of habit, an agent may still reach for
`mv`. The server sends a short instruction to clients, but an explicit rule in the
agent's own context is more reliable. Suggested wording:

```markdown
- Moving or renaming a note or folder in the vault: only with the `vault_*` tools
  of the `obsidian-vault` MCP server, which go through Obsidian and update links.
  Never `mv`, `git mv`, or copy-then-delete. If these tools are unreachable
  (Obsidian closed, desktop app not running), ask the user to do the move in Obsidian.
```

Where to put it:

- **A `CLAUDE.md` at the vault root**: read by Claude Code, and by Cowork when the vault
  is the working folder. One place covers both.
- **Cowork without the vault as working folder**: in Cowork's global instructions, or
  in a small skill (e.g. "obsidian-vault-ops") whose description triggers on moving,
  renaming or reorganising notes.
- **Claude Code, hard enforcement (optional)**: a `PreToolUse` hook on `Bash` that
  rejects `mv`/`git mv` commands touching the vault path turns the rule into a guard.

## Notes

- `obsidian move` refuses folders, hence the `eval` route for `vault_move_folder`.
- When a folder is moved, Obsidian may rewrite path-qualified links to their shortest
  form (depending on your *New link format* setting); links remain valid.

## License

MIT
