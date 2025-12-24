import os
import subprocess
import sys
import re
import time
import json
import requests
from typing import Optional, Union, List, Any, Dict

try:
    from agno.tools.duckduckgo import DuckDuckGoTools
    from agno.tools.baidusearch import BaiduSearchTools
except ImportError:
    DuckDuckGoTools = None
    BaiduSearchTools = None

# Keywords that indicate public opinion/sentiment related queries
OPINION_KEYWORDS = [
    # Chinese keywords
    "舆论", "舆情", "热搜", "热点", "热门", "新闻", "头条", "热议",
    "评论", "讨论", "争议", "风波", "事件", "动态", "趋势", "话题",
    "热度", "关注", "传闻", "报道", "消息", "最新", "实时",
    "社会", "民意", "公众", "大众", "网友", "网民", "社交媒体",
    # English keywords  
    "news", "trending", "hot", "opinion", "public", "sentiment",
    "discussion", "controversy", "event", "trend", "topic",
    "headline", "breaking", "latest", "viral", "social media",
    "public opinion", "buzz", "rumor", "report"
]

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

try:
    from src.agents.memory_agent import MemoryAgent
    from src.schema.models import Context
except ImportError:
    MemoryAgent = None
    Context = None

class WorkspaceTools:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        if not os.path.exists(self.workspace_root):
            os.makedirs(self.workspace_root)

    def _get_full_path(self, filepath: str) -> str:
        """Ensure the path is within the workspace."""
        # Simple check to prevent traversing up
        filepath = filepath.lstrip("/")
        full_path = os.path.abspath(os.path.join(self.workspace_root, filepath))
        if not full_path.startswith(self.workspace_root):
            raise ValueError(f"Access denied: {filepath} is outside workspace {self.workspace_root}")
        return full_path

    def save_file(self, filename: str, content: str) -> str:
        """Saves content to a file in the workspace."""
        try:
            full_path = self._get_full_path(filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            return f"Successfully saved file: {filename}"
        except Exception as e:
            return f"Error saving file {filename}: {str(e)}"

    def read_file(self, filename: str) -> str:
        """Reads content from a file in the workspace."""
        try:
            full_path = self._get_full_path(filename)
            if not os.path.exists(full_path):
                return f"Error: File {filename} does not exist."
            with open(full_path, "r") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {filename}: {str(e)}"

    def read_file_head(self, filename: str, n_lines: int = 5) -> str:
        """Reads the first n lines of a file."""
        try:
            full_path = self._get_full_path(filename)
            if not os.path.exists(full_path):
                return f"Error: File {filename} does not exist."
            
            lines = []
            with open(full_path, "r") as f:
                for _ in range(n_lines):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line.strip())
            return "\n".join(lines)
        except Exception as e:
            return f"Error reading file head {filename}: {str(e)}"

    def get_csv_summaries(self) -> tuple[str, list]:
        """
        Get summaries of all CSV files in workspace.
        Returns: (file_summaries_string, csv_files_list)
        Prevents duplicate code across agents.
        """
        try:
            current_files = self.list_files()
            file_summaries = ""
            csv_files = []
            
            if "Workspace is empty" not in current_files:
                for f in current_files.split("\n"):
                    f = f.strip()
                    if f.endswith(".csv"):
                        csv_files.append(f)
                        head = self.read_file_head(f)
                        file_summaries += f"\n--- {f} (First 5 lines) ---\n{head}\n"
            
            return file_summaries, csv_files
        except Exception as e:
            return f"Error getting CSV summaries: {str(e)}", []

    def list_files(self) -> str:
        """Lists files in the workspace."""
        try:
            files = []
            for root, _, filenames in os.walk(self.workspace_root):
                for filename in filenames:
                    rel_path = os.path.relpath(os.path.join(root, filename), self.workspace_root)
                    files.append(rel_path)
            return "\n".join(files) if files else "Workspace is empty."
        except Exception as e:
            return f"Error listing files: {str(e)}"

    def install_package(self, package_name: str) -> str:
        """Installs a python package using pip."""
        try:
            print(f"📦 Installing package: {package_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            return f"Successfully installed {package_name}"
        except subprocess.CalledProcessError as e:
            return f"Error installing {package_name}: {str(e)}"
        except Exception as e:
            return f"Error installing {package_name}: {str(e)}"

    def execute_python(self, code: str, filename: Optional[str] = None) -> str:
        """
        Executes Python code. 
        If filename is provided, saves code to file first then runs it.
        Otherwise runs as a script via -c.
        Automatically attempts to install missing packages.
        """
        try:
            if filename:
                save_msg = self.save_file(filename, code)
                if "Error" in save_msg:
                    return save_msg
                script_path = self._get_full_path(filename)
                cmd = [sys.executable, script_path]
            else:
                cmd = [sys.executable, "-c", code]

            # Run in the workspace directory
            result = subprocess.run(
                cmd, 
                cwd=self.workspace_root, 
                capture_output=True, 
                text=True, 
                timeout=60 # 1 minute timeout
            )
            
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            
            # Check for ModuleNotFoundError
            if "ModuleNotFoundError" in output:
                match = re.search(r"ModuleNotFoundError: No module named '(.*?)'", output)
                if match:
                    missing_module = match.group(1)
                    # Try to install
                    install_msg = self.install_package(missing_module)
                    output += f"\n--- Auto-Install Attempt ---\n{install_msg}\n"
                    
                    if "Successfully installed" in install_msg:
                        output += "Retrying execution...\n"
                        # Retry execution
                        result_retry = subprocess.run(
                            cmd, 
                            cwd=self.workspace_root, 
                            capture_output=True, 
                            text=True, 
                            timeout=60
                        )
                        if result_retry.stdout:
                            output += f"RETRY STDOUT:\n{result_retry.stdout}\n"
                        if result_retry.stderr:
                            output += f"RETRY STDERR:\n{result_retry.stderr}\n"
            
            if not output:
                output = "Code executed successfully with no output."
                
            return output
        except subprocess.TimeoutExpired:
            return "Error: Code execution timed out (60s)."
        except Exception as e:
            return f"Error executing code: {str(e)}"

class SearchWrapper:
    def __init__(self, workspace_tools: WorkspaceTools):
        self.workspace_tools = workspace_tools
        self.ddg_tool = DuckDuckGoTools() if DuckDuckGoTools else None
        self.baidu_tool = BaiduSearchTools() if BaiduSearchTools else None

    def search_and_save(self, query: str) -> str:
        """
        Searches the web using DuckDuckGo and saves the raw results to a file.
        Use this for general English or international queries.
        
        Args:
            query (str): The search query.
            
        Returns:
            str: Search results and the filename where they are saved.
        """
        if not self.ddg_tool:
            return "Error: DuckDuckGoTools not available."
        return self._perform_search(self.ddg_tool.duckduckgo_search, "ddg", query)

    def search_baidu_and_save(self, query: str) -> str:
        """
        Searches the web using Baidu and saves the raw results to a file.
        Use this for Chinese-specific queries or when looking for information in China.
        
        Args:
            query (str): The search query in Chinese.
            
        Returns:
            str: Search results and the filename where they are saved.
        """
        if not self.baidu_tool:
            return "Error: BaiduSearchTools not available."
        return self._perform_search(self.baidu_tool.baidu_search, "baidu", query)

    def _perform_search(self, search_func, engine_name, query) -> str:
        # Handle both string and list inputs
        queries = query if isinstance(query, list) else [query]
        
        all_results = []
        all_filenames = []
        
        # Perform searches for each query
        for idx, q in enumerate(queries):
            # Add delay between requests to avoid rate limiting
            if idx > 0:
                wait_time = 2
                print(f"Waiting {wait_time}s before next search...")
                time.sleep(wait_time)
            
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    print(f"Searching {engine_name} for: '{q}' (attempt {retry_count + 1}/{max_retries})")
                    
                    results = search_func(q)
                    all_results.append(f"=== {engine_name.upper()} Results for '{q}' ===\n{results}\n")
                    
                    # Create filename
                    sanitized_query = "".join(c for c in q if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')[:30]
                    filename = f"tmp/search_{engine_name}_{sanitized_query}_{int(time.time())}.txt"
                    
                    # Save to workspace
                    self.workspace_tools.save_file(filename, str(results))
                    all_filenames.append(filename)
                    success = True
                    print(f"✓ {engine_name.upper()} Search successful for '{q}'")
                    
                except Exception as e:
                    retry_count += 1
                    error_str = str(e).lower()
                    is_rate_limit = any(keyword in error_str for keyword in ['rate', 'timeout', 'connection', 'no results'])
                    
                    if is_rate_limit and retry_count < max_retries:
                        wait_time = 3 ** retry_count
                        print(f"⚠️  Rate limit/timeout. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        error_msg = f"=== {engine_name.upper()} Results for '{q}' ===\nError: {str(e)}\n"
                        all_results.append(error_msg)
                        filename = f"tmp/search_{engine_name}_{int(time.time())}_error.txt"
                        self.workspace_tools.save_file(filename, error_msg)
                        all_filenames.append(filename)
                        success = True
        
        combined_results = "\n".join(all_results)
        filenames_str = ", ".join(all_filenames)
        
        if not all_filenames:
            return f"Error: No {engine_name} search results could be retrieved."
        
        return f"{engine_name.upper()} Search results saved to '{filenames_str}'.\n\nResults:\n{combined_results}"


class NewsNowWrapper:
    """
    Wrapper for NewsNow API to fetch trending news from various sources.
    Used when queries involve public opinion, trending topics, or news-related content.
    
    Available sources include:
    - weibo: 微博热搜
    - zhihu: 知乎热榜
    - baidu: 百度热搜
    - toutiao: 今日头条
    - douyin: 抖音热搜
    - bilibili: B站热门
    - kr36: 36氪
    - ithome: IT之家
    - thepaper: 澎湃新闻
    - hackernews: Hacker News
    - producthunt: Product Hunt
    - github: GitHub Trending
    And 30+ more sources...
    """
    
    # Default news sources to query
    DEFAULT_SOURCES = ["weibo", "zhihu", "baidu", "toutiao"]
    
    # Available news sources with descriptions
    AVAILABLE_SOURCES = {
        # Chinese sources
        "weibo": "微博热搜 - Weibo Hot Search",
        "zhihu": "知乎热榜 - Zhihu Hot List",
        "baidu": "百度热搜 - Baidu Hot Search",
        "toutiao": "今日头条 - Toutiao Headlines",
        "douyin": "抖音热搜 - Douyin Hot Search",
        "bilibili": "B站热门 - Bilibili Trending",
        "thepaper": "澎湃新闻 - The Paper",
        "36kr": "36氪 - 36Kr News",
        "ithome": "IT之家 - IT Home",
        "wallstreetcn": "华尔街见闻 - Wall Street CN",
        "cls": "财联社 - CLS News",
        "caixin": "财新网 - Caixin",
        "yicai": "第一财经 - Yicai",
        "sina-finance": "新浪财经 - Sina Finance",
        "eastmoney": "东方财富 - East Money",
        "stockstar": "证券之星 - Stock Star",
        "jiemian": "界面新闻 - Jiemian",
        "ifeng": "凤凰新闻 - iFeng News",
        "netease": "网易新闻 - NetEase News",
        "qq": "腾讯新闻 - QQ News",
        "163": "网易热榜 - NetEase Hot",
        "weread": "微信读书 - WeRead",
        "sspai": "少数派 - SSPai",
        "coolapk": "酷安热榜 - Coolapk",
        "hupu": "虎扑热搜 - Hupu",
        "tieba": "百度贴吧 - Tieba",
        "douban-movie": "豆瓣电影 - Douban Movie",
        "douban-group": "豆瓣小组 - Douban Group",
        # Tech sources
        "hackernews": "Hacker News - Tech News",
        "producthunt": "Product Hunt - New Products",
        "github": "GitHub Trending - Open Source",
        "v2ex": "V2EX - Tech Forum",
        "juejin": "掘金 - Tech Articles",
        "csdn": "CSDN - IT Community",
        "oschina": "开源中国 - OSChina",
        "segmentfault": "思否 - SegmentFault",
        "infoq": "InfoQ - Software Dev",
    }
    
    def __init__(self, workspace_tools: WorkspaceTools, 
                 base_url: str = "https://newsnow.busiyi.world"):
        """
        Initialize NewsNowWrapper.
        
        Args:
            workspace_tools: WorkspaceTools instance for file operations
            base_url: Base URL for NewsNow API
        """
        self.workspace_tools = workspace_tools
        self.base_url = base_url or os.getenv("NEWSNOW_BASE_URL", "https://newsnow.busiyi.world")
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    
    @staticmethod
    def is_opinion_related(query: str) -> bool:
        """
        Check if a query is related to public opinion/sentiment/news.
        
        Args:
            query: The search query
            
        Returns:
            bool: True if the query is opinion-related
        """
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in OPINION_KEYWORDS)
    
    def get_news(self, source_id: str, count: int = 10, logger=None) -> Dict:
        """
        Get news from a specific source.
        
        Args:
            source_id: The news source ID (e.g., 'weibo', 'zhihu')
            count: Number of news items to return
            logger: Optional logger function
            
        Returns:
            dict: News items with title and url
        """
        try:
            msg = f"📰 Fetching news from {source_id}..."
            if logger: logger(msg)
            else: print(msg)
            
            response = requests.get(
                f"{self.base_url}/api/s",
                params={"id": source_id},
                headers={"User-Agent": self.user_agent},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])[:count]
                
                result = {
                    "source": source_id,
                    "source_name": self.AVAILABLE_SOURCES.get(source_id, source_id),
                    "status": data.get("status", "unknown"),
                    "updated_time": data.get("updatedTime"),
                    "items": [
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "extra": item.get("extra", {})
                        }
                        for item in items
                    ]
                }
                
                msg = f"✓ Got {len(result['items'])} news items from {source_id}"
                if logger: logger(msg)
                else: print(msg)
                
                return result
            else:
                error_msg = f"API error: {response.status_code}"
                if logger: logger(f"❌ {error_msg}")
                else: print(f"❌ {error_msg}")
                return {"source": source_id, "error": error_msg, "items": []}
                
        except Exception as e:
            error_msg = f"Failed to fetch news from {source_id}: {str(e)}"
            if logger: logger(f"❌ {error_msg}")
            else: print(f"❌ {error_msg}")
            return {"source": source_id, "error": error_msg, "items": []}
    
    def get_hot_topics_and_save(self, sources: Optional[List[str]] = None, 
                               count_per_source: int = 10, logger=None) -> str:
        """
        Fetch trending/hot topics across multiple sources and save results.
        Use this when you need to know what's currently trending or popular on social media/news sites.
        
        Args:
            sources: List of source IDs to query (defaults to DEFAULT_SOURCES)
            count_per_source: Number of items per source
            logger: Optional logger function
            
        Returns:
            str: Formatted hot topics and saved file info
        """
        sources = sources or self.DEFAULT_SOURCES
        
        msg = f"🔍 Fetching hot topics from {len(sources)} sources"
        if logger: logger(msg)
        else: print(msg)
        
        all_results = []
        all_items = []
        
        for source in sources:
            # Add delay between requests
            if all_results:
                time.sleep(0.5)
            
            result = self.get_news(source, count_per_source, logger=logger)
            all_results.append(result)
            
            if result.get("items"):
                all_items.extend([
                    {**item, "source": source, "source_name": result.get("source_name", source)}
                    for item in result["items"]
                ])
        
        # Format results
        formatted_output = f"=== NewsNow Hot Topics ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n"
        formatted_output += f"Sources: {', '.join(sources)}\n"
        formatted_output += f"Total items found: {len(all_items)}\n\n"
        
        for result in all_results:
            source_name = result.get("source_name", result.get("source", "Unknown"))
            formatted_output += f"\n--- {source_name} ---\n"
            
            if result.get("error"):
                formatted_output += f"Error: {result['error']}\n"
            else:
                for i, item in enumerate(result.get("items", []), 1):
                    title = item.get("title", "No title")
                    url = item.get("url", "")
                    extra = item.get("extra", {})
                    info = extra.get("info", "") if isinstance(extra, dict) else ""
                    
                    formatted_output += f"{i}. {title}"
                    if info:
                        formatted_output += f" ({info})"
                    if url:
                        formatted_output += f"\n   URL: {url}"
                    formatted_output += "\n"
        
        # Save results to file
        filename = f"tmp/hot_topics_{int(time.time())}.txt"
        
        self.workspace_tools.save_file(filename, formatted_output)
        
        msg = f"✓ Hot topics saved to {filename}"
        if logger: logger(msg)
        else: print(msg)
        
        return f"Hot topics saved to '{filename}'.\n\n{formatted_output}"
    
    def list_available_sources(self) -> str:
        """
        List all available news sources.
        
        Returns:
            str: Formatted list of available sources
        """
        output = "=== Available NewsNow Sources ===\n\n"
        for source_id, description in self.AVAILABLE_SOURCES.items():
            output += f"- {source_id}: {description}\n"
        return output


class VisitAndSave:
    """Visits webpages and saves their content, with optional summarization using LLM."""
    
    def __init__(self, workspace_tools: WorkspaceTools, jina_api_key: Optional[str] = None, 
                 llm_config: Optional[dict] = None, crawl_server_url: Optional[str] = None,
                 model: Optional[Any] = None):
        """
        Initialize VisitAndSave.
        
        Args:
            workspace_tools: WorkspaceTools instance for file operations
            jina_api_key: API key for Jina service (optional)
            llm_config: LLM configuration with 'api_key', 'base_url', 'model' keys (optional)
            crawl_server_url: URL of local crawl server (optional)
            model: LLM model instance for MemoryAgent (optional)
        """
        self.workspace_tools = workspace_tools
        self.jina_api_key = jina_api_key or os.getenv("JINA_API_KEYS", "")
        self.crawl_server_url = crawl_server_url or os.getenv("CRAWL_SERVER_URL", "")
        self.llm_config = llm_config or {
            "api_key": os.getenv("API_KEY"),
            "base_url": os.getenv("API_BASE"),
            "model": os.getenv("SUMMARY_MODEL_NAME", "")
        }
        self.visit_timeout = int(os.getenv("VISIT_SERVER_TIMEOUT", 200))
        self.max_content_length = int(os.getenv("WEBCONTENT_MAXLENGTH", 150000))
        
        # Initialize MemoryAgent for content summarization
        self.model = model
        self.memory_agent = MemoryAgent() if MemoryAgent else None

    @staticmethod
    def truncate_to_tokens(text: str, max_tokens: int = 95000) -> str:
        """Truncate text to maximum tokens using tiktoken."""
        if tiktoken is None:
            # Fallback: estimate 1 token ≈ 4 characters
            max_chars = max_tokens * 4
            return text[:max_chars]
        
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            tokens = encoding.encode(text)
            if len(tokens) <= max_tokens:
                return text
            truncated_tokens = tokens[:max_tokens]
            return encoding.decode(truncated_tokens)
        except Exception as e:
            print(f"Warning: Token truncation failed: {e}, using character-based truncation")
            max_chars = max_tokens * 4
            return text[:max_chars]

    def crawl_server_readpage(self, url: str, excluded_tags: Optional[List[str]] = None) -> str:
        """
        Read webpage content using local crawl server.
        
        Args:
            url: The URL to read
            excluded_tags: HTML tags to exclude (e.g., ["nav", "footer", "aside", "ads"])
            
        Returns:
            str: The webpage content (markdown format) or error message
        """
        if not self.crawl_server_url:
            return "[visit] Crawl server URL not configured."
        
        max_retries = 3
        timeout = 60
        excluded_tags = excluded_tags or ["nav", "footer", "aside", "ads"]
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.crawl_server_url}/crawl/clean",
                    json={
                        "url": url,
                        "excluded_tags": excluded_tags
                    },
                    timeout=timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    markdown_content = data.get('markdown', '')
                    if markdown_content:
                        return markdown_content
                    else:
                        raise ValueError("Empty markdown content from crawl server")
                else:
                    print(f"Crawl server error: {response.status_code} - {response.text}")
                    raise ValueError(f"Crawl server error: {response.status_code}")
            except Exception as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                time.sleep(1)
                if attempt == max_retries - 1:
                    return "[visit] Failed to read page via crawl server."
        
        return "[visit] Failed to read page via crawl server."

    def jina_readpage(self, url: str) -> str:
        """
        Read webpage content using Jina service.
        
        Args:
            url: The URL to read
            
        Returns:
            str: The webpage content or error message
        """
        if not self.jina_api_key:
            return "[visit] Jina API key not configured."
        
        max_retries = 3
        timeout = 50
        
        for attempt in range(max_retries):
            headers = {
                "Authorization": f"Bearer {self.jina_api_key}",
            }
            try:
                response = requests.get(
                    f"https://r.jina.ai/{url}",
                    headers=headers,
                    timeout=timeout
                )
                if response.status_code == 200:
                    webpage_content = response.text
                    return webpage_content
                else:
                    print(f"Jina API error: {response.status_code} - {response.text}")
                    raise ValueError("jina readpage error")
            except Exception as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                time.sleep(0.5)
                if attempt == max_retries - 1:
                    return "[visit] Failed to read page."
        
        return "[visit] Failed to read page."

    def html_readpage_auto(self, url: str, excluded_tags: Optional[List[str]] = None) -> str:
        """
        Automatically select the best available method to read webpage.
        Priority: crawl_server > jina
        
        Args:
            url: The URL to read
            excluded_tags: HTML tags to exclude for crawl server
            
        Returns:
            str: The webpage content or error message
        """
        # Try crawl server first if available
        if self.crawl_server_url:
            print(f"Attempting to read {url} via crawl server...")
            content = self.crawl_server_readpage(url, excluded_tags)
            if content and not content.startswith("[visit]"):
                return content
        
        # Fallback to Jina if available
        if self.jina_api_key:
            print(f"Attempting to read {url} via Jina API...")
            content = self.html_readpage_jina(url)
            if content and not content.startswith("[visit]"):
                return content
        
        return "[visit] No webpage reading service available. Configure CRAWL_SERVER_URL or JINA_API_KEYS."

    def html_readpage_jina(self, url: str) -> str:
        """Attempt to read webpage with Jina with multiple retries."""
        max_attempts = 8
        for attempt in range(max_attempts):
            content = self.jina_readpage(url)
            if content and not content.startswith("[visit]"):
                return content
            print(f"Retry {attempt + 1}/{max_attempts} for {url}")
        return "[visit] Failed to read page."

    def call_llm_summarize(self, messages: list, max_retries: int = 2) -> str:
        """
        Call LLM to summarize/extract content.
        
        Args:
            messages: Chat messages for the LLM
            max_retries: Maximum retry attempts
            
        Returns:
            str: LLM response or empty string on failure
        """
        if not self.llm_config.get("api_key") or OpenAI is None:
            return ""
        
        try:
            client = OpenAI(
                api_key=self.llm_config["api_key"],
                base_url=self.llm_config.get("base_url"),
            )
            for attempt in range(max_retries):
                try:
                    chat_response = client.chat.completions.create(
                        model=self.llm_config["model"],
                        messages=messages,
                        temperature=0.7
                    )
                    content = chat_response.choices[0].message.content
                    if content:
                        return content
                except Exception as e:
                    print(f"LLM attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        return ""
                    time.sleep(1)
            return ""
        except Exception as e:
            print(f"LLM call error: {str(e)}")
            return ""

    def visit_and_save(self, url: Union[str, List[str]], goal: str, 
                       summarize: bool = False, save_raw: bool = True, 
                       excluded_tags: Optional[List[str]] = None, logger=None) -> dict:
        """
        Visit webpage(s) and save content.
        
        Args:
            url: Single URL or list of URLs to visit
            goal: The goal/purpose of visiting
            summarize: Whether to summarize content using LLM
            save_raw: Whether to save raw webpage content
            excluded_tags: HTML tags to exclude for crawl server
            
        Returns:
            dict: Results with keys 'urls', 'saved_files', 'contents', 'summary'
        """
        urls = [url] if isinstance(url, str) else url
        results = {
            "urls": urls,
            "saved_files": [],
            "contents": [],
            "summaries": [],
            "errors": []
        }
        
        for idx, u in enumerate(urls):
            try:
                msg = f"\n[{idx + 1}/{len(urls)}] Visiting {u}..."
                if logger: logger(msg)
                else: print(msg)
                
                # Read webpage content using best available method
                content = self.html_readpage_auto(u, excluded_tags)
                
                if content.startswith("[visit]"):
                    results["errors"].append({"url": u, "error": content})
                    msg = f"❌ Failed to read {u}: {content}"
                    if logger: logger(msg)
                    else: print(msg)
                    continue
                
                # Truncate content to token limit
                original_length = len(content)
                content = self.truncate_to_tokens(content, max_tokens=95000)
                msg = f"✓ Content retrieved: {original_length} chars -> {len(content)} chars (after truncation)"
                if logger: logger(msg)
                else: print(msg)
                results["contents"].append(content)
                
                # Save raw content if requested
                saved_file = None
                if save_raw:
                    filename = f"visit_data/raw_{int(time.time())}_{idx}.txt"
                    save_result = self.workspace_tools.save_file(filename, content)
                    if "Successfully" in save_result:
                        saved_file = filename
                        results["saved_files"].append(filename)
                        print(f"✓ Raw content saved to {filename}")
                
                # Summarize content if requested
                if summarize:
                    msg = f"Summarizing content for {u}..."
                    if logger: logger(msg)
                    else: print(msg)
                    summary = self._summarize_content(content, goal)
                    results["summaries"].append({
                        "url": u,
                        "summary": summary
                    })
                    
                    # Save summary
                    if saved_file:
                        summary_file = saved_file.replace("raw_", "summary_").replace(".txt", "_summary.txt")
                        self.workspace_tools.save_file(summary_file, summary)
                        print(f"✓ Summary saved to {summary_file}")
                        results["saved_files"].append(summary_file)
                
            except Exception as e:
                results["errors"].append({"url": u, "error": str(e)})
                print(f"❌ Error processing {u}: {str(e)}")
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Summary: {len(urls) - len(results['errors'])} success, {len(results['errors'])} failed")
        print(f"Files saved: {len(results['saved_files'])}")
        print(f"{'='*60}")
        
        return results

    def _summarize_content(self, content: str, goal: str) -> str:
        """
        Summarize content using MemoryAgent's summary_page method.
        
        Args:
            content: Webpage content to summarize
            goal: The goal for summarization
            
        Returns:
            str: Summarized/extracted content
        """
        # Fallback to LLM if MemoryAgent is not available
        if not self.memory_agent or not self.model:
            print("⚠️ MemoryAgent not available, falling back to direct LLM call")
            return self._summarize_content_fallback(content, goal)
        
        try:
            # Create context for MemoryAgent
            context = Context(
                user_goal=goal,
                workspace_root=self.workspace_tools.workspace_root,
                shared_state={"goal": goal, "content_length": len(content)}
            )
            
            # Use MemoryAgent's summary_page method to extract and summarize
            result = self.memory_agent.summary_page(content, goal, context, self.model)
            
            # Format the result
            if isinstance(result, dict):
                rational = result.get("rational", "")
                evidence = result.get("evidence", "")
                summary = result.get("summary", "")
                task_info = result.get("task_specific_info", {})
                
                # Build formatted output
                output = f"Rational: {rational}\n\n"
                output += f"Evidence: {evidence}\n\n"
                output += f"Summary: {summary}\n\n"
                
                # Add task-specific info if available
                if task_info:
                    output += f"Key Topics: {', '.join(task_info.get('key_topics', []))}\n"
                    output += f"Key Entities: {', '.join(task_info.get('key_entities', []))}\n"
                
                return output
            else:
                return str(result)
                
        except Exception as e:
            print(f"⚠️ MemoryAgent summary_page error: {e}, falling back to direct LLM")
            return self._summarize_content_fallback(content, goal)
    
    def _summarize_content_fallback(self, content: str, goal: str) -> str:
        """
        Fallback: return the original content when MemoryAgent is not available.
        
        Args:
            content: Webpage content
            goal: The goal for summarization (unused in fallback)
            
        Returns:
            str: The original content as-is
        """
        print("⚠️ Returning original content (MemoryAgent not available)")
        return content

    def visit_and_save_batch(self, urls: List[str], goal: str, 
                            summarize: bool = True) -> dict:
        """
        Visit multiple URLs and save all results in one operation.
        
        Args:
            urls: List of URLs to visit
            goal: The goal/purpose of visiting
            summarize: Whether to summarize content
            
        Returns:
            dict: Combined results from all visits
        """
        return self.visit_and_save(urls, goal, summarize=summarize, save_raw=True)
