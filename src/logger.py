"""簡化日誌系統。

職責：
- 提供統一的日誌配置
- AI 命令專用日誌記錄
- 移除複雜的單例模式，使用標準 logging
"""

import json
import logging
import logging.handlers
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Global storage for logging configuration
_logging_configured = False
_ai_logging_enabled = False
_ai_log_format = "readable"
_ai_log_detail_level = "summary"
_ai_log_prompt_max_chars = 200


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    max_file_size: str = "10MB",
    backup_count: int = 5,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    ai_command_logging: bool = True,
    ai_log_format: str = "readable",
    ai_log_detail_level: str = "summary",
    ai_log_prompt_max_chars: int = 200,
) -> None:
    """Setup simplified logging system."""
    global _logging_configured, _ai_logging_enabled, _ai_log_format, _ai_log_detail_level, _ai_log_prompt_max_chars

    if _logging_configured:
        return

    # Store AI logging configuration
    _ai_logging_enabled = ai_command_logging
    _ai_log_format = ai_log_format
    _ai_log_detail_level = ai_log_detail_level
    _ai_log_prompt_max_chars = ai_log_prompt_max_chars

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Parse file size
    max_bytes = parse_file_size(max_file_size)

    # Configure root logger
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(log_format)

    # Setup main application logger
    setup_file_logger(
        "digin",
        log_path / "digin.log",
        numeric_level,
        formatter,
        max_bytes,
        backup_count,
    )

    # Setup AI command logger if enabled
    if ai_command_logging:
        ai_formatter = logging.Formatter(
            "%(asctime)s - AI_COMMAND - %(levelname)s - %(message)s"
        )
        setup_file_logger(
            "digin.ai_commands",
            log_path / "ai_commands.log",
            numeric_level,
            ai_formatter,
            max_bytes,
            backup_count,
        )

    # Setup error logger
    error_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - ERROR - %(message)s - [%(pathname)s:%(lineno)d]"
    )
    setup_file_logger(
        "digin.errors",
        log_path / "errors.log",
        logging.WARNING,
        error_formatter,
        max_bytes,
        backup_count,
    )

    _logging_configured = True


def setup_file_logger(
    name: str,
    filename: Path,
    level: int,
    formatter: logging.Formatter,
    max_bytes: int,
    backup_count: int,
) -> None:
    """Setup a file logger with rotation."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create rotating file handler
    handler = logging.handlers.RotatingFileHandler(
        filename, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(formatter)
    handler.setLevel(level)

    logger.addHandler(handler)
    logger.propagate = False


def parse_file_size(size_str: str) -> int:
    """Parse file size string to bytes."""
    size_str = size_str.upper().strip()

    if size_str.endswith("KB"):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith("MB"):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith("GB"):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        return int(size_str)


def get_logger(name: str) -> logging.Logger:
    """Get logger by name."""
    full_name = f"digin.{name}" if not name.startswith("digin") else name
    return logging.getLogger(full_name)


def log_ai_command(
    provider: str,
    command: List[str],
    prompt_size: int,
    directory: str,
    start_time: float,
    success: bool,
    response_size: int,
    error_msg: str,
    prompt: str,
) -> None:
    """Log AI command execution details."""
    if not _ai_logging_enabled:
        return

    duration = time.time() - start_time
    logger = get_logger("ai_commands")

    if _ai_log_format == "readable":
        # Human-readable format
        status = "SUCCESS" if success else "FAILED"
        truncated_prompt = (
            prompt[:_ai_log_prompt_max_chars] + "..."
            if len(prompt) > _ai_log_prompt_max_chars
            else prompt
        )

        log_msg = f"{provider.upper()} {status} | Dir: {directory} | Duration: {duration:.2f}s | Prompt: {prompt_size} chars | Response: {response_size} chars"

        if not success and error_msg:
            log_msg += f" | Error: {error_msg}"

        if _ai_log_detail_level == "full":
            log_msg += (
                f" | Command: {' '.join(command)} | Prompt preview: {truncated_prompt}"
            )

        logger.info(log_msg)
    else:
        # JSON format for detailed analysis
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "command": command,
            "directory": directory,
            "duration_seconds": round(duration, 2),
            "prompt_size": prompt_size,
            "response_size": response_size,
            "success": success,
            "error_msg": error_msg if error_msg else None,
        }

        if _ai_log_detail_level == "full":
            log_data["prompt_preview"] = prompt[:_ai_log_prompt_max_chars]

        logger.info(json.dumps(log_data, ensure_ascii=False))
