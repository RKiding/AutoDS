from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class Step(BaseModel):
    id: int
    task: str
    description: str
    status: str = "pending" # pending, in_progress, completed, failed
    result: Optional[str] = None
    sub_steps: List[Dict[str, Any]] = [] # Tracks micro-actions within this step

class Plan(BaseModel):
    steps: List[Step] = []

class ExecutionLog(BaseModel):
    step_id: int
    agent: str # CodeAgent or AnalystAgent
    content: Optional[str] = None # For Analyst insights or general messages
    code: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    artifacts: List[str] = []

class Context(BaseModel):
    user_goal: str
    workspace_root: str
    workspace_files: List[str] = []
    plan: Plan = Field(default_factory=Plan)
    execution_history: List[ExecutionLog] = []
    
    # Shared state for task-specific information (e.g., file paths, metrics, key findings)
    shared_state: Dict[str, Any] = Field(default_factory=dict)
    
    # For memory management
    _execution_summary: Optional[str] = None  # Compressed summary of old executions
    
    def get_current_step_context(self, step_id: int) -> str:
        """
        Retrieves the execution history relevant to the current step.
        """
        logs = [log for log in self.execution_history if log.step_id == step_id]
        context_str = ""
        for log in logs:
            context_str += f"--- Agent: {log.agent} ---\n"
            if log.content:
                context_str += f"Insight/Message: {log.content}\n"
            if log.code:
                context_str += f"Code Executed:\n{log.code}\n"
            if log.output:
                context_str += f"Output:\n{log.output}\n"
            if log.error:
                context_str += f"Error:\n{log.error}\n"
            context_str += "\n"
        return context_str if context_str else "No previous actions in this step."

    def compress_execution_history(self, keep_last_n: int = 10) -> None:
        """
        Compress old execution history to prevent unbounded growth.
        Keeps the last N execution logs in full, summarizes older ones.
        
        Args:
            keep_last_n: Number of most recent logs to keep in full
        """
        if len(self.execution_history) <= keep_last_n:
            return
        
        # Summarize old logs
        old_logs = self.execution_history[:-keep_last_n]
        summary_lines = []
        
        for log in old_logs:
            summary_lines.append(f"Step {log.step_id} ({log.agent}): {log.agent} completed task")
            if log.error:
                summary_lines.append(f"  - Error: {log.error[:100]}...")
        
        # Store summary and remove old logs
        self._execution_summary = "\n".join(summary_lines)
        self.execution_history = self.execution_history[-keep_last_n:]

    def get_project_history(self) -> str:
        """
        Returns a summary of all completed steps and the current shared state.
        """
        history = "--- Project History ---\n"
        
        # 1. Shared State Summary
        if self.shared_state:
            history += "Shared State (Key Information):\n"
            # Prioritize current_dataset
            if "current_dataset" in self.shared_state:
                history += f"  >>> CURRENT DATASET: {self.shared_state['current_dataset']} <<<\n"
            
            for k, v in self.shared_state.items():
                if k != "current_dataset":
                    history += f"- {k}: {v}\n"
            history += "\n"
            
        # 2. Step Summaries
        completed_steps = [s for s in self.plan.steps if s.status == "completed"]
        if not completed_steps:
            history += "No steps completed yet.\n"
        else:
            for step in completed_steps:
                history += f"Step {step.id}: {step.task}\n"
                # Find the last log for this step to get the result/output
                step_logs = [l for l in self.execution_history if l.step_id == step.id]
                if step_logs:
                    last_log = step_logs[-1]
                    if last_log.content:
                        history += f"  Result: {last_log.content[:200]}...\n"
                    elif last_log.output:
                        history += f"  Output: {last_log.output[:200]}...\n"
        
        return history
