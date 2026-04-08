"""
Shared constants for the human TUI.
Imported by both tui.py and tui_config.py.
"""

# Brand colours
ORANGE = "#FF6B35"
ORANGE_DIM = "#CC4A10"
DIM = "dim"

# Braille spinner frames (same as Hermes Agent)
SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

# Dropout point colour map
DROPOUT_COLORS = {
    "subject_line": "red",
    "opening": "yellow",
    "body": "yellow",
    "cta": "cyan",
    "none": "green",
    "n/a": "dim",
}

# Slash commands for autocomplete
SLASH_COMMANDS = [
    "/icp", "/add", "/variants", "/rm", "/run",
    "/why", "/rounds", "/parallel", "/history",
    "/config", "/setup", "/clear", "/new", "/help", "/quit",
]

# Config keys exposed via /config set <key> <value>
CONFIG_KEYS = {
    # CLI-level (stored in ~/.prospect-sim/config.json)
    "api-url":  "Backend URL (e.g. http://localhost:5001)",
    "rounds":   "Default rounds per variant (e.g. 12)",
    "parallel": "Parallel mode — true or false",
    # Backend-level (sent to POST /api/settings live, no restart)
    "model":    "LLM model name (e.g. gpt-4o, gpt-4o-mini, llama3)",
    "base-url": "LLM base URL — for Ollama: http://localhost:11434/v1",
    "api-key":  "LLM API key (backend in-memory until restart)",
}

# ASCII logo (full width ≥72 cols)
LOGO = f"""[bold {ORANGE}]
 ██████╗ ██████╗  ██████╗ ███████╗██████╗ ███████╗ ██████╗████████╗
 ██╔══██╗██╔══██╗██╔═══██╗██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝
 ██████╔╝██████╔╝██║   ██║███████╗██████╔╝█████╗  ██║        ██║
 ██╔═══╝ ██╔══██╗██║   ██║╚════██║██╔═══╝ ██╔══╝  ██║        ██║
 ██║     ██║  ██║╚██████╔╝███████║██║     ███████╗╚██████╗   ██║
 ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝
[/][dim]  ·  B2B Cold Email Variant Simulator  ·  Type /help to start[/dim]"""

LOGO_COMPACT = f"[bold {ORANGE}]📧 PROSPECT SIM[/]  [dim]B2B Cold Email Variant Simulator[/dim]"
