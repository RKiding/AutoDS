import re

def extract_code_block(text: str) -> str:
    """
    Extracts Python code from a text.
    1. Looks for ```python ... ``` blocks.
    2. Looks for ``` ... ``` blocks.
    3. If neither, returns the text itself (fallback, though risky).
    """
    if "```python" in text:
        match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    if "```" in text:
        match = re.search(r"```\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
            
    return ""
