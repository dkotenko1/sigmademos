import http.server, os, re, sys, json
ROOT=os.path.expanduser(os.environ.get("PLUGINS_DIR","~/Code/plugins/plugins"))
HERE=os.path.dirname(os.path.abspath(__file__))
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        m=re.match(r"^/p/([^/]+)/index\.html",self.path)
        if m:
            s=open(os.path.join(ROOT,m.group(1),"index.html")).read()
            s=s.replace("https://unpkg.com/react@18.3.1/umd/react.production.min.js","/react.js")
            s=re.sub(r"https://unpkg\.com/@sigmacomputing/plugin@1\.[0-9]\.[0-9]/dist/umd/sigmacomputing-plugin\.umd\.js","/sdk.js",s)
            b=s.encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        mo=re.match(r"^/o/([^/]+)/index\.html",self.path)
        if mo:
            import subprocess
            raw=subprocess.run(["git","-C",os.path.expanduser("~/Code/plugins"),"show","HEAD:plugins/%s/index.html"%mo.group(1)],capture_output=True,text=True).stdout
            raw=raw.replace("https://unpkg.com/@sigmacomputing/plugin","/sdk.js")
            b=raw.encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path=="/list.json":
            b=json.dumps(sorted(d for d in os.listdir(ROOT) if os.path.exists(os.path.join(ROOT,d,"index.html")))).encode()
            self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(b); return
        return super().do_GET()
    def log_message(self,*a): pass
os.chdir(HERE); http.server.ThreadingHTTPServer(("127.0.0.1",8732),H).serve_forever()
