"""
Cross-platform digest for multi-platform simulations.

Maintains a shared in-memory log of agent actions across platforms
and generates text digests that can be injected into agent system
messages, giving each agent awareness of their own activity on
OTHER platforms.

Usage:
    log = CrossPlatformLog()

    # After each round, record what happened:
    log.record("twitter", actual_actions)

    # Before the next round, build a digest for an agent:
    digest = log.build_digest(agent_id=5, exclude_platform="reddit")
    # Returns a string summarizing agent 5's recent Twitter activity
    # (excludes Reddit since that's the platform about to act)
"""
from collections import defaultdict
from typing import Dict, List, Optional


# Action types worth surfacing in cross-platform digests
# (skip noisy low-signal actions)
_SKIP_ACTIONS = {
    'DO_NOTHING', 'REFRESH', 'TREND', 'SEARCH_POSTS', 'SEARCH_USER',
    'do_nothing', 'refresh', 'trend', 'search_posts', 'search_user',
}

# Human-readable labels for action types
_ACTION_LABELS = {
    'CREATE_POST': 'posted',
    'LIKE_POST': 'liked a post',
    'DISLIKE_POST': 'disliked a post',
    'REPOST': 'reposted',
    'QUOTE_POST': 'quote-posted',
    'FOLLOW': 'followed someone',
    'MUTE': 'muted someone',
    'CREATE_COMMENT': 'commented',
    'LIKE_COMMENT': 'liked a comment',
    'DISLIKE_COMMENT': 'disliked a comment',
}

# Max content preview length in digest
_MAX_CONTENT_LEN = 200


class CrossPlatformLog:
    """
    Shared in-memory log of agent actions across all platforms.

    Safe for concurrent use within a single asyncio event loop
    (all callers share the same thread).
    """

    def __init__(self, max_actions_per_agent: int = 15):
        # platform -> agent_id -> list of action dicts
        self._log: Dict[str, Dict[int, List[dict]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.max_actions_per_agent = max_actions_per_agent

    def record(self, platform: str, actions: List[dict]):
        """
        Record a batch of actions from one platform round.

        Args:
            platform: Platform name ("twitter", "reddit", ...)
            actions: List of action dicts, each with at least:
                     agent_id, agent_name, action_type, action_args
        """
        for action in actions:
            agent_id = action.get('agent_id')
            action_type = action.get('action_type', '')

            if agent_id is None:
                continue
            if action_type in _SKIP_ACTIONS:
                continue

            entry = {
                'action_type': action_type,
                'args': action.get('action_args', {}),
            }

            bucket = self._log[platform][agent_id]
            bucket.append(entry)

            # Trim to keep memory bounded
            if len(bucket) > self.max_actions_per_agent:
                del bucket[:-self.max_actions_per_agent]

    def build_digest(
        self,
        agent_id: int,
        exclude_platform: str,
        max_items: int = 5,
    ) -> Optional[str]:
        """
        Build a text digest of an agent's recent activity on OTHER platforms.

        Args:
            agent_id: The agent to build the digest for.
            exclude_platform: The platform the agent is about to act on
                              (excluded from the digest).
            max_items: Max recent actions to include per platform.

        Returns:
            A formatted string, or None if there's nothing to report.
        """
        sections = []

        for platform, agents in self._log.items():
            if platform == exclude_platform:
                continue

            agent_actions = agents.get(agent_id)
            if not agent_actions:
                continue

            lines = []
            for entry in agent_actions[-max_items:]:
                line = self._format_action(entry)
                if line:
                    lines.append(f"  - {line}")

            if lines:
                sections.append(
                    f"On {platform.title()}:\n" + "\n".join(lines)
                )

        if not sections:
            return None

        header = "# YOUR RECENT ACTIVITY ON OTHER PLATFORMS"
        body = "\n".join(sections)
        footer = (
            "Consider how your activity elsewhere might relate to "
            "what you do on this platform."
        )
        return f"{header}\n{body}\n{footer}"

    def _format_action(self, entry: dict) -> Optional[str]:
        """Format a single action entry as a readable line."""
        action_type = entry.get('action_type', '')
        args = entry.get('args', {})

        label = _ACTION_LABELS.get(action_type, action_type.lower())

        # Extract the most informative content from action_args
        content = (
            args.get('content')
            or args.get('quote_content')
            or args.get('post_content')
            or args.get('comment_content')
        )

        if content:
            if len(content) > _MAX_CONTENT_LEN:
                content = content[:_MAX_CONTENT_LEN] + "..."
            return f'{label}: "{content}"'

        # For actions targeting other users/posts
        target = (
            args.get('target_user_name')
            or args.get('post_author_name')
            or args.get('comment_author_name')
        )
        if target:
            return f"{label} by {target}"

        return label

    def clear(self):
        """Clear all recorded actions."""
        self._log.clear()


# Cross-platform context marker used to find/replace the injected section
_CROSS_PLATFORM_MARKER = "\n\n# YOUR RECENT ACTIVITY ON OTHER PLATFORMS"


def inject_cross_platform_context(agent, digest: str):
    """
    Inject a cross-platform digest into an agent's system message.

    Appends (or replaces) the cross-platform section at the end of
    the agent's system_message.content.

    Args:
        agent: A SocialAgent instance (has .system_message.content).
        digest: The digest text from CrossPlatformLog.build_digest().
    """
    content = agent.system_message.content

    # Remove previous cross-platform section if present
    marker_pos = content.find(_CROSS_PLATFORM_MARKER)
    if marker_pos != -1:
        content = content[:marker_pos]

    # Append new digest
    agent.system_message.content = content + "\n\n" + digest


def clear_cross_platform_context(agent):
    """
    Remove the cross-platform digest section from an agent's system message.

    Args:
        agent: A SocialAgent instance.
    """
    content = agent.system_message.content
    marker_pos = content.find(_CROSS_PLATFORM_MARKER)
    if marker_pos != -1:
        agent.system_message.content = content[:marker_pos]
