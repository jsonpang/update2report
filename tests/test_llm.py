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
