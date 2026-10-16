import functools
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from pipeline.reader_serve import ReaderHandler


def test_loopback_server_supports_media_seeks_and_denies_directory_listing(tmp_path):
    (tmp_path / 'sample.wav').write_bytes(b'0123456789')
    handler = functools.partial(ReaderHandler, directory=str(tmp_path))
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for header, expected in [('bytes=2-4', b'234'), ('bytes=7-', b'789'), ('bytes=-3', b'789')]:
                request = urllib.request.Request(base + '/sample.wav', headers={'Range': header})
                with urllib.request.urlopen(request) as response:
                    assert response.status == 206
                    assert response.read() == expected
                    assert response.headers['Accept-Ranges'] == 'bytes'
            for path in ['/', '/missing']:
                try:
                    urllib.request.urlopen(base + path)
                    assert False, 'Listing or missing path must not succeed'
                except urllib.error.HTTPError as error:
                    assert error.code == 404
        finally:
            server.shutdown()
            thread.join(timeout=5)
