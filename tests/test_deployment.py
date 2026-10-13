import app

def test_launch_config_supports_spaces_and_localhost(monkeypatch):
    monkeypatch.delenv('SPACE_ID',raising=False)
    assert app.launch_config() == {'server_name':'127.0.0.1','server_port':7860}
    monkeypatch.setenv('SPACE_ID','fictional/update2report')
    assert app.launch_config() == {'server_name':'0.0.0.0','server_port':7860}
