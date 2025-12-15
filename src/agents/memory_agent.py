from typing import Any, Dict, Optional
from agno.agent import Agent
from src.schema.models import Context, Step, ExecutionLog

class MemoryAgent:
    def summarize_step(self, step: Step, log: ExecutionLog, context: Context, model: Any) -> Dict[str, Any]:
        """
        Analyzes the execution log of a step and extracts key information to update the shared state.
        Returns a dictionary of updates.
        """
        prompt = f"""
        You are a Memory Manager. Your job is to extract key information from the execution log of a completed step.
        
        Step Task: {step.task}
        Step Description: {step.description}
        
        Execution Log:
        Agent: {log.agent}
        Content: {log.content}
        Code: {log.code}
        Output: {log.output}
        
        Current Shared State:
        {context.shared_state}
        
        Instructions:
        1. Identify any NEW files created (look for "OUTPUT_FILE:" tags or file saving code).
        2. Identify any key metrics calculated (look for "METRIC:" tags or printed numbers like accuracy, score).
        3. CRITICAL: Identify the "current_dataset" if a new dataset was created or processed. This is the file that subsequent steps should use.
        4. Summarize the outcome in 1 sentence.
        5. Return a JSON object with the updates.
        
        JSON Format:
        {{
            "new_files": ["file1.csv", ...],
            "metrics": {{"accuracy": 0.85, ...}},
            "summary": "Cleaned data and saved to train_clean.csv",
            "task_specific_info": {{ 
                "current_dataset": "train_clean.csv", 
                "target_column": "price",
                ...any other relevant info... 
            }}
        }}
        """
        
        agent = Agent(
            name="MemoryAgent",
            model=model,
            instructions=["You are a memory manager. Output valid JSON only."],
            markdown=False,
        )
        
        try:
            response = agent.run(prompt)
            import json
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        except Exception as e:
            print(f"Memory Agent Error: {e}")
            return {}
    
    def summary_page(self, page_content: str, goal: str, context: Context, model: Any) -> Dict[str, Any]:
        """
        Summarizes and extracts key information from a webpage.
        
        Args:
            page_content: The raw webpage content to summarize
            goal: The extraction goal or user intent
            context: The execution context containing shared state
            model: The LLM model to use for summarization
            
        Returns:
            Dictionary with keys:
                - "rational": Why this information is relevant to the goal
                - "evidence": The extracted evidence/information
                - "summary": Concise summary of key findings
                - "task_specific_info": Any task-specific extracted data
        """
        prompt = f"""
        You are an expert content analyst and information extractor. Your job is to analyze webpage content and extract information relevant to a specific goal.
        
        User Goal: {goal}
        
        Webpage Content:
        {page_content}
        
        Current Context:
        {context.shared_state}
        
        Instructions:
        1. Carefully read the webpage content.
        2. Identify sections and information directly relevant to the goal.
        3. Extract the most important evidence and data points.
        4. Provide a concise but comprehensive summary.
        5. Return a JSON object with your analysis.
        
        JSON Format:
        {{
            "rational": "Why this information is relevant to the goal (1-2 sentences)",
            "evidence": "The most relevant information extracted from the content (3+ paragraphs, preserve full context)",
            "summary": "A concise summary of key findings in 2-3 sentences",
            "task_specific_info": {{
                "key_topics": ["topic1", "topic2", ...],
                "key_entities": ["entity1", "entity2", ...],
                "main_insights": ["insight1", "insight2", ...],
                ...any other relevant structured data...
            }}
        }}
        """
        
        agent = Agent(
            name="PageSummaryAgent",
            model=model,
            instructions=[
                "You are a content analysis expert.",
                "Extract information relevant to the user's goal.",
                "Preserve important context and details.",
                "Output valid JSON only."
            ],
            markdown=False,
        )
        
        try:
            response = agent.run(prompt)
            import json
            content = response.content
            
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Ensure all required keys exist
            required_keys = ["rational", "evidence", "summary", "task_specific_info"]
            for key in required_keys:
                if key not in result:
                    result[key] = ""
            
            return result
        except Exception as e:
            print(f"Page Summary Error: {e}")
            return {
                "rational": "Failed to analyze",
                "evidence": "",
                "summary": f"Error during summarization: {str(e)}",
                "task_specific_info": {}
            }
