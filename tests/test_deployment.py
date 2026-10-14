import app


def test_launch_config_defaults_to_localhost_7860(monkeypatch):
    monkeypatch.delenv('GRADIO_SERVER_NAME', raising=False)
    monkeypatch.delenv('GRADIO_SERVER_PORT', raising=False)
    monkeypatch.delenv('SPACE_ID', raising=False)
    assert app.launch_config() == {'server_name': '127.0.0.1', 'server_port': 7860}


def test_launch_config_overridden_by_env(monkeypatch):
    monkeypatch.setenv('GRADIO_SERVER_NAME', '0.0.0.0')
    monkeypatch.setenv('GRADIO_SERVER_PORT', '8080')
    assert app.launch_config() == {'server_name': '0.0.0.0', 'server_port': 8080}
