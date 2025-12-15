import os
import yaml
from typing import Dict, Any, List
from pydantic import BaseModel

class ModelConfig(BaseModel):
    provider: str
    model_id: str
    host: str = ""
    api_key: str = ""
    
    def to_kwargs(self) -> Dict[str, Any]:
        kwargs = {}
        # Only use host for ollama provider
        if self.host and self.provider == "ollama":
            kwargs["host"] = self.host
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return kwargs

class AgentSettings(ModelConfig):
    available_models: List[ModelConfig] = []

class AgentConfig(BaseModel):
    planner: AgentSettings
    deep_research_planner: AgentSettings = None  # Specialized planner for deep research
    selector: AgentSettings
    code_agent: AgentSettings
    analyst_agent: AgentSettings
    enable_search_tool: bool = False
    enable_hitl: bool = False
    enable_simple_task_check: bool = False
    enable_deep_research: bool = False
    deep_research_use_simple_goal: bool = False  # If True, use simple goal sentence; if False, generate detailed plan
    crawler: Dict[str, Any] = {}  # Configuration for crawler server

def load_agent_config(path: str = "agent_config.yaml") -> AgentConfig:
    """
    Loads agent configuration from a YAML file.
    Falls back to defaults if file is missing or incomplete.
    """
    # Default settings
    default_settings = {
        "provider": "ollama",
        "model_id": "qwen2.5:7b",
        "host": "http://localhost:11434"
    }

    if not os.path.exists(path):
        print(f"⚠️ Config file '{path}' not found. Using defaults.")
        default_model = AgentSettings(**default_settings)
        return AgentConfig(
            planner=default_model,
            selector=default_model,
            code_agent=default_model,
            analyst_agent=default_model,
            deep_research_use_simple_goal=False
        )
    
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
            
        defaults = data.get("defaults", default_settings)
        agents = data.get("agents", {})
        
        def get_settings(agent_name: str) -> AgentSettings:
            # Start with defaults
            config = defaults.copy()
            # Update with agent specific config
            if agent_name in agents and agents[agent_name]:
                config.update(agents[agent_name])
            
            # Ensure available_models inherit defaults (like host) if not specified
            if "available_models" in config and isinstance(config["available_models"], list):
                default_host = config.get("host", "")
                default_api_key = config.get("api_key", "")
                default_provider = config.get("provider", "")
                
                for model_cfg in config["available_models"]:
                    if isinstance(model_cfg, dict):
                        # Only inherit host if provider is ollama
                        model_provider = model_cfg.get("provider", default_provider)
                        if "host" not in model_cfg and default_host and model_provider == "ollama":
                            model_cfg["host"] = default_host
                        if "api_key" not in model_cfg and default_api_key:
                            model_cfg["api_key"] = default_api_key
                        if "provider" not in model_cfg and default_provider:
                            model_cfg["provider"] = default_provider

            return AgentSettings(**config)
            
        return AgentConfig(
            planner=get_settings("planner"),
            deep_research_planner=get_settings("deep_research_planner") if "deep_research_planner" in agents else None,
            selector=get_settings("selector"),
            code_agent=get_settings("code_agent"),
            analyst_agent=get_settings("analyst_agent"),
            enable_search_tool=data.get("enable_search_tool", False),
            enable_hitl=data.get("enable_hitl", False),
            enable_simple_task_check=data.get("enable_simple_task_check", False),
            enable_deep_research=data.get("enable_deep_research", False),
            deep_research_use_simple_goal=data.get("deep_research_use_simple_goal", False),
            crawler=data.get("crawler", {})
        )
        
    except Exception as e:
        print(f"❌ Error loading config: {e}. Using defaults.")
        default_model = AgentSettings(**default_settings)
        return AgentConfig(
            planner=default_model,
            selector=default_model,
            code_agent=default_model,
            analyst_agent=default_model,
            deep_research_use_simple_goal=False
        )
