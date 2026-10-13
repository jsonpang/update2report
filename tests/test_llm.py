from types import SimpleNamespace
import pytest
from update2report import llm
from update2report.extract import extract_updates

def test_llm_has_explicit_timeout_and_one_transport_retry(monkeypatch):
    settings = {}
    def factory(**kwargs):
        settings.update(kwargs)
        return SimpleNamespace()
    monkeypatch.setenv('LLM_BASE_URL','http://localhost:8317/v1')
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
    monkeypatch.setenv('LLM_BASE_URL','http://localhost:8317/v1')
    monkeypatch.setenv('LLM_MODEL','test-model')
    monkeypatch.setattr(llm,'OpenAI',factory)
    with pytest.raises(RuntimeError,match='timed out') as error:
        llm.LLMClient().complete('system','fictional notes')
    assert len(attempts) == 2
    assert 'private-provider-detail' not in str(error.value)
