"""Tests for AI client functionality."""

from unittest.mock import Mock, patch

import pytest

from src.ai_client import AIClientError, AIClientFactory, ClaudeClient, GeminiClient
from src.config import DigginSettings


class TestClaudeClient:
    """Test Claude AI client."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return DigginSettings(
            api_provider="claude",
            api_options={
                "model": "claude-3-sonnet",
                "max_tokens": 4000,
                "append_system_prompt": "Output JSON only",
            },
        )

    @pytest.fixture
    def claude_client(self, settings):
        """Create Claude client."""
        with patch.object(
            ClaudeClient,
            "_load_prompt_template",
            return_value="Test prompt: {directory_path}",
        ):
            return ClaudeClient(settings)

    def test_init(self, settings):
        """Test Claude client initialization."""
        with patch.object(
            ClaudeClient, "_load_prompt_template", return_value="Test prompt"
        ):
            client = ClaudeClient(settings)
            assert client.settings == settings
            assert client.api_options == settings.api_options
            assert client.prompt_template == "Test prompt"

    @patch("subprocess.run")
    def test_is_available_success(self, mock_run, claude_client):
        """Test successful availability check."""
        mock_run.return_value = Mock(returncode=0)

        assert claude_client.is_available() is True
        mock_run.assert_called_once_with(
            ["claude", "--version"], capture_output=True, timeout=5, text=True
        )

    @patch("subprocess.run")
    def test_is_available_failure(self, mock_run, claude_client):
        """Test failed availability check."""
        mock_run.return_value = Mock(returncode=1)

        assert claude_client.is_available() is False

    @patch("subprocess.run")
    def test_is_available_not_found(self, mock_run, claude_client):
        """Test CLI not found."""
        mock_run.side_effect = FileNotFoundError()

        assert claude_client.is_available() is False

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

        claude_client.prompt_template = (
            "Path: {directory_path}\nFiles: {file_list}\n"
            "Code: {code_snippets}\nChildren: {children_digests}"
        )

        prompt = claude_client._build_prompt(directory_info, [])

        assert "/test/project" in prompt
        assert "main.py (.py, 100 bytes)" in prompt
        assert "utils.py (.py, 50 bytes)" in prompt
        assert "def main()" in prompt
        assert "无子目录（叶子目录）" in prompt

    @patch("subprocess.run")
    def test_call_claude_cli_success(self, mock_run, claude_client):
        """Test successful Claude CLI call."""
        mock_run.return_value = Mock(
            returncode=0, stdout='{"name": "test", "summary": "test module"}'
        )

        result = claude_client._call_claude_cli("test prompt")

        assert result == '{"name": "test", "summary": "test module"}'

        # Verify command construction
        expected_cmd = [
            "claude",
            "--print",
            "--append-system-prompt",
            "Output JSON only",
            "--model",
            "sonnet",
        ]
        mock_run.assert_called_once_with(
            expected_cmd,
            input="test prompt",
            capture_output=True,
            text=True,
            timeout=120,
        )

    @patch("subprocess.run")
    def test_call_claude_cli_failure(self, mock_run, claude_client):
        """Test failed Claude CLI call."""
        mock_run.return_value = Mock(returncode=1, stderr="API error")

        with pytest.raises(AIClientError, match="Claude CLI failed"):
            claude_client._call_claude_cli("test prompt")

    @patch("subprocess.run")
    def test_call_claude_cli_timeout(self, mock_run, claude_client):
        """Test Claude CLI timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)

        with pytest.raises(AIClientError, match="Claude CLI timed out"):
            claude_client._call_claude_cli("test prompt")

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

    @patch.object(ClaudeClient, "_call_claude_cli")
    @patch.object(ClaudeClient, "_build_prompt")
    def test_analyze_directory_success(
        self, mock_build_prompt, mock_call_cli, claude_client
    ):
        """Test successful directory analysis."""
        mock_build_prompt.return_value = "test prompt"
        mock_call_cli.return_value = '{"name": "test", "kind": "service"}'

        directory_info = {"name": "test", "path": "/test"}

        result = claude_client.analyze_directory(directory_info)

        assert result["name"] == "test"
        assert result["kind"] == "service"
        assert "analyzed_at" in result
        assert "analyzer_version" in result

    @patch.object(ClaudeClient, "_call_claude_cli")
    def test_analyze_directory_failure(self, mock_call_cli, claude_client):
        """Test failed directory analysis."""
        mock_call_cli.side_effect = AIClientError("Test error")

        directory_info = {"name": "test", "path": "/test"}

        result = claude_client.analyze_directory(directory_info)

        assert result is None


class TestGeminiClient:
    """Test Gemini AI client."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return DigginSettings(
            api_provider="gemini", api_options={"model": "gemini-pro"}
        )

    @pytest.fixture
    def gemini_client(self, settings):
        """Create Gemini client."""
        with patch.object(
            ClaudeClient, "_load_prompt_template", return_value="Test prompt"
        ):
            return GeminiClient(settings)

    @patch("subprocess.run")
    def test_is_available(self, mock_run, gemini_client):
        """Test Gemini availability check."""
        mock_run.return_value = Mock(returncode=0)

        assert gemini_client.is_available() is True
        mock_run.assert_called_once_with(
            ["gemini", "--version"], capture_output=True, timeout=5, text=True
        )

    @patch("subprocess.run")
    def test_call_gemini_cli(self, mock_run, gemini_client):
        """Test Gemini CLI call."""
        mock_run.return_value = Mock(returncode=0, stdout='{"name": "test"}')

        result = gemini_client._call_gemini_cli("test prompt")

        assert result == '{"name": "test"}'

        expected_cmd = ["gemini", "-m", "gemini-pro", "-p", "test prompt"]
        mock_run.assert_called_once_with(
            expected_cmd, capture_output=True, text=True, timeout=120
        )


class TestAIClientFactory:
    """Test AI client factory."""

    def test_create_claude_client(self):
        """Test creating Claude client."""
        settings = DigginSettings(api_provider="claude")

        with patch.object(
            ClaudeClient, "_load_prompt_template", return_value="Test prompt"
        ):
            client = AIClientFactory.create_client(settings)

        assert isinstance(client, ClaudeClient)

    def test_create_gemini_client(self):
        """Test creating Gemini client."""
        settings = DigginSettings(api_provider="gemini")

        with patch.object(
            ClaudeClient, "_load_prompt_template", return_value="Test prompt"
        ):
            client = AIClientFactory.create_client(settings)

        assert isinstance(client, GeminiClient)

    def test_unsupported_provider(self):
        """Test unsupported provider."""
        settings = DigginSettings(api_provider="unknown")

        with pytest.raises(ValueError, match="Unsupported AI provider"):
            AIClientFactory.create_client(settings)
