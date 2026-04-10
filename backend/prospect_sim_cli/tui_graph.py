"""
TuiGraphMixin — /graph command for ProspectSimTUI.

Fetches the ICP knowledge graph structure from the backend and renders
it as a Rich panel: entity type breakdown, node/edge counts, top entities.
Optionally opens the browser for the full D3 force-directed visualization.
"""

from __future__ import annotations

import webbrowser
from collections import Counter

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .client import ApiError
from .tui_constants import DIM, ORANGE


class TuiGraphMixin:
    """Graph inspection command. Mixed into ProspectSimTUI."""

    def _cmd_graph(self, args: str) -> None:
        """
        Show the ICP knowledge graph structure.

        /graph          — print entity breakdown + counts
        /graph open     — also open the D3 web view in a browser
        """
        if not self.project_id:
            self._print_err("No project loaded. Run /icp <file> first.")
            return

        open_browser = args.strip().lower() == "open"

        # Resolve project → graph_id
        with self.console.status(f"[{ORANGE}]Fetching graph data…[/{ORANGE}]", spinner="dots"):
            try:
                project = self.client.get_project(self.project_id)
            except ApiError as exc:
                self._print_err(f"Could not fetch project: {exc.message}")
                return

            graph_id = project.get("graph_id") or project.get("id")
            if not graph_id:
                self._print_err("Project has no graph_id. Was the graph built?")
                return

            try:
                data = self.client.get_graph_data(graph_id)
            except ApiError as exc:
                self._print_err(f"Could not fetch graph data: {exc.message}")
                return

        self._render_graph(data, graph_id)

        if open_browser:
            # Web UI lives at the Vite dev server — guess the port from api_url
            # Default: http://localhost:5173
            web_url = self.client.base_url.replace("5001", "5173")
            webbrowser.open(f"{web_url}/graph/{graph_id}")
            self._print_hint(f"Opened graph in browser: {web_url}/graph/{graph_id}")
        else:
            self._print_hint("Run /graph open to view the full D3 visualization in your browser.")

    def _render_graph(self, data: dict, graph_id: str) -> None:
        """Render the graph overview panel with entity breakdown table."""
        node_count = data.get("node_count", 0)
        edge_count = data.get("edge_count", 0)
        entity_types = data.get("entity_types", [])
        nodes = data.get("nodes", [])

        # ── Header stats ──────────────────────────────────────────────────────
        stats = Table.grid(padding=(0, 4))
        stats.add_column(style=f"bold {ORANGE}")
        stats.add_column(style=DIM)

        stats.add_row(str(node_count), "nodes")
        stats.add_row(str(edge_count), "edges")
        stats.add_row(str(len(entity_types)), "entity types")

        # ── Entity type breakdown ─────────────────────────────────────────────
        # Count by type from nodes list when available; fall back to entity_types list
        type_counts: Counter = Counter()
        if nodes:
            for n in nodes:
                t = n.get("type") or n.get("label") or "unknown"
                type_counts[t] += 1
        elif entity_types:
            for t in entity_types:
                type_counts[t] = type_counts.get(t, 0) + 1

        breakdown = Table(
            show_header=True,
            header_style=f"bold {ORANGE}",
            border_style=ORANGE,
            show_lines=False,
            padding=(0, 1),
        )
        breakdown.add_column("Entity Type", min_width=22)
        breakdown.add_column("Count", justify="right", min_width=6)
        breakdown.add_column("Bar", min_width=20)

        if type_counts:
            max_count = max(type_counts.values()) or 1
            bar_width = 18
            for entity_type, count in type_counts.most_common():
                filled = int(bar_width * count / max_count)
                bar = Text()
                bar.append("█" * filled, style=f"bold {ORANGE}")
                bar.append("░" * (bar_width - filled), style=DIM)
                breakdown.add_row(entity_type, str(count), bar)
        else:
            breakdown.add_row("[dim]No type data available[/dim]", "—", "")

        # ── Top entities (sample) ─────────────────────────────────────────────
        sample_panel = None
        if nodes:
            sample_table = Table(
                show_header=True,
                header_style=f"bold {ORANGE}",
                border_style=DIM,
                show_lines=False,
                padding=(0, 1),
            )
            sample_table.add_column("Name", min_width=24)
            sample_table.add_column("Type", min_width=16)

            # Show up to 8 entities, varied by type
            seen_types: set = set()
            shown = 0
            for n in nodes:
                t = n.get("type") or n.get("label") or "unknown"
                name = n.get("name") or n.get("id") or "?"
                # Prefer one per type first, then fill with the rest
                if t not in seen_types or shown < 8:
                    sample_table.add_row(
                        f"[{ORANGE}]{name}[/{ORANGE}]" if t not in seen_types else name,
                        f"[{DIM}]{t}[/{DIM}]",
                    )
                    seen_types.add(t)
                    shown += 1
                if shown >= 8:
                    break

            if shown < node_count:
                sample_table.add_row(
                    f"[{DIM}]… and {node_count - shown} more[/{DIM}]", ""
                )

            sample_panel = Panel(
                sample_table,
                title=f"[{DIM}]Sample Entities[/{DIM}]",
                border_style=DIM,
            )

        # ── Compose final output ──────────────────────────────────────────────
        self.console.print()
        self.console.print(
            Panel(
                stats,
                title=f"[bold {ORANGE}]ICP Knowledge Graph[/bold {ORANGE}]",
                subtitle=f"[{DIM}]{graph_id[:16]}…[/{DIM}]",
                border_style=ORANGE,
                padding=(0, 2),
            )
        )

        self.console.print(
            Panel(
                breakdown,
                title=f"[{DIM}]Entity Types[/{DIM}]",
                border_style=ORANGE,
            )
        )

        if sample_panel:
            self.console.print(sample_panel)

        self.console.print()
