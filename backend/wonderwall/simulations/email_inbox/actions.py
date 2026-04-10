"""Email inbox agent actions — LLM-callable tools for B2B decision-maker personas.

Each public async method is auto-discovered as an LLM tool via
BaseAction.get_openai_function_list(). Docstrings become the tool descriptions
the LLM sees — they must guide realistic B2B inbox behavior.
"""
from __future__ import annotations

from wonderwall.simulations.base import BaseAction


class EmailInboxAction(BaseAction):
    """Actions available to a B2B decision-maker agent in the email inbox simulation."""

    async def open_email(self, variant_id: int):
        """Open a cold email to see the sender and subject line preview.

        Call this when a subject line catches your attention and you want to
        see more. This is a low-commitment action — opening does NOT mean
        you will reply. You open maybe 20-40% of cold emails you receive.

        Common triggers for opening:
        - Subject mentions something specific about your company or role
        - A timeline or event hooks your curiosity (not generic pain)
        - The sender is known to you or referred by someone you trust
        - The subject is short, specific, and doesn't feel like a template

        Args:
            variant_id (int): The ID of the email variant to open.

        Returns:
            dict: Contains 'subject_line', 'body', and 'hook_type' of the email.
        """
        return await self.perform_action(variant_id, "open_email")

    async def read_email(self, variant_id: int):
        """Read the entire email body after opening.

        Call this only AFTER opening the email (open_email first), and only
        if the first paragraph didn't immediately make you want to archive it.
        You fully read maybe 40-60% of emails you open.

        You stop reading when:
        - The opening is generic ("I help companies like yours...")
        - You hit a pain/problem framing that feels presumptuous
        - The email is longer than 150 words and not immediately relevant
        - There's no specific detail that proves they know your situation

        Args:
            variant_id (int): The ID of the email variant to read fully.

        Returns:
            dict: Confirmation that you've read to completion.
        """
        return await self.perform_action(variant_id, "read_email")

    async def reply(self, variant_id: int, notes: str = ""):
        """Send a positive reply to the email — genuine interest signal.

        Call this only if the email passed ALL of:
        1. Subject was specific enough to open
        2. Opening didn't feel like a template
        3. The body addressed something you actually care about right now
        4. The CTA was specific and low-commitment (not 'book a 30-min demo')
        5. The timing felt right for your current situation

        As a busy HR Director, you reply to maybe 5-15% of cold emails you open.
        Do NOT reply unless all conditions are met — be realistic about your
        skepticism and calendar constraints.

        Args:
            variant_id (int): The ID of the email variant you're replying to.
            notes (str): Brief reason for your reply or what triggered it.

        Returns:
            dict: Confirmation of reply.
        """
        return await self.perform_action((variant_id, notes), "reply")

    async def forward(self, variant_id: int, notes: str = ""):
        """Forward the email to a colleague for their opinion or to loop them in.

        Call this when the email is relevant but you want a second opinion,
        or when it maps to a colleague's responsibility. Forwarding is a
        stronger positive signal than just reading — it means you see value
        AND have an internal champion in mind.

        Typical trigger: email addresses an initiative your team is working on
        and you think the CEO/CFO/team lead should see it.

        Args:
            variant_id (int): The ID of the email variant to forward.
            notes (str): Who you'd forward it to and why.

        Returns:
            dict: Confirmation of forward action.
        """
        return await self.perform_action((variant_id, notes), "forward")

    async def archive(self, variant_id: int, dropout_point: str = "unknown"):
        """Archive the email without replying — you've decided it's not worth your time.

        Call this when you decide to stop engaging with an email. Be specific
        about WHERE you dropped off — this is the most valuable feedback.

        dropout_point options:
        - 'subject_line' — never opened it; subject didn't grab you
        - 'opening'      — opened but first sentence killed it (generic/wrong person)
        - 'body'         — got into the body but lost interest before the CTA
        - 'cta'          — read everything but the ask was too big or wrong timing
        - 'timing'       — content is fine but wrong moment in your calendar/budget cycle

        This is your default action for most cold emails. HR Directors archive
        80-95% of cold outreach they receive.

        Args:
            variant_id (int): The ID of the email variant to archive.
            dropout_point (str): Where you stopped engaging. Be specific.

        Returns:
            dict: Confirmation with your dropout point recorded.
        """
        return await self.perform_action((variant_id, dropout_point), "archive")
