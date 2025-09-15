"""集中式日志管理模块。

职责：
- 提供统一的日志配置和轮换策略（RotatingFileHandler）。
- 支持多种日志级别（DEBUG/INFO/WARNING/ERROR）和专用日志器。
- AI 命令专用日志记录，包含完整命令、参数、响应时间、成功/失败状态。
- 自动创建日志目录，处理并发安全，支持结构化日志格式。

设计重点：为调试和审计提供详尽信息，同时控制磁盘使用（自动轮换+压缩）。
"""

import json
import logging
import logging.handlers
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class DigginLogger:
    """Digin 应用专用日志管理器。"""

    _instance: Optional["DigginLogger"] = None
    _initialized = False

    def __new__(cls) -> "DigginLogger":
        """单例模式确保全局唯一的日志配置。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化日志管理器（仅执行一次）。"""
        if self._initialized:
            return
        self._initialized = True
        self.loggers: Dict[str, logging.Logger] = {}

    def setup_logging(
        self,
        log_dir: str = "logs",
        log_level: str = "INFO",
        max_file_size: str = "10MB",
        backup_count: int = 5,
        log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        ai_command_logging: bool = True,
    ) -> None:
        """设置日志系统配置。

        Args:
            log_dir: 日志目录路径
            log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
            max_file_size: 单个日志文件最大大小
            backup_count: 保留的轮换文件数量
            log_format: 日志格式字符串
            ai_command_logging: 是否启用 AI 命令专用日志
        """
        # 创建日志目录
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        (self.log_dir / "archive").mkdir(exist_ok=True)

        # 解析文件大小
        max_bytes = self._parse_file_size(max_file_size)

        # 配置根日志级别
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)

        # 创建格式化器
        formatter = logging.Formatter(log_format)

        # 创建主应用日志器
        self._create_logger(
            "digin.main",
            "digin.log",
            numeric_level,
            formatter,
            max_bytes,
            backup_count
        )

        # 创建 AI 命令专用日志器
        if ai_command_logging:
            ai_formatter = logging.Formatter(
                "%(asctime)s - AI_COMMAND - %(levelname)s - %(message)s"
            )
            self._create_logger(
                "digin.ai_commands",
                "ai_commands.log",
                numeric_level,
                ai_formatter,
                max_bytes,
                backup_count,
            )

        # 创建错误专用日志器
        error_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - ERROR - %(message)s - [%(pathname)s:%(lineno)d]"
        )
        self._create_logger(
            "digin.errors",
            "errors.log",
            logging.WARNING,  # 只记录 WARNING 及以上
            error_formatter,
            max_bytes,
            backup_count,
        )

    def _create_logger(
        self,
        name: str,
        filename: str,
        level: int,
        formatter: logging.Formatter,
        max_bytes: int,
        backup_count: int,
    ) -> logging.Logger:
        """创建配置好的日志器。"""
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # 避免重复添加处理器
        if logger.handlers:
            return logger

        # 创建轮换文件处理器
        handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        # Ensure handler flushes immediately
        handler.flush()

        self.loggers[name] = logger
        return logger

    def _parse_file_size(self, size_str: str) -> int:
        """解析文件大小字符串为字节数。"""
        size_str = size_str.upper().strip()
        if size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)

    def get_logger(self, component: str = "main") -> logging.Logger:
        """获取指定组件的日志器。

        Args:
            component: 组件名 (main/ai_commands/errors)

        Returns:
            配置好的日志器实例
        """
        logger_name = f"digin.{component}"
        if logger_name not in self.loggers:
            # 如果请求的日志器不存在，返回主日志器
            logger_name = "digin.main"
        return self.loggers.get(logger_name, logging.getLogger(logger_name))

    def log_ai_command(
        self,
        provider: str,
        command: list,
        prompt_size: int,
        directory: str,
        start_time: float,
        success: bool = True,
        response_size: int = 0,
        error_msg: str = "",
    ) -> None:
        """记录 AI 命令执行详情。

        Args:
            provider: AI 提供商 (claude/gemini)
            command: 完整命令列表
            prompt_size: 提示词字符数
            directory: 被分析的目录
            start_time: 命令开始时间戳
            success: 是否执行成功
            response_size: 响应内容大小
            error_msg: 错误信息（如果失败）
        """
        logger = self.get_logger("ai_commands")
        duration_ms = int((time.time() - start_time) * 1000)

        # 创建结构化日志数据
        log_data = {
            "provider": provider,
            "command": " ".join(command),
            "command_args": command[1:],  # 除了二进制名的参数
            "prompt_size": prompt_size,
            "response_size": response_size,
            "duration_ms": duration_ms,
            "directory": directory,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        }

        if not success and error_msg:
            log_data["error"] = error_msg

        # 记录为格式化的 JSON 以便后续分析
        json_str = json.dumps(log_data, ensure_ascii=False, separators=(",", ":"))

        if success:
            logger.info(json_str)
        else:
            logger.error(json_str)
            # 同时记录到错误日志
            self.get_logger("errors").error(
                f"AI command failed - Provider: {provider}, Directory: {directory}, Error: {error_msg}"
            )

        # Force flush all handlers to ensure immediate write
        for handler in logger.handlers:
            handler.flush()

        if not success:
            error_logger = self.get_logger("errors")
            for handler in error_logger.handlers:
                handler.flush()


# 全局日志管理器实例
_logger_instance = DigginLogger()


def setup_logging(**kwargs) -> None:
    """设置全局日志配置。"""
    _logger_instance.setup_logging(**kwargs)


def get_logger(component: str = "main") -> logging.Logger:
    """获取日志器实例。"""
    return _logger_instance.get_logger(component)


def log_ai_command(**kwargs) -> None:
    """记录 AI 命令执行。"""
    _logger_instance.log_ai_command(**kwargs)