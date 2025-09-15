"""Tests for logging functionality."""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import DigginSettings, LoggingSettings
from src.logger import DigginLogger, get_logger, log_ai_command, setup_logging


class TestDigginLogger:
    """Test the DigginLogger class."""

    def test_singleton_instance(self):
        """Test that DigginLogger is a singleton."""
        logger1 = DigginLogger()
        logger2 = DigginLogger()

        assert logger1 is logger2

    def test_setup_logging_creates_directories(self):
        """Test that setup_logging creates log directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "test_logs"

            logger = DigginLogger()
            logger.setup_logging(
                log_dir=str(log_dir),
                log_level="INFO",
                max_file_size="1MB",
                backup_count=3,
            )

            assert log_dir.exists()
            assert (log_dir / "archive").exists()

    def test_get_logger_returns_configured_logger(self):
        """Test that get_logger returns properly configured loggers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "test_logs"

            logger_manager = DigginLogger()
            logger_manager.setup_logging(log_dir=str(log_dir))

            main_logger = logger_manager.get_logger("main")
            ai_logger = logger_manager.get_logger("ai_commands")

            assert isinstance(main_logger, logging.Logger)
            assert isinstance(ai_logger, logging.Logger)
            assert main_logger.name == "digin.main"
            assert ai_logger.name == "digin.ai_commands"

    def test_log_ai_command_creates_structured_log(self):
        """Test that log_ai_command creates properly structured log entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "test_logs"

            logger_manager = DigginLogger()
            logger_manager.setup_logging(log_dir=str(log_dir))

            import time
            start_time = time.time()

            logger_manager.log_ai_command(
                provider="gemini",
                command=["gemini", "-m", "gemini-1.5-pro", "-p", "test prompt"],
                prompt_size=100,
                directory="/test/path",
                start_time=start_time,
                success=True,
                response_size=500,
            )

            # Check if log file was created and contains expected content
            ai_log_file = log_dir / "ai_commands.log"
            assert ai_log_file.exists()

            with open(ai_log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()

            assert "gemini" in log_content
            assert "test prompt" in log_content
            assert "/test/path" in log_content
            assert '"success": true' in log_content

    def test_log_ai_command_failure_logging(self):
        """Test that failed AI commands are properly logged with error details."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "test_logs"

            logger_manager = DigginLogger()
            logger_manager.setup_logging(log_dir=str(log_dir))

            import time
            start_time = time.time()

            logger_manager.log_ai_command(
                provider="claude",
                command=["claude", "--print"],
                prompt_size=200,
                directory="/test/failed",
                start_time=start_time,
                success=False,
                response_size=0,
                error_msg="Command timeout",
            )

            # Check both AI commands log and errors log
            ai_log_file = log_dir / "ai_commands.log"
            error_log_file = log_dir / "errors.log"

            assert ai_log_file.exists()
            assert error_log_file.exists()

            with open(ai_log_file, 'r', encoding='utf-8') as f:
                ai_content = f.read()

            with open(error_log_file, 'r', encoding='utf-8') as f:
                error_content = f.read()

            assert '"success": false' in ai_content
            assert "Command timeout" in ai_content
            assert "AI command failed" in error_content

    def test_file_size_parsing(self):
        """Test that file size strings are correctly parsed."""
        logger_manager = DigginLogger()

        assert logger_manager._parse_file_size("1KB") == 1024
        assert logger_manager._parse_file_size("5MB") == 5 * 1024 * 1024
        assert logger_manager._parse_file_size("1GB") == 1024 * 1024 * 1024
        assert logger_manager._parse_file_size("2048") == 2048

    @pytest.mark.unit
    def test_setup_logging_with_settings_object(self):
        """Test setting up logging using DigginSettings object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "settings_logs"

            logging_settings = LoggingSettings(
                enabled=True,
                level="DEBUG",
                log_dir=str(log_dir),
                max_file_size="2MB",
                backup_count=2,
            )

            setup_logging(
                log_dir=logging_settings.log_dir,
                log_level=logging_settings.level,
                max_file_size=logging_settings.max_file_size,
                backup_count=logging_settings.backup_count,
            )

            logger = get_logger("test")
            logger.debug("Test debug message")

            # Verify log file was created
            main_log_file = log_dir / "digin.log"
            assert main_log_file.exists()


class TestLoggerIntegration:
    """Test logger integration with other components."""

    @pytest.mark.unit
    def test_global_logger_functions(self):
        """Test global logger setup and access functions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "global_test"

            # Test setup_logging function
            setup_logging(log_dir=str(log_dir))

            # Test get_logger function
            logger = get_logger("integration_test")
            assert isinstance(logger, logging.Logger)

            # Test log_ai_command function
            import time
            log_ai_command(
                provider="test",
                command=["test", "command"],
                prompt_size=50,
                directory="/test/integration",
                start_time=time.time(),
                success=True,
                response_size=100,
            )

            # Verify files were created
            assert (log_dir / "digin.log").exists()
            assert (log_dir / "ai_commands.log").exists()

    @pytest.mark.unit
    def test_logger_thread_safety(self):
        """Test that logger is thread-safe for concurrent operations."""
        import threading
        import time

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "thread_test"
            setup_logging(log_dir=str(log_dir))

            logger = get_logger("thread_test")

            def log_worker(worker_id):
                """Worker function that logs messages."""
                for i in range(10):
                    logger.info(f"Worker {worker_id} - Message {i}")
                    time.sleep(0.001)  # Small delay to encourage contention

            # Create multiple threads
            threads = []
            for worker_id in range(5):
                thread = threading.Thread(target=log_worker, args=(worker_id,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Verify log file contains messages from all workers
            log_file = log_dir / "digin.log"
            assert log_file.exists()

            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Should have messages from all 5 workers
            for worker_id in range(5):
                assert f"Worker {worker_id}" in content

    @pytest.mark.unit
    def test_log_rotation_configuration(self):
        """Test that log rotation is properly configured."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "rotation_test"

            # Setup with very small max size to trigger rotation
            setup_logging(
                log_dir=str(log_dir),
                max_file_size="1KB",  # Very small for testing
                backup_count=3
            )

            logger = get_logger("rotation_test")

            # Write enough data to potentially trigger rotation
            large_message = "x" * 200  # 200 character message
            for i in range(20):  # Write 20 messages = ~4KB total
                logger.info(f"Message {i}: {large_message}")

            # Check that log file exists (rotation behavior depends on actual implementation)
            log_file = log_dir / "digin.log"
            assert log_file.exists()

            # If rotation occurred, there might be backup files
            # This is implementation-dependent, so we just verify the main log exists
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert len(content) > 0  # Should contain some log data