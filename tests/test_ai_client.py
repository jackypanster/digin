"""Tests for AI client functionality using real CLI commands."""

import pytest

from src.ai_client import AIClientError, AIClientFactory, ClaudeClient, GeminiClient
from src.config import DigginSettings


class TestClaudeClient:
    """Test Claude AI client with real CLI commands."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return DigginSettings(
            api_provider="claude",
            api_options={
                "model": "claude-3-sonnet",
                "max_tokens": 4000,
                "append_system_prompt": "只输出JSON格式，严格按照Schema定义",
            },
        )

    @pytest.fixture
    def claude_client(self, settings):
        """Create Claude client."""
        return ClaudeClient(settings)

    def test_init(self, settings):
        """Test Claude client initialization."""
        client = ClaudeClient(settings)
        assert client.settings == settings
        assert client.api_options == settings.api_options
        assert client.prompt_template is not None

    @pytest.mark.real_ai
    def test_is_available(self, claude_client):
        """Test Claude CLI availability (real command)."""
        # This tests the actual claude --version command
        is_available = claude_client.is_available()
        # Should be True since claude is installed
        assert is_available is True

    def test_build_prompt(self, claude_client):
        """Test prompt building."""
        directory_info = {
            "path": "/test/project",
            "name": "project",
            "files": [
                {
                    "name": "main.py",
                    "extension": ".py",
                    "size": 100,
                    "content_preview": "def main():\n    pass",
                },
                {"name": "utils.py", "extension": ".py", "size": 50},
            ],
        }

        prompt = claude_client._build_prompt(directory_info, [])

        assert "/test/project" in prompt
        assert "main.py (.py, 100 bytes)" in prompt
        assert "utils.py (.py, 50 bytes)" in prompt
        assert "def main()" in prompt
        assert "无子目录（叶子目录）" in prompt

    @pytest.mark.real_ai
    def test_call_claude_cli_real(self, claude_client):
        """Test real Claude CLI call with simple prompt."""
        prompt = """请分析这个简单的Python模块并返回JSON格式分析结果：

目录路径: /test/sample
文件列表:
- main.py (.py, 50 bytes)

代码片段:
**main.py**:
```python
def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
```

子目录摘要: 无子目录（叶子目录）

请返回包含以下字段的JSON:
- name: 目录名称
- kind: 类型 (service|lib|ui|infra|config|test|docs|unknown)
- summary: 功能概述
- capabilities: 能力列表
- confidence: 置信度 (0-100)

只返回JSON，无其他文字。"""

        try:
            result = claude_client._call_claude_cli(prompt)
            assert result is not None
            assert len(result) > 0
            # Result should be JSON-like string
            assert "{" in result and "}" in result
        except AIClientError as e:
            # If Claude CLI fails, we want to know about it
            pytest.fail(f"Claude CLI call failed: {e}")

    def test_parse_response_valid_json(self, claude_client):
        """Test parsing valid JSON response."""
        response = '{"name": "test", "kind": "service"}'

        result = claude_client._parse_response(response)

        assert result == {"name": "test", "kind": "service"}

    def test_parse_response_json_in_text(self, claude_client):
        """Test parsing JSON embedded in text."""
        response = """Here is the analysis:

        {"name": "test", "kind": "lib", "summary": "A test library"}

        That's the result."""

        result = claude_client._parse_response(response)

        assert result["name"] == "test"
        assert result["kind"] == "lib"

    def test_parse_response_invalid_json(self, claude_client):
        """Test parsing invalid JSON."""
        response = "This is not JSON at all"

        result = claude_client._parse_response(response)

        assert result is None

    @pytest.mark.real_ai
    def test_analyze_directory_real(self, claude_client):
        """Test real directory analysis with Claude CLI."""
        directory_info = {
            "name": "sample_module",
            "path": "/test/sample_module",
            "files": [
                {
                    "name": "main.py",
                    "extension": ".py",
                    "size": 120,
                    "content_preview": """def main():
    print("Hello from main!")

def calculate(x, y):
    return x + y

if __name__ == "__main__":
    main()
"""
                },
                {
                    "name": "utils.py",
                    "extension": ".py",
                    "size": 80,
                    "content_preview": """def helper_function():
    return "helper"

CONSTANT = 42
"""
                }
            ]
        }

        try:
            result = claude_client.analyze_directory(directory_info, [])

            # Verify the result has expected structure
            assert result is not None
            assert isinstance(result, dict)
            assert "name" in result
            assert "kind" in result
            assert "summary" in result
            assert "analyzed_at" in result
            assert "analyzer_version" in result

            # Basic content validation
            assert result["name"] is not None
            assert result["kind"] in ["service", "lib", "ui", "infra", "config", "test", "docs", "unknown"]
            assert isinstance(result["summary"], str)
            assert len(result["summary"]) > 0

        except AIClientError as e:
            pytest.fail(f"Real Claude analysis failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error in Claude analysis: {e}")


class TestGeminiClient:
    """Test Gemini AI client with real CLI commands."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return DigginSettings(
            api_provider="gemini",
            api_options={"model": "gemini-1.5-pro"}
        )

    @pytest.fixture
    def gemini_client(self, settings):
        """Create Gemini client."""
        return GeminiClient(settings)

    @pytest.mark.real_ai
    def test_is_available(self, gemini_client):
        """Test Gemini CLI availability (real command)."""
        # This tests the actual gemini --version command
        is_available = gemini_client.is_available()
        # Should be True since gemini is installed
        assert is_available is True

    @pytest.mark.real_ai
    def test_call_gemini_cli_real(self, gemini_client):
        """Test real Gemini CLI call with simple prompt."""
        prompt = """请分析这个简单的Python模块并返回JSON格式分析结果：

目录路径: /test/sample
文件列表:
- main.py (.py, 50 bytes)

代码片段:
**main.py**:
```python
def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
```

子目录摘要: 无子目录（叶子目录）

请返回包含以下字段的JSON:
- name: 目录名称
- kind: 类型 (service|lib|ui|infra|config|test|docs|unknown)
- summary: 功能概述
- capabilities: 能力列表
- confidence: 置信度 (0-100)

只返回JSON，无其他文字。"""

        try:
            result = gemini_client._call_gemini_cli(prompt)
            assert result is not None
            assert len(result) > 0
            # Result should be JSON-like string
            assert "{" in result and "}" in result
        except AIClientError as e:
            # If Gemini CLI fails, we want to know about it
            pytest.fail(f"Gemini CLI call failed: {e}")

    @pytest.mark.real_ai
    def test_analyze_directory_real(self, gemini_client):
        """Test real directory analysis with Gemini CLI."""
        directory_info = {
            "name": "sample_module",
            "path": "/test/sample_module",
            "files": [
                {
                    "name": "main.py",
                    "extension": ".py",
                    "size": 120,
                    "content_preview": """def main():
    print("Hello from main!")

def calculate(x, y):
    return x + y

if __name__ == "__main__":
    main()
"""
                },
                {
                    "name": "utils.py",
                    "extension": ".py",
                    "size": 80,
                    "content_preview": """def helper_function():
    return "helper"

CONSTANT = 42
"""
                }
            ]
        }

        try:
            result = gemini_client.analyze_directory(directory_info, [])

            # Verify the result has expected structure
            assert result is not None
            assert isinstance(result, dict)
            assert "name" in result
            assert "kind" in result
            assert "summary" in result
            assert "analyzed_at" in result
            assert "analyzer_version" in result

            # Basic content validation
            assert result["name"] is not None
            assert result["kind"] in ["service", "lib", "ui", "infra", "config", "test", "docs", "unknown"]
            assert isinstance(result["summary"], str)
            assert len(result["summary"]) > 0

        except AIClientError as e:
            pytest.fail(f"Real Gemini analysis failed: {e}")


class TestAIClientFactory:
    """Test AI client factory."""

    def test_create_claude_client(self):
        """Test creating Claude client."""
        settings = DigginSettings(api_provider="claude")
        client = AIClientFactory.create_client(settings)
        assert isinstance(client, ClaudeClient)

    def test_create_gemini_client(self):
        """Test creating Gemini client."""
        settings = DigginSettings(api_provider="gemini")
        client = AIClientFactory.create_client(settings)
        assert isinstance(client, GeminiClient)

    def test_unsupported_provider(self):
        """Test unsupported provider."""
        settings = DigginSettings(api_provider="unknown")

        with pytest.raises(ValueError, match="Unsupported AI provider"):
            AIClientFactory.create_client(settings)
