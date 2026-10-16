"""Loopback-only static reader server with media byte ranges. Standalone in release packages."""
from __future__ import annotations

import argparse
import functools
import re
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class ReaderHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,".mjs":"text/javascript",".m4a":"audio/mp4",".wasm":"application/wasm",".webmanifest":"application/manifest+json"}

    def send_head(self):
        self.remaining = None
        path = Path(self.translate_path(self.path))
        root = Path(self.directory).resolve()
        if not path.resolve().is_relative_to(root):
            self.send_error(HTTPStatus.FORBIDDEN)
            return None
        if path.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND,"Bitte /reader.html öffnen")
            return None
        if "Range" not in self.headers or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        match = re.fullmatch(r"bytes=(\d*)-(\d*)",self.headers["Range"])
        if not match or not any(match.groups()):
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            return None
        start,end = match.groups()
        if start:
            start,end = int(start),min(int(end),size-1) if end else size-1
        else:
            start,end = max(0,size-int(end)),size-1
        if start > end or start >= size:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range",f"bytes */{size}")
            self.send_header("Content-Length","0")
            self.end_headers()
            return None
        stream = path.open("rb")
        stream.seek(start)
        self.remaining = end-start+1
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type",self.guess_type(str(path)))
        self.send_header("Content-Length",str(self.remaining))
        self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
        self.end_headers()
        return stream

    def end_headers(self):
        self.send_header("Accept-Ranges","bytes")
        self.send_header("X-Content-Type-Options","nosniff")
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            if self.remaining is None:
                return super().copyfile(source,outputfile)
            remaining = self.remaining
            while remaining:
                block = source.read(min(65536,remaining))
                if not block:
                    break
                outputfile.write(block)
                remaining -= len(block)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            pass                         # browser cancelled a seek or changed chapter


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--open",action="store_true")
    args = parser.parse_args(argv)
    if not (args.directory / "reader.html").is_file():
        parser.error("Kein Reader in diesem Verzeichnis. Zuerst python -m pipeline interactive ausführen.")
    handler = functools.partial(ReaderHandler,directory=str(args.directory.resolve()))
    with ThreadingHTTPServer(("127.0.0.1",args.port),handler) as server:
        url = f"http://127.0.0.1:{args.port}/reader.html"
        print(f"Lernrepo Reader: {url} (Strg+C beendet den Server)",flush=True)
        if args.open:
            threading.Timer(.5,lambda:webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
