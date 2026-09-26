from __future__ import annotations
import json,time
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlparse
from .contracts import DashboardConfig
from .service import DashboardService

class _Handler(BaseHTTPRequestHandler):
    server_version="StockBotDashboard/1.0"
    def _json(self,payload,status=200):
        raw=json.dumps(payload,separators=(",",":"),default=str).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def _static(self,name,ctype):
        root=Path(__file__).with_name("static").resolve(); path=(root/name).resolve()
        if root not in path.parents: return self.send_error(404)
        try: raw=path.read_bytes()
        except OSError: return self.send_error(404)
        self.send_response(200); self.send_header("Content-Type",ctype); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    @property
    def service(self): return self.server.dashboard_service
    def do_GET(self):
        p=urlparse(self.path); q=parse_qs(p.query); path=p.path
        static={"/":("index.html","text/html; charset=utf-8"),"/index.html":("index.html","text/html; charset=utf-8"),"/app.js":("app.js","text/javascript; charset=utf-8"),"/styles.css":("styles.css","text/css; charset=utf-8")}
        if path in static: return self._static(*static[path])
        if path=="/api/overview": return self._json(self.service.overview())
        if path=="/api/agents": return self._json(self.service.agents())
        if path=="/api/pipeline": return self._json(self.service.pipeline())
        if path=="/api/models": return self._json(self.service.models())
        if path=="/api/health": return self._json(self.service.health())
        if path=="/api/learning": return self._json(self.service.learning())
        if path=="/api/decisions": return self._json(self.service.decisions(q.get("correlation_id",[None])[0]))
        if path=="/api/events": return self._json(self.service.events(int(q.get("limit",["100"])[0]),q.get("source",[None])[0],q.get("event_type",[None])[0],q.get("correlation_id",[None])[0]))
        if path=="/api/replay":
            cid=q.get("correlation_id",[None])[0]
            return self._json(self.service.replay(cid),400 if not cid else 200)
        if path=="/api/stream": return self._stream()
        self.send_error(404)
    def _stream(self):
        self.send_response(200); self.send_header("Content-Type","text/event-stream; charset=utf-8"); self.send_header("Cache-Control","no-cache"); self.send_header("Connection","keep-alive"); self.end_headers()
        last=None
        try:
            for _ in range(120):
                xs=self.service.events(1); cur=xs[-1]["event_id"] if xs else None
                if cur and cur!=last:
                    last=cur; self.wfile.write(("event: telemetry\ndata: "+json.dumps(xs[-1],separators=(",",":"))+"\n\n").encode())
                else: self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush(); time.sleep(self.service.config.refresh_seconds)
        except (BrokenPipeError,ConnectionResetError): pass
    def log_message(self,*args): pass

class DashboardServer(ThreadingHTTPServer):
    def __init__(self,config,service=None):
        self.dashboard_service=service or DashboardService.from_environment(config)
        super().__init__((config.host,config.port),_Handler)

def serve(config=None):
    config=config or DashboardConfig()
    server=DashboardServer(config)
    print(f"STOCK_BOT OPS CENTER: http://{config.host}:{config.port}")
    server.serve_forever()
