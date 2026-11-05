"""Loopback-only analyst console with bounded, cancellable real runs."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
from .engine import ConsoleService,ALGORITHMS,CONDITIONS,BusyError,CancelledError,DeadlineError
from midnight_queue.config import CONFIG
from .evidence import load_evidence,load_runs


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,data,content_type="application/json"):
            body=json.dumps(data,allow_nan=False).encode() if content_type=="application/json" else data
            self.send_response(status)
            self.send_header("Content-Type",content_type+"; charset=utf-8")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass

        def do_GET(self):
            if self.path=="/":
                self.send(200,(Path(__file__).parent/"index.html").read_bytes(),"text/html")
            elif self.path in ("/style.css","/app.js","/ui.js"):
                self.send(200,(Path(__file__).parent/self.path[1:]).read_bytes(),
                          "text/css" if self.path.endswith(".css") else "text/javascript")
            elif self.path=="/api/config":
                self.send(200,dict(algorithms=ALGORITHMS,conditions=CONDITIONS,sizes=CONFIG.sizes,k=CONFIG.k,seed=CONFIG.seed))
            elif self.path=="/api/evidence":
                try: self.send(200,load_evidence())
                except FileNotFoundError: self.send(503,{"error":"Saved benchmark evidence is unavailable. Prepare the project artifacts first."})
            elif self.path=="/api/runs":
                self.send(200,{"runs":load_runs()})
            else: self.send(404,{"error":"Page not found"})

        def do_POST(self):
            origin=self.headers.get("Origin")
            expected=f"http://127.0.0.1:{self.server.server_port}"
            if origin and origin!=expected:
                self.send(403,{"error":"Requests must originate from this local console"});return
            if self.headers.get_content_type()!="application/json":
                self.send(415,{"error":"Send application/json"});return
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=2048: raise ValueError("Invalid request size")
                params=json.loads(self.rfile.read(size))
                if not isinstance(params,dict): raise ValueError("A JSON object is required")
                if self.path=="/api/run":
                    self.send(200,service.run(params))
                elif self.path=="/api/cancel":
                    self.send(200,{"cancelled":service.cancel(params.get("request_id"))})
                else: self.send(404,{"error":"Endpoint not found"})
            except (ValueError,KeyError) as exc: self.send(400,{"error":str(exc)})
            except BusyError as exc: self.send(409,{"error":str(exc)})
            except CancelledError as exc: self.send(409,{"error":str(exc)})
            except DeadlineError as exc: self.send(408,{"error":str(exc),"dnf":True})
            except FileNotFoundError: self.send(503,{"error":"Place the official creditcard.csv in data/ before running a queue."})
            except Exception as exc: self.send(500,{"error":str(exc)})

        def log_message(self,*args): pass
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    service=ConsoleService()
    with ThreadingHTTPServer(("127.0.0.1",args.port),make_handler(service)) as server:
        print(f"Analyst console: http://127.0.0.1:{server.server_port}",flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: service.cancel(service.request_id)
