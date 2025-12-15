from fastapi import FastAPI, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import queue
import time
import os
import sys
import uuid
import hashlib

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import AgentSystem

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
class SessionState:
    def __init__(self):
        self.logs = []
        self.is_running = False
        self.waiting_for_input = False
        self.input_event = threading.Event()
        self.user_input = None
        self.system = None
        self.workspace_root = os.path.abspath("workspace_web")
        # Allow signaling a stop request from the frontend (best-effort)
        self.request_stop = False

session = SessionState()

def log_callback(msg):
    print(msg) # Keep printing to console for debug
    # Parse structured logs if possible
    log_type = "log"
    if "❌" in str(msg) or "Error" in str(msg):
        log_type = "error"
    elif "✅" in str(msg) or "Complete" in str(msg):
        log_type = "success"
    elif "⚠️" in str(msg) or "Warning" in str(msg):
        log_type = "warning"
    elif "🔬" in str(msg) or "Research" in str(msg):
        log_type = "research"
    elif "▶️" in str(msg) or "Executing" in str(msg):
        log_type = "execution"
    
    session.logs.append({
        "timestamp": time.time(), 
        "message": str(msg),
        "type": log_type
    })

def input_callback(prompt):
    session.waiting_for_input = True
    session.logs.append({
        "timestamp": time.time(), 
        "message": str(prompt), 
        "type": "input_request"
    })
    session.input_event.clear()
    # Wait in small intervals so we can honor stop requests promptly
    try:
        while True:
            signaled = session.input_event.wait(0.25)
            if signaled:
                break
            # Cooperative cancel while waiting for input
            if session.request_stop:
                session.waiting_for_input = False
                return "__STOP_REQUESTED__"
    finally:
        # Ensure flag consistency even if exceptions occur
        if session.waiting_for_input:
            session.waiting_for_input = False
    return session.user_input

from typing import Optional, Dict

class GoalRequest(BaseModel):
    goal: str
    workspace_root: Optional[str] = None
    config: Optional[Dict[str, bool]] = None

class InputRequest(BaseModel):
    text: str

def run_agent_task(goal: str, workspace_root: str = None, config_overrides: dict = None):
    session.is_running = True
    session.request_stop = False
    try:
        # Initialize system
        root = workspace_root if workspace_root else session.workspace_root
        session.system = AgentSystem(
            workspace_root=root,
            logger=log_callback,
            input_provider=input_callback,
            config_overrides=config_overrides,
            stop_checker=lambda: session.request_stop
        )
        # Best-effort: run the system. Note: AgentSystem doesn't implement cooperative cancellation,
        # so /api/stop will set a request flag that agents may or may not honor.
        session.system.run(goal)
    except Exception as e:
        log_callback(f"❌ System Error: {e}")
    finally:
        session.is_running = False
        session.request_stop = False

@app.post("/api/run")
def run_agent(req: GoalRequest, background_tasks: BackgroundTasks):
    if session.is_running:
        return {"status": "error", "message": "Agent is already running"}
    
    session.logs = [] # Clear logs
    session.waiting_for_input = False
    session.request_stop = False
    session.input_event.clear()
    
    # Determine workspace root
    ws_root = req.workspace_root if req.workspace_root else session.workspace_root
    
    # DEBUG: Log received config
    print(f"🔧 /api/run received config: {req.config}")
    
    background_tasks.add_task(run_agent_task, req.goal, ws_root, req.config or {})
    return {"status": "started"}

@app.get("/api/status")
def get_status():
    return {
        "is_running": session.is_running,
        "waiting_for_input": session.waiting_for_input,
        "logs": session.logs
    }


@app.get("/api/workspace")
def get_workspace_info(root: str = None):
    # Always expose the server base workspace root (where new session workspaces are created)
    base_root = session.workspace_root
    target_root = base_root
    
    # If explicit root provided, get stats for that specific workspace
    if root:
        # Handle both absolute and relative paths
        if os.path.isabs(root):
            candidate = os.path.normpath(root)
        else:
            candidate = os.path.normpath(os.path.join(base_root, root))
        # Security: must be under base_root
        if candidate.startswith(os.path.normpath(base_root)):
            target_root = candidate

    # Also expose the active workspace root if an agent run is active (for UI visibility)
    active_root = None
    if session.system and getattr(session.system, 'workspace_root', None):
        active_root = session.system.workspace_root

    total_files = 0
    total_size = 0
    if os.path.exists(target_root):
        for dirpath, dirnames, filenames in os.walk(target_root):
            for f in filenames:
                total_files += 1
                try:
                    total_size += os.path.getsize(os.path.join(dirpath, f))
                except:
                    pass

    return {
        "workspace_root": base_root, # Global base
        "target_root": target_root, # The one we measured
        "active_workspace_root": active_root,
        "file_count": total_files,
        "total_size": total_size
    }

@app.get("/api/files")
def list_files(root: str = None):
    base_root = session.workspace_root
    
    # If root param provided, it could be absolute or relative
    if root:
        # Handle both absolute and relative paths
        if os.path.isabs(root):
            candidate = os.path.normpath(root)
        else:
            candidate = os.path.normpath(os.path.join(base_root, root))
        # Security: must be under base_root
        if not candidate.startswith(os.path.normpath(base_root)):
            return {"status": "error", "message": "Invalid workspace root"}
        target_root = candidate
    else:
        # Fallback: use active system workspace or base
        if session.system and getattr(session.system, 'workspace_root', None):
            target_root = session.system.workspace_root
        else:
            target_root = base_root

    files = []
    if os.path.exists(target_root):
        for dirpath, dirnames, filenames in os.walk(target_root):
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                rel_path = os.path.relpath(full_path, target_root)
                files.append(rel_path)
    return {"files": sorted(files)}


@app.get("/api/download-file")
def download_file(path: str, root: str = None):
    base_root = session.workspace_root
    
    # Determine target workspace
    if root:
        if os.path.isabs(root):
            target_root = os.path.normpath(root)
        else:
            target_root = os.path.normpath(os.path.join(base_root, root))
        if not target_root.startswith(os.path.normpath(base_root)):
            return {"status": "error", "message": "Invalid workspace root"}
    else:
        if session.system and getattr(session.system, 'workspace_root', None):
            target_root = session.system.workspace_root
        else:
            target_root = base_root

    full_path = os.path.join(target_root, path)
    full_path = os.path.normpath(full_path)

    # Security check: ensure path is within workspace
    if not full_path.startswith(os.path.normpath(target_root)):
        return {"status": "error", "message": "Access denied"}

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return {"status": "error", "message": "File not found"}

    return FileResponse(full_path, filename=os.path.basename(full_path))

@app.get("/api/file-preview")
def preview_file(path: str, root: str = None):
    base_root = session.workspace_root

    # Determine target workspace
    if root:
        if os.path.isabs(root):
            target_root = os.path.normpath(root)
        else:
            target_root = os.path.normpath(os.path.join(base_root, root))
        if not target_root.startswith(os.path.normpath(base_root)):
            return {"status": "error", "message": "Invalid workspace root"}
    else:
        if session.system and getattr(session.system, 'workspace_root', None):
            target_root = session.system.workspace_root
        else:
            target_root = base_root

    full_path = os.path.normpath(os.path.join(target_root, path))

    # Security check: ensure path is within workspace
    if not full_path.startswith(os.path.normpath(target_root)):
        return {"status": "error", "message": "Access denied"}

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return {"status": "error", "message": "File not found"}

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"content": content, "path": path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/logs-stream")
def logs_stream():
    """Server-Sent Events stream for logs. Clients can open an EventSource on this endpoint.
    This yields new log lines as they arrive.
    """
    def event_generator():
        last_index = 0
        try:
            while True:
                # Yield any new logs
                if last_index < len(session.logs):
                    for l in session.logs[last_index:]:
                        data = f"data: {l['timestamp']}|{l['type']}|{l['message'].replace('\n', ' ')}\n\n"
                        yield data
                    last_index = len(session.logs)

                # If not running and no new logs for a while, keep connection alive
                time.sleep(0.5)
        except GeneratorExit:
            return

    return StreamingResponse(event_generator(), media_type='text/event-stream')


@app.post("/api/stop")
def stop_agent():
    # Best-effort stop: set request flag and log. AgentSystem may or may not honor this.
    if not session.is_running:
        return {"status": "error", "message": "Agent not running"}

    session.request_stop = True
    session.logs.append({"timestamp": time.time(), "message": "Stop requested from frontend", "type": "control"})
    return {"status": "requested"}

@app.post("/api/clear-workspace")
def clear_workspace():
    if session.is_running:
        return {"status": "error", "message": "Cannot clear workspace while agent is running"}
    
    root = session.workspace_root
    if session.system and session.system.workspace_root:
        root = session.system.workspace_root
    
    try:
        import shutil
        if os.path.exists(root):
            shutil.rmtree(root)
        os.makedirs(root, exist_ok=True)
        return {"status": "success", "message": "Workspace cleared"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/upload-file")
async def upload_file(file: UploadFile = File(...), root: Optional[str] = None):
    if session.is_running:
        return {"status": "error", "message": "Cannot upload file while agent is running"}
    
    base_root = session.workspace_root
    
    # Determine target workspace root
    if root:
        # Handle both absolute and relative paths
        if os.path.isabs(root):
            target_root = os.path.normpath(root)
        else:
            target_root = os.path.normpath(os.path.join(base_root, root))
        # Security: must be under base_root
        if not target_root.startswith(os.path.normpath(base_root)):
            return {"status": "error", "message": "Invalid workspace root"}
    else:
        # Fallback to system workspace or base
        if session.system and session.system.workspace_root:
            target_root = session.system.workspace_root
        else:
            target_root = base_root
    
    try:
        # Ensure workspace exists
        os.makedirs(target_root, exist_ok=True)
        
        # Save uploaded file
        file_path = os.path.join(target_root, file.filename)
        file_path = os.path.normpath(file_path)
        
        # Security check: ensure path is within workspace
        if not file_path.startswith(os.path.normpath(target_root)):
            return {"status": "error", "message": "Invalid file path"}
        
        # Create subdirectories if needed
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        contents = await file.read()
        with open(file_path, 'wb') as f:
            f.write(contents)
        
        return {"status": "success", "message": f"File {file.filename} uploaded", "filename": file.filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/delete-file")
def delete_file(path: str, root: str = None):
    if session.is_running:
        return {"status": "error", "message": "Cannot delete file while agent is running"}
    
    base_root = session.workspace_root
    
    # Determine target workspace
    if root:
        if os.path.isabs(root):
            target_root = os.path.normpath(root)
        else:
            target_root = os.path.normpath(os.path.join(base_root, root))
        if not target_root.startswith(os.path.normpath(base_root)):
            return {"status": "error", "message": "Invalid workspace root"}
    else:
        if session.system and session.system.workspace_root:
            target_root = session.system.workspace_root
        else:
            target_root = base_root
    
    try:
        full_path = os.path.join(target_root, path)
        full_path = os.path.normpath(full_path)
        
        # Security check: ensure path is within workspace
        if not full_path.startswith(os.path.normpath(target_root)):
            return {"status": "error", "message": "Access denied"}
        
        if not os.path.exists(full_path):
            return {"status": "error", "message": "File not found"}
        
        if not os.path.isfile(full_path):
            return {"status": "error", "message": "Not a file"}
        
        os.remove(full_path)
        return {"status": "success", "message": f"File {path} deleted"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/input")
def provide_input(req: InputRequest):
    if not session.waiting_for_input:
        return {"status": "error", "message": "Not waiting for input"}
    
    session.user_input = req.text
    session.input_event.set()
    return {"status": "accepted"}

@app.post("/api/cancel-input")
def cancel_input():
    """Cancel waiting for user input"""
    if not session.waiting_for_input:
        return {"status": "error", "message": "Not waiting for input"}
    
    session.user_input = "CANCELLED_BY_USER"
    session.waiting_for_input = False
    session.input_event.set()
    session.logs.append({"timestamp": time.time(), "message": "User cancelled input request", "type": "control"})
    return {"status": "cancelled"}

@app.get("/api/config")
def get_config():
    """Get current configuration settings"""
    config = {
        "enable_search_tool": True,
        "enable_hitl": True,
        "enable_simple_task_check": True,
        "enable_deep_research": True,
        "deep_research_use_simple_goal": False,
    }
    if session.system and hasattr(session.system, 'config'):
        config.update({
            "enable_search_tool": session.system.config.enable_search_tool,
            "enable_hitl": session.system.config.enable_hitl,
            "enable_simple_task_check": session.system.config.enable_simple_task_check,
            "enable_deep_research": session.system.config.enable_deep_research,
            "deep_research_use_simple_goal": session.system.config.deep_research_use_simple_goal,
        })
    return {"config": config}


@app.post("/api/create-workspace")
def create_workspace(group: str = None):
    """Create a new workspace directory under the base workspace root and return its name.
    The name is a short hash to avoid collisions and keep paths tidy.
    """
    base = session.workspace_root
    # If a group is provided, create (and use) a subfolder under base for grouping related sessions
    if group:
        # sanitize group to avoid path traversal or absolute paths
        group = os.path.normpath(group).replace('..', '')
        # prevent absolute paths
        if os.path.isabs(group):
            group = os.path.basename(group)
        base = os.path.join(base, group)
        os.makedirs(base, exist_ok=True)
    # Use UUID + timestamp to generate a unique name, then shorten via sha1
    raw = f"{uuid.uuid4().hex}-{time.time()}"
    name = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]
    target = os.path.join(base, name)
    try:
        os.makedirs(target, exist_ok=True)
        # Optionally create a placeholder README
        readme = os.path.join(target, 'README.md')
        if not os.path.exists(readme):
            with open(readme, 'w', encoding='utf-8') as f:
                f.write(f"# Workspace {name}\n\nCreated at {time.ctime()}")
        # Return created workspace name and group (if used) so clients can construct paths
        result = {"status": "created", "workspace": name}
        if group:
            result["group"] = group
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/delete-workspace")
def delete_workspace(workspace: str, group: str = None):
    """Delete a specific workspace directory."""
    if session.is_running:
        return {"status": "error", "message": "Cannot delete workspace while agent is running"}

    base = session.workspace_root
    if group:
         # sanitization
         group = os.path.normpath(group).replace('..', '')
         if os.path.isabs(group): group = os.path.basename(group)
         base = os.path.join(base, group)
    
    # sanitation
    workspace = os.path.normpath(workspace).replace('..', '')
    if os.path.isabs(workspace): workspace = os.path.basename(workspace)
    
    target = os.path.join(base, workspace)
    
    try:
        import shutil
        if os.path.exists(target) and target.startswith(session.workspace_root):
            shutil.rmtree(target)
            return {"status": "success", "message": f"Workspace {workspace} deleted"}
        else:
             return {"status": "error", "message": "Workspace not found or invalid path"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
