"""
Round Memory — sliding-window context from all platforms for every agent.

After each round, raw actions from Twitter and Reddit are recorded. An LLM
compacts old rounds into short summaries. The resulting context follows a
sliding window:

    rounds 0 … N-3  →  compacted (one paragraph each, batched into a single block)
    round  N-2       →  compacted
    round  N-1       →  FULL detail (every action)
    round  N         →  current (actions so far this round, from platforms that
                         have already stepped)

This gives agents a sense of history without blowing up the prompt.

Usage in the simulation loop:

    memory = RoundMemory(llm_client, minutes_per_round)

    for round_num in range(total_rounds):
        memory.start_round(round_num, simulated_day, simulated_hour)

        # After each platform steps:
        memory.record("twitter", round_num, actual_actions)
        memory.record("reddit",  round_num, actual_actions)

        # End of round — compact the PREVIOUS round (N-1) if not yet compacted
        await memory.compact_previous_round(round_num)
"""

from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Action formatting helpers ────────────────────────────────────────

_ACTION_LABELS = {
    "CREATE_POST": "posted",
    "CREATE_COMMENT": "commented",
    "LIKE_POST": "liked a post",
    "DISLIKE_POST": "disliked a post",
    "LIKE_COMMENT": "liked a comment",
    "DISLIKE_COMMENT": "disliked a comment",
    "REPOST": "reposted",
    "QUOTE_POST": "quote-posted",
    "FOLLOW": "followed",
    "MUTE": "muted",
}

_SKIP_ACTIONS = {
    "DO_NOTHING", "REFRESH", "TREND", "SEARCH_POSTS", "SEARCH_USER",
    "do_nothing", "refresh", "trend", "search_posts", "search_user",
}

_MAX_CONTENT_PREVIEW = 180


def _format_action(action: Dict[str, Any]) -> Optional[str]:
    """Format a single action dict into a readable one-liner."""
    action_type = action.get("action_type", "")
    if action_type in _SKIP_ACTIONS:
        return None

    agent_name = action.get("agent_name", f"Agent_{action.get('agent_id', '?')}")
    label = _ACTION_LABELS.get(action_type, action_type.lower())
    args = action.get("action_args", {})

    content = (
        args.get("content")
        or args.get("quote_content")
        or args.get("post_content")
        or args.get("comment_content")
    )

    if content:
        if len(content) > _MAX_CONTENT_PREVIEW:
            content = content[:_MAX_CONTENT_PREVIEW] + "…"
        return f'{agent_name} {label}: "{content}"'

    # Targeting another user
    target = (
        args.get("target_user_name")
        or args.get("post_author_name")
        or args.get("followee_name")
    )
    if target:
        return f"{agent_name} {label} {target}"

    return f"{agent_name} {label}"


def _format_actions_full(platform: str, actions: List[Dict[str, Any]]) -> str:
    """Format all meaningful actions from one platform into a block."""
    lines = []
    for a in actions:
        line = _format_action(a)
        if line:
            lines.append(f"  - {line}")
    if not lines:
        return f"  [{platform.title()}] No notable activity"
    return f"  [{platform.title()}]\n" + "\n".join(lines)


# ── Round record ─────────────────────────────────────────────────────

@dataclass
class RoundRecord:
    """One round's data across all platforms."""

    round_num: int
    simulated_day: int = 1
    simulated_hour: int = 0
    platform_actions: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    compacted_summary: Optional[str] = None

    @property
    def is_compacted(self) -> bool:
        return self.compacted_summary is not None

    def full_text(self) -> str:
        """Full-detail rendering of all actions this round."""
        header = f"Day {self.simulated_day}, {self.simulated_hour:02d}:00 (round {self.round_num + 1})"
        parts = [header]
        for platform in ("twitter", "reddit"):
            actions = self.platform_actions.get(platform, [])
            if actions:
                parts.append(_format_actions_full(platform, actions))
        if len(parts) == 1:
            parts.append("  No activity across any platform")
        return "\n".join(parts)

    def action_count(self) -> int:
        return sum(len(a) for a in self.platform_actions.values())


# ── Main class ───────────────────────────────────────────────────────

class RoundMemory:
    """Sliding-window round memory with LLM compaction.

    Args:
        llm_client: An LLM client with a .chat(messages, temperature) method.
        minutes_per_round: Simulated minutes per round (for time labels).
        compact_batch_size: How many old compacted rounds to batch into one
            combined summary when the history gets long.
    """

    def __init__(
        self,
        llm_client=None,
        minutes_per_round: int = 60,
        compact_batch_size: int = 6,
    ):
        self.llm = llm_client
        self.minutes_per_round = minutes_per_round
        self.compact_batch_size = compact_batch_size

        self._rounds: Dict[int, RoundRecord] = {}
        # Combined summary of very old rounds (batched compaction)
        self._ancient_summary: Optional[str] = None
        self._ancient_up_to_round: int = -1  # inclusive
        # Thread pool for background compaction (doesn't block the round loop)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="compact")

    def start_round(self, round_num: int, simulated_day: int, simulated_hour: int):
        """Initialize a new round record."""
        if round_num not in self._rounds:
            self._rounds[round_num] = RoundRecord(
                round_num=round_num,
                simulated_day=simulated_day,
                simulated_hour=simulated_hour,
            )

    def record(self, platform: str, round_num: int, actions: List[Dict[str, Any]]):
        """Record actions from one platform for a round.

        Call this after each platform steps, BEFORE the next platform steps,
        so that subsequent platforms see what happened.
        """
        if round_num not in self._rounds:
            self._rounds[round_num] = RoundRecord(round_num=round_num)
        self._rounds[round_num].platform_actions[platform] = actions

    # ── Context building ─────────────────────────────────────────

    def build_context(self, current_round: int) -> str:
        """Build the full memory context string for injection.

        Returns a prompt section with:
        1. Ancient summary (batched compaction of very old rounds)
        2. Individual compacted rounds (N-2 and older, not yet batched)
        3. Full detail of round N-1
        4. Partial detail of round N (platforms that have already stepped)
        """
        sections = []

        # ── Ancient batched summary ──
        if self._ancient_summary:
            sections.append(
                f"[Simulation history through round {self._ancient_up_to_round + 1}]\n"
                + self._ancient_summary
            )

        # ── Individual compacted rounds (between ancient and N-2) ──
        compacted_rounds = []
        for rnum in sorted(self._rounds.keys()):
            if rnum > self._ancient_up_to_round and rnum < current_round - 1:
                rec = self._rounds[rnum]
                if rec.is_compacted:
                    compacted_rounds.append(
                        f"Day {rec.simulated_day}, {rec.simulated_hour:02d}:00 "
                        f"(round {rnum + 1}): {rec.compacted_summary}"
                    )
                else:
                    # Not yet compacted — use a quick summary
                    count = rec.action_count()
                    compacted_rounds.append(
                        f"Day {rec.simulated_day}, {rec.simulated_hour:02d}:00 "
                        f"(round {rnum + 1}): {count} actions across platforms"
                    )

        if compacted_rounds:
            sections.append(
                "[Recent history]\n" + "\n".join(compacted_rounds)
            )

        # ── Full detail of round N-1 ──
        prev_round = current_round - 1
        if prev_round >= 0 and prev_round in self._rounds:
            rec = self._rounds[prev_round]
            sections.append(
                "[Previous round — full detail]\n" + rec.full_text()
            )

        # ── Current round (partial — platforms that have already acted) ──
        if current_round in self._rounds:
            rec = self._rounds[current_round]
            if rec.platform_actions:
                parts = [
                    f"[Current round — Day {rec.simulated_day}, "
                    f"{rec.simulated_hour:02d}:00 (round {current_round + 1})]"
                ]
                for platform in ("twitter", "reddit"):
                    actions = rec.platform_actions.get(platform, [])
                    if actions:
                        parts.append(_format_actions_full(platform, actions))
                if len(parts) > 1:
                    sections.append("\n".join(parts))

        if not sections:
            return ""

        header = "# SIMULATION MEMORY — WHAT HAS HAPPENED"
        footer = (
            "Use this history to inform your decisions. "
            "React to trends and arguments you observe."
        )
        return header + "\n\n" + "\n\n".join(sections) + "\n\n" + footer

    # ── Compaction ───────────────────────────────────────────────

    async def compact_previous_round(self, current_round: int):
        """Compact round N-2 (the round before the previous one).

        Called at the end of each round. Runs the LLM call in a background
        thread so it doesn't block the simulation loop. If the compaction
        isn't done by the time the next round needs it, it falls back to
        a plain action count.
        """
        target = current_round - 2
        if target < 0:
            return
        rec = self._rounds.get(target)
        if not rec or rec.is_compacted:
            return

        if rec.action_count() == 0:
            rec.compacted_summary = "No notable activity."
            return

        if not self.llm:
            rec.compacted_summary = self._fallback_summary(rec)
            return

        # Run LLM compaction in background thread (non-blocking)
        full_text = rec.full_text()
        loop = asyncio.get_event_loop()
        loop.run_in_executor(self._pool, self._compact_sync, rec, full_text)

        # Also check if we should batch-compact ancient rounds
        self._maybe_batch_compact_sync(current_round)

    def _compact_sync(self, rec: RoundRecord, full_text: str):
        """Synchronous compaction — runs in thread pool."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a simulation historian. Summarize the following "
                        "simulation round into 2-3 concise sentences. Focus on: "
                        "key posts/arguments made, significant trades or market "
                        "movements, notable opinion shifts, and any emerging "
                        "conflicts or alliances. Be specific — name agents and "
                        "quote key phrases when important."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this simulation round:\n\n{full_text}",
                },
            ]
            summary = self.llm.chat(messages=messages, temperature=0.3)
            rec.compacted_summary = summary.strip()
            logger.info(f"Compacted round {rec.round_num + 1}: {len(rec.compacted_summary)} chars")
        except Exception as e:
            logger.warning(f"LLM compaction failed for round {rec.round_num + 1}: {e}")
            rec.compacted_summary = self._fallback_summary(rec)

    @staticmethod
    def _fallback_summary(rec: RoundRecord) -> str:
        """Quick fallback summary without LLM."""
        parts = []
        for platform, actions in rec.platform_actions.items():
            meaningful = [a for a in actions if a.get("action_type") not in _SKIP_ACTIONS]
            if meaningful:
                parts.append(f"{len(meaningful)} actions on {platform.title()}")
        return "; ".join(parts) if parts else "Minor activity."

    def _maybe_batch_compact_sync(self, current_round: int):
        """Batch-compact very old individual summaries into one block.

        When there are more than compact_batch_size compacted rounds
        sitting individually, merge them into _ancient_summary.
        """
        compacted_rounds = [
            rnum for rnum in sorted(self._rounds.keys())
            if rnum > self._ancient_up_to_round
            and rnum < current_round - 2
            and self._rounds[rnum].is_compacted
        ]

        if len(compacted_rounds) < self.compact_batch_size:
            return

        # Take all but the last 2 compacted rounds (keep some individual detail)
        to_batch = compacted_rounds[:-2]
        if not to_batch:
            return

        # Build text to summarize
        individual_summaries = []
        for rnum in to_batch:
            rec = self._rounds[rnum]
            individual_summaries.append(
                f"Round {rnum + 1} (Day {rec.simulated_day}, "
                f"{rec.simulated_hour:02d}:00): {rec.compacted_summary}"
            )

        combined_text = "\n".join(individual_summaries)

        if self._ancient_summary:
            combined_text = (
                f"Previous summary:\n{self._ancient_summary}\n\n"
                f"New rounds to integrate:\n{combined_text}"
            )

        if self.llm:
            try:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a simulation historian. Merge these round "
                            "summaries into a single coherent narrative paragraph "
                            "(4-6 sentences). Highlight the main story arcs: "
                            "how opinions evolved, key arguments that gained "
                            "traction, market movements, and any turning points. "
                            "Preserve specific agent names and key quotes."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Merge these summaries:\n\n{combined_text}",
                    },
                ]
                self._ancient_summary = self.llm.chat(
                    messages=messages, temperature=0.3
                ).strip()
            except Exception as e:
                logger.warning(f"Batch compaction failed: {e}")
                # Fallback: just concatenate
                self._ancient_summary = " | ".join(
                    f"R{self._rounds[r].round_num+1}: {self._rounds[r].compacted_summary}"
                    for r in to_batch
                )
        else:
            self._ancient_summary = " | ".join(
                f"R{self._rounds[r].round_num+1}: {self._rounds[r].compacted_summary}"
                for r in to_batch
            )

        self._ancient_up_to_round = to_batch[-1]

        # Free memory for batched rounds
        for rnum in to_batch:
            del self._rounds[rnum]

        logger.info(
            f"Batch-compacted rounds up to {self._ancient_up_to_round + 1} "
            f"({len(to_batch)} rounds merged)"
        )


# ── Injection helper (same marker pattern as belief_state, etc.) ─────

_ROUND_MEMORY_MARKER = "\n\n# SIMULATION MEMORY — WHAT HAS HAPPENED"


def inject_round_memory(agent, memory_text: str):
    """Inject round memory context into an agent's system message.

    Follows the same marker-replace pattern used by inject_belief_context
    and inject_cross_platform_context.
    """
    if not memory_text:
        return
    content = agent.system_message.content

    marker_pos = content.find(_ROUND_MEMORY_MARKER)
    if marker_pos != -1:
        # Find the next section marker (or end)
        next_marker = content.find("\n\n# ", marker_pos + len(_ROUND_MEMORY_MARKER))
        if next_marker != -1:
            content = content[:marker_pos] + content[next_marker:]
        else:
            content = content[:marker_pos]

    agent.system_message.content = content + "\n\n" + memory_text


def clear_round_memory(agent):
    """Remove the round memory section from an agent's system message."""
    content = agent.system_message.content
    marker_pos = content.find(_ROUND_MEMORY_MARKER)
    if marker_pos != -1:
        next_marker = content.find("\n\n# ", marker_pos + len(_ROUND_MEMORY_MARKER))
        if next_marker != -1:
            agent.system_message.content = content[:marker_pos] + content[next_marker:]
        else:
            agent.system_message.content = content[:marker_pos]
