"""
prospect-sim human TUI — interactive REPL for cold email variant testing.

Designed for humans, not agents. Drop into a session with `prospect-sim-tui`,
load your ICP, build variants interactively, watch simulations run live.

Brand colour: orange (#FF6B35).
Inspired by Hermes Agent (NousResearch) — prompt_toolkit REPL + Rich output.

Architecture:
  ProspectSimTUI  — session state + REPL loop
  _run_simulation_dashboard  — Rich.Live panel during runs
  _cmd_*  — one method per slash command
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .cache import CACHE_DIR, CliConfig, IcpCache
from .client import ApiClient, ApiError
from .tui_constants import (
    ORANGE, DIM, SPINNER, DROPOUT_COLORS,
    SLASH_COMMANDS, CONFIG_KEYS, LOGO, LOGO_COMPACT,
)
from .tui_config import TuiConfigMixin
from .tui_graph import TuiGraphMixin


class SlashCompleter(Completer):
    """Autocomplete slash commands + file paths for /icp."""

    def __init__(self) -> None:
        self._path_completer = PathCompleter(only_directories=False)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        # File path completion after /icp
        if text.startswith("/icp "):
            path_doc = document.__class__(text[5:], len(text) - 5)
            for c in self._path_completer.get_completions(path_doc, complete_event):
                yield c
            return
        # /config set <key> completion
        if text.startswith("/config set "):
            partial = text[len("/config set "):]
            for key in CONFIG_KEYS:
                if key.startswith(partial):
                    yield Completion(key, start_position=-len(partial))
            return
        # Slash command completion
        if text.startswith("/") and " " not in text:
            word = text.lstrip("/")
            for cmd in SLASH_COMMANDS:
                if cmd.lstrip("/").startswith(word):
                    yield Completion(cmd, start_position=-len(text))


class ProspectSimTUI(TuiConfigMixin, TuiGraphMixin):
    """
    Interactive REPL session for prospect-sim.

    Session state:
      icp_path     — currently loaded ICP file
      project_id   — cached project_id for current ICP
      variants     — list of variant dicts (built interactively)
      rounds       — simulation rounds per variant (default 8)
      parallel     — run variants in parallel (default False)
      last_run_ids — simulation IDs from last /run (for /why)
      last_report  — report dict from last /run
    """

    def __init__(self, api_url: str = "") -> None:
        config = CliConfig()
        resolved_url = api_url or config.get("api_url") or "http://localhost:5001"
        self.client = ApiClient(base_url=resolved_url)
        self.cache = IcpCache()

        # Session state
        self.icp_path: Optional[Path] = None
        self.project_id: Optional[str] = None
        self.variants: list[dict] = []
        self.rounds: int = config.get("default_rounds") or 8
        self.parallel: bool = config.get("default_parallel") or False
        self.last_run_ids: list[dict] = []
        self.last_report: Optional[dict] = None

        # Determine colour support
        no_color = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()
        self.console = Console(no_color=no_color, highlight=False)
        self._no_color = no_color

        # History file
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        history_path = str(CACHE_DIR / "history")
        self._session: PromptSession = PromptSession(
            history=FileHistory(history_path),
            completer=SlashCompleter(),
            auto_suggest=AutoSuggestFromHistory(),
        )

    # ── Rendering helpers ─────────────────────────────────────────────────────

    def _print(self, *args, **kwargs) -> None:
        """Thin wrapper so all output goes through our console."""
        self.console.print(*args, **kwargs)

    def _print_header(self) -> None:
        """Print branded session header."""
        terminal_width = self.console.width or 80
        logo = LOGO if terminal_width >= 72 else LOGO_COMPACT
        backend_ok = self.client.health_check()
        status_dot = f"[green]●[/green] online" if backend_ok else f"[red]●[/red] offline"
        icp_label = self.icp_path.name if self.icp_path else "none loaded"
        subtitle = (
            f"  backend: {status_dot}   "
            f"icp: [bold]{icp_label}[/bold]   "
            f"variants: [bold]{len(self.variants)}[/bold]   "
            f"rounds: [bold]{self.rounds}[/bold]"
        )
        panel = Panel(
            f"{logo}\n{subtitle}",
            border_style=ORANGE,
            padding=(0, 2),
        )
        self._print(panel)

    def _print_hint(self, msg: str) -> None:
        self._print(f"[{DIM}]  {msg}[/{DIM}]")

    def _print_ok(self, msg: str) -> None:
        self._print(f"[bold {ORANGE}]✓[/bold {ORANGE}]  {msg}")

    def _print_err(self, msg: str) -> None:
        self._print(f"[red]✗[/red]  {msg}")

    def _print_info(self, msg: str) -> None:
        self._print(f"[{DIM}]  → {msg}[/{DIM}]")

    # ── REPL loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Main entry point. Auto-onboard on first launch, then start REPL."""
        from .cache import CONFIG_FILE
        first_run = not CONFIG_FILE.exists()

        if first_run:
            self._run_onboarding()
        else:
            self._print_header()
            self._print_hint("No ICP loaded. Run /icp <file> to start, or /help for commands.\n")

        with patch_stdout():
            while True:
                try:
                    raw = self._session.prompt(
                        [("bold", " > "), ("", " ")],
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    self._print("\n[dim]Use /quit to exit.[/dim]")
                    continue

                if not raw:
                    continue
                self._dispatch(raw)

    def _dispatch(self, text: str) -> None:
        """Route input to the appropriate command handler."""
        if not text.startswith("/"):
            self._print_hint("Commands start with /. Type /help for the list.")
            return

        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/icp": self._cmd_icp,
            "/add": lambda _: self._cmd_add(),
            "/variants": lambda _: self._cmd_variants(),
            "/rm": self._cmd_rm,
            "/run": lambda _: self._cmd_run(),
            "/why": self._cmd_why,
            "/graph": self._cmd_graph,
            "/runs": self._cmd_runs,
            "/rounds": self._cmd_rounds,
            "/parallel": lambda _: self._cmd_parallel(),
            "/history": lambda _: self._cmd_history(),
            "/config": self._cmd_config,
            "/setup": lambda _: self._cmd_setup(),
            "/clear": lambda _: self._cmd_clear(),
            "/new": lambda _: self._cmd_new(),
            "/help": lambda _: self._cmd_help(),
            "/quit": lambda _: self._cmd_quit(),
        }

        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            self._print_err(f"Unknown command: {cmd}. Type /help for the list.")

    # ── Command handlers ──────────────────────────────────────────────────────

    def _cmd_icp(self, args: str) -> None:
        """Load an ICP file. Checks cache; builds graph if needed."""
        if not args:
            self._print_err("Usage: /icp <file>")
            return

        path = Path(args.strip()).expanduser()
        if not path.exists():
            self._print_err(f"File not found: {path}")
            return

        icp_hash = self.cache.hash_file(path)
        cached = self.cache.get(icp_hash)

        if cached:
            # Verify project still exists on backend
            try:
                self.client.get_project(cached["project_id"])
                self.icp_path = path
                self.project_id = cached["project_id"]
                self._print_ok(f"⚡ reusing project [bold]{self.project_id}[/bold]  ({path.name})")
                return
            except ApiError:
                self.cache.delete(icp_hash)
                self._print_info("Cached project no longer exists on backend — rebuilding.")

        # Need to build
        if not self.client.health_check():
            self._print_err(f"Backend offline. Start it first: cd backend && uv run python run.py")
            return

        self._print_info(f"Building ICP graph for {path.name} (~5-10 min)…")
        project_name = path.stem.replace("-", " ").replace("_", " ").title()
        requirement = (
            "Test B2B cold email copy variants against HR Director / Head of People personas. "
            "Focus on open rate, reply intent, and dropout point analysis."
        )
        try:
            with self.console.status(
                f"[{ORANGE}]Generating ontology…[/{ORANGE}]", spinner="dots"
            ):
                result = self.client.generate_ontology(path, project_name, requirement)

            project_id = result.get("project_id")
            if not project_id:
                self._print_err("Backend returned no project_id.")
                return

            self._print_info(f"Project created: {project_id}")

            with self.console.status(
                f"[{ORANGE}]Building knowledge graph…[/{ORANGE}]", spinner="dots"
            ):
                task_id = self.client.build_graph(project_id)
                self.client.poll_task(task_id)

            self.cache.set(icp_hash, project_id, str(path.resolve()))
            self.icp_path = path
            self.project_id = project_id
            self._print_ok(f"Graph built and cached: [bold]{project_id}[/bold]  ({path.name})")

        except ApiError as exc:
            self._print_err(f"{exc.code}: {exc.message}")
            if exc.fix:
                self._print_hint(f"Fix: {exc.fix}")

    def _cmd_add(self) -> None:
        """Interactive wizard to add a new email variant."""
        self._print(f"\n[bold {ORANGE}]Adding variant[/bold {ORANGE}]  (Ctrl+C to cancel)\n")

        fields = [
            ("label", "Name / label (e.g. 'problem-hook-v1'): "),
            ("subject_line", "Subject line: "),
            ("body", "Email body (one line, or paste): "),
            ("hook_type", "Hook type [problem / social_proof / insight / curiosity]: "),
            ("cta", "CTA (call-to-action phrase): "),
        ]

        variant: dict = {}
        try:
            for key, prompt_text in fields:
                val = self._session.prompt(f"  {prompt_text}").strip()
                if not val:
                    self._print_hint("Cancelled — empty input.")
                    return
                variant[key] = val
        except (KeyboardInterrupt, EOFError):
            self._print_hint("\nCancelled.")
            return

        variant["id"] = len(self.variants) + 1
        self.variants.append(variant)
        self._print_ok(f"Variant #{variant['id']} added: [bold]{variant['label']}[/bold]")
        self._print_hint(f"Now you have {len(self.variants)} variant(s). Run /run when ready.")

    def _cmd_variants(self) -> None:
        """Show current variant list as a Rich table."""
        if not self.variants:
            self._print_hint("No variants yet. Use /add to create one.")
            return

        table = Table(
            title="Current Variants",
            show_header=True,
            header_style=f"bold {ORANGE}",
            border_style=DIM,
        )
        table.add_column("#", style=DIM, width=4)
        table.add_column("Label", min_width=20)
        table.add_column("Hook", min_width=12)
        table.add_column("Subject Line", min_width=30)

        for v in self.variants:
            table.add_row(
                str(v.get("id", "?")),
                v.get("label", "—"),
                v.get("hook_type", "—"),
                v.get("subject_line", "—"),
            )

        self.console.print(table)

    def _cmd_rm(self, args: str) -> None:
        """Remove a variant by number."""
        if not args.strip().isdigit():
            self._print_err("Usage: /rm <number>  (use /variants to see numbers)")
            return

        n = int(args.strip())
        idx = next((i for i, v in enumerate(self.variants) if v.get("id") == n), None)
        if idx is None:
            self._print_err(f"No variant with id {n}.")
            return

        removed = self.variants.pop(idx)
        self._print_ok(f"Removed variant #{n}: {removed.get('label', '?')}")

    def _cmd_run(self) -> None:
        """Run simulations for current ICP + variants. Shows live dashboard."""
        if not self.icp_path or not self.project_id:
            self._print_err("No ICP loaded. Run /icp <file> first.")
            return
        if not self.variants:
            self._print_err("No variants. Run /add to create at least one.")
            return
        if len(self.variants) > 6:
            self._print_err("Maximum 6 variants per run. Use /rm to remove some.")
            return
        if not self.client.health_check():
            self._print_err("Backend offline. Start it first.")
            return

        self._print(
            f"\n[bold {ORANGE}]Starting run[/bold {ORANGE}]  "
            f"[{DIM}]{len(self.variants)} variant(s) · {self.rounds} rounds each · "
            f"{'parallel' if self.parallel else 'sequential'}[/{DIM}]\n"
        )

        requirement = (
            "Rank email copy variants by reply intent. Identify dropout points "
            "(subject_line / opening / body / cta) for each variant."
        )

        try:
            run_ids = self.client.run_variant_test(
                self.project_id, self.variants, requirement, self.parallel, self.rounds,
            )
        except ApiError as exc:
            self._print_err(f"{exc.code}: {exc.message}")
            return

        # Prepare and start all simulations
        for entry in run_ids:
            sim_id = entry["simulation_id"]
            label = entry.get("variant_label", sim_id)
            try:
                with self.console.status(
                    f"[{DIM}]Preparing '{label}'…[/{DIM}]", spinner="dots"
                ):
                    task_id = self.client.prepare_simulation(sim_id)
                    self.client.poll_task(task_id, timeout=300)
                self.client.start_simulation(sim_id)
            except ApiError as exc:
                self._print_err(f"Failed to prepare '{label}': {exc.message}")
                return

        # Live dashboard
        self._run_simulation_dashboard(run_ids)

        # Generate report
        self._print_info("Generating ranking report…")
        try:
            with self.console.status(
                f"[{ORANGE}]Running ReACT report agent…[/{ORANGE}]", spinner="dots"
            ):
                report_id = self.client.generate_report(run_ids[0]["simulation_id"])
                report = self.client.poll_report(report_id)
        except ApiError as exc:
            self._print_err(f"Report failed: {exc.message}")
            return

        self.last_run_ids = run_ids
        self.last_report = report
        self._render_results(report, run_ids)

    def _run_simulation_dashboard(self, run_ids: list[dict]) -> None:
        """
        Live dashboard showing per-variant simulation progress.
        Updates every 0.5s until all simulations complete.
        """
        # Track state for each simulation
        states: dict[str, dict] = {}
        for entry in run_ids:
            states[entry["simulation_id"]] = {
                "label": entry.get("variant_label", entry["simulation_id"]),
                "status": "running",
                "spinner_frame": 0,
            }

        def _poll_all() -> None:
            """Background thread: poll each simulation until done."""
            for entry in run_ids:
                sim_id = entry["simulation_id"]
                try:
                    self.client.poll_simulation(sim_id)
                    states[sim_id]["status"] = "done"
                except ApiError as exc:
                    states[sim_id]["status"] = f"error: {exc.message}"

        poll_thread = threading.Thread(target=_poll_all, daemon=True)
        poll_thread.start()

        spinner_cycle = 0
        with Live(
            self._build_dashboard(states, spinner_cycle),
            console=self.console,
            refresh_per_second=4,
        ) as live:
            while poll_thread.is_alive():
                spinner_cycle += 1
                live.update(self._build_dashboard(states, spinner_cycle))
                time.sleep(0.25)
            # Final update — all done
            live.update(self._build_dashboard(states, spinner_cycle))

        poll_thread.join()

    def _build_dashboard(self, states: dict, spinner_cycle: int) -> Panel:
        """Build the Rich Panel for the live simulation dashboard."""
        table = Table.grid(padding=(0, 2))
        table.add_column(width=3)   # spinner / checkmark
        table.add_column(min_width=24)  # label
        table.add_column(min_width=10)  # status

        frame = SPINNER[spinner_cycle % len(SPINNER)]

        for sim_id, s in states.items():
            label = s["label"]
            status = s["status"]
            if status == "done":
                icon = f"[green]✓[/green]"
                status_text = Text("complete", style="green")
            elif status.startswith("error"):
                icon = f"[red]✗[/red]"
                status_text = Text(status, style="red")
            else:
                icon = f"[{ORANGE}]{frame}[/{ORANGE}]"
                status_text = Text("running…", style=DIM)

            table.add_row(icon, f"[bold]{label}[/bold]", status_text)

        all_done = all(s["status"] in ("done",) or s["status"].startswith("error")
                       for s in states.values())
        title_color = "green" if all_done else ORANGE
        title = f"[bold {title_color}]Simulations[/bold {title_color}]"

        return Panel(table, title=title, border_style=ORANGE if not all_done else "green")

    def _render_results(self, report: dict, run_ids: list[dict]) -> None:
        """Render the final ranking table inline after a run."""
        ranking = report.get("ranking", [])
        failure_points = report.get("failure_points", {})

        if not ranking:
            # Fallback — build basic ranking from run_ids
            ranking = [
                {
                    "variant_id": str(entry.get("variant_id", i)),
                    "label": entry.get("variant_label", f"Variant {i+1}"),
                    "hook_type": entry.get("hook_type", "unknown"),
                    "open_score": "n/a",
                    "reply_score": "n/a",
                }
                for i, entry in enumerate(run_ids)
            ]

        table = Table(
            title="Variant Ranking",
            show_header=True,
            header_style=f"bold {ORANGE}",
            border_style=ORANGE,
        )
        table.add_column("#", style=DIM, width=4)
        table.add_column("Variant", min_width=20)
        table.add_column("Hook", min_width=12)
        table.add_column("Opens", justify="right")
        table.add_column("Replies", justify="right")
        table.add_column("Main Dropout", min_width=14)

        for i, entry in enumerate(ranking):
            vid = str(entry.get("variant_id", ""))
            dropout = failure_points.get(vid, "n/a")
            drop_color = DROPOUT_COLORS.get(dropout, "white")

            if i == 0:
                rank_str = f"[bold {ORANGE}]👑 1[/]"
                label_text = f"[bold {ORANGE}]{entry.get('label', vid)}[/]"
                row_style = f"bold {ORANGE}"
            else:
                rank_str = f"  {i + 1}"
                label_text = entry.get("label", vid)
                row_style = ""

            table.add_row(
                rank_str,
                label_text,
                entry.get("hook_type", "—"),
                str(entry.get("open_score", "—")),
                str(entry.get("reply_score", "—")),
                f"[{drop_color}]{dropout}[/]",
                style=row_style if i == 0 else "",
            )

        self.console.print()
        self.console.print(table)

        winner = ranking[0].get("label") if ranking else None
        if winner:
            self.console.print(
                f"\n[bold {ORANGE}]🏆 Winner: {winner}[/bold {ORANGE}]\n"
            )
        self._print_hint("Run /why <number> to ask why a variant ranked where it did.")

    def _cmd_why(self, args: str) -> None:
        """Stream a ReACT explanation for why a variant ranked as it did."""
        if not self.last_report:
            self._print_err("No results yet. Run /run first.")
            return

        # Resolve variant by number or label
        ranking = self.last_report.get("ranking", [])
        if not ranking:
            self._print_err("No ranking data in last report.")
            return

        target = None
        args = args.strip()
        if args.isdigit():
            idx = int(args) - 1
            if 0 <= idx < len(ranking):
                target = ranking[idx]
            else:
                self._print_err(f"No variant #{args} in ranking (1–{len(ranking)}).")
                return
        else:
            target = next(
                (r for r in ranking if args.lower() in r.get("label", "").lower()), None
            )
            if not target:
                self._print_err(f"No variant matching '{args}'. Use /variants to check labels.")
                return

        label = target.get("label", "?")
        rank_pos = ranking.index(target) + 1
        dropout = self.last_report.get("failure_points", {}).get(
            str(target.get("variant_id", "")), "unknown"
        )

        # Build a synthetic explanation from report content
        report_content = self.last_report.get("content", "")

        self._print(f"\n[{DIM}]Why did '{label}' rank #{rank_pos}?[/{DIM}]\n")

        if report_content:
            # Stream it word by word for the Hermes-style effect
            with self.console.status("", spinner="dots"):
                time.sleep(0.3)  # brief pause for effect

            lines = report_content.split("\n")
            relevant = [l for l in lines if label.lower()[:8] in l.lower() or "variant" in l.lower()]
            content_to_show = "\n".join(relevant[:20]) if relevant else report_content[:800]

            # Print in a dim italic panel
            self.console.print(
                Panel(
                    f"[italic]{content_to_show}[/italic]",
                    title=f"[{DIM}]Analysis: {label}[/{DIM}]",
                    border_style=DIM,
                    subtitle=f"[{DIM}]dropout: {dropout}[/{DIM}]",
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[italic]Ranked #{rank_pos}. "
                    f"Primary dropout point: [bold]{dropout}[/bold].\n\n"
                    f"Open score: {target.get('open_score', 'n/a')}  "
                    f"Reply score: {target.get('reply_score', 'n/a')}[/italic]",
                    title=f"[{DIM}]Analysis: {label}[/{DIM}]",
                    border_style=DIM,
                )
            )

    def _cmd_rounds(self, args: str) -> None:
        """Set default rounds per variant."""
        if not args.strip().isdigit():
            self._print_err("Usage: /rounds <number>  (e.g. /rounds 12)")
            return
        self.rounds = int(args.strip())
        self._print_ok(f"Rounds set to {self.rounds}")

    def _cmd_parallel(self) -> None:
        """Toggle parallel simulation mode."""
        self.parallel = not self.parallel
        mode = "parallel" if self.parallel else "sequential"
        self._print_ok(f"Mode: {mode}")

    def _cmd_history(self) -> None:
        """Show cached ICP projects."""
        entries = self.cache.list_all()
        if not entries:
            self._print_hint("No cached projects. Load an ICP with /icp <file>.")
            return

        table = Table(
            title="Cached ICP Projects",
            header_style=f"bold {ORANGE}",
            border_style=DIM,
        )
        table.add_column("Project ID", min_width=16)
        table.add_column("ICP File", min_width=24)
        table.add_column("Cached At", min_width=20)

        for e in entries:
            table.add_row(
                e.get("project_id", "?"),
                e.get("icp_file", "?"),
                e.get("created_at", "?"),
            )
        self.console.print(table)

    def _cmd_clear(self) -> None:
        """Clear all current variants."""
        n = len(self.variants)
        self.variants = []
        self._print_ok(f"Cleared {n} variant(s).")

    def _cmd_new(self) -> None:
        """Reset session — clear ICP, variants, last results."""
        self.icp_path = None
        self.project_id = None
        self.variants = []
        self.last_run_ids = []
        self.last_report = None
        self._print_ok("Session reset. Load a new ICP with /icp <file>.")

    def _cmd_help(self) -> None:
        """Print slash command reference."""
        table = Table(
            title="Commands",
            show_header=True,
            header_style=f"bold {ORANGE}",
            border_style=DIM,
            show_lines=False,
        )
        table.add_column("Command", style=f"bold {ORANGE}", min_width=18)
        table.add_column("Description")

        rows = [
            ("── Simulation ──────────────", ""),
            ("/icp <file>",          "Load an ICP file (tab-autocomplete). Builds graph if not cached."),
            ("/add",                 "Interactive wizard: add an email variant to the session."),
            ("/variants",            "Show all current variants in a table."),
            ("/rm <n>",              "Remove variant by number."),
            ("/run",                 "Simulate all variants. Shows live dashboard + inline results."),
            ("/why <n|label>",       "Explain why a variant ranked where it did."),
            ("/graph",               "Show ICP knowledge graph structure (entity types, counts)."),
            ("/graph open",          "Same, and open the D3 visualization in your browser."),
            ("/runs",                "List all past runs (name, ICP file, sims, reports, disk)."),
            ("/runs show <n>",       "Inspect a run: graph entity breakdown, agents, report outline."),
            ("/runs graph <n>",      "Show graph nodes (entities) and edges (relationships)."),
            ("/runs report <n>",     "Render the full simulation report inline."),
            ("/runs rm <n>",         "Delete run by number — removes graph, files, and cache entry."),
            ("── Session ─────────────────", ""),
            ("/rounds <n>",          "Set rounds per variant (default: 8)."),
            ("/parallel",            "Toggle parallel / sequential simulation mode."),
            ("/history",             "Show all cached ICP projects."),
            ("/clear",               "Clear all current variants."),
            ("/new",                 "Reset session (clear ICP + variants + results)."),
            ("── Configuration ───────────", ""),
            ("/config",              "Show all settings (CLI + backend model/URL)."),
            ("/config set <k> <v>",  "Change a setting. Keys: api-url, rounds, parallel, model, base-url, api-key"),
            ("/config test",         "Test the LLM connection and report latency."),
            ("/setup",               "Re-run the setup wizard."),
            ("── Other ───────────────────", ""),
            ("/help",                "Show this help table."),
            ("/quit",                "Exit the session."),
        ]
        for cmd, desc in rows:
            table.add_row(cmd, desc)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def _cmd_runs(self, args: str) -> None:
        """
        List all past runs, or delete one by number.

        /runs          — show the list table
        /runs rm <n>   — delete run #n (confirms inline)
        """
        parts = args.strip().split(None, 1)
        sub = parts[0].lower() if parts else ""

        if sub == "graph":
            # ── Show graph nodes + edges ────────────────────────────────
            n_str = parts[1].strip() if len(parts) > 1 else ""
            if not n_str:
                self._print_err("Usage: /runs graph <number>")
                return
            with self.console.status(f"[{ORANGE}]Fetching graph…[/{ORANGE}]", spinner="dots"):
                try:
                    runs = self.client.get_runs()
                    row = int(n_str)
                    if row < 1 or row > len(runs):
                        self._print_err(f"Row {row} out of range (1–{len(runs)}).")
                        return
                    project_id = runs[row - 1]["project_id"]
                    detail = self.client.get_run_detail(project_id)
                    graph_id = detail.get("project", {}).get("graph_id")
                    if not graph_id:
                        self._print_err("No graph built for this run.")
                        return
                    data = self.client.get_graph_data(graph_id)
                except (ApiError, ValueError) as exc:
                    self._print_err(str(exc))
                    return
            # Delegate to CLI renderer
            from .commands.runs import runs_graph as _runs_graph_cmd  # noqa — import for renderer only
            from .commands import runs as runs_mod
            # Build a fake detail dict and call the graph renderer directly
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            self._render_graph_inline(nodes, edges, graph_id)

        elif sub == "report":
            # ── Show full report ─────────────────────────────────────────
            n_str = parts[1].strip() if len(parts) > 1 else ""
            if not n_str:
                self._print_err("Usage: /runs report <number>")
                return
            with self.console.status(f"[{ORANGE}]Fetching report…[/{ORANGE}]", spinner="dots"):
                try:
                    runs = self.client.get_runs()
                    row = int(n_str)
                    if row < 1 or row > len(runs):
                        self._print_err(f"Row {row} out of range (1–{len(runs)}).")
                        return
                    project_id = runs[row - 1]["project_id"]
                    detail = self.client.get_run_detail(project_id)
                    report_id = None
                    for sim in detail.get("simulations", []):
                        for rep in sim.get("reports", []):
                            report_id = rep.get("report_id")
                            if report_id:
                                break
                        if report_id:
                            break
                    if not report_id:
                        self._print_hint("No report found for this run.")
                        return
                    report = self.client.get_report(report_id)
                except ApiError as exc:
                    self._print_err(f"Could not fetch report: {exc.message}")
                    return
            from rich.markdown import Markdown
            md = report.get("markdown_content") or ""
            if not md:
                self._print_hint("Report is empty.")
                return
            self.console.print()
            self.console.print(Panel(
                Markdown(md),
                title=f"[bold {ORANGE}]Report[/bold {ORANGE}]",
                border_style=ORANGE,
                padding=(1, 2),
            ))
            self.console.print()

        elif sub == "show":
            # ── Inspect run ─────────────────────────────────────────────
            n_str = parts[1].strip() if len(parts) > 1 else ""
            if not n_str:
                self._print_err("Usage: /runs show <number>  (use /runs to see the list)")
                return

            with self.console.status(f"[{ORANGE}]Fetching runs…[/{ORANGE}]", spinner="dots"):
                try:
                    runs = self.client.get_runs()
                except ApiError as exc:
                    self._print_err(f"Could not fetch runs: {exc.message}")
                    return

            try:
                row = int(n_str)
            except ValueError:
                self._print_err(f"{n_str!r} is not a valid row number.")
                return

            if row < 1 or row > len(runs):
                self._print_err(f"Row {row} is out of range (1–{len(runs)}).")
                return

            project_id = runs[row - 1]["project_id"]

            with self.console.status(f"[{ORANGE}]Loading run detail…[/{ORANGE}]", spinner="dots"):
                try:
                    detail = self.client.get_run_detail(project_id)
                except ApiError as exc:
                    self._print_err(f"Could not fetch run detail: {exc.message}")
                    return

            # Delegate rendering to the CLI renderer (same output, same style)
            from .commands.runs import _render_run_detail
            _render_run_detail(detail)

        elif sub == "rm":
            # ── Delete run ──────────────────────────────────────────────
            n_str = parts[1].strip() if len(parts) > 1 else ""
            if not n_str:
                self._print_err("Usage: /runs rm <number>  (use /runs to see the list)")
                return

            # Fetch runs to resolve the number → project_id
            with self.console.status(f"[{ORANGE}]Fetching runs…[/{ORANGE}]", spinner="dots"):
                try:
                    runs = self.client.get_runs()
                except ApiError as exc:
                    self._print_err(f"Could not fetch runs: {exc.message}")
                    return

            try:
                row = int(n_str)
            except ValueError:
                self._print_err(f"{n_str!r} is not a valid row number.")
                return

            if row < 1 or row > len(runs):
                self._print_err(f"Row {row} is out of range (1–{len(runs)}).")
                return

            run = runs[row - 1]
            project_id = run["project_id"]
            name = run.get("name", project_id)
            n_sims = run.get("total_simulations", 0)
            n_reports = run.get("total_reports", 0)

            # Confirm inline before destroying data
            self.console.print(
                f"[bold {ORANGE}]Delete[/bold {ORANGE}] "
                f"[bold]{name}[/bold] ([{DIM}]{project_id}[/{DIM}]) "
                f"with {n_sims} sim(s) and {n_reports} report(s)? [y/N] ",
                end="",
            )
            answer = input().strip().lower()
            if answer not in ("y", "yes"):
                self._print_hint("Aborted.")
                return

            with self.console.status(f"[{ORANGE}]Deleting…[/{ORANGE}]", spinner="dots"):
                try:
                    result = self.client.delete_run(project_id)
                except ApiError as exc:
                    self._print_err(f"Delete failed: {exc.message}")
                    return

            # Clear local cache entry (CLI owns this, not the backend)
            from .cache import IcpCache
            cache = IcpCache()
            data = cache._load()
            hash_to_remove = next(
                (h for h, v in data.items() if v.get("project_id") == project_id), None
            )
            if hash_to_remove:
                cache.delete(hash_to_remove)

            sims_del = result.get("deleted_simulations", 0)
            reports_del = result.get("deleted_reports", 0)
            graph_del = result.get("graph_deleted", False)
            cache_str = "cleared" if hash_to_remove else "not found"
            self._print_hint(
                f"Deleted {name} — "
                f"sims: {sims_del}, reports: {reports_del}, "
                f"graph: {'yes' if graph_del else 'no'}, cache: {cache_str}"
            )

            # Reset session if we just deleted the loaded project
            if hasattr(self, "project_id") and self.project_id == project_id:
                self.project_id = None
                self.graph_id = None
                self._print_hint("Active project cleared (it was the deleted run).")

        else:
            # ── List runs ──────────────────────────────────────────────
            with self.console.status(f"[{ORANGE}]Fetching runs…[/{ORANGE}]", spinner="dots"):
                try:
                    runs = self.client.get_runs()
                except ApiError as exc:
                    self._print_err(f"Could not fetch runs: {exc.message}")
                    return

            if not runs:
                self._print_hint("No runs found.")
                return

            table = Table(
                show_header=True,
                header_style=f"bold {ORANGE}",
                border_style=DIM,
                show_lines=False,
                padding=(0, 1),
            )
            table.add_column("#",        justify="right", min_width=3,  style=DIM)
            table.add_column("Name",     min_width=18)
            table.add_column("ICP file", min_width=16, style=DIM)
            table.add_column("Created",  min_width=16)
            table.add_column("Sims",     justify="right", min_width=4)
            table.add_column("Reports",  justify="right", min_width=7)
            table.add_column("Size",     justify="right", min_width=8)

            from rich.text import Text as RichText
            for i, run in enumerate(runs, start=1):
                icp = run.get("icp_file", "—")
                if len(icp) > 20:
                    icp = "…" + icp[-18:]

                created = run.get("created_at", "")
                if "T" in created:
                    created = created.replace("T", " ")[:16]

                name_text = RichText(run.get("name", "—"))
                name_text.stylize(f"bold {ORANGE}")

                table.add_row(
                    str(i),
                    name_text,
                    icp,
                    created,
                    str(run.get("total_simulations", 0)),
                    str(run.get("total_reports", 0)),
                    f"{run.get('disk_mb', 0):.1f} MB",
                )

            self.console.print()
            self.console.print(table)
            self.console.print()
            self._print_hint(f"{len(runs)} run(s). Use /runs rm <n> to delete one.")

    def _render_graph_inline(self, nodes: list, edges: list, graph_id: str) -> None:
        """Render graph nodes + edges as Rich panels inside the TUI."""
        # Stats header
        stats = Table.grid(padding=(0, 3))
        stats.add_column(style=f"bold {ORANGE}", min_width=6)
        stats.add_column(style=DIM)
        stats.add_row(str(len(nodes)), "nodes")
        stats.add_row(str(len(edges)), "edges")
        self.console.print()
        self.console.print(Panel(
            stats,
            title=f"[bold {ORANGE}]ICP Knowledge Graph[/bold {ORANGE}]  "
                  f"[{DIM}]{graph_id[:16]}…[/{DIM}]",
            border_style=ORANGE, padding=(0, 2),
        ))

        # Nodes
        node_table = Table(show_header=True, header_style=f"bold {ORANGE}",
                           border_style=DIM, show_lines=True, padding=(0, 1))
        node_table.add_column("Type",    min_width=20, style=f"bold {ORANGE}")
        node_table.add_column("Name",    min_width=20)
        node_table.add_column("Summary", min_width=30, style=DIM)
        for n in nodes:
            labels = n.get("labels") or []
            entity_type = labels[0] if labels else "—"
            name = n.get("name") or "—"
            summary = (n.get("summary") or "").strip()
            if summary.startswith(name):
                summary = summary[len(name):].strip(" -()")
            node_table.add_row(entity_type, name, summary[:70] if summary else "—")
        self.console.print(Panel(node_table,
                                 title=f"[{DIM}]Entities ({len(nodes)})[/{DIM}]",
                                 border_style=ORANGE))

        # Edges
        if edges:
            edge_table = Table(show_header=True, header_style=f"bold {ORANGE}",
                               border_style=DIM, show_lines=True, padding=(0, 1))
            edge_table.add_column("Source",       min_width=16)
            edge_table.add_column("Relationship", min_width=20, style=f"bold {ORANGE}")
            edge_table.add_column("Target",       min_width=16)
            edge_table.add_column("Fact",         min_width=36, style=DIM)
            for e in edges:
                edge_table.add_row(
                    e.get("source_node_name") or "—",
                    e.get("fact_type") or "—",
                    e.get("target_node_name") or "—",
                    (e.get("fact") or "")[:80],
                )
            self.console.print(Panel(edge_table,
                                     title=f"[{DIM}]Relationships ({len(edges)})[/{DIM}]",
                                     border_style=ORANGE))
        self.console.print()

    def _cmd_quit(self) -> None:
        """Exit cleanly."""
        self._print(f"\n[{DIM}]Goodbye.[/{DIM}]\n")
        raise SystemExit(0)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for `prospect-sim-tui` script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="prospect-sim human TUI — interactive cold email variant tester",
        add_help=True,
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("PROSPECT_SIM_API_URL", ""),
        help="Backend URL (default: from config or http://localhost:5001)",
    )
    args = parser.parse_args()

    tui = ProspectSimTUI(api_url=args.api_url)
    try:
        tui.run()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
