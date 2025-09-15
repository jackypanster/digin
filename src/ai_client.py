"""AI 客戶端封裝（Claude/Gemini）- 簡化版。

職責：
- 讀取 prompt.txt 模板，拼裝目錄文件列表、代碼片段與子摘要
- 調用對應 CLI（claude/gemini），失敗時直接拋出異常
- 解析 JSON 響應，添加元數據

設計原則：快速失敗，移除不必要的抽象層
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .__version__ import __version__
from .config import DigginSettings
from .logger import get_logger, log_ai_command


def load_prompt_template() -> str:
    """Load prompt template from file."""
    prompt_path = Path(__file__).parent.parent / "config" / "prompt.txt"
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    # Fallback basic prompt
    return """請分析以下目錄並以JSON格式輸出：

目錄路徑: {directory_path}
文件列表: {file_list}
代碼片段: {code_snippets}
子目錄摘要: {children_digests}

輸出JSON格式包含：
- name: 目錄名稱
- path: 路徑
- kind: 類型 (service|lib|ui|infra|config|test|docs|unknown)
- summary: 功能概述
- capabilities: 能力列表
- confidence: 置信度 (0-100)

請只輸出JSON，無其他文字："""


def build_prompt(template: str, directory_info: Dict[str, Any], children_digests: List[Dict[str, Any]]) -> str:
    """Build analysis prompt from template."""
    file_list_str = format_file_list(directory_info.get("files", []))
    code_snippets_str = format_code_snippets(directory_info.get("files", []))
    children_digests_str = format_children_digests(children_digests)

    return template.format(
        directory_path=directory_info.get("path", ""),
        file_list=file_list_str,
        code_snippets=code_snippets_str,
        children_digests=children_digests_str,
    )


def format_file_list(files: List[Dict[str, Any]]) -> str:
    """Format file list for prompt."""
    if not files:
        return "无直接文件"

    file_list = []
    for file_info in files:
        extension = file_info.get("extension", "")
        size = file_info.get("size", 0)
        file_list.append(f"- {file_info['name']} ({extension}, {size} bytes)")

    return "\n".join(file_list)


def format_code_snippets(files: List[Dict[str, Any]]) -> str:
    """Format code snippets for prompt."""
    code_snippets = []

    # Include up to 20 files with content
    files_with_content = [f for f in files if "content_preview" in f]
    max_files = min(20, len(files_with_content))

    for file_info in files_with_content[:max_files]:
        content = file_info["content_preview"]
        file_ext = file_info.get("extension", "")

        # Add language hint for syntax highlighting
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.rs': 'rust',
            '.go': 'go', '.rb': 'ruby', '.php': 'php', '.cs': 'csharp',
            '.vue': 'vue', '.jsx': 'jsx', '.tsx': 'tsx', '.sql': 'sql',
            '.sh': 'bash', '.yml': 'yaml', '.yaml': 'yaml', '.json': 'json',
            '.xml': 'xml', '.html': 'html', '.css': 'css', '.scss': 'scss',
            '.md': 'markdown', '.dockerfile': 'dockerfile', '.tf': 'terraform'
        }
        lang = lang_map.get(file_ext.lower(), '')

        code_snippets.append(
            f"**{file_info['name']}** ({file_info.get('size', 0)} bytes):\n```{lang}\n{content}\n```"
        )

    if not code_snippets:
        return "无代码内容或所有文件都是二进制文件"

    return "\n\n".join(code_snippets)


def format_children_digests(children_digests: List[Dict[str, Any]]) -> str:
    """Format children digests for prompt."""
    if not children_digests:
        return "无子目录（叶子目录）"

    children_summaries = []
    for child in children_digests:
        summary = f"- {child.get('name', '未知')}: {child.get('summary', '无摘要')}"
        children_summaries.append(summary)

    return "\n".join(children_summaries)


def parse_json_response(response: str) -> Dict[str, Any]:
    """Parse AI response as JSON - fail fast on errors."""
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from response text
        lines = response.split("\n")
        json_lines = []
        in_json = False
        brace_count = 0

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("{"):
                in_json = True
                json_lines.append(line)
                brace_count += line.count("{") - line.count("}")
            elif in_json:
                json_lines.append(line)
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    break

        if json_lines:
            json_str = "\n".join(json_lines)
            return json.loads(json_str)

        # If we can't parse JSON, this is a failure
        raise ValueError(f"Failed to parse AI response as JSON: {response[:500]}...")


def call_claude_cli(prompt: str, api_options: Dict[str, Any], directory: str = "") -> str:
    """Call Claude CLI with prompt."""
    cmd = ["claude", "--print"]

    if "append_system_prompt" in api_options:
        cmd.extend(["--append-system-prompt", api_options["append_system_prompt"]])

    if "model" in api_options:
        model = api_options["model"]
        # Map common model names to valid Claude CLI model names
        if model == "claude-3-sonnet":
            model = "sonnet"
        elif model == "claude-3-opus":
            model = "opus"
        elif model == "claude-3-haiku":
            model = "haiku"
        cmd.extend(["--model", model])

    start_time = time.time()
    logger = get_logger("ai_client")
    logger.info(f"Starting Claude CLI call for directory: {directory}")

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        response = result.stdout.strip()

        # Log successful command
        log_ai_command(
            provider="claude",
            command=cmd,
            prompt_size=len(prompt),
            directory=directory,
            start_time=start_time,
            success=True,
            response_size=len(response),
            error_msg="",
            prompt=prompt,
        )

        logger.info(f"Claude CLI call completed successfully for: {directory}")
        return response

    except subprocess.TimeoutExpired:
        error_msg = "Claude CLI timed out"
        log_ai_command(
            provider="claude",
            command=cmd,
            prompt_size=len(prompt),
            directory=directory,
            start_time=start_time,
            success=False,
            response_size=0,
            error_msg=error_msg,
            prompt=prompt,
        )
        raise RuntimeError(error_msg)

    except Exception as e:
        error_msg = str(e)
        log_ai_command(
            provider="claude",
            command=cmd,
            prompt_size=len(prompt),
            directory=directory,
            start_time=start_time,
            success=False,
            response_size=0,
            error_msg=error_msg,
            prompt=prompt,
        )
        logger.error(f"Claude CLI call failed for: {directory} - {error_msg}")
        raise


def call_gemini_cli(prompt: str, api_options: Dict[str, Any], directory: str = "") -> str:
    """Call Gemini CLI with prompt."""
    cmd = ["gemini"]

    if "model" in api_options:
        cmd.extend(["-m", api_options["model"]])

    cmd.extend(["-p", prompt])

    start_time = time.time()
    logger = get_logger("ai_client")
    logger.info(f"Starting Gemini CLI call for directory: {directory}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            raise RuntimeError(f"Gemini CLI failed: {result.stderr}")

        response = result.stdout.strip()

        # Log successful command
        log_ai_command(
            provider="gemini",
            command=cmd,
            prompt_size=len(prompt),
            directory=directory,
            start_time=start_time,
            success=True,
            response_size=len(response),
            error_msg="",
            prompt=prompt,
        )

        logger.info(f"Gemini CLI call completed successfully for: {directory}")
        return response

    except subprocess.TimeoutExpired:
        error_msg = "Gemini CLI timed out"
        log_ai_command(
            provider="gemini",
            command=cmd,
            prompt_size=len(prompt),
            directory=directory,
            start_time=start_time,
            success=False,
            response_size=0,
            error_msg=error_msg,
            prompt=prompt,
        )
        raise RuntimeError(error_msg)

    except Exception as e:
        error_msg = str(e)
        log_ai_command(
            provider="gemini",
            command=cmd,
            prompt_size=len(prompt),
            directory=directory,
            start_time=start_time,
            success=False,
            response_size=0,
            error_msg=error_msg,
            prompt=prompt,
        )
        logger.error(f"Gemini CLI call failed for: {directory} - {error_msg}")
        raise


def is_cli_available(provider: str) -> bool:
    """Check if AI CLI tool is available."""
    try:
        result = subprocess.run(
            [provider, "--version"], capture_output=True, timeout=5, text=True
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def analyze_directory_with_ai(
    provider: str,
    directory_info: Dict[str, Any],
    children_digests: Optional[List[Dict[str, Any]]] = None,
    settings: Optional[DigginSettings] = None
) -> Dict[str, Any]:
    """Analyze directory using specified AI provider."""
    if not settings:
        from .config import DigginSettings
        settings = DigginSettings()

    # Load prompt template
    prompt_template = load_prompt_template()

    # Build prompt
    prompt = build_prompt(prompt_template, directory_info, children_digests or [])

    # Call appropriate AI CLI
    if provider.lower() == "claude":
        response = call_claude_cli(prompt, settings.api_options, directory_info.get("path", ""))
    elif provider.lower() == "gemini":
        response = call_gemini_cli(prompt, settings.api_options, directory_info.get("path", ""))
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")

    # Parse response
    digest = parse_json_response(response)

    # Add metadata
    digest.update({
        "analyzed_at": datetime.now().isoformat(),
        "analyzer_version": __version__,
    })

    return digest