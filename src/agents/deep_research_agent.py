from typing import Any, Optional, Dict
from agno.agent import Agent
from src.utils.tools import WorkspaceTools, SearchWrapper, VisitAndSave
from src.schema.models import ExecutionLog

class DeepResearchAgent:
    """
    Performs deep research on a given topic using search and web visiting capabilities.
    """
    
    def __init__(self, workspace_tools: WorkspaceTools, enable_search: bool = True):
        """
        Initialize DeepResearchAgent.
        
        Args:
            workspace_tools: WorkspaceTools instance
            enable_search: Whether to enable search functionality
        """
        self.workspace_tools = workspace_tools
        self.enable_search = enable_search
        
        # Initialize search and visit tools
        self.search_wrapper = SearchWrapper(workspace_tools) if enable_search else None
        self.visitor = None  # Will be initialized with model when needed
    
    def initialize_visitor(self, model: Any, crawl_server_url: Optional[str] = None):
        """
        Initialize VisitAndSave with a model for web page summarization.
        
        Args:
            model: The LLM model to use for summarization
            crawl_server_url: URL of the local crawl server
        """
        self.visitor = VisitAndSave(
            workspace_tools=self.workspace_tools,
            crawl_server_url=crawl_server_url,
            model=model
        )
    
    def run(self, research_topic: str, research_plan: str, model: Any, 
            crawl_server_url: Optional[str] = None, stop_checker=None, logger=None) -> ExecutionLog:
        """
        Perform deep research on a topic.
        
        Args:
            research_topic: The main topic to research
            research_plan: Detailed research plan from planner (URLs, search queries, etc.)
            model: The LLM model to use
            crawl_server_url: URL of the local crawl server (optional)
            
        Returns:
            ExecutionLog with the research results
        """
        
        # Initialize visitor if not already done
        if self.visitor is None:
            self.initialize_visitor(model, crawl_server_url)
        
        # Build the research prompt based on research plan
        prompt = f"""You are a Deep Research Agent. Your task is to perform comprehensive research on the following topic and provide a detailed report.

Research Topic: {research_topic}

Research Plan:
{research_plan}

Instructions:
1. Use available tools (search_and_save, visit_and_save) to gather information
2. Search for relevant information and visit important websites
3. Organize findings into a comprehensive report
4. Include specific details, statistics, and insights
5. Cite sources where applicable
6. Provide clear conclusions and recommendations

Please conduct the research and provide a detailed report."""
        
        # Create an agent with search and web visiting capabilities
        tools = []
        
        if self.enable_search and self.search_wrapper:
            tools.append(lambda q: self.search_wrapper.search_and_save(q, logger=logger))
        
        if self.visitor:
            tools.append(lambda u, g, s=False, r=True, e=None: self.visitor.visit_and_save(u, g, s, r, e, logger=logger))
        
        # Create and run the research agent
        research_agent = Agent(
            name="DeepResearchAgent",
            model=model,
            tools=tools if tools else None,
            instructions=[
                "You are a thorough research expert.",
                "Use all available tools to gather comprehensive information.",
                "Organize information logically and cite sources.",
                "Provide detailed, accurate, and well-structured reports."
            ],
            markdown=True,
        )
        
        try:
            # Check for stop request before deep research
            if stop_checker and stop_checker():
                return ExecutionLog(
                    step_id=0,
                    agent="DeepResearchAgent",
                    content=prompt,
                    code="",
                    output="",
                    error="Deep research stopped by user",
                    artifacts=[]
                )
            
            response = research_agent.run(prompt)
            content = response.content
            
            # Save research results to file
            output_file = f"research_{research_topic.replace(' ', '_')}.md"
            self.workspace_tools.save_file(output_file, content)
            
            return ExecutionLog(
                step_id=0,
                agent="DeepResearchAgent",
                content=prompt,
                code="",
                output=content,
                artifacts=[output_file]
            )
        except Exception as e:
            error_msg = f"Deep research failed: {str(e)}"
            return ExecutionLog(
                step_id=0,
                agent="DeepResearchAgent",
                content=prompt,
                code="",
                output="",
                error=error_msg,
                artifacts=[]
            )
