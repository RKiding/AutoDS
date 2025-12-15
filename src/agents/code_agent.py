from typing import Any, Optional
from agno.agent import Agent
from src.schema.models import Context, Step, ExecutionLog
from src.utils.tools import WorkspaceTools, SearchWrapper
from src.utils.parser import extract_code_block

class CodeAgent:
    def __init__(self, workspace_tools: WorkspaceTools, enable_search: bool = False):
        self.workspace_tools = workspace_tools
        self.enable_search = enable_search
        self.search_wrapper = SearchWrapper(workspace_tools) if enable_search else None

    def run(self, step: Step, context: Context, model: Any, stop_checker=None) -> ExecutionLog:
        """
        Executes a step by generating and running Python code.
        """
        # 1. Construct Prompt
        current_files = self.workspace_tools.list_files()
        
        # ENHANCEMENT: Get file summaries for CSVs to prevent hallucination of columns
        file_summaries, csv_files = self.workspace_tools.get_csv_summaries()
        
        # Get context specific to this step (e.g. what Analyst found)
        step_context = context.get_current_step_context(step.id)
        
        # Get project history (previous steps and shared state)
        project_history = context.get_project_history()
        
        prompt = f"""
        You are an expert Python Developer.
        Your task is to write Python code to complete the following step:
        
        Task: {step.task}
        Description: {step.description}
        
        Context:
        User Goal: {context.user_goal}
        Current Workspace Files:
        {current_files}
        
        AVAILABLE DATASETS (List of valid filenames):
        {csv_files}
        
        File Previews (First 5 lines of each CSV - Use this to determine headers and separators):
        {file_summaries}
        
        Project History & Shared State:
        {project_history}
        
        Previous Actions in this Step:
        {step_context}
        
        Instructions:
        1. Write complete, executable Python code.
        2. CRITICAL: You MUST pick ONE filename from the 'AVAILABLE DATASETS' list above if you need to load data. 
           - Example: If the list is ['data.csv'], use "data.csv". 
           - DO NOT use the string "AVAILABLE_DATASETS" as a filename.
           - DO NOT use placeholders like "your_dataset.csv".
        3. DATA LOADING: Look at the 'File Previews'. 
           - If the first line looks like headers, use `header=0`. 
           - Check the separator (comma, semicolon, tab).
        4. DATA INTEGRITY: 
           - Do NOT blindly convert all columns to numeric. 
           - Preserve categorical columns (strings) unless you are explicitly encoding them.
           - Do NOT fill NaNs with 0 unless it makes sense for that specific column.
        5. ISOLATION WARNING: This code runs in a completely new process. Variables from previous steps (like 'df', 'model', 'X_train') are NOT available.
        6. PERSISTENCE: You MUST load data from files created in previous steps. You MUST save any intermediate data (processed datasets, models, encoders) to files (e.g., .csv, .pkl, .joblib) if they are needed in future steps.
        7. ROBUSTNESS: Check if files exist before loading. Handle potential missing values or type mismatches gracefully.
        8. Output the code in a ```python ... ``` block.
        9. Do NOT generate synthetic/dummy data to bypass errors. If a file is missing, fail so we can fix the path.
        """
        
        tools = []
        if self.enable_search and self.search_wrapper:
            tools.append(self.search_wrapper.search_and_save)
            prompt += "\n        9. You have access to a 'search_and_save' tool. Use it if you need to find external documentation or libraries."

        # 2. Create Agent (Lightweight wrapper)
        agent = Agent(
            name="CodeAgent",
            model=model,
            tools=tools,
            instructions=["You are a helpful coding assistant."],
            markdown=True
        )
        
        # 3. Execution Loop (Simple retry)
        max_retries = 2
        retry_count = 0
        execution_log = ExecutionLog(step_id=step.id, agent="CodeAgent")
        
        while retry_count <= max_retries:
            # Check for stop request
            if stop_checker and stop_checker():
                execution_log.error = "Execution stopped by user"
                return execution_log
            
            try:
                # Generate Code
                response = agent.run(prompt)
                execution_log.content = response.content # Save raw response
                code = extract_code_block(response.content)
                
                if not code:
                    prompt += "\n\nERROR: No code block found. Please output code in ```python ... ```."
                    retry_count += 1
                    continue
                
                execution_log.code = code
                
                # Execute Code
                filename = f"tmp/step_{step.id}_attempt_{retry_count}.py"
                output = self.workspace_tools.execute_python(code, filename)
                execution_log.output = output
                execution_log.artifacts.append(filename)
                
                # Check for errors
                # Enhanced error detection: Check for common error keywords even if exit code was 0 (which execute_python might mask)
                error_keywords = ["Traceback", "Error:", "Exception:", "SyntaxError", "NameError", "TypeError", "ValueError", "ImportError", "ModuleNotFoundError", "AttributeError", "IndexError", "KeyError", "FileNotFoundError"]
                is_error = any(keyword in output for keyword in error_keywords)
                
                if is_error:
                    execution_log.error = output
                    
                    # ENHANCEMENT: Provide better feedback for FileNotFoundError
                    error_hint = ""
                    if "FileNotFoundError" in output:
                        error_hint = f"\nCRITICAL ERROR: File not found. \nREAL AVAILABLE FILES: {self.workspace_tools.list_files()}\nPlease use one of these exact filenames."

                    prompt = f"""
                    The code failed to execute.
                    
                    Your previous code:
                    ```python
                    {code}
                    ```
                    
                    Error Output:
                    {output}
                    {error_hint}
                    
                    Please analyze the error and provide the FIXED code in a new ```python ... ``` block.
                    """
                    retry_count += 1
                else:
                    # Success
                    execution_log.error = None
                    return execution_log
                    
            except Exception as e:
                execution_log.error = str(e)
                retry_count += 1
        
        return execution_log
