"""
Claude Code LLM client
Routes LLM calls through the local Claude Code CLI (`claude -p`).
Uses your Claude Code login — no API key required.

Note: Each call spawns a subprocess (~2-5s overhead), so this is best
suited for low-volume workloads (report generation, small simulations).
"""

import json
import os
import re
import subprocess
from typing import Optional, Dict, Any, List

from .logger import get_logger

logger = get_logger('miroshark.claude_code_client')


class ClaudeCodeClient:
    """
    Drop-in replacement for LLMClient that shells out to `claude -p`.
    Implements the same chat() / chat_json() interface.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        timeout: float = 300.0
    ):
        self.model = model or os.environ.get('CLAUDE_CODE_MODEL', '')
        self.timeout = timeout
        self._verify_claude_installed()

    def _verify_claude_installed(self):
        """Check that the claude CLI is available."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "Claude Code CLI returned an error. "
                    "Make sure you're logged in: run `claude` in your terminal."
                )
            logger.info(f"Claude Code CLI found: {result.stdout.strip()}")
        except FileNotFoundError:
            raise RuntimeError(
                "Claude Code CLI not found. "
                "Install it: https://docs.anthropic.com/en/docs/claude-code"
            )

    def _build_prompt(self, messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        """Convert OpenAI-style messages to a single prompt string."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[System Instructions]\n{content}")
            elif role == "assistant":
                parts.append(f"[Assistant]\n{content}")
            else:
                parts.append(content)

        prompt = "\n\n".join(parts)

        if json_mode:
            prompt += (
                "\n\nIMPORTANT: Respond with valid JSON only. "
                "No markdown fences, no explanation — just the JSON object."
            )

        return prompt

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send a chat request via Claude Code CLI.

        Args:
            messages: List of messages (OpenAI format)
            temperature: Ignored (Claude Code doesn't expose this)
            max_tokens: Max tokens for response
            response_format: If {"type": "json_object"}, appends JSON instruction

        Returns:
            Model response text
        """
        json_mode = bool(
            response_format and response_format.get("type") == "json_object"
        )
        prompt = self._build_prompt(messages, json_mode=json_mode)

        cmd = ["claude", "-p", prompt, "--output-format", "json"]
        if self.model:
            cmd.extend(["--model", self.model])
        if max_tokens:
            cmd.extend(["--max-turns", "1"])

        logger.debug(f"Calling claude -p ({len(prompt)} chars)")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(
                f"Claude Code call timed out after {self.timeout}s"
            )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown error"
            raise RuntimeError(f"Claude Code CLI error: {error_msg}")

        # Parse the JSON output from claude --output-format json
        try:
            output = json.loads(result.stdout)
            content = output.get("result", result.stdout)
        except json.JSONDecodeError:
            # Fallback: treat raw stdout as the response
            content = result.stdout.strip()

        # Strip <think> tags (same as LLMClient)
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send a chat request and return parsed JSON.

        Args:
            messages: List of messages
            temperature: Ignored
            max_tokens: Max tokens for response

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )

        cleaned = response.strip()
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON from Claude Code: {cleaned[:200]}")
