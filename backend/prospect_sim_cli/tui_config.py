"""
TuiConfigMixin — /config and /setup command logic for ProspectSimTUI.

Extracted to keep tui.py under 1000 lines.
Mixin expects self to have: .client, .console, .rounds, .parallel,
._session, ._print_ok, ._print_err, ._print_hint, ._print_header
"""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from .cache import CliConfig
from .client import ApiClient, ApiError
from .tui_constants import DIM, ORANGE, CONFIG_KEYS


class TuiConfigMixin:
    """Config and setup commands. Mixed into ProspectSimTUI."""

    # ── /config ───────────────────────────────────────────────────────────────

    def _cmd_config(self, args: str) -> None:
        """
        Show or change configuration.

        /config              — show all settings (CLI + backend)
        /config set <key> <value>  — update a setting
        /config test         — test LLM connection
        """
        args = args.strip()
        if not args:
            self._show_config()
        elif args == "test":
            self._config_test_llm()
        elif args.startswith("set "):
            rest = args[4:].strip()
            parts = rest.split(None, 1)
            if len(parts) < 2:
                self._print_err(
                    f"Usage: /config set <key> <value>  ·  Keys: {', '.join(CONFIG_KEYS)}"
                )
                return
            self._config_set(parts[0], parts[1])
        else:
            self._print_err("Usage: /config  |  /config set <key> <value>  |  /config test")

    def _show_config(self) -> None:
        """Render the full config table: CLI settings + backend live settings."""
        cli_cfg = CliConfig().all()

        table = Table(
            title="Configuration",
            show_header=True,
            header_style=f"bold {ORANGE}",
            border_style=ORANGE,
            show_lines=True,
        )
        table.add_column("Key", style=f"bold {ORANGE}", min_width=16)
        table.add_column("Value", min_width=30)
        table.add_column("Where", style=DIM, min_width=8)

        table.add_row("api-url",  cli_cfg.get("api_url", "http://localhost:5001"), "cli")
        table.add_row("rounds",   str(cli_cfg.get("default_rounds", 8)),           "cli")
        table.add_row("parallel", str(cli_cfg.get("default_parallel", False)),     "cli")

        backend_ok = self.client.health_check()
        if backend_ok:
            try:
                settings = self.client.get_settings()
                llm = settings.get("llm", {})
                neo4j = settings.get("neo4j", {})
                table.add_row("model",    llm.get("model_name", "—"),     "backend")
                table.add_row("base-url", llm.get("base_url", "—"),       "backend")
                table.add_row("api-key",  llm.get("api_key_masked", "—"), "backend")
                table.add_row("neo4j",    neo4j.get("uri", "—"),          "backend")
            except ApiError:
                table.add_row("backend", "[red]error fetching settings[/red]", "backend")
        else:
            table.add_row(
                "backend", f"[red]offline[/red]  ({self.client.base_url})", "backend"
            )

        self.console.print()
        self.console.print(table)
        self.console.print(
            f"[{DIM}]  /config set <key> <value>  ·  /config test[/{DIM}]\n"
        )

    def _config_set(self, key: str, value: str) -> None:
        """Apply one config change — CLI keys saved to disk, backend keys sent live."""
        if key not in CONFIG_KEYS:
            self._print_err(
                f"Unknown key: '{key}'  ·  Valid: {', '.join(CONFIG_KEYS)}"
            )
            return

        cli_config = CliConfig()

        if key == "api-url":
            cli_config.set("api_url", value)
            self.client = ApiClient(base_url=value)
            self._print_ok(f"api-url → {value}")

        elif key == "rounds":
            if not value.isdigit():
                self._print_err("rounds must be an integer.")
                return
            cli_config.set("default_rounds", int(value))
            self.rounds = int(value)
            self._print_ok(f"rounds → {value}")

        elif key == "parallel":
            v = value.lower() in ("true", "1", "yes")
            cli_config.set("default_parallel", v)
            self.parallel = v
            self._print_ok(f"parallel → {v}")

        elif key in ("model", "base-url", "api-key"):
            if not self.client.health_check():
                self._print_err("Backend offline. Start it first.")
                return
            llm_map = {"model": "model_name", "base-url": "base_url", "api-key": "api_key"}
            try:
                self.client.update_settings(llm={llm_map[key]: value})
                display = "****" + value[-4:] if key == "api-key" else value
                self._print_ok(f"{key} → {display}")
                self._print_hint("Updated in-memory. Restart backend to persist to .env.")
            except ApiError as exc:
                self._print_err(f"Backend update failed: {exc.message}")

    def _config_test_llm(self) -> None:
        """Fire a minimal test call to the current LLM and report latency."""
        if not self.client.health_check():
            self._print_err("Backend offline.")
            return
        with self.console.status(f"[{ORANGE}]Testing LLM…[/{ORANGE}]", spinner="dots"):
            result = self.client.test_llm()
        if result.get("success"):
            self._print_ok(
                f"LLM reachable  ·  model: {result.get('model', '?')}"
                f"  ·  latency: {result.get('latency_ms', '?')}ms"
            )
        else:
            self._print_err(f"LLM test failed: {result.get('error', 'unknown')}")

    # ── /setup ────────────────────────────────────────────────────────────────

    def _cmd_setup(self) -> None:
        """Re-run the onboarding wizard manually."""
        self._run_onboarding(is_rerun=True)

    def _run_onboarding(self, is_rerun: bool = False) -> None:
        """
        First-time setup wizard (auto-triggered) or /setup (manual re-run).
        3 steps: backend URL → LLM model → simulation defaults.
        Inspired by `hermes setup`.
        """
        self.console.print()
        self.console.print(
            Panel(
                f"[bold {ORANGE}]👋 Welcome to prospect-sim![/]\n\n"
                f"[{DIM}]Let's get you set up in ~30 seconds.[/{DIM}]",
                border_style=ORANGE,
                padding=(0, 3),
            )
        )
        self.console.print()

        cli_config = CliConfig()

        # Step 1 — Backend URL
        self.console.print(f"[bold {ORANGE}]Step 1/3[/]  Backend URL")
        self._print_hint("The backend runs locally (default) or on a remote server.")
        current_url = cli_config.get("api_url") or "http://localhost:5001"

        try:
            raw = self._session.prompt(f"  Backend URL [{current_url}]: ").strip()
        except (KeyboardInterrupt, EOFError):
            self._print_hint("\nSetup cancelled.")
            self._print_header()
            return

        api_url = raw or current_url
        cli_config.set("api_url", api_url)
        self.client = ApiClient(base_url=api_url)

        with self.console.status(f"[{DIM}]Testing connection…[/{DIM}]", spinner="dots"):
            backend_ok = self.client.health_check()

        current_model = None
        if backend_ok:
            try:
                settings = self.client.get_settings()
                llm = settings.get("llm", {})
                current_model = llm.get("model_name", "unknown")
                provider = llm.get("provider", "?")
                self._print_ok(
                    f"Backend online  ·  model: [bold]{current_model}[/bold]  ·  provider: {provider}"
                )
            except ApiError:
                self._print_ok("Backend online")
        else:
            self._print(
                f"  [yellow]⚠[/yellow]  Not reachable at {api_url}. "
                f"Configure anyway — start backend before /run."
            )

        self.console.print()

        # Step 2 — Model
        self.console.print(f"[bold {ORANGE}]Step 2/3[/]  LLM Model")
        hint = f"Current: {current_model}" if current_model else "Backend offline — can set later with /config set model"
        self._print_hint(hint)
        self._print_hint("Common: gpt-4o, gpt-4o-mini, llama3  (Enter to skip)")

        try:
            raw_model = self._session.prompt("  New model (or Enter to skip): ").strip()
        except (KeyboardInterrupt, EOFError):
            raw_model = ""

        if raw_model and backend_ok:
            try:
                self.client.update_settings(llm={"model_name": raw_model})
                self._print_ok(f"Model → {raw_model}")
                current_model = raw_model
            except ApiError as exc:
                self._print_err(f"Could not update model: {exc.message}")
        elif raw_model and not backend_ok:
            self._print_hint("Backend offline — skipped. Run /config set model <name> later.")
        else:
            self._print_hint(f"Keeping {current_model or 'backend default'}.")

        self.console.print()

        # Step 3 — Simulation defaults
        self.console.print(f"[bold {ORANGE}]Step 3/3[/]  Simulation defaults")
        current_rounds = cli_config.get("default_rounds") or 8

        try:
            raw_rounds = self._session.prompt(
                f"  Rounds per variant [{current_rounds}]: "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            raw_rounds = ""

        self.rounds = int(raw_rounds) if raw_rounds.isdigit() else current_rounds
        cli_config.set("default_rounds", self.rounds)

        try:
            raw_par = self._session.prompt("  Run variants in parallel? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            raw_par = ""

        self.parallel = raw_par in ("y", "yes")
        cli_config.set("default_parallel", self.parallel)

        # Summary
        self.console.print()
        self.console.rule(f"[{ORANGE}]You're all set![/]")
        self.console.print()
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style=DIM, min_width=12)
        grid.add_column()
        grid.add_row("Backend:", api_url)
        grid.add_row("Model:",   current_model or "backend default")
        grid.add_row("Rounds:",  str(self.rounds))
        grid.add_row("Mode:",    "parallel" if self.parallel else "sequential")
        self.console.print(grid)
        self.console.print()
        self._print_hint("Run /icp <file> to load your ICP and start simulating.")
        self._print_hint("Change anything with /config  ·  re-run this wizard with /setup\n")
