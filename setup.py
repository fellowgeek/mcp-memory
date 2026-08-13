#!/usr/bin/env python3
import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()

TOOL_MAP = {
    "1": ("Google Antigravity (~/.gemini/antigravity)", Path("~/.gemini/antigravity/mcp_config.json")),
    "2": ("Claude Desktop (~/.claude)", Path("~/Library/Application Support/Claude/claude_desktop_config.json")),
    "3": ("Claude Code CLI", None),
    "4": ("Cursor IDE (~/.cursor)", Path("~/.cursor/mcp.json")),
    "5": ("Windsurf Editor (~/.codeium/windsurf)", Path("~/.codeium/windsurf/mcp_config.json")),
    "6": ("Codex Desktop (~/.codex)", Path("~/.codex/config.toml")),
    "7": ("Codex CLI", None),
    "8": ("Auto-detect & Configure All Installed Tools", None),
}

def print_banner():
    print("==================================================")
    print("          🧠  MCP Memory Setup Wizard  🧠         ")
    print("==================================================\n")

def get_interactive_choice_key(options, prompt_text, default_key="1"):
    print(prompt_text)
    for key, tuple_val in options.items():
        label = tuple_val[0]
        default_indicator = " (default)" if key == default_key else ""
        print(f"  [{key}] {label}{default_indicator}")

    choice = input(f"\nSelect option [1-{len(options)}] (default {default_key}): ").strip()
    if choice not in options:
        choice = default_key
    return choice

def inject_mcp_config_toml(path: Path, run_sh_path: Path):
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    command_str = str(run_sh_path).replace("\\", "\\\\") # escape backslashes for TOML
    
    if not path.exists():
        content = f'[mcp_servers.memory]\ncommand = "{command_str}"\n'
        path.write_text(content, encoding="utf-8")
        return path
        
    lines = path.read_text(encoding="utf-8").splitlines()
    
    # Find where [mcp_servers.memory] starts
    section_header = "[mcp_servers.memory]"
    section_index = -1
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_index = i
            break
            
    if section_index != -1:
        command_index = -1
        for i in range(section_index + 1, len(lines)):
            line_strip = lines[i].strip()
            if line_strip.startswith("["):
                break
            if line_strip.startswith("command") and "=" in line_strip:
                command_index = i
                
        if command_index != -1:
            orig_line = lines[command_index]
            indent = orig_line[:len(orig_line) - len(orig_line.lstrip())]
            lines[command_index] = f'{indent}command = "{command_str}"'
        else:
            lines.insert(section_index + 1, f'command = "{command_str}"')
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(section_header)
        lines.append(f'command = "{command_str}"')
        
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

def inject_mcp_config(config_path: Path, run_sh_path: Path):
    path = config_path.expanduser()
    if path.suffix == ".toml":
        return inject_mcp_config_toml(path, run_sh_path)
        
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}

    data["mcpServers"]["memory"] = {
        "command": str(run_sh_path)
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path

def find_claude_binary():
    claude_bin = shutil.which("claude")
    if claude_bin:
        return claude_bin

    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/opt/homebrew/bin/claude"),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None

def configure_claude_code(run_sh_path: Path):
    claude_bin = find_claude_binary()
    cmd_str = f"claude mcp add --scope user memory -- {run_sh_path}"
    if claude_bin:
        try:
            cmd = [claude_bin, "mcp", "add", "--scope", "user", "memory", "--", str(run_sh_path)]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, cmd_str
        except Exception as e:
            return False, f"Attempted '{cmd_str}' but failed: {e}"
    else:
        return False, f"Command to run manually: {cmd_str}"

def find_codex_binary():
    codex_bin = shutil.which("codex")
    if codex_bin:
        return codex_bin

    candidates = [
        Path.home() / ".local" / "bin" / "codex",
        Path("/usr/local/bin/codex"),
        Path("/opt/homebrew/bin/codex"),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None

def configure_codex_cli(run_sh_path: Path):
    codex_bin = find_codex_binary()
    cmd_str = f"codex mcp add memory -- {run_sh_path}"
    if codex_bin:
        try:
            cmd = [codex_bin, "mcp", "add", "memory", "--", str(run_sh_path)]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, cmd_str
        except Exception as e:
            return False, f"Attempted '{cmd_str}' but failed: {e}"
    else:
        return False, f"Command to run manually: {cmd_str}"

def main():
    parser = argparse.ArgumentParser(description="Interactive setup wizard for mcp-memory.")
    parser.add_argument("--tool", help="Target tool choice (1: Antigravity, 2: Claude Desktop, 3: Claude CLI, 4: Cursor, 5: Windsurf, 6: Codex Desktop, 7: Codex CLI, 8: All)")
    parser.add_argument("--no-config-edit", action="store_true", help="Skip editing tool JSON configuration files")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode using defaults")
    args = parser.parse_args()

    if not args.non_interactive:
        print_banner()

    selected_tool_key = "8" # Default All
    if args.tool and args.tool in TOOL_MAP:
        selected_tool_key = args.tool
    elif not args.non_interactive:
        selected_tool_key = get_interactive_choice_key(
            TOOL_MAP, "Select your primary AI Coding Tool:", default_key="1"
        )

    tool_label, config_json_path = TOOL_MAP[selected_tool_key]

    # Ensure run.sh is executable
    run_sh_path = (PROJECT_DIR / "run.sh").resolve()
    if run_sh_path.exists():
        current_mode = run_sh_path.stat().st_mode
        run_sh_path.chmod(current_mode | 0o111)

    updated_configs = []
    cli_cmd_results = []
    if not args.no_config_edit:
        if selected_tool_key == "3":
            success, msg = configure_claude_code(run_sh_path)
            cli_cmd_results.append((success, msg))
        elif selected_tool_key == "7":
            success, msg = configure_codex_cli(run_sh_path)
            cli_cmd_results.append((success, msg))
        elif selected_tool_key == "8":
            for key, (_, cfg_p) in TOOL_MAP.items():
                if cfg_p:
                    try:
                        updated_path = inject_mcp_config(cfg_p, run_sh_path)
                        updated_configs.append(updated_path)
                    except Exception as e:
                        print(f"⚠️ Could not write config to {cfg_p}: {e}", file=sys.stderr)
            success, msg = configure_claude_code(run_sh_path)
            cli_cmd_results.append((success, msg))
            success, msg = configure_codex_cli(run_sh_path)
            cli_cmd_results.append((success, msg))
        else:
            if config_json_path:
                try:
                    updated_path = inject_mcp_config(config_json_path, run_sh_path)
                    updated_configs.append(updated_path)
                except Exception as e:
                    print(f"⚠️ Could not write config to {config_json_path}: {e}", file=sys.stderr)

    has_successful_cli = any(res[0] for res in cli_cmd_results)
    if updated_configs or has_successful_cli:
        print("\n🔧 Automatically configured MCP Server:")
        for cfg_p in updated_configs:
            print(f"   • Configured: {cfg_p}")
        for success, msg in cli_cmd_results:
            if success:
                print(f"   • Executed: {msg}")

    if not updated_configs and not has_successful_cli:
        print("\nNext Step: Add the MCP server config to your client settings:")
        print("\nFor JSON-based clients (Antigravity, Claude Desktop, Cursor, Windsurf):")
        print("```json")
        print("{\n  \"mcpServers\": {\n    \"memory\": {")
        print(f"      \"command\": \"{run_sh_path}\"")
        print("    }\n  }\n}")
        print("```")

if __name__ == "__main__":
    main()
