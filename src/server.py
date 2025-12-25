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
import json

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# Session storage file path
SESSIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions.json')
# Config file path
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'agent_config.yaml')

from src.main import AgentSystem
from src.schema.config import load_agent_config
from src.utils.tools import NewsNowWrapper, PolymarketWrapper, WorkspaceTools, HotDataCache

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

from typing import Optional, Dict, List, Any

# ==================== Session Persistence ====================

def load_sessions() -> List[Dict[str, Any]]:
    """Load sessions from JSON file"""
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load sessions: {e}")
    return []

def save_sessions(sessions_list: List[Dict[str, Any]]) -> bool:
    """Save sessions to JSON file"""
    try:
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions_list, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Failed to save sessions: {e}")
        return False

# ==================== Pydantic Models ====================

class GoalRequest(BaseModel):
    goal: str
    workspace_root: Optional[str] = None
    config: Optional[Dict[str, bool]] = None

class InputRequest(BaseModel):
    text: str

class SessionCreate(BaseModel):
    name: Optional[str] = None

class SessionUpdate(BaseModel):
    name: Optional[str] = None
    logs: Optional[List[Dict[str, Any]]] = None

def run_agent_task(goal: str, workspace_root: str = None, config_overrides: dict = None):
    session.is_running = True
    session.request_stop = False
    try:
        # Initialize system
        root = workspace_root if workspace_root else session.workspace_root
        session.system = AgentSystem(
            workspace_root=root,
            config_path=CONFIG_FILE,
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
    active_workspace = None
    if session.system and hasattr(session.system, 'workspace_root'):
        active_workspace = session.system.workspace_root
        
    return {
        "is_running": session.is_running,
        "waiting_for_input": session.waiting_for_input,
        "logs": session.logs,
        "active_workspace": active_workspace
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

@app.get("/api/hot-data")
def get_hot_data(background_tasks: BackgroundTasks):
    """Fetch hot data from Polymarket and NewsNow with background pre-fetching"""
    try:
        # Initialize tools
        ws_tools = WorkspaceTools(session.workspace_root)
        nn_wrapper = NewsNowWrapper(ws_tools)
        pm_wrapper = PolymarketWrapper(ws_tools)
        
        # Try to get from cache first for immediate response
        pm_markets = pm_wrapper.get_active_markets(limit=10)
        
        nn_data = {}
        # Expanded list of sources - all available platforms
        sources = [
            "weibo", "zhihu", "baidu", "toutiao", "douyin", 
            "bilibili", "thepaper", "36kr", "ithome", 
            "wallstreetcn", "cls", "caixin", "yicai", 
            "sina-finance", "eastmoney", "jiemian"
        ]
        
        # Check if we have all sources in cache
        for source in sources:
            cache_key = f"newsnow_{source}_10"
            cached = HotDataCache.get(cache_key)
            if cached and "items" in cached:
                nn_data[source] = cached["items"]
            else:
                # If not cached, fetch immediately for this request
                try:
                    result = nn_wrapper.get_news(source, count=10)
                    if result and "items" in result:
                        nn_data[source] = result["items"]
                except Exception as e:
                    print(f"Error fetching {source}: {e}")
                    # Continue with other sources even if one fails
        
        return {
            "status": "success",
            "polymarket": pm_markets or [],
            "newsnow": nn_data
        }
    except Exception as e:
        print(f"Error in get_hot_data: {e}")
        return {
            "status": "error", 
            "message": str(e),
            "polymarket": [],
            "newsnow": {}
        }

def refresh_hot_data_cache(sources):
    """Background task to refresh cache"""
    try:
        ws_tools = WorkspaceTools(session.workspace_root)
        nn_wrapper = NewsNowWrapper(ws_tools)
        for source in sources:
            nn_wrapper.get_news(source, count=10)
    except:
        pass

@app.get("/api/config")
def get_config():
    """Get current configuration settings"""
    # Try to get config from active system first
    if session.system and hasattr(session.system, 'config'):
        cfg = session.system.config
    else:
        # Fallback to loading from file
        cfg = load_agent_config(CONFIG_FILE)
        
    config = {
        "enable_search_tool": cfg.enable_search_tool,
        "enable_hitl": cfg.enable_hitl,
        "enable_simple_task_check": cfg.enable_simple_task_check,
        "enable_deep_research": cfg.enable_deep_research,
        "deep_research_use_simple_goal": cfg.deep_research_use_simple_goal,
    }
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

# ==================== Session Management API ====================

@app.get("/api/sessions")
def list_sessions():
    """List all sessions"""
    sessions_list = load_sessions()
    return {"sessions": sessions_list}

@app.post("/api/sessions")
def create_session_api(req: SessionCreate = None):
    """Create a new session and corresponding workspace"""
    sessions_list = load_sessions()
    
    session_id = int(time.time() * 1000)  # Use timestamp as ID
    session_name = req.name if req and req.name else f"Session {len(sessions_list) + 1}"
    
    # Create workspace for this session
    SESSION_GROUP = 'workspacea'
    base = session.workspace_root
    
    # Sanitize group
    group = os.path.normpath(SESSION_GROUP).replace('..', '')
    if os.path.isabs(group):
        group = os.path.basename(group)
    base_with_group = os.path.join(base, group)
    os.makedirs(base_with_group, exist_ok=True)
    
    # Generate unique workspace name
    raw = f"{uuid.uuid4().hex}-{time.time()}"
    workspace_name = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]
    target = os.path.join(base_with_group, workspace_name)
    
    try:
        os.makedirs(target, exist_ok=True)
        # Create placeholder README
        readme = os.path.join(target, 'README.md')
        if not os.path.exists(readme):
            with open(readme, 'w', encoding='utf-8') as f:
                f.write(f"# Workspace {workspace_name}\n\nCreated at {time.ctime()}")
    except Exception as e:
        return {"status": "error", "message": f"Failed to create workspace: {e}"}
    
    # Create session object
    new_session = {
        "id": session_id,
        "name": session_name,
        "workspace": workspace_name,
        "group": group,
        "logs": [],
        "createdAt": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()),
        "updatedAt": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    }
    
    # Add to list (newest first)
    sessions_list.insert(0, new_session)
    
    if save_sessions(sessions_list):
        return {"status": "created", "session": new_session}
    else:
        return {"status": "error", "message": "Failed to save session"}

@app.get("/api/sessions/{session_id}")
def get_session(session_id: int):
    """Get a specific session by ID"""
    sessions_list = load_sessions()
    for s in sessions_list:
        if s.get("id") == session_id:
            return {"status": "success", "session": s}
    return {"status": "error", "message": "Session not found"}

@app.put("/api/sessions/{session_id}")
def update_session(session_id: int, req: SessionUpdate):
    """Update a session (name or logs)"""
    sessions_list = load_sessions()
    
    for i, s in enumerate(sessions_list):
        if s.get("id") == session_id:
            if req.name is not None:
                sessions_list[i]["name"] = req.name
            if req.logs is not None:
                sessions_list[i]["logs"] = req.logs
            sessions_list[i]["updatedAt"] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            
            if save_sessions(sessions_list):
                return {"status": "success", "session": sessions_list[i]}
            else:
                return {"status": "error", "message": "Failed to save session"}
    
    return {"status": "error", "message": "Session not found"}

@app.delete("/api/sessions/{session_id}")
def delete_session_api(session_id: int):
    """Delete a session and its workspace"""
    if session.is_running:
        return {"status": "error", "message": "Cannot delete session while agent is running"}
    
    sessions_list = load_sessions()
    session_to_delete = None
    
    for s in sessions_list:
        if s.get("id") == session_id:
            session_to_delete = s
            break
    
    if not session_to_delete:
        return {"status": "error", "message": "Session not found"}
    
    # Delete workspace
    workspace = session_to_delete.get("workspace", "")
    group = session_to_delete.get("group", "")
    
    base = session.workspace_root
    if group:
        group = os.path.normpath(group).replace('..', '')
        if os.path.isabs(group):
            group = os.path.basename(group)
        base = os.path.join(base, group)
    
    workspace = os.path.normpath(workspace).replace('..', '')
    if os.path.isabs(workspace):
        workspace = os.path.basename(workspace)
    
    target = os.path.join(base, workspace)
    
    try:
        import shutil
        if os.path.exists(target) and target.startswith(session.workspace_root):
            shutil.rmtree(target)
    except Exception as e:
        print(f"⚠️ Failed to delete workspace: {e}")
    
    # Remove from sessions list
    sessions_list = [s for s in sessions_list if s.get("id") != session_id]
    
    if save_sessions(sessions_list):
        return {"status": "success", "message": f"Session {session_id} deleted"}
    else:
        return {"status": "error", "message": "Failed to save sessions after deletion"}

@app.post("/api/sessions/{session_id}/logs")
def update_session_logs(session_id: int, logs: List[Dict[str, Any]]):
    """Update session logs (optimized endpoint for log updates)"""
    sessions_list = load_sessions()
    
    for i, s in enumerate(sessions_list):
        if s.get("id") == session_id:
            sessions_list[i]["logs"] = logs
            sessions_list[i]["updatedAt"] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            
            if save_sessions(sessions_list):
                return {"status": "success"}
            else:
                return {"status": "error", "message": "Failed to save logs"}
    
    return {"status": "error", "message": "Session not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

