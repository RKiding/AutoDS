import json
from typing import Any, Dict
from agno.agent import Agent
from src.schema.models import Plan, Step
from src.utils.tools import WorkspaceTools, SearchWrapper

class PlannerAgent:
    def __init__(self, workspace_tools: WorkspaceTools, enable_search: bool = False):
        self.workspace_tools = workspace_tools
        self.enable_search = enable_search
        self.search_wrapper = SearchWrapper(workspace_tools) if enable_search else None

    def create_plan(self, user_goal: str, model: Any, stop_checker=None) -> dict:
        """
        Create a plan for the given user goal.
        
        Returns:
            dict: Contains 'plan' (Plan object) and 'debug_info' (dict with raw responses and parsing details)
        """
        current_files = self.workspace_tools.list_files()
        
        # ENHANCEMENT: Get file summaries for CSVs
        file_summaries, _ = self.workspace_tools.get_csv_summaries()
        
        # Detect if this is a hot topic analysis task
        is_hot_topic_analysis = any(keyword in user_goal.lower() for keyword in [
            "热点", "舆情", "股票", "股价", "热搜", "趋势", "新闻", 
            "hot topic", "trending", "stock", "market", "sentiment"
        ])

        prompt = f"""
        You are an expert Technical Project Manager.
        Your goal is to create a high-level project roadmap to achieve the User Goal.
        
        User Goal: {user_goal}
        
        Current Workspace Files:
        {current_files}
        
        File Previews (Use these to understand the data structure):
        {file_summaries}
        
        Guidelines:
        1. Create a concise plan with 3-6 High-Level Milestones.
        2. AVOID granular steps like "Install libraries", "Import pandas", "Load data" (as a standalone step), or "Print output".
        3. Group related technical tasks into a single milestone.
           - Example BAD: 1. Load Data. 2. Check Nulls. 3. Fill Nulls.
           - Example GOOD: 1. Data Preprocessing (Load data, assess quality, handle missing values, save cleaned data).
        4. Each milestone should be assignable to a single specialized agent (either a Coder or an Analyst).
           - Coding Milestones: Data processing, model training, system implementation, generating visualizations.
           - Analysis Milestones: Research, data interpretation, reviewing results, planning next steps.
        5. Return the plan strictly as a JSON object with ONLY "steps" key at the top level.
        
        REQUIRED JSON Format (no other keys allowed):
        {{
            "steps": [
                {{
                    "id": 1,
                    "task": "Milestone Title",
                    "description": "Detailed description of the objectives and requirements for this milestone."
                }},
                {{
                    "id": 2,
                    "task": "Next Milestone Title",
                    "description": "More details..."
                }}
            ]
        }}
        
        IMPORTANT: Output ONLY valid JSON with the exact structure above. No markdown, no extra text, no other keys.
        """
        
        # Add hot topic analysis specific guidelines
        if is_hot_topic_analysis:
            prompt += """
        
        🔥 HOT TOPIC ANALYSIS MODE DETECTED:
        - The system has built-in tools for getting trending topics: get_hot_topics_and_save (supports weibo, zhihu, baidu, etc.)
        - The system has akshare for Chinese stock price data
        - DO NOT suggest using external APIs like Yahoo Finance or Alpha Vantage
        - Steps should focus on: 1) Get trending topics, 2) Analyze relevant stocks with akshare, 3) Generate visualizations
        - Emphasize using BUILT-IN tools rather than web scraping or external APIs
        """
        
        tools = []
        if self.enable_search and self.search_wrapper:
            tools.append(self.search_wrapper.search_and_save)
            prompt += "\n        6. You have access to a 'search_and_save' tool. Use it if you need to research the domain before planning."

        agent = Agent(
            name="PlannerAgent",
            model=model,
            tools=tools,
            instructions=["You are a planner. Output ONLY valid JSON with the exact structure requested. Do not include any conversational text, markdown, or any keys other than 'steps'."],
            markdown=False,
        )
        
        max_retries = 3
        retry_count = 0
        last_error = None
        debug_info = {
            "attempts": [],
            "final_response_raw": None,
            "final_parsed_json": None,
            "final_error": None,
            "validation_details": ""
        }
        
        while retry_count <= max_retries:
            # Check for stop request
            if stop_checker and stop_checker():
                print("🛑 Planner stopped by user.")
                return {
                    "plan": Plan(steps=[]),
                    "debug_info": {"final_error": "Stopped by user"}
                }
            
            # Initialize attempt_info before try block to avoid undefined variable errors
            attempt_info = {
                "attempt": retry_count + 1,
                "raw_response": None,
                "error": None,
                "validation_error": None,
                "parsed_json": None
            }
            
            try:
                response = agent.run(prompt)
                content = response.content
                
                # Store raw response for debugging
                attempt_info["raw_response"] = content
                
                # Clean up potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # Attempt to parse JSON
                data = json.loads(content)
                
                # Validate schema: must have 'steps' key with list of dict objects
                if "steps" not in data:
                    raise ValueError("JSON must contain 'steps' key. Got keys: " + str(list(data.keys())))
                
                if not isinstance(data["steps"], list):
                    raise ValueError(f"'steps' must be a list, got {type(data['steps'])}")
                
                if len(data["steps"]) == 0:
                    raise ValueError("'steps' list cannot be empty")
                
                # Validate each step has required fields
                for step in data["steps"]:
                    if not isinstance(step, dict):
                        raise ValueError(f"Each step must be a dict, got {type(step)}")
                    if "id" not in step or "task" not in step or "description" not in step:
                        raise ValueError(f"Each step must have 'id', 'task', and 'description'. Got: {step.keys()}")
                
                attempt_info["parsed_json"] = data
                debug_info["attempts"].append(attempt_info)
                debug_info["final_response_raw"] = response.content
                debug_info["final_parsed_json"] = data
                debug_info["validation_details"] = f"Success: validated {len(data['steps'])} steps"
                
                return {
                    "plan": Plan(**data),
                    "debug_info": debug_info
                }
                
            except Exception as e:
                last_error = e
                attempt_info["error"] = str(e)
                debug_info["attempts"].append(attempt_info)
                print(f"Planner Error (Attempt {retry_count+1}/{max_retries+1}): {e}")
                
                # Update prompt for retry with more explicit instructions
                previous_content = response.content if 'response' in locals() else "No response"
                retry_prompt_addon = f"""

ERROR on previous attempt: {str(e)}
Previous Output: {previous_content[:500]}...

Please output ONLY the raw JSON object in the exact format specified, with no additional text, markdown, or other keys:
{{
    "steps": [
        {{"id": 1, "task": "...", "description": "..."}},
        ...
    ]
}}
"""
                prompt += retry_prompt_addon
                retry_count += 1
        
        # If all retries failed
        debug_info["final_error"] = str(last_error)
        debug_info["validation_details"] = f"Failed after {max_retries + 1} attempts: {str(last_error)}"
        print(f"Planner failed after {max_retries + 1} attempts. Returning empty plan.")
        return {
            "plan": Plan(steps=[]),
            "debug_info": debug_info
        }

    def create_deep_research_plan(self, research_topic: str, model: Any, stop_checker=None) -> Dict[str, Any]:
        """
        Create a deep research plan for the given topic.
        Returns a research strategy with search queries, URLs to visit, and analysis approach.
        
        Args:
            research_topic: The topic to research
            model: The LLM model to use
            
        Returns:
            dict: Contains 'research_plan' (string) and 'debug_info' (dict)
        """
        prompt = f"""
        You are an expert Research Strategist. Your task is to create a comprehensive research plan for the following topic.
        
        Research Topic: {research_topic}
        
        Please provide a detailed research strategy that includes:
        
        1. RESEARCH OBJECTIVES
           - What specific aspects of the topic should be covered?
           - What are the key questions to answer?
        
        2. SEARCH STRATEGY
           - List 5-10 specific search queries that would help gather comprehensive information
           - Focus on different angles and aspects of the topic
           - Example queries:
             * "topic overview and fundamentals"
             * "recent developments and trends"
             * "industry-specific applications"
             * "challenges and limitations"
        
        3. KEY WEBSITES TO VISIT
           - Recommend 5-8 authoritative websites, research papers, or documentation pages
           - Include relevant sections or documentation URLs
           - Prioritize by authority and relevance
        
        4. ANALYSIS APPROACH
           - How should the gathered information be organized?
           - What metrics or comparisons are important?
           - How to synthesize findings into actionable insights?
        
        5. EXPECTED OUTCOMES
           - What kind of report/analysis would be most valuable?
           - Key sections to include in final report
        
        Format your response as a clear, structured plan that an AI research agent can follow.
        """
        
        debug_info = {
            "attempts": [],
            "final_error": None,
            "validation_details": ""
        }
        
        try:
            planner = Agent(
                name="DeepResearchPlanner",
                model=model,
                instructions=[
                    "You are a research planning expert.",
                    "Create detailed, actionable research strategies.",
                    "Include specific search queries and websites.",
                    "Provide clear, structured guidance for research execution."
                ],
                markdown=False,
            )
            
            if stop_checker and stop_checker():
                print("🛑 Deep research planner stopped by user.")
                return {
                    "research_plan": "Stopped by user",
                    "debug_info": {"final_error": "Stopped by user"}
                }
                
            response = planner.run(prompt)
            research_plan = response.content
            
            debug_info["status"] = "success"
            debug_info["plan_length"] = len(research_plan)
            
            return {
                "research_plan": research_plan,
                "debug_info": debug_info
            }
        
        except Exception as e:
            error_msg = f"Deep research plan generation failed: {str(e)}"
            debug_info["final_error"] = error_msg
            print(f"⚠️ {error_msg}")
            
            # Return a default research plan
            default_plan = f"""
            RESEARCH PLAN FOR: {research_topic}
            
            1. RESEARCH OBJECTIVES
               - Gather comprehensive information about {research_topic}
               - Identify key aspects and current trends
               - Find authoritative sources and recent developments
            
            2. SEARCH STRATEGY
               - Search for "{research_topic} overview"
               - Search for "{research_topic} recent developments"
               - Search for "{research_topic} best practices"
               - Search for "{research_topic} tools and implementations"
               - Search for "{research_topic} challenges and solutions"
            
            3. ANALYSIS APPROACH
               - Organize findings by theme
               - Identify patterns and trends
               - Synthesize key insights
            
            4. EXPECTED OUTCOMES
               - Comprehensive report covering all aspects
               - Actionable recommendations
               - List of authoritative sources
            """
            
            return {
                "research_plan": default_plan,
                "debug_info": debug_info
            }
        # Fallback plan
        return Plan(steps=[
            Step(id=1, task="Execute Goal", description=f"Attempt to achieve: {user_goal}")
        ])
