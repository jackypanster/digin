"""AI 客戶端封裝（Claude/Gemini）。

職責：
- 讀取 `config/prompt.txt` 模板，拼裝目錄文件列表、代碼片段與子摘要。
- 調用對應 CLI（claude/gemini），並在超時/錯誤時回退。
- 解析 JSON（帶「從文本提取 JSON」容錯），補充 `analyzed_at`/`analyzer_version` 元數據。
- 工廠 `AIClientFactory` 根據配置選擇提供方，便於擴展與替換。

設計動機：將供應商交互與提示工程從主流程解耦，降低耦合度，提升可維護性。
"""

import json
import subprocess
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .__version__ import __version__
from .config import DigginSettings
from .logger import get_logger, log_ai_command


class AIClientError(Exception):
    """Exception raised by AI client operations."""

    pass


class BaseAIClient(ABC):
    """Abstract base class for AI clients."""

    @abstractmethod
    def analyze_directory(
        self,
        directory_info: Dict[str, Any],
        children_digests: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze directory using AI."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if AI CLI tool is available."""
        pass


class ClaudeClient(BaseAIClient):
    """AI client for Claude CLI."""

    def __init__(self, settings: DigginSettings):
        """Initialize Claude client.

        Args:
            settings: Configuration settings
        """
        self.settings = settings
        self.api_options = settings.api_options
        self.prompt_template = self._load_prompt_template()
        self.logger = get_logger("ai_client")

    def analyze_directory(
        self,
        directory_info: Dict[str, Any],
        children_digests: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze directory using Claude.

        Args:
            directory_info: Information about the directory
            children_digests: List of child directory digests

        Returns:
            Analysis result dictionary or None if failed
        """
        try:
            # Build prompt
            prompt = self._build_prompt(directory_info, children_digests or [])

            # Call Claude CLI
            response = self._call_claude_cli(prompt, directory_info.get("path", ""))

            # Parse response
            digest = self._parse_response(response)
            if digest:
                # Add metadata
                digest.update(
                    {
                        "analyzed_at": datetime.now().isoformat(),
                        "analyzer_version": __version__,
                    }
                )

            return digest

        except Exception as e:
            if self.settings.verbose:
                print(f"Claude analysis failed: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Claude CLI is available."""
        try:
            result = subprocess.run(
                ["claude", "--version"], capture_output=True, timeout=5, text=True
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _load_prompt_template(self) -> str:
        """Load prompt template from file."""
        prompt_path = Path(__file__).parent.parent / "config" / "prompt.txt"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            # Fallback basic prompt
            return self._get_fallback_prompt()

    def _build_prompt(
        self, directory_info: Dict[str, Any], children_digests: List[Dict[str, Any]]
    ) -> str:
        """Build analysis prompt from template."""
        file_list_str = self._format_file_list(directory_info.get("files", []))
        code_snippets_str = self._format_code_snippets(directory_info.get("files", []))
        children_digests_str = self._format_children_digests(children_digests)

        return self.prompt_template.format(
            directory_path=directory_info.get("path", ""),
            file_list=file_list_str,
            code_snippets=code_snippets_str,
            children_digests=children_digests_str,
        )

    def _format_file_list(self, files: List[Dict[str, Any]]) -> str:
        """Format file list for prompt."""
        if not files:
            return "无直接文件"

        file_list = []
        for file_info in files:
            extension = file_info.get("extension", "")
            size = file_info.get("size", 0)
            file_list.append(f"- {file_info['name']} ({extension}, {size} bytes)")

        return "\n".join(file_list)

    def _format_code_snippets(self, files: List[Dict[str, Any]]) -> str:
        """Format code snippets for prompt."""
        code_snippets = []

        # For Gemini with 1M token context, include more files
        # Prioritize files with content and reasonable size
        files_with_content = [f for f in files if "content_preview" in f]

        # Include up to 20 files (or all if fewer) to leverage large context windows
        max_files = min(20, len(files_with_content))

        for file_info in files_with_content[:max_files]:
            content = file_info["content_preview"]
            file_ext = file_info.get("extension", "")

            # Add language hint for better syntax highlighting
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

            code_snippets.append(f"**{file_info['name']}** ({file_info.get('size', 0)} bytes):\n```{lang}\n{content}\n```")

        if not code_snippets:
            return "无代码内容或所有文件都是二进制文件"

        return "\n\n".join(code_snippets)

    def _format_children_digests(self, children_digests: List[Dict[str, Any]]) -> str:
        """Format children digests for prompt."""
        if not children_digests:
            return "无子目录（叶子目录）"

        children_summaries = []
        for child in children_digests:
            summary = f"- {child.get('name', '未知')}: {child.get('summary', '无摘要')}"
            children_summaries.append(summary)

        return "\n".join(children_summaries)

    def _call_claude_cli(self, prompt: str, directory: str = "") -> str:
        """Call Claude CLI with prompt.

        Args:
            prompt: Analysis prompt
            directory: Directory being analyzed (for logging)

        Returns:
            Claude's response
        """
        cmd = ["claude", "--print"]  # Use --print for non-interactive mode

        # Add system prompt if specified
        if "append_system_prompt" in self.api_options:
            cmd.extend(
                ["--append-system-prompt", self.api_options["append_system_prompt"]]
            )

        # Add model if specified
        if "model" in self.api_options:
            # Map common model names to valid Claude CLI model names
            model = self.api_options["model"]
            if model == "claude-3-sonnet":
                model = "sonnet"
            elif model == "claude-3-opus":
                model = "opus"
            elif model == "claude-3-haiku":
                model = "haiku"
            cmd.extend(["--model", model])

        start_time = time.time()
        prompt_size = len(prompt)
        response = ""
        success = False
        error_msg = ""

        self.logger.info(f"Starting Claude CLI call for directory: {directory}")
        self.logger.debug(f"Command: {' '.join(cmd)}")

        try:
            # Pass prompt via stdin instead of as argument
            result = subprocess.run(
                cmd,
                input=prompt,  # Pass prompt through stdin
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr
                raise AIClientError(f"Claude CLI failed: {error_msg}")

            response = result.stdout.strip()
            success = True
            return response

        except subprocess.TimeoutExpired:
            error_msg = "Claude CLI timed out"
            raise AIClientError(error_msg)

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # 记录 AI 命令执行详情
            log_ai_command(
                provider="claude",
                command=cmd,
                prompt_size=prompt_size,
                directory=directory,
                start_time=start_time,
                success=success,
                response_size=len(response),
                error_msg=error_msg,
            )

            if success:
                self.logger.info(f"Claude CLI call completed successfully for: {directory}")
            else:
                self.logger.error(f"Claude CLI call failed for: {directory} - {error_msg}")

    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse Claude response as JSON.

        Args:
            response: Raw response from Claude

        Returns:
            Parsed JSON dictionary or None if failed
        """
        try:
            # Try direct JSON parsing first
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
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            if self.settings.verbose:
                print("Failed to parse Claude response as JSON")
                print(f"Response: {response[:500]}...")

            return None

    def _get_fallback_prompt(self) -> str:
        """Get fallback prompt if template file not found."""
        return """请分析以下目录并以JSON格式输出：

目录路径: {directory_path}
文件列表: {file_list}
代码片段: {code_snippets}
子目录摘要: {children_digests}

输出JSON格式包含：
- name: 目录名称
- path: 路径
- kind: 类型 (service|lib|ui|infra|config|test|docs|unknown)
- summary: 功能概述
- capabilities: 能力列表
- confidence: 置信度 (0-100)

请只输出JSON，无其他文字："""


class GeminiClient(BaseAIClient):
    """AI client for Gemini CLI."""

    def __init__(self, settings: DigginSettings):
        """Initialize Gemini client.

        Args:
            settings: Configuration settings
        """
        self.settings = settings
        self.api_options = settings.api_options
        self.prompt_template = ClaudeClient(
            settings
        ).prompt_template  # Reuse same template
        self.logger = get_logger("ai_client")

    def analyze_directory(
        self,
        directory_info: Dict[str, Any],
        children_digests: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze directory using Gemini."""
        try:
            # Build prompt (reuse Claude's logic)
            claude_client = ClaudeClient(self.settings)
            prompt = claude_client._build_prompt(directory_info, children_digests or [])

            # Call Gemini CLI
            response = self._call_gemini_cli(prompt, directory_info.get("path", ""))

            # Parse response (reuse Claude's logic)
            digest = claude_client._parse_response(response)
            if digest:
                # Add metadata
                digest.update(
                    {
                        "analyzed_at": datetime.now().isoformat(),
                        "analyzer_version": __version__,
                    }
                )

            return digest

        except Exception as e:
            if self.settings.verbose:
                print(f"Gemini analysis failed: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Gemini CLI is available."""
        try:
            result = subprocess.run(
                ["gemini", "--version"], capture_output=True, timeout=5, text=True
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _call_gemini_cli(self, prompt: str, directory: str = "") -> str:
        """Call Gemini CLI with prompt."""
        cmd = ["gemini"]

        # Add model if specified
        if "model" in self.api_options:
            cmd.extend(["-m", self.api_options["model"]])

        # Add prompt
        cmd.extend(["-p", prompt])

        start_time = time.time()
        prompt_size = len(prompt)
        response = ""
        success = False
        error_msg = ""

        self.logger.info(f"Starting Gemini CLI call for directory: {directory}")
        self.logger.debug(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120  # 2 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr
                raise AIClientError(f"Gemini CLI failed: {error_msg}")

            response = result.stdout.strip()
            success = True
            return response

        except subprocess.TimeoutExpired:
            error_msg = "Gemini CLI timed out"
            raise AIClientError(error_msg)

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # 记录 AI 命令执行详情
            log_ai_command(
                provider="gemini",
                command=cmd,
                prompt_size=prompt_size,
                directory=directory,
                start_time=start_time,
                success=success,
                response_size=len(response),
                error_msg=error_msg,
            )

            if success:
                self.logger.info(f"Gemini CLI call completed successfully for: {directory}")
            else:
                self.logger.error(f"Gemini CLI call failed for: {directory} - {error_msg}")


class AIClientFactory:
    """Factory for creating AI clients."""

    @staticmethod
    def create_client(settings: DigginSettings) -> BaseAIClient:
        """Create AI client based on settings.

        Args:
            settings: Configuration settings

        Returns:
            AI client instance
        """
        provider = settings.api_provider.lower()

        if provider == "claude":
            return ClaudeClient(settings)
        elif provider == "gemini":
            return GeminiClient(settings)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
