import os
import sys
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path to allow importing 'src' modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from src directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from src.schema.models import Context, Plan, Step
from src.utils.tools import WorkspaceTools
from src.schema.config import load_agent_config
from src.agents.planner_agent import PlannerAgent
from src.agents.selector_agent import SelectorAgent
from src.agents.code_agent import CodeAgent
from src.agents.analyst_agent import AnalystAgent
from src.agents.memory_agent import MemoryAgent
from src.agents.report_agent import ReportAgent
from src.agents.deep_research_agent import DeepResearchAgent
from src.utils.factory import get_model 
from src.utils.performance import PerformanceManager

class AgentSystem:
    def __init__(self, workspace_root: str, config_path: str = "agent_config.yaml", logger=None, input_provider=None, config_overrides: dict = None, stop_checker=None):
        self.workspace_root = workspace_root
        self.logger_callback = logger if logger else print
        self.input_provider = input_provider if input_provider else input
        self.stop_checker = stop_checker if stop_checker else (lambda: False)
        
        # Ensure workspace exists
        if not os.path.exists(self.workspace_root):
            os.makedirs(self.workspace_root)
            
        # Initialize Tools
        self.workspace_tools = WorkspaceTools(self.workspace_root)
        self.performance_manager = PerformanceManager(self.workspace_root)
        
        # Load Configuration
        self.config = load_agent_config(config_path)
        
        # Apply Overrides
        if config_overrides:
            print(f"⚙️ Applying config overrides: {config_overrides}")
            if 'enable_search_tool' in config_overrides:
                self.config.enable_search_tool = config_overrides['enable_search_tool']
            if 'enable_hitl' in config_overrides:
                self.config.enable_hitl = config_overrides['enable_hitl']
            if 'enable_simple_task_check' in config_overrides:
                self.config.enable_simple_task_check = config_overrides['enable_simple_task_check']
            if 'enable_deep_research' in config_overrides:
                self.config.enable_deep_research = config_overrides['enable_deep_research']
            if 'deep_research_use_simple_goal' in config_overrides:
                self.config.deep_research_use_simple_goal = config_overrides['deep_research_use_simple_goal']

        print(f"⚙️ Loaded configuration from {config_path}")
        print(f"⚙️ Final enable_deep_research = {self.config.enable_deep_research}")
        
        # Initialize Models for each agent
        self.planner_model = get_model(
            self.config.planner.provider, 
            self.config.planner.model_id, 
            **self.config.planner.to_kwargs()
        )
        # Initialize deep research planner model if configured
        self.deep_research_planner_model = None
        if self.config.deep_research_planner:
            self.deep_research_planner_model = get_model(
                self.config.deep_research_planner.provider,
                self.config.deep_research_planner.model_id,
                **self.config.deep_research_planner.to_kwargs()
            )
        else:
            # Fallback to regular planner model
            self.deep_research_planner_model = self.planner_model
        
        self.selector_model = get_model(
            self.config.selector.provider, 
            self.config.selector.model_id, 
            **self.config.selector.to_kwargs()
        )
        self.code_model = get_model(
            self.config.code_agent.provider, 
            self.config.code_agent.model_id, 
            **self.config.code_agent.to_kwargs()
        )
        self.analyst_model = get_model(
            self.config.analyst_agent.provider, 
            self.config.analyst_agent.model_id, 
            **self.config.analyst_agent.to_kwargs()
        )
        # Reuse analyst model for memory agent for now
        self.memory_model = self.analyst_model
        
        # Initialize Agents
        enable_search = self.config.enable_search_tool
        self.planner = PlannerAgent(self.workspace_tools, enable_search=enable_search)
        self.selector = SelectorAgent()
        self.code_agent = CodeAgent(self.workspace_tools, enable_search=enable_search)
        self.analyst_agent = AnalystAgent(self.workspace_tools, enable_search=enable_search)
        self.memory_agent = MemoryAgent()
        
        # Initialize DeepResearchAgent if enabled
        self.deep_research_enabled = self.config.enable_deep_research
        self.deep_research_agent = DeepResearchAgent(
            self.workspace_tools, 
            enable_search=enable_search
        ) if self.deep_research_enabled else None
        
        # Initialize Context
        files_str = self.workspace_tools.list_files()
        # Convert string output to list, handling empty/error cases
        if "Workspace is empty" in files_str or "Error" in files_str:
            files_list = []
        else:
            files_list = [f.strip() for f in files_str.split("\n") if f.strip()]

        self.context = Context(
            user_goal="",
            workspace_root=self.workspace_root,
            workspace_files=files_list
        )

    def _check_is_simple_task(self, user_goal: str) -> bool:
        """
        Uses the selector model to judge if a task is simple enough to be answered directly.
        """
        from agno.agent import Agent
        
        prompt = f"""
        Analyze the following User Goal and determine if it is a "Simple Task" or a "Complex Task".
        
        User Goal: {user_goal}
        
        Definitions:
        - Simple Task: Can be answered directly with general knowledge or a single web search. Does not require creating files, writing code, or multi-step planning.
          Examples: "What is the capital of France?", "Explain quantum computing", "Search for the latest news on AI".
        - Complex Task: Requires multiple steps, writing code, data analysis, creating files, or using specific tools in sequence.
          Examples: "Train a model on this dataset", "Scrape this website and save to CSV", "Analyze the sales data".
        
        Output ONLY "SIMPLE" or "COMPLEX".
        """
        
        try:
            judge = Agent(model=self.selector_model)
            response = judge.run(prompt)
            result = response.content.strip().upper()
            return "SIMPLE" in result
        except Exception as e:
            print(f"⚠️ Error checking task complexity: {e}")
            return False

    def log(self, *args, **kwargs):
        """Helper to log messages via the configured callback."""
        # Convert all args to string and join them, similar to print default behavior
        msg = " ".join(map(str, args))
        self.logger_callback(msg)

    def run(self, user_goal: str):
        self.log(f"🚀 Starting Agent System")
        self.log(f"🎯 Goal: {user_goal}")
        
        self.context.user_goal = user_goal

        # LOGGING: System Start
        self.performance_manager.log_performance(
            task="System Initialization",
            agent="System",
            model_id="N/A",
            status="start",
            input_context={
                "user_goal": user_goal, 
                "workspace_root": self.workspace_root,
                "config": self.config.model_dump() if hasattr(self.config, "model_dump") else str(self.config)
            }
        )
        
        # 0. Simple Task Check
        if self.config.enable_simple_task_check:
            # Check for stop before starting simple task check
            if self.stop_checker():
                self.log("\n🛑 Stop requested by user. Exiting gracefully...")
                return
                
            if self._check_is_simple_task(user_goal):
                self.log("\nℹ️ Task identified as SIMPLE. Executing directly...")
                from agno.agent import Agent
                
                # Use Analyst Agent (with search if enabled) for direct answer
                tools = []
                if self.config.enable_search_tool and self.analyst_agent.search_wrapper:
                    tools.append(self.analyst_agent.search_wrapper.search_and_save)
                
                direct_agent = Agent(
                    name="DirectAgent",
                    model=self.analyst_model,
                    tools=tools,
                    instructions=["You are a helpful assistant. Answer the user's question directly."],
                    markdown=True
                )
                response = direct_agent.run(user_goal)
                self.log(f"\n💬 Response:\n{response.content}")
                self.log("\n🏁 Mission Complete!")
                return

        # 0.5 Deep Research Phase (if enabled)
        # Use self.config.enable_deep_research to ensure runtime config overrides are respected
        if self.config.enable_deep_research and self.deep_research_agent:
            self.log("\n🔬 Starting Deep Research Phase...")
            
            try:
                # Generate research plan using deep research planner model (or use simple goal if configured)
                if self.config.deep_research_use_simple_goal:
                    # Use simple goal sentence without detailed planning
                    self.log("📋 Using simple goal for deep research (no detailed plan generation)...")
                    research_plan = f"Research Goal: {user_goal}"
                    self.log(f"✅ Research Goal: {research_plan}")
                else:
                    # Generate detailed research plan
                    self.log("📋 Generating Research Plan...")
                    plan_result = self.planner.create_deep_research_plan(user_goal, self.deep_research_planner_model, stop_checker=self.stop_checker)
                    research_plan = plan_result["research_plan"]
                    
                    self.log(f"✅ Research Plan Generated:")
                    self.log(research_plan)
                
                # Initialize visitor with model for summarization
                # Get crawl server URL from config (crawler is a dict)
                crawl_server_url = None
                if isinstance(self.config.crawler, dict):
                    crawl_server_url = self.config.crawler.get('server_url')
                elif hasattr(self.config.crawler, 'server_url'):
                    crawl_server_url = self.config.crawler.server_url
                
                self.deep_research_agent.initialize_visitor(self.analyst_model, crawl_server_url=crawl_server_url)
                
                # Execute deep research
                self.log("\n🌐 Executing Deep Research...")
                log = self.deep_research_agent.run(
                    user_goal,
                    research_plan,
                    self.analyst_model,
                    crawl_server_url=crawl_server_url,
                    stop_checker=self.stop_checker,
                    logger=self.log
                )
                
                # Save research results to context and workspace
                research_content = log.output or "Research completed"
                research_file = "deep_research_findings.md"
                
                # Check for stop request after deep research
                if not self.stop_checker():
                    # Only process results if not stopped
                    # Save to workspace for other agents to read
                    self.workspace_tools.save_file(research_file, research_content)
                    
                    # Add to context for planner awareness
                    self.context.shared_state['deep_research_findings'] = research_content
                    self.context.shared_state['deep_research_file'] = research_file
                    self.context.workspace_files.append(research_file)
                    
                    # Log research execution
                    self.performance_manager.log_performance(
                        task="Deep Research Execution",
                        agent="DeepResearchAgent",
                        model_id=self.config.analyst_agent.model_id,
                        status="success",
                        input_context={
                            "user_goal": user_goal,
                            "research_plan": research_plan
                        },
                        output_context={
                            "findings": research_content,
                            "artifacts_saved": log.artifacts + [research_file]
                        }
                    )
                    
                    self.log(f"\n✅ Deep Research Complete")
                    self.log(f"📄 Research findings saved to: {research_file}")
                else:
                    self.log("\n🛑 Stop requested by user. Exiting gracefully...")
                    return
                
            except Exception as e:
                self.log(f"⚠️ Deep Research failed: {e}")
                import traceback
                traceback.print_exc()
                # Continue to normal planning pipeline despite error

        # 1. Planning Phase
        self.log("\n📋 Generating Plan...")
        # Stop check before planning (LLM call may take long)
        if self.stop_checker():
            self.log("\n🛑 Stop requested by user before planning. Exiting gracefully...")
            return
        
        # Prepare planning context with deep research findings if available
        planning_goal = user_goal
        if 'deep_research_findings' in self.context.shared_state:
            research_findings = self.context.shared_state['deep_research_findings']
            planning_goal = f"""
Original Goal: {user_goal}

---

Deep Research Findings (available as context for planning):
{research_findings}

---

Use the research findings above to inform your planning. Agents can read the file '{self.context.shared_state.get('deep_research_file', 'deep_research_findings.md')}' during execution for more details.
"""
        
        # Use planner_model
        # Another stop check just before the actual LLM call
        if self.stop_checker():
            self.log("\n🛑 Stop requested by user before creating plan. Exiting gracefully...")
            return
        plan_result = self.planner.create_plan(planning_goal, self.planner_model, stop_checker=self.stop_checker)
        plan = plan_result["plan"]
        debug_info = plan_result.get("debug_info", {})
        self.context.plan = plan
        
        # Format plan for better display
        plan_details = "\n".join([f"  Step {step.id}: {step.task}\n    └─ {step.description}" for step in plan.steps])
        self.log(f"\n📋 PLAN REVIEW\n{'='*60}\n✅ Plan Generated with {len(plan.steps)} steps:\n\n{plan_details}\n{'='*60}")

        # LOGGING: Plan Generated
        self.performance_manager.log_performance(
            task="Plan Generation",
            agent="PlannerAgent",
            model_id=self.config.planner.model_id,
            status="success",
            input_context={
                "user_goal": user_goal,
                "workspace_files": self.context.workspace_files
            },
            output_context={
                "plan": [s.model_dump() for s in plan.steps],
                "debug_info": debug_info
            }
        )
            
        # 1.5 HITL: Plan Review
        if self.config.enable_hitl:
            while True:
                # Check for stop request at the beginning of each iteration
                if self.stop_checker():
                    self.log("\n🛑 Stop requested by user during plan review. Exiting gracefully...")
                    return
                    
                self.log("\n⏸️ [HITL] Plan Review")
                user_input = self.input_provider("Press Enter to approve the plan, or type feedback to modify it: ").strip()

                # If input provider signaled a stop while waiting
                if user_input == "__STOP_REQUESTED__":
                    self.log("\n🛑 Stop requested by user during plan review. Exiting gracefully...")
                    return
                
                # Check again after receiving input (in case stop was requested while waiting)
                if self.stop_checker():
                    self.log("\n🛑 Stop requested by user. Exiting gracefully...")
                    return
                
                if not user_input:
                    self.log("✅ Plan Approved.")
                    break
                else:
                    self.log("🔄 Refining Plan based on feedback...")
                    # Use planner to refine
                    refinement_prompt = f"""
                    Current Plan:
                    {[s.model_dump() for s in plan.steps]}
                    
                    User Feedback: {user_input}
                    
                    Please update the plan to address the user's feedback.
                    Return the full updated plan as JSON.
                    """
                    # We can reuse create_plan logic if we pass the refinement prompt as the "goal" 
                    # but create_plan expects a user_goal string and wraps it.
                    # Let's manually call the agent inside planner or just call create_plan with a constructed prompt.
                    # Calling create_plan is safer as it handles JSON parsing.
                    
                    new_plan_result = self.planner.create_plan(
                        f"Original Goal: {user_goal}. \nCurrent Plan: {[s.model_dump() for s in plan.steps]}. \nUser Feedback: {user_input}. \nUpdate the plan.",
                        self.planner_model,
                        stop_checker=self.stop_checker
                    )
                    
                    new_plan = new_plan_result.get("plan") if new_plan_result else None
                    if new_plan and new_plan.steps:
                        plan = new_plan
                        self.context.plan = plan
                        self.log(f"✅ Plan Updated with {len(plan.steps)} steps:")
                        for step in plan.steps:
                            self.log(f"  - [{step.id}] {step.task}")
                    else:
                        self.log("❌ Failed to update plan. Keeping original.")

        # 2. Execution Phase
        # Use a while loop to allow dynamic plan modification
        step_idx = 0
        while step_idx < len(plan.steps):
            # Check for stop request before each step
            if self.stop_checker():
                self.log("\n🛑 Stop requested by user. Exiting gracefully...")
                break
                
            step = plan.steps[step_idx]
            self.log(f"\n▶️ Executing Step {step.id}: {step.task}")
            self.log(f"   Description: {step.description}")
            
            # Select Agent using selector_model
            # Get relevant history for both agents
            history_code = self.performance_manager.get_relevant_history(step.task, "CodeAgent")
            history_analyst = self.performance_manager.get_relevant_history(step.task, "AnalystAgent")
            combined_history = f"CodeAgent History:\n{history_code}\n\nAnalystAgent History:\n{history_analyst}"
            
            agent_name, model_id = self.selector.select_agent(
                step, 
                self.context, 
                self.selector_model,
                code_models=[m.model_id for m in self.config.code_agent.available_models],
                analyst_models=[m.model_id for m in self.config.analyst_agent.available_models],
                performance_history=combined_history
            )
            self.log(f"   🤖 Selected Agent: {agent_name} (Model: {model_id or 'Default'})")

            # LOGGING: Selector Agent
            self.performance_manager.log_performance(
                task="Agent Selection",
                agent="SelectorAgent",
                model_id=self.config.selector.model_id,
                status="success",
                input_context={
                    "step_task": step.task,
                    "step_description": step.description,
                    "user_goal": self.context.user_goal
                },
                output_context={
                    "selected_agent": agent_name,
                    "selected_model": model_id
                }
            )
            
            # Instantiate the selected model if a specific ID was chosen
            selected_model = None
            if model_id:
                # Find the model config in available_models
                model_config = None
                if agent_name == "CodeAgent":
                    for m in self.config.code_agent.available_models:
                        if m.model_id == model_id:
                            model_config = m
                            break
                elif agent_name == "AnalystAgent":
                    for m in self.config.analyst_agent.available_models:
                        if m.model_id == model_id:
                            model_config = m
                            break
                
                if model_config:
                    try:
                        selected_model = get_model(
                            model_config.provider, 
                            model_config.model_id, 
                            **model_config.to_kwargs()
                        )
                    except Exception as e:
                        self.log(f"   ⚠️ Failed to load model {model_id}: {e}. Using default.")
                else:
                    self.log(f"   ⚠️ Model config for {model_id} not found. Using default.")
            
            # Execute
            step.status = "in_progress"
            log = None
            
            if agent_name == "CodeAgent":
                # Use selected_model or default code_model
                model_to_use = selected_model if selected_model else self.code_model
                log = self.code_agent.run(step, self.context, model_to_use, stop_checker=self.stop_checker)
            elif agent_name == "AnalystAgent":
                # Use selected_model or default analyst_model
                model_to_use = selected_model if selected_model else self.analyst_model
                log = self.analyst_agent.run(step, self.context, model_to_use, stop_checker=self.stop_checker)

                # FALLBACK: Check if Analyst requested CodeAgent
                if log.content and "TASK_REQUIRES_CODE_AGENT" in log.content:
                    self.log("   ⚠️ AnalystAgent requested CodeAgent. Switching...")
                    agent_name = "CodeAgent"
                    log = self.code_agent.run(step, self.context, self.code_model, stop_checker=self.stop_checker)
            else:
                self.log(f"   ❌ Error: Unknown agent selected: {agent_name}")
                step.status = "failed"
                step_idx += 1
                continue
            
            # Check for stop request after agent execution
            if self.stop_checker():
                self.log("\n🛑 Stop requested by user. Exiting gracefully...")
                break
            
            # Log Performance
            status = "failed" if log.error else "success"
            
            code_details = None
            if log.code:
                code_details = {
                    "code": log.code,
                    "output": log.output,
                    "artifacts": log.artifacts
                }

            self.performance_manager.log_performance(
                task=step.task,
                agent=agent_name,
                model_id=model_id or "default",
                status=status,
                feedback=log.error if log.error else "Completed successfully",
                input_context={
                    "user_goal": self.context.user_goal,
                    "step_id": step.id,
                    "step_index": step_idx,
                    "total_steps": len(plan.steps),
                    "step_description": step.description,
                    "shared_state": self.context.shared_state,
                    "workspace_root": self.workspace_root
                },
                output_context={
                    "raw_response": log.content,
                    "execution_output": log.output
                },
                code_execution=code_details
            )
                
            # Update Context
            self.context.execution_history.append(log)
            
            # Parse Output for Shared State Updates
            if log.output:
                for line in log.output.split("\n"):
                    if "OUTPUT_FILE:" in line:
                        try:
                            _, val = line.split("OUTPUT_FILE:", 1)
                            self.context.shared_state["last_output_file"] = val.strip()
                            self.log(f"   🔄 State Updated: last_output_file = {val.strip()}")
                        except: pass
                    if "METRIC:" in line:
                        try:
                            _, val = line.split("METRIC:", 1)
                            if "=" in val:
                                k, v = val.split("=", 1)
                                self.context.shared_state[k.strip()] = v.strip()
                                self.log(f"   🔄 State Updated: {k.strip()} = {v.strip()}")
                        except: pass
            
            # Check Result
            # Double check for error keywords in output even if log.error is None (in case CodeAgent missed it)
            error_keywords = ["Traceback", "Error:", "Exception:", "SyntaxError", "NameError", "TypeError", "ValueError", "ImportError", "ModuleNotFoundError", "AttributeError", "IndexError", "KeyError", "FileNotFoundError"]
            if not log.error and log.output and any(keyword in log.output for keyword in error_keywords):
                log.error = f"Detected error in output: {log.output[:200]}..."

            if log.error:
                self.log(f"   ❌ Step Failed: {log.error}")
                step.status = "failed"
                
                # --- Error Recovery / Plan Update ---
                self.log(f"   ⚠️ Attempting to recover from failure...")
                
                # 1. Ask Planner/Analyst to analyze the error and suggest a fix
                # For now, we will try a simple "Retry with modified instructions" approach
                # or we could insert a new step.
                
                # Let's try to re-run the step with the error explicitly added to the context/instructions
                # But CodeAgent already does retries. If it failed here, it means retries failed.
                
                # If it's a CodeAgent failure, maybe we need to switch to Analyst to debug?
                # Or maybe we just stop for now as requested by the user "update plan (small scope modification)".
                
                # Let's implement a "Plan Refinement" logic here.
                # We will ask the Planner to generate a *new* plan starting from this failed step,
                # given the error message.
                
                recovery_prompt = f"""
                The step '{step.task}' failed with the following error:
                {log.error}
                
                Current Plan Status:
                {[s.model_dump() for s in plan.steps]}
                
                Please generate a REVISED plan to achieve the original goal, starting from the failed step.
                You can modify the failed step or add new steps (e.g., 'Clean Data' before 'Train Model').
                Keep the plan concise.
                """
                
                self.log("   🔄 Requesting Plan Refinement...")
                new_plan_result = self.planner.create_plan(
                    f"Original Goal: {user_goal}. \nContext: We failed at step '{step.task}'. \nError: {log.error}. \nFix the plan.", 
                    self.planner_model,
                    stop_checker=self.stop_checker
                )
                
                new_plan = new_plan_result.get("plan") if new_plan_result else None
                if new_plan and new_plan.steps:
                    self.log(f"   ✅ Plan Refined with {len(new_plan.steps)} steps.")
                    
                    # LOGGING: Plan Refinement
                    self.performance_manager.log_performance(
                        task="Plan Refinement",
                        agent="PlannerAgent",
                        model_id=self.config.planner.model_id,
                        status="success",
                        input_context={
                            "failed_step_id": step.id,
                            "failed_step_task": step.task,
                            "error_message": log.error,
                            "current_step_index": step_idx
                        },
                        output_context={
                            "new_plan_steps": [s.model_dump() for s in new_plan.steps]
                        }
                    )

                    # Keep completed steps (0 to step_idx-1)
                    completed_steps = plan.steps[:step_idx]
                    
                    # Re-index new steps
                    last_id = completed_steps[-1].id if completed_steps else 0
                    for new_step in new_plan.steps:
                        last_id += 1
                        new_step.id = last_id
                    
                    # Update the plan
                    plan.steps = completed_steps + new_plan.steps
                    
                    # Do NOT increment step_idx, so we execute the first step of the new plan (which replaced the failed one)
                    continue
                else:
                    self.log("   ❌ Could not refine plan. Stopping.")
                    break
            else:
                self.log(f"   ✅ Step Completed")
                step.status = "completed"
                step.result = log.content or log.output # Store result in step
                
                if log.content:
                    self.log(f"   📝 Insight: {log.content[:200]}...")
                if log.output:
                    self.log(f"   💻 Output: {log.output[:200]}...")
                
                # --- Memory Update ---
                self.log(f"   🧠 Updating Memory...")
                updates = self.memory_agent.summarize_step(step, log, self.context, self.memory_model)

                # LOGGING: Memory Agent
                self.performance_manager.log_performance(
                    task="Memory Update",
                    agent="MemoryAgent",
                    model_id=self.config.analyst_agent.model_id, # Reusing analyst model
                    status="success",
                    input_context={
                        "step_task": step.task,
                        "execution_log_content": log.content,
                        "execution_log_output": log.output
                    },
                    output_context={
                        "updates": updates
                    }
                )
                
                if updates:
                    # Update shared state
                    if "new_files" in updates:
                        # VERIFICATION: Check if files actually exist
                        verified_files = []
                        for f in updates["new_files"]:
                            # Handle potential paths
                            full_path = os.path.join(self.workspace_root, f)
                            if os.path.exists(full_path):
                                verified_files.append(f)
                            else:
                                self.log(f"      ⚠️ Warning: Agent claimed to create '{f}' but it was not found.")
                        
                        updates["new_files"] = verified_files

                        for f in updates["new_files"]:
                            if f not in self.context.workspace_files:
                                self.context.workspace_files.append(f)
                                self.log(f"      + New File: {f}")
                                
                    if "metrics" in updates:
                        self.context.shared_state.update(updates["metrics"])
                        self.log(f"      + Metrics: {updates['metrics']}")
                        
                    if "task_specific_info" in updates:
                        self.context.shared_state.update(updates["task_specific_info"])
                        self.log(f"      + Info: {updates['task_specific_info']}")
                        
                    if "summary" in updates:
                        step.result = updates["summary"] # Refine step result
                        self.log(f"      + Summary: {updates['summary']}")
                
                # Periodically compress execution history to prevent unbounded growth
                if step_idx % 5 == 0 and step_idx > 0:  # Every 5 steps
                    self.context.compress_execution_history(keep_last_n=10)
                    self.log(f"   🗜️ Compressed execution history (keeping last 10 logs)")
                
                step_idx += 1
                    
        # --- Final Summary ---
        self.log("\n📊 Generating Final Summary...")
        
        # Use ReportAgent to generate intelligent, task-type-aware final report
        if not self.analyst_model:
            self.log("   ⚠️ No analyst model available for summary.")
        else:
            task_type, report_content = ReportAgent.generate_final_report(
                user_goal=user_goal,
                project_history=self.context.get_project_history(),
                model=self.analyst_model,
                logger_callback=self.log
            )
            self.log(f"\n📝 Final Report ({task_type}):\n{report_content}")

            # LOGGING: System Completion
            self.performance_manager.log_performance(
                task="System Completion",
                agent="System",
                model_id="N/A",
                status="success",
                output_context={
                    "final_report": report_content,
                    "task_type": task_type,
                    "execution_history_summary": f"{len(self.context.execution_history)} steps executed",
                    "final_shared_state": self.context.shared_state
                }
            )
                    
        self.log("\n🏁 Mission Complete!")
        
        # Flush any pending performance records
        self.performance_manager.flush()

if __name__ == "__main__":
    import argparse
    
    # Command-line argument parser
    parser = argparse.ArgumentParser(
        description="Run the AutoDS Agent System with a specified configuration file."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="agent_config_ust.yaml",
        help="Path to the YAML configuration file (default: agent_config.yaml)"
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="/Users/rk2k/Downloads/RBM/agent/autods_agent/cluster_result/cluster_ustgpt4o_research",
        help="Path to the workspace root directory"
    )
    parser.add_argument(
        "--goal",
        type=str,
        default="Need to perform clustering to summarize customer segments. Generate visualizations to illustrate the clusters and save them as PNG images. Also, generate a report summarizing the clusters and their characteristics.",
        help="The user goal/task to accomplish"
    )
    
    args = parser.parse_args()
    
    # Example usage with command-line arguments
    # python main.py --config agent_config_qwen.yaml --workspace ./workspace --goal "Your task here"
    system = AgentSystem(
        workspace_root=args.workspace,
        config_path=args.config
    )
    system.run(args.goal)