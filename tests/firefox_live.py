"""Real Firefox live-feed check in a disposable headless profile, no personal data."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge import BridgeServer

HTML = b'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Live feed fixture</title><meta name="description" content="Initial metadata"></head>
<body><main><h1 id="heading">Initial heading</h1><p id="caption">First caption text</p>
<video controls width="320" height="100"></video>
<input value="FORM_SECRET_SENTINEL"><textarea>PRIVATE_ENTRY_SENTINEL</textarea>
<p style="margin-top:1000px">Offscreen article context</p></main>
<script>setTimeout(()=>{document.getElementById('heading').textContent='Updated heading';
document.querySelector('meta[name="description"]').content='Updated metadata';},1500);
setTimeout(()=>{history.pushState({},'', '/second?secret=must-be-removed');
document.title='Second fixture page';document.getElementById('caption').textContent='Updated caption text';},3200);</script>
</body></html>'''


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(HTML)))
        self.end_headers()
        self.wfile.write(HTML)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--web-ext-js',required=True)
    parser.add_argument('--node',default=r'C:\Program Files\nodejs\node.exe')
    parser.add_argument('--firefox',default=r'C:\Program Files\Mozilla Firefox\firefox.exe')
    args = parser.parse_args()
    local = ROOT/'.local'
    local.mkdir(exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix='firefox-test-',dir=local,ignore_cleanup_errors=True)
    work = Path(temporary.name).resolve()
    assert work.is_relative_to(local.resolve()), 'Disposable profile must stay inside the workspace'
    inbox = queue.Queue(maxsize=100)
    sink = BridgeServer('b'*48,inbox,port=0)
    website = ThreadingHTTPServer(('127.0.0.1',0),Fixture)
    for server in (sink,website):
        threading.Thread(target=server.serve_forever,daemon=True).start()
    extension = work/'extension'
    shutil.copytree(ROOT/'extension',extension)
    manifest = json.loads((extension/'manifest.json').read_text(encoding='utf-8'))
    # Grant test-page access only in this disposable test profile, without user prompts.
    manifest['host_permissions'] = ['http://*/*','https://*/*']
    manifest['browser_specific_settings']['gecko']['id'] = 'screen-squatters-tests@littlrayray.local'
    (extension/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    background = (extension/'background.js').read_text(encoding='utf-8')
    background = background.replace('http://127.0.0.1:17373',f'http://127.0.0.1:{sink.server_port}')
    startup = 'browser.storage.local.get("following").then(saved => saved.following ? configure(true) : setFeed("off", "Live updates are off.")).catch(() => {});'
    assert startup in background
    background = background.replace(startup,'// Test bootstrap owns initial configuration.')
    background += f'''
(async()=>{{
  await browser.storage.local.set({{following:true,pairingCode:{json.dumps('b'*48)}}});
  await configure(true);
  const tab=await browser.tabs.create({{url:"http://127.0.0.1:{website.server_port}/fixture",active:true}});
  await browser.windows.update(tab.windowId,{{focused:true}});
}})().catch(error=>console.error("Test bootstrap:",error.message));
'''
    (extension/'background.js').write_text(background,encoding='utf-8')
    command = [args.node,args.web_ext_js,'run','--source-dir',str(extension),'--firefox',args.firefox,
               '--arg=-headless','--no-reload','--no-input','--no-config-discovery']
    process = None
    pages = []
    try:
        with (work/'runner.log').open('w',encoding='utf-8') as log:
            process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline = time.monotonic()+45
            while time.monotonic()<deadline:
                try:
                    item = inbox.get(timeout=.5)
                except queue.Empty:
                    if process.poll() is not None:
                        break
                    continue
                if item.get('kind') == 'browser-state':
                    continue
                pages.append(item)
                if len(pages)>=4 and any(p['url'].endswith('/second') and 'Updated caption text' in p['text'] for p in pages):
                    break
        if not pages:
            print((work/'runner.log').read_text(encoding='utf-8',errors='replace')[-5000:])
            raise AssertionError('Firefox delivered no page snapshots')
        assert len(pages)>=4, f'Expected repeated updates, got {len(pages)}'
        assert any(p['metadata']['description']=='Updated metadata' for p in pages), 'Metadata changes must update'
        assert any('Updated heading' in p['headings'] for p in pages), 'DOM heading changes must update'
        assert any(p['url'].endswith('/second') for p in pages), 'SPA navigation must update'
        assert any('Updated caption text' in p['text'] for p in pages), 'Visible captions must update'
        assert pages[-1]['media'][0]['kind']=='video'
        assert 'Offscreen article context' in pages[-1]['page_text']
        raw = json.dumps(pages)
        assert 'FORM_SECRET_SENTINEL' not in raw and 'PRIVATE_ENTRY_SENTINEL' not in raw
        assert 'secret=' not in raw
        assert all(page['browser']=='firefox' and page['automatic'] for page in pages)
        assert all(a['sequence']<b['sequence'] for a,b in zip(pages,pages[1:]))
        assert sink.awake is False, 'The feed must work while all companions sleep'
        print(f'Firefox live test passed: {len(pages)} real updates; metadata, DOM changes, SPA route, visible captions, media, offscreen context and private-field filtering; companions asleep.')
    finally:
        if process and process.poll() is None:
            # Only the process tree created above; never another Firefox profile.
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for server in (sink,website):
            server.shutdown()
            server.server_close()
        temporary.cleanup()


if __name__=='__main__':
    main()
