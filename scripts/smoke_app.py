"""Start our own app process, curl its homepage, and always stop that process."""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',7860))
    out = ROOT / 'out'
    out.mkdir(exist_ok=True)
    result = {'url':'http://127.0.0.1:7860/', 'http_status':None, 'process_stopped':False}
    with (out / 'round2-app.stdout.log').open('w',encoding='utf-8') as stdout, (out / 'round2-app.stderr.log').open('w',encoding='utf-8') as stderr:
        child = subprocess.Popen([sys.executable,'app.py'],cwd=ROOT,stdout=stdout,stderr=stderr,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(60):
                if child.poll() is not None:
                    raise RuntimeError('Application exited before HTTP readiness; inspect startup logs.')
                response = subprocess.run(['curl.exe' if sys.platform == 'win32' else 'curl','--silent',
                    '--max-time','1','--output',str(out / 'round2-homepage.html'),'--write-out','%{http_code}',
                    result['url']],capture_output=True,text=True)
                if response.returncode == 0 and response.stdout == '200':
                    result['http_status'] = 200
                    break
                time.sleep(0.5)
            assert result['http_status'] == 200, 'Homepage did not return HTTP 200'
            assert 'Update2Report' in (out / 'round2-homepage.html').read_text(encoding='utf-8')
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)
            result['process_stopped'] = child.poll() is not None
            (out / 'round2-startup.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result))


if __name__ == '__main__':
    main()
