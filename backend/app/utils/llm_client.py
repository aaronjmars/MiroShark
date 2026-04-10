"""
LLM client wrapper
Unified API calls using OpenAI format.
Supports OpenAI-compatible APIs and Claude Code CLI.
"""

import inspect
import json
import os
import re
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .event_logger import EventLogger, LOG_PROMPTS
from .trace_context import TraceContext


def create_llm_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 300.0
):
    """
    Factory: returns ClaudeCodeClient when LLM_PROVIDER=claude-code,
    otherwise returns the standard LLMClient.
    """
    if Config.LLM_PROVIDER == 'claude-code':
        from .claude_code_client import ClaudeCodeClient
        return ClaudeCodeClient(model=model, timeout=timeout)
    return LLMClient(api_key=api_key, base_url=base_url, model=model, timeout=timeout)


def create_smart_llm_client(timeout: float = 300.0):
    """
    Factory for intelligence-sensitive workflows (reports, ontology, graph reasoning).
    Uses SMART_* config when set, otherwise falls back to the default LLM client.
    """
    if not Config.SMART_MODEL_NAME:
        return create_llm_client(timeout=timeout)

    provider = Config.SMART_PROVIDER or Config.LLM_PROVIDER

    if provider == 'claude-code':
        from .claude_code_client import ClaudeCodeClient
        return ClaudeCodeClient(model=Config.SMART_MODEL_NAME, timeout=timeout)

    return LLMClient(
        api_key=Config.SMART_API_KEY or Config.LLM_API_KEY,
        base_url=Config.SMART_BASE_URL or Config.LLM_BASE_URL,
        model=Config.SMART_MODEL_NAME,
        timeout=timeout,
    )


def create_ner_llm_client(timeout: float = 120.0):
    """
    Factory for NER extraction — a mechanical task that works fine on smaller/faster models.
    Uses NER_* config when set, otherwise falls back to the default LLM client.
    """
    if not Config.NER_MODEL_NAME:
        return create_llm_client(timeout=timeout)

    return LLMClient(
        api_key=Config.NER_API_KEY or Config.LLM_API_KEY,
        base_url=Config.NER_BASE_URL or Config.LLM_BASE_URL,
        model=Config.NER_MODEL_NAME,
        timeout=timeout,
    )


class LLMClient:
    """LLM client using OpenAI-compatible APIs"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 300.0
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            default_headers={
                'HTTP-Referer': 'https://github.com/aaronjmars/MiroShark',
                'X-Title': 'MiroShark - Universal Swarm Intelligence Engine',
                'X-Description': 'Multi-agent social media simulation platform. Builds knowledge graphs from documents, generates AI agent personas, and runs parallel simulations across Twitter/Reddit to predict narrative dynamics.',
                'X-OpenRouter-Categories': 'multi-agent,simulation,research',
            },
        )

        # Ollama context window size — prevents prompt truncation.
        self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    def _is_ollama(self) -> bool:
        """Check if we're talking to an Ollama server."""
        return '11434' in (self.base_url or '')

    def _emit_llm_event(self, messages, content, t0, *, response=None, error=None, temperature=0.7):
        """Emit an llm_call observability event (best-effort, never raises)."""
        try:
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)

            # Caller context: walk up the stack to find the first frame outside this file
            caller = 'unknown'
            for frame_info in inspect.stack()[2:6]:
                mod = frame_info.filename
                if 'llm_client' not in mod and 'claude_code_client' not in mod:
                    module_name = os.path.splitext(os.path.basename(mod))[0]
                    caller = f'{module_name}.{frame_info.function}'
                    break

            # Token counts from OpenAI response
            tokens_input = tokens_output = tokens_total = None
            if response and hasattr(response, 'usage') and response.usage:
                tokens_input = getattr(response.usage, 'prompt_tokens', None)
                tokens_output = getattr(response.usage, 'completion_tokens', None)
                tokens_total = getattr(response.usage, 'total_tokens', None)

            data = {
                'caller': caller,
                'model': self.model,
                'temperature': temperature,
                'tokens_input': tokens_input,
                'tokens_output': tokens_output,
                'tokens_total': tokens_total,
                'latency_ms': latency_ms,
                'response_preview': (content or '')[:200] if content else None,
                'error': str(error) if error else None,
            }

            if LOG_PROMPTS:
                data['messages'] = messages
                data['response'] = content
            EventLogger().emit('llm_call', data)
        except Exception:
            pass  # observability must never break LLM calls

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send a chat request

        Args:
            messages: List of messages
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # For Ollama: pass num_ctx via extra_body to prevent prompt truncation
        if self._is_ollama() and self._num_ctx:
            kwargs["extra_body"] = {
                "options": {"num_ctx": self._num_ctx}
            }

        t0 = time.perf_counter()
        error_info = None
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            error_info = exc
            self._emit_llm_event(messages, None, t0, error=exc, temperature=temperature)
            raise

        content = response.choices[0].message.content
        # Some models (e.g., MiniMax M2.5) include <think> reasoning content in the content field, which needs to be removed
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

        self._emit_llm_event(messages, content, t0, response=response, temperature=temperature)
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send a chat request and return JSON

        Args:
            messages: List of messages
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean up markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format returned by LLM: {cleaned_response}")
