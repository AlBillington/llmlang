# llmlang for VS Code

Syntax highlighting and basic editor configuration for `.llm` and `.llmflow` files. Not published to the Marketplace - install it locally.

## What this gives you

- **Syntax highlighting** for every real llmlang line type: folder/file/class headers, named and data entry headers (with the summary shown distinctly from the identifier), `@policy:`, `@entry-point`/`@entry-point(label)`, `~` test bullets (italicized), `# ` commentary bullets (colored as comments), `→ call`/`← return` arrows, and `if yes`/`if no`/`checks whether`/`for X case:`/`chooses ... by`/`repeats` keywords inside regular bullets.
- **Comment toggling**: `# ` is registered as the line-comment character, so Ctrl+/ (Cmd+/ on macOS) on a bullet turns it into a `#` commentary bullet.
- **Indentation hinting**: a line ending in `:` (a header, or a decision/case/repeat parent) signals the next line should indent.

This is presentation only - there is no diagnostics, hover, or go-to-definition support here. Run `llmlang check` for actual verification; this extension just makes the file easier to read while you edit it.

## Install locally

This extension isn't on the Marketplace. Two ways to use it from a local checkout:

**Symlink into your extensions folder** (picked up automatically, survives `git pull`):

```sh
# macOS/Linux
ln -s "$(pwd)/editors/vscode-llmlang" ~/.vscode/extensions/llmlang.llmlang-0.1.0

# Windows (PowerShell, from the repo root)
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.vscode\extensions\llmlang.llmlang-0.1.0" -Target "$(Get-Location)\editors\vscode-llmlang"
```

Restart VS Code (or run "Developer: Reload Window").

**Package and install a `.vsix`** (works without touching your extensions folder directly, but you'll need to reinstall it after editing the grammar):

```sh
npm install -g @vscode/vsce
cd editors/vscode-llmlang
vsce package
code --install-extension llmlang-0.1.0.vsix
```

## Recommended workspace settings

llmlang requires exactly one tab per indent level, no spaces (llmlang-format.md §2). Add to `.vscode/settings.json`:

```json
"[llmlang]": {
  "editor.insertSpaces": false,
  "editor.tabSize": 4
}
```

(`tabSize` here is purely how wide a tab *renders* in the editor - llmlang's own grammar only cares about tab count, not visual width.)
