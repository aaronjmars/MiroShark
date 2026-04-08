"""Email inbox simulation for B2B cold outreach copy variant testing.

Tests cold email copy variants against synthetic B2B decision-maker personas
(HR Director, Head of People at Spanish SMEs) before sending to real leads.

Usage::

    from wonderwall.simulations.email_inbox import email_inbox_simulation

    env = oasis.make(
        agent_graph=agent_graph,
        simulation=email_inbox_simulation,
        database_path="./data/inbox.db",
    )
"""
from wonderwall.simulations.base import SimulationConfig
from wonderwall.simulations.email_inbox.actions import EmailInboxAction
from wonderwall.simulations.email_inbox.environment import EmailInboxEnvironment
from wonderwall.simulations.email_inbox.platform import EmailInboxPlatform
from wonderwall.simulations.email_inbox.prompts import EmailInboxPromptBuilder

email_inbox_simulation = SimulationConfig(
    name="email_inbox",
    platform_cls=EmailInboxPlatform,
    action_cls=EmailInboxAction,
    environment_cls=EmailInboxEnvironment,
    prompt_builder=EmailInboxPromptBuilder(),
    default_actions=[
        "open_email",
        "read_email",
        "reply",
        "forward",
        "archive",
        "do_nothing",
    ],
    # Variants are injected at runtime via platform_kwargs
    platform_kwargs={},
)

__all__ = [
    "email_inbox_simulation",
    "EmailInboxPlatform",
    "EmailInboxAction",
    "EmailInboxEnvironment",
    "EmailInboxPromptBuilder",
]
