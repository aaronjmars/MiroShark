"""Email inbox agent environment — what the B2B agent observes each round.

Converts the platform's inbox state into a text prompt the agent's LLM receives.
The agent sees their inbox, which emails they've already opened/read/replied to,
and a reminder of their current workload context.
"""
from __future__ import annotations

from wonderwall.simulations.base import BaseEnvironment


class EmailInboxEnvironment(BaseEnvironment):
    """Converts inbox state into the text observation prompt for B2B agents."""

    async def to_text_prompt(self) -> str:
        # Fetch the agent's current inbox state from the platform
        inbox_data = await self.action.perform_action(
            self.action.agent_id, "get_inbox"
        )

        parts = []

        if inbox_data.get("success") and inbox_data.get("inbox"):
            parts.append("YOUR INBOX — COLD EMAILS RECEIVED:")
            parts.append("")

            for email in inbox_data["inbox"]:
                status_parts = []
                if email["replied"]:
                    status_parts.append("✓ REPLIED")
                elif email["forwarded"]:
                    status_parts.append("→ FORWARDED")
                elif email["read_to_completion"]:
                    status_parts.append("READ")
                elif email["opened"]:
                    status_parts.append("OPENED")
                else:
                    status_part = "UNREAD"
                    status_parts.append(status_part)

                if email["dropout_point"] and not email["replied"]:
                    status_parts.append(f"[dropped at: {email['dropout_point']}]")

                status = " | ".join(status_parts)
                parts.append(
                    f"  [{email['variant_id']}] {email['variant_label']}\n"
                    f"      Subject: \"{email['subject_line']}\"\n"
                    f"      Hook type: {email['hook_type']} | Status: {status}"
                )
                parts.append("")
        else:
            parts.append("No emails in your inbox yet.")
            parts.append("")

        # Inject cross-platform context if available (e.g., from social media rounds)
        if self.extra_observation_context:
            parts.append(f"CONTEXT FROM OTHER CHANNELS:\n{self.extra_observation_context}")
            parts.append("")

        parts.append("DECIDE how to interact with your inbox this round:")
        parts.append("  - open_email(variant_id) — open an unread email")
        parts.append("  - read_email(variant_id) — read an opened email fully")
        parts.append("  - reply(variant_id, notes) — send a positive reply")
        parts.append("  - forward(variant_id, notes) — forward to a colleague")
        parts.append("  - archive(variant_id, dropout_point) — discard without replying")
        parts.append("  - do_nothing() — no action this round (busy, distracted, etc.)")
        parts.append("")
        parts.append(
            "You receive dozens of cold emails per week. Be realistic — most will be archived. "
            "Only engage further if the email is genuinely relevant to your current situation."
        )

        return "\n".join(parts)
