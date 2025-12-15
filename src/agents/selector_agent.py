from typing import Any, List, Tuple
from agno.agent import Agent
from src.schema.models import Context, Step

class SelectorAgent:
    def select_agent(self, step: Step, context: Context, model: Any, 
                     code_models: List[str], analyst_models: List[str], 
                     performance_history: str) -> Tuple[str, str]:
        """
        Decides which agent AND which model should execute the current step.
        Returns: (AgentName, ModelID)
        """
        prompt = f"""
        You are an expert Orchestrator. Your goal is to route the current task to the most appropriate specialized agent and select the best model for the job.
        
        Available Agents & Models:
        1. CodeAgent: 
           - Writes and executes Python code.
           - MUST be selected for: Data processing, cleaning, training models, generating plots/visualizations, creating new files (CSV, PNG, etc.), or any task requiring calculation.
           - Models: {code_models}
           
        2. AnalystAgent:
           - Performs web research and analyzes text files.
           - MUST be selected for: Reading documentation, searching the web, summarizing text, or planning.
           - CANNOT execute code or generate images/plots.
           - Models: {analyst_models}

        Current Task:
        {step.task}
        
        Task Description:
        {step.description}
        
        User Goal:
        {context.user_goal}
        
        Model Performance History (Reference):
        {performance_history}
        
        Instructions:
        1. Select the best Agent (CodeAgent or AnalystAgent).
        2. Select the best Model ID from the available list for that agent.
           - Use a smaller model (e.g. 1.5b, 3b) for simple tasks.
           - Use a larger model (e.g. 14b, 32b) for complex reasoning or coding.
           - Refer to history: if a model failed a similar task, try a different one.
        3. Return the result in this format: "AgentName:ModelID"
           Example: "CodeAgent:qwen2.5-coder:7b"
        """
        
        agent = Agent(
            name="SelectorAgent",
            model=model,
            instructions=["You are a routing assistant. Return only 'AgentName:ModelID'."],
            markdown=False,
        )
        
        try:
            response = agent.run(prompt)
            selection = response.content.strip()
            if ":" in selection:
                agent_name, model_id = selection.split(":", 1)
                return agent_name.strip(), model_id.strip()
            else:
                # Fallback if format is wrong
                return selection, "" 
        except Exception as e:
            print(f"⚠️ Selector Error: {e}")
            return "CodeAgent", "" # Default fallback
