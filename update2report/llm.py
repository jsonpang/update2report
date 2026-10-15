import os
import time
import sys
import logging
from openai import (
    OpenAI,
    OpenAIError,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)

_log = logging.getLogger('update2report.llm')
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter('%(message)s'))
    _log.addHandler(_handler)
    _log.setLevel(logging.INFO)


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError, TimeoutError, ConnectionError)):
        return True
    status_code = getattr(exc, 'status_code', None)
    if status_code is not None:
        try:
            code = int(status_code)
            if code == 429 or code >= 500:
                return True
        except (ValueError, TypeError):
            pass
    msg = str(exc).lower()
    if '429' in msg or 'timeout' in msg or 'connection' in msg or 'queue.full' in msg:
        return True
    return False


class LLMClient:
    def __init__(self):
        base_url = os.getenv('LLM_BASE_URL')
        if not base_url:
            raise RuntimeError('LLM_BASE_URL is required for uncached generation')
        self.client = OpenAI(base_url=base_url, api_key=os.getenv('LLM_API_KEY') or 'ollama', timeout=45, max_retries=1)
        self.model = os.getenv('LLM_MODEL')
        if not self.model:
            raise RuntimeError('LLM_MODEL is required')
        fallback = os.getenv('LLM_FALLBACK_MODEL')
        self.fallback_model = fallback.strip() if fallback and fallback.strip() else None
        self.fallback_delay = float(os.getenv('LLM_FALLBACK_DELAY') or 0)
        self.actual_model = None
        self.last_model = None
        self.total_tokens = 0

    def complete(self, system, user):
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
        try:
            result = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.2)
            self.actual_model = self.model
            self.last_model = self.model
            _log.info('llm_call model=%s result=ok', self.model)
        except (OpenAIError, TimeoutError, ConnectionError) as exc:
            if self.fallback_model and _is_retryable_error(exc):
                _log.warning('llm_fallback primary=%s fallback=%s reason=%s', self.model, self.fallback_model, exc)
                # Rate limits are often seconds long; LLM_FALLBACK_DELAY lets a
                # fallback to the same model wait them out.
                time.sleep(self.fallback_delay)
                try:
                    result = self.client.chat.completions.create(model=self.fallback_model, messages=messages, temperature=0.2)
                    self.actual_model = self.fallback_model
                    self.last_model = self.fallback_model
                    _log.info('llm_call model=%s result=ok (fallback)', self.fallback_model)
                except (OpenAIError, TimeoutError, ConnectionError):
                    raise RuntimeError('The model service is unavailable or timed out after one retry. Please try again later, or load a cached sample.') from None
            else:
                raise RuntimeError('The model service is unavailable or timed out after one retry. Please try again later, or load a cached sample.') from None

        if result.usage:
            self.total_tokens += result.usage.total_tokens or 0
        return result.choices[0].message.content or '' if result.choices else ''
