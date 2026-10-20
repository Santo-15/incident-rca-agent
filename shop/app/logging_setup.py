import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_SKIP = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "color_message"}

class JsonFormatter(logging.Formatter):       
    def format(self, record: logging.LogRecord) -> str:  
        entry = {                            
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),  # when, in UTC, e.g. 2026-10-17T07:30:31.123Z
            "level": record.levelname,        
            "logger": record.name,            
            "msg": record.getMessage(),      
            "request_id": request_id_var.get(),  
        }
        for key, value in vars(record).items():  
            if key not in _SKIP:              
                entry[key] = value            
        if record.exc_info:                   
            entry["exc_info"] = self.formatException(record.exc_info)  
        return json.dumps(entry, default=str) 

def setup_logging(level: str) -> None:        
    handler = logging.StreamHandler(sys.stdout)  
    handler.setFormatter(JsonFormatter())     
    root = logging.getLogger()                
    root.handlers = [handler]                 
    root.setLevel(level)                      
    for name in ("uvicorn", "uvicorn.error"): 
        uv = logging.getLogger(name)          
        uv.handlers = []                      
        uv.propagate = True                   
    logging.getLogger("uvicorn.access").disabled = True