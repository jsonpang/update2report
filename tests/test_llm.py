from types import SimpleNamespace
import pytest
from update2report import llm
from update2report.extract import extract_updates

def test_llm_has_explicit_timeout_and_one_transport_retry(monkeypatch):
    settings = {}
    def factory(**kwargs):
        settings.update(kwargs)
        return SimpleNamespace()
    monkeypatch.setenv('LLM_BASE_URL','http://localhost:11434/v1')
    monkeypatch.setenv('LLM_MODEL','test-model')
    monkeypatch.setattr(llm,'OpenAI',factory)
    llm.LLMClient()
    assert settings['timeout'] == 45
    assert settings['max_retries'] == 1

def test_invalid_json_error_does_not_disclose_raw_response():
    class BadClient:
        def complete(self, *args):
            return 'private-invalid-payload'
    with pytest.raises(ValueError) as error:
        extract_updates(BadClient(), 'fictional notes')
    assert 'private-invalid-payload' not in str(error.value)
    assert 'Please try again' in str(error.value)

def test_transport_timeout_retries_once_and_returns_safe_message(monkeypatch):
    import httpx
    from openai import OpenAI
    attempts = []
    def timeout(request):
        attempts.append(request)
        raise httpx.ReadTimeout('private-provider-detail',request=request)
    def factory(**kwargs):
        return OpenAI(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(timeout)))
    monkeypatch.setenv('LLM_BASE_URL','http://localhost:11434/v1')
    monkeypatch.setenv('LLM_MODEL','test-model')
    monkeypatch.setattr(llm,'OpenAI',factory)
    with pytest.raises(RuntimeError,match='timed out') as error:
        llm.LLMClient().complete('system','fictional notes')
    assert len(attempts) == 2
    assert 'private-provider-detail' not in str(error.value)


def test_fallback_model_on_429(monkeypatch):
    import httpx
    from openai import RateLimitError

    calls = []
    req = httpx.Request('POST', 'http://localhost')
    err_429 = RateLimitError('queue.full', response=httpx.Response(429, request=req), body=None)

    def mock_create(*args, **kwargs):
        model = kwargs.get('model')
        calls.append(model)
        if model == 'primary-model':
            raise err_429
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='fallback answer'))],
            usage=SimpleNamespace(total_tokens=15)
        )

    class MockClient:
        chat = SimpleNamespace(completions=SimpleNamespace(create=mock_create))

    monkeypatch.setenv('LLM_BASE_URL', 'http://localhost:11434/v1')
    monkeypatch.setenv('LLM_MODEL', 'primary-model')
    monkeypatch.setenv('LLM_FALLBACK_MODEL', 'fallback-model')
    monkeypatch.setattr(llm, 'OpenAI', lambda **kwargs: MockClient())

    client = llm.LLMClient()
    res = client.complete('sys', 'user')
    assert res == 'fallback answer'
    assert calls == ['primary-model', 'fallback-model']
    assert client.actual_model == 'fallback-model'
    assert client.total_tokens == 15


def test_fallback_model_both_fail_raises_unavailable(monkeypatch):
    import httpx
    from openai import RateLimitError, InternalServerError

    calls = []
    req = httpx.Request('POST', 'http://localhost')
    err_429 = RateLimitError('queue.full', response=httpx.Response(429, request=req), body=None)
    err_500 = InternalServerError('server error', response=httpx.Response(500, request=req), body=None)

    def mock_create(*args, **kwargs):
        model = kwargs.get('model')
        calls.append(model)
        if model == 'primary-model':
            raise err_429
        raise err_500

    class MockClient:
        chat = SimpleNamespace(completions=SimpleNamespace(create=mock_create))

    monkeypatch.setenv('LLM_BASE_URL', 'http://localhost:11434/v1')
    monkeypatch.setenv('LLM_MODEL', 'primary-model')
    monkeypatch.setenv('LLM_FALLBACK_MODEL', 'fallback-model')
    monkeypatch.setattr(llm, 'OpenAI', lambda **kwargs: MockClient())

    client = llm.LLMClient()
    with pytest.raises(RuntimeError, match='unavailable'):
        client.complete('sys', 'user')
    assert calls == ['primary-model', 'fallback-model']


def test_no_fallback_model_does_not_retry_on_429(monkeypatch):
    import httpx
    from openai import RateLimitError

    calls = []
    req = httpx.Request('POST', 'http://localhost')
    err_429 = RateLimitError('queue.full', response=httpx.Response(429, request=req), body=None)

    def mock_create(*args, **kwargs):
        calls.append(kwargs.get('model'))
        raise err_429

    class MockClient:
        chat = SimpleNamespace(completions=SimpleNamespace(create=mock_create))

    monkeypatch.setenv('LLM_BASE_URL', 'http://localhost:11434/v1')
    monkeypatch.setenv('LLM_MODEL', 'primary-model')
    monkeypatch.delenv('LLM_FALLBACK_MODEL', raising=False)
    monkeypatch.setattr(llm, 'OpenAI', lambda **kwargs: MockClient())

    client = llm.LLMClient()
    with pytest.raises(RuntimeError, match='unavailable'):
        client.complete('sys', 'user')
    assert calls == ['primary-model']

