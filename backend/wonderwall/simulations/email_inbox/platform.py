"""Email inbox simulation platform.

Server-side platform that handles B2B email inbox interactions.
Each agent receives cold email variants and decides how to engage.
Tracks open → read → reply intent → booking probability per variant.

Follows the same BasePlatform pattern as PolymarketPlatform.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, List, Dict

from wonderwall.clock.clock import Clock
from wonderwall.simulations.base import BasePlatform

logger = logging.getLogger(__name__)


class EmailInboxPlatform(BasePlatform):
    """B2B email inbox platform for cold outreach copy variant testing.

    Agents represent HR Director / Head of People personas at Spanish SMEs.
    Each round, agents decide how to interact with the emails in their inbox.
    State is tracked in SQLite: opens, reads, replies, and dropout points.
    """

    required_schemas = ["email.sql"]

    def __init__(
        self,
        db_path: str,
        channel: Any = None,
        sandbox_clock: Clock | None = None,
        start_time: datetime | None = None,
        variants: List[Dict] | None = None,
    ):
        # Store variants before super().__init__ so _seed_variants can be called after DB init
        self._pending_variants = variants or []
        super().__init__(
            db_path=db_path,
            channel=channel,
            sandbox_clock=sandbox_clock,
            start_time=start_time,
        )
        # Seed variants into DB immediately after schema init
        if self._pending_variants:
            self._seed_variants(self._pending_variants)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _seed_variants(self, variants: List[Dict]) -> None:
        """Insert email copy variants into the DB at simulation start."""
        current_time = self.get_current_time()
        for v in variants:
            self._execute_db_command(
                "INSERT OR IGNORE INTO email_variant "
                "(variant_id, variant_label, subject_line, body, hook_type, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    v.get("variant_id", v.get("id", 0)),
                    v.get("variant_label", v.get("label", f"Variant {v.get('id', 0)}")),
                    v.get("subject_line", ""),
                    v.get("body", ""),
                    v.get("hook_type", "unknown"),
                    current_time,
                ),
                commit=False,
            )
        self.db.commit()
        logger.info(f"Seeded {len(variants)} email variants into inbox DB")

    # ------------------------------------------------------------------
    # Platform actions (dispatched via getattr by BasePlatform.running)
    # ------------------------------------------------------------------

    async def open_email(self, agent_id: int, message: Any) -> Dict:
        """Agent opens an email variant — records the open event."""
        variant_id = int(message) if message is not None else 0
        current_time = self.get_current_time()

        # Update or insert inbox state (mark opened)
        self._execute_db_command(
            "INSERT INTO agent_inbox_state "
            "(agent_id, variant_id, opened, last_round, created_at) "
            "VALUES (?, ?, 1, ?, ?) "
            "ON CONFLICT(agent_id, variant_id) DO UPDATE SET "
            "opened=1, last_round=excluded.last_round",
            (agent_id, variant_id, 0, current_time),
            commit=True,
        )
        self._record_trace(agent_id, "open_email", {"variant_id": variant_id}, current_time)
        self._log_inbox_event(agent_id, variant_id, "open_email", None, None, current_time)

        # Return the email content so the agent can read it
        row = self._execute_db_command(
            "SELECT subject_line, body, hook_type FROM email_variant WHERE variant_id=?",
            (variant_id,)
        ).fetchone()

        if row:
            return {
                "success": True,
                "variant_id": variant_id,
                "subject_line": row[0],
                "body": row[1],
                "hook_type": row[2],
            }
        return {"success": False, "error": f"Variant {variant_id} not found"}

    async def read_email(self, agent_id: int, message: Any) -> Dict:
        """Agent reads the email body to completion."""
        variant_id = int(message) if message is not None else 0
        current_time = self.get_current_time()

        self._execute_db_command(
            "INSERT INTO agent_inbox_state "
            "(agent_id, variant_id, opened, read_to_completion, last_round, created_at) "
            "VALUES (?, ?, 1, 1, ?, ?) "
            "ON CONFLICT(agent_id, variant_id) DO UPDATE SET "
            "opened=1, read_to_completion=1, last_round=excluded.last_round",
            (agent_id, variant_id, 0, current_time),
            commit=True,
        )
        self._record_trace(agent_id, "read_email", {"variant_id": variant_id}, current_time)
        self._log_inbox_event(agent_id, variant_id, "read_email", None, None, current_time)

        return {"success": True, "variant_id": variant_id, "action": "read_to_completion"}

    async def reply(self, agent_id: int, message: Any) -> Dict:
        """Agent sends a positive reply to an email variant.

        This is the primary success signal — represents genuine interest.
        """
        # message is (variant_id, reply_text)
        if isinstance(message, (list, tuple)) and len(message) >= 1:
            variant_id = int(message[0])
            notes = str(message[1]) if len(message) > 1 else None
        else:
            variant_id = int(message) if message is not None else 0
            notes = None

        current_time = self.get_current_time()

        self._execute_db_command(
            "INSERT INTO agent_inbox_state "
            "(agent_id, variant_id, opened, read_to_completion, replied, reply_intent_score, last_round, created_at) "
            "VALUES (?, ?, 1, 1, 1, 1.0, ?, ?) "
            "ON CONFLICT(agent_id, variant_id) DO UPDATE SET "
            "opened=1, read_to_completion=1, replied=1, reply_intent_score=1.0, "
            "last_round=excluded.last_round",
            (agent_id, variant_id, 0, current_time),
            commit=True,
        )
        self._record_trace(agent_id, "reply", {"variant_id": variant_id, "notes": notes}, current_time)
        self._log_inbox_event(agent_id, variant_id, "reply", None, notes, current_time)

        return {"success": True, "variant_id": variant_id, "action": "replied"}

    async def archive(self, agent_id: int, message: Any) -> Dict:
        """Agent archives the email without replying — records dropout point."""
        # message is (variant_id, dropout_point)
        if isinstance(message, (list, tuple)) and len(message) >= 1:
            variant_id = int(message[0])
            dropout_point = str(message[1]) if len(message) > 1 else "unknown"
        else:
            variant_id = int(message) if message is not None else 0
            dropout_point = "unknown"

        current_time = self.get_current_time()

        # Record dropout point — only set if not already set (first dropout wins)
        self._execute_db_command(
            "INSERT INTO agent_inbox_state "
            "(agent_id, variant_id, opened, dropout_point, last_round, created_at) "
            "VALUES (?, ?, 1, ?, ?, ?) "
            "ON CONFLICT(agent_id, variant_id) DO UPDATE SET "
            "opened=CASE WHEN opened=0 THEN 1 ELSE opened END, "
            "dropout_point=CASE WHEN dropout_point IS NULL THEN excluded.dropout_point ELSE dropout_point END, "
            "last_round=excluded.last_round",
            (agent_id, variant_id, dropout_point, 0, current_time),
            commit=True,
        )
        self._record_trace(agent_id, "archive", {"variant_id": variant_id, "dropout_point": dropout_point}, current_time)
        self._log_inbox_event(agent_id, variant_id, "archive", dropout_point, None, current_time)

        return {"success": True, "variant_id": variant_id, "dropout_point": dropout_point}

    async def forward(self, agent_id: int, message: Any) -> Dict:
        """Agent forwards the email to a colleague — strong positive signal.

        Forwarding indicates the agent sees value AND wants an internal sponsor.
        """
        if isinstance(message, (list, tuple)) and len(message) >= 1:
            variant_id = int(message[0])
            notes = str(message[1]) if len(message) > 1 else None
        else:
            variant_id = int(message) if message is not None else 0
            notes = None

        current_time = self.get_current_time()

        # Forward implies opened + read + high intent (0.8)
        self._execute_db_command(
            "INSERT INTO agent_inbox_state "
            "(agent_id, variant_id, opened, read_to_completion, forwarded, reply_intent_score, last_round, created_at) "
            "VALUES (?, ?, 1, 1, 1, 0.8, ?, ?) "
            "ON CONFLICT(agent_id, variant_id) DO UPDATE SET "
            "opened=1, read_to_completion=1, forwarded=1, "
            "reply_intent_score=MAX(reply_intent_score, 0.8), "
            "last_round=excluded.last_round",
            (agent_id, variant_id, 0, current_time),
            commit=True,
        )
        self._record_trace(agent_id, "forward", {"variant_id": variant_id, "notes": notes}, current_time)
        self._log_inbox_event(agent_id, variant_id, "forward", None, notes, current_time)

        return {"success": True, "variant_id": variant_id, "action": "forwarded_to_colleague"}

    # ------------------------------------------------------------------
    # Query helpers used by EmailInboxEnvironment
    # ------------------------------------------------------------------

    async def get_inbox(self, agent_id: int) -> Dict:
        """Return all email variants with current open/read status for the agent."""
        variants = self._execute_db_command(
            "SELECT v.variant_id, v.variant_label, v.subject_line, v.hook_type, "
            "COALESCE(s.opened, 0), COALESCE(s.read_to_completion, 0), "
            "COALESCE(s.replied, 0), COALESCE(s.forwarded, 0), s.dropout_point "
            "FROM email_variant v "
            "LEFT JOIN agent_inbox_state s "
            "ON v.variant_id = s.variant_id AND s.agent_id = ? "
            "ORDER BY v.variant_id",
            (agent_id,)
        ).fetchall()

        return {
            "success": True,
            "inbox": [
                {
                    "variant_id": row[0],
                    "variant_label": row[1],
                    "subject_line": row[2],
                    "hook_type": row[3],
                    "opened": bool(row[4]),
                    "read_to_completion": bool(row[5]),
                    "replied": bool(row[6]),
                    "forwarded": bool(row[7]),
                    "dropout_point": row[8],
                }
                for row in variants
            ]
        }

    # ------------------------------------------------------------------
    # Report data helpers — called by report agent after simulation
    # ------------------------------------------------------------------

    def get_variant_summary(self) -> List[Dict]:
        """Aggregate stats per variant across all agents — for report generation."""
        rows = self._execute_db_command(
            "SELECT "
            "  v.variant_id, v.variant_label, v.hook_type, "
            "  COUNT(DISTINCT s.agent_id) as total_agents, "
            "  SUM(s.opened) as total_opens, "
            "  SUM(s.read_to_completion) as total_reads, "
            "  SUM(s.replied) as total_replies, "
            "  SUM(s.forwarded) as total_forwards, "
            "  AVG(s.reply_intent_score) as avg_intent "
            "FROM email_variant v "
            "LEFT JOIN agent_inbox_state s ON v.variant_id = s.variant_id "
            "GROUP BY v.variant_id "
            "ORDER BY total_replies DESC, avg_intent DESC",
        ).fetchall()

        return [
            {
                "variant_id": row[0],
                "variant_label": row[1],
                "hook_type": row[2],
                "total_agents": row[3] or 0,
                "total_opens": row[4] or 0,
                "total_reads": row[5] or 0,
                "total_replies": row[6] or 0,
                "total_forwards": row[7] or 0,
                "avg_reply_intent": round(float(row[8] or 0), 3),
                "open_rate": round((row[4] or 0) / max(row[3] or 1, 1), 3),
                "reply_rate": round((row[6] or 0) / max(row[3] or 1, 1), 3),
            }
            for row in rows
        ]

    def get_dropout_breakdown(self) -> Dict[str, List[Dict]]:
        """Per-variant dropout point distribution — where agents lost interest."""
        rows = self._execute_db_command(
            "SELECT v.variant_label, s.dropout_point, COUNT(*) as count "
            "FROM agent_inbox_state s "
            "JOIN email_variant v ON s.variant_id = v.variant_id "
            "WHERE s.dropout_point IS NOT NULL "
            "GROUP BY v.variant_id, s.dropout_point "
            "ORDER BY v.variant_id, count DESC"
        ).fetchall()

        result: Dict[str, List[Dict]] = {}
        for row in rows:
            label = row[0]
            if label not in result:
                result[label] = []
            result[label].append({"dropout_point": row[1], "count": row[2]})
        return result

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _log_inbox_event(
        self,
        agent_id: int,
        variant_id: int,
        event_type: str,
        dropout_point: str | None,
        notes: str | None,
        timestamp: str,
    ) -> None:
        """Append a row to the inbox_event log."""
        # Derive current round from last_round value in agent_inbox_state
        row = self._execute_db_command(
            "SELECT last_round FROM agent_inbox_state WHERE agent_id=? AND variant_id=?",
            (agent_id, variant_id)
        ).fetchone()
        round_num = row[0] if row else 0

        self._execute_db_command(
            "INSERT INTO inbox_event "
            "(agent_id, variant_id, round_num, event_type, dropout_point, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agent_id, variant_id, round_num, event_type, dropout_point, notes, timestamp),
            commit=True,
        )
