import time
from typing import Any
from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools
from src.schema.models import Context, Step, ExecutionLog
from src.utils.tools import WorkspaceTools, SearchWrapper

class AnalystAgent:
    def __init__(self, workspace_tools: WorkspaceTools, enable_search: bool = True):
        self.workspace_tools = workspace_tools
        self.enable_search = enable_search
        self.search_wrapper = SearchWrapper(workspace_tools) if enable_search else None

    def run(self, step: Step, context: Context, model: Any, stop_checker=None) -> ExecutionLog:
        """
        Executes a step by performing research or analysis.
        """
        # 1. Construct Prompt
        current_files = self.workspace_tools.list_files()
        
        # ENHANCEMENT: Get file summaries
        file_summaries, csv_files = self.workspace_tools.get_csv_summaries()

        step_context = context.get_current_step_context(step.id)
        
        # Get project history (previous steps and shared state)
        project_history = context.get_project_history()
        
        prompt = f"""
        You are an expert Data Analyst and Researcher.
        Your task is to provide insights, research external information, or interpret results for the following step:
        
        Task: {step.task}
        Description: {step.description}
        
        Context:
        User Goal: {context.user_goal}
        Current Workspace Files:
        {current_files}
        
        AVAILABLE DATASETS (List of valid filenames):
        {csv_files}
        
        File Previews (First 5 lines of each CSV):
        {file_summaries}
        
        Project History & Shared State:
        {project_history}
        
        Previous Actions in this Step:
        {step_context}
        
        Instructions:
        1. If you need external information, use the search_and_save tool.
        2. If you need to analyze a file, use the read_file tool.
        3. Provide a clear, concise summary of your findings.
        4. Do NOT write Python code to be executed. You CANNOT execute code.
        5. If the task requires creating new data files (CSV, PNG, etc.) or performing calculations, you MUST state: "TASK_REQUIRES_CODE_AGENT".
        6. If you find data that should be saved, use the save_file tool (ONLY for text/markdown).
        7. Focus on ANALYSIS (finding patterns, issues, insights), not just formatting or repeating the data.
        
        CRITICAL OUTPUT INSTRUCTION:
        If the Task Description above asks you to start your response with a specific string (e.g., "DATA_ISSUE_FOUND:"), you MUST do it. 
        Do not add any introductory text before that string.
        """
        
        # 2. Create Agent
        # We give it read/save/list tools + search_and_save wrapper
        tools = [
            self.workspace_tools.read_file,
            self.workspace_tools.save_file,
            self.workspace_tools.list_files
        ]
        
        if self.enable_search and self.search_wrapper:
            tools.append(self.search_wrapper.search_and_save)
        
        agent = Agent(
            name="AnalystAgent",
            model=model,
            tools=tools,
            instructions=["You are a helpful analyst."],
            markdown=True,
            # show_tool_calls=True  # Removed: Not supported in this version
        )
        
        execution_log = ExecutionLog(step_id=step.id, agent="AnalystAgent")
        
        # Check for stop request before execution
        if stop_checker and stop_checker():
            execution_log.error = "Execution stopped by user"
            return execution_log
        
        try:
            # Run Agent
            response = agent.run(prompt)
            execution_log.content = response.content
            
            # We don't capture code/output here as it's an analysis agent
            # But we could capture tool outputs if needed. 
            # For now, the response content usually summarizes the tool results.
            
        except Exception as e:
            execution_log.error = str(e)
            
        return execution_log
