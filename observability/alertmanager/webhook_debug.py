import json                                                    
from http.server import BaseHTTPRequestHandler, HTTPServer     

class Handler(BaseHTTPRequestHandler):                         
    def do_POST(self):                                         
        length = int(self.headers.get("Content-Length", 0))    
        body = json.loads(self.rfile.read(length))             
        for a in body["alerts"]:                               
            print(f'group={body["status"]:8} alert={a["status"]:8} {a["labels"]["alertname"]:18} {a["annotations"].get("summary", "")}', flush=True)  
        print(json.dumps(body), flush=True)                    
        self.send_response(200)                                
        self.end_headers()                                    

    def log_message(self, *args):                             
        pass

HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()        