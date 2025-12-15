import os
import json
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class PerformanceRecord(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    task: str
    agent: str
    model_id: str
    status: str # "success" or "failed"
    feedback: str = ""
    input_context: Optional[Dict[str, Any]] = None
    output_context: Optional[Dict[str, Any]] = None
    code_execution: Optional[Dict[str, Any]] = None

class PerformanceManager:
    def __init__(self, workspace_root: str):
        self.history_file = os.path.join(workspace_root, "model_performance.json")
        self.history: List[PerformanceRecord] = self._load_history()
        self._batch_writes = []  # Buffer for batch writing
        self._batch_size = 5  # Write to disk every N records

    def _load_history(self) -> List[PerformanceRecord]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                    return [PerformanceRecord(**r) for r in data]
            except Exception as e:
                print(f"⚠️ Error loading performance history: {e}")
                return []
        return []

    def log_performance(
        self, 
        task: str, 
        agent: str, 
        model_id: str, 
        status: str, 
        feedback: str = "",
        input_context: Optional[Dict[str, Any]] = None,
        output_context: Optional[Dict[str, Any]] = None,
        code_execution: Optional[Dict[str, Any]] = None
    ):
        record = PerformanceRecord(
            task=task,
            agent=agent,
            model_id=model_id,
            status=status,
            feedback=feedback,
            input_context=input_context,
            output_context=output_context,
            code_execution=code_execution
        )
        self.history.append(record)
        self._batch_writes.append(record)
        
        # Write to disk every N records (batch writing for performance)
        if len(self._batch_writes) >= self._batch_size:
            self._save_history()

    def _save_history(self):
        """Save all history to disk."""
        try:
            with open(self.history_file, "w") as f:
                json.dump([r.model_dump() for r in self.history], f, indent=2)
            self._batch_writes = []  # Clear batch buffer
        except Exception as e:
            print(f"⚠️ Error saving performance history: {e}")

    def flush(self):
        """Explicitly flush pending writes to disk."""
        if self._batch_writes:
            self._save_history()

    def get_relevant_history(self, task: str, agent_type: str, limit: int = 5) -> str:
        """
        Returns a string summary of relevant history for the given agent type.
        For now, it just returns the most recent records for that agent.
        In a real RAG system, this would use embeddings to find semantically similar tasks.
        """
        relevant = [r for r in self.history if r.agent == agent_type]
        # Simple "similarity": maybe just recent ones?
        # Or maybe filter by status?
        
        if not relevant:
            return "No history available."
            
        # Return last 'limit' records
        summary = []
        for r in relevant[-limit:]:
            summary.append(f"- Task: {r.task[:50]}... | Model: {r.model_id} | Status: {r.status}")
            
        return "\n".join(summary)
