"""集中式日志管理模块。

职责：
- 提供统一的日志配置和轮换策略（RotatingFileHandler）。
- 支持多种日志级别（DEBUG/INFO/WARNING/ERROR）和专用日志器。
- AI 命令专用日志记录，包含完整命令、参数、响应时间、成功/失败状态。
- 自动创建日志目录，处理并发安全，支持结构化日志格式。

设计重点：为调试和审计提供详尽信息，同时控制磁盘使用（自动轮换+压缩）。
"""

import hashlib
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
        ai_log_format: str = "readable",
        ai_log_detail_level: str = "summary",
        ai_log_prompt_max_chars: int = 200,
    ) -> None:
        """设置日志系统配置。

        Args:
            log_dir: 日志目录路径
            log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
            max_file_size: 单个日志文件最大大小
            backup_count: 保留的轮换文件数量
            log_format: 日志格式字符串
            ai_command_logging: 是否启用 AI 命令专用日志
            ai_log_format: AI 日志格式 ("readable" 或 "json")
            ai_log_detail_level: AI 日志详细程度 ("summary" 或 "full")
            ai_log_prompt_max_chars: 提示词显示最大字符数
        """
        # 保存配置
        self.ai_log_format = ai_log_format
        self.ai_log_detail_level = ai_log_detail_level
        self.ai_log_prompt_max_chars = ai_log_prompt_max_chars

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
            if ai_log_format == "readable":
                # 创建人类可读格式的 AI 命令日志器
                self._create_ai_readable_logger(numeric_level, max_bytes, backup_count)
            else:
                # 创建 JSON 格式的 AI 命令日志器（保持原有格式）
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

            # 始终创建详细日志器（JSONL 格式）
            if ai_log_detail_level == "full":
                detailed_formatter = logging.Formatter("%(message)s")
                self._create_logger(
                    "digin.ai_commands_detailed",
                    "ai_commands_detailed.jsonl",
                    numeric_level,
                    detailed_formatter,
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

    def _create_ai_readable_logger(self, level: int, max_bytes: int, backup_count: int) -> logging.Logger:
        """创建人类可读的 AI 命令日志器。"""
        logger = logging.getLogger("digin.ai_commands")
        logger.setLevel(level)

        # 避免重复添加处理器
        if logger.handlers:
            return logger

        # 创建自定义格式化器（不使用标准格式）
        class AIReadableFormatter(logging.Formatter):
            def format(self, record):
                # 直接返回消息内容，不添加时间戳等前缀
                return record.getMessage()

        # 创建轮换文件处理器
        handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / "ai_commands.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(AIReadableFormatter())

        logger.addHandler(handler)

        # Ensure handler flushes immediately
        handler.flush()

        self.loggers["digin.ai_commands"] = logger
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

    def _hash_prompt(self, prompt: str) -> str:
        """计算提示词的 SHA256 哈希值。"""
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]

    def _truncate_prompt(self, prompt: str, max_chars: int = None) -> str:
        """截断提示词到指定长度。"""
        if max_chars is None:
            max_chars = self.ai_log_prompt_max_chars

        if len(prompt) <= max_chars:
            return prompt

        return prompt[:max_chars] + "..."

    def _redact_sensitive_prompt(self, prompt: str) -> str:
        """对提示词进行脱敏处理，移除文件内容但保留结构信息。"""
        if not prompt:
            return ""

        # 查找代码内容部分并替换
        import re

        # 匹配代码块的模式
        code_pattern = r'```[\w]*\n(.*?)\n```'
        redacted_prompt = re.sub(code_pattern, '```\n[REDACTED_CODE_CONTENT]\n```', prompt, flags=re.DOTALL)

        # 如果提示词仍然很长，保留前100字符 + 结构信息
        if len(redacted_prompt) > 300:
            lines = redacted_prompt.split('\n')
            structure_info = []
            for line in lines[:10]:  # 只保留前10行的结构信息
                if '**' in line or '##' in line or '目录路径' in line or '包含的文件' in line:
                    structure_info.append(line)

            if structure_info:
                return '\n'.join(structure_info) + '\n[...CONTENT_REDACTED...]'

        return redacted_prompt[:100] + "..." if len(redacted_prompt) > 100 else redacted_prompt

    def _format_readable_ai_log(
        self,
        provider: str,
        command: list,
        prompt: str,
        directory: str,
        success: bool,
        duration_ms: int,
        prompt_size: int,
        response_size: int,
        error_msg: str = "",
    ) -> str:
        """格式化人类可读的 AI 命令日志。"""
        status_icon = "✅ SUCCESS" if success else "❌ FAILED"
        prompt_hash = self._hash_prompt(prompt)

        # 使用脱敏的提示词预览
        prompt_preview = self._redact_sensitive_prompt(prompt)

        duration_str = f"{duration_ms / 1000:.2f} seconds"
        if duration_ms >= 120000:  # 2+ minutes
            duration_str += " (SLOW)"

        # 构建脱敏的命令，替换实际提示词
        redacted_command = command.copy()
        for i, arg in enumerate(redacted_command):
            if arg == '-p' and i + 1 < len(redacted_command):
                redacted_command[i + 1] = '[REDACTED_PROMPT]'
                break

        log_entry = f"""
{'=' * 80}
[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] AI COMMAND: {provider.upper()}
{'=' * 80}
Status:     {status_icon}
Directory:  {directory}
Model:      {command[2] if len(command) > 2 and command[1] == '-m' else 'default'}
Duration:   {duration_str}
Prompt:     [{prompt_size} chars] {prompt_preview}
Response:   [{response_size} chars]
Hash:       {prompt_hash}
Command:    {' '.join(redacted_command)}"""

        if not success and error_msg:
            log_entry += f"\nError:      {error_msg}"

        log_entry += "\n" + "-" * 80 + "\n"

        return log_entry

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
        prompt: str = "",
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
            prompt: 完整提示词内容（用于可读格式日志）
        """
        logger = self.get_logger("ai_commands")
        duration_ms = int((time.time() - start_time) * 1000)

        # 根据配置选择日志格式
        if hasattr(self, 'ai_log_format') and self.ai_log_format == "readable":
            # 使用人类可读格式
            readable_log = self._format_readable_ai_log(
                provider=provider,
                command=command,
                prompt=prompt,
                directory=directory,
                success=success,
                duration_ms=duration_ms,
                prompt_size=prompt_size,
                response_size=response_size,
                error_msg=error_msg,
            )

            if success:
                logger.info(readable_log)
            else:
                logger.error(readable_log)
        else:
            # 使用原有的 JSON 格式
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

        # 记录详细的 JSONL 格式（如果启用）
        if hasattr(self, 'ai_log_detail_level') and self.ai_log_detail_level == "full":
            detailed_logger = self.get_logger("ai_commands_detailed")
            if detailed_logger:
                detailed_data = {
                    "timestamp": datetime.now().isoformat(),
                    "provider": provider,
                    "status": "success" if success else "failed",
                    "directory": directory,
                    "model": command[2] if len(command) > 2 and command[1] == '-m' else 'default',
                    "prompt_hash": self._hash_prompt(prompt) if prompt else "",
                    "prompt_preview": self._truncate_prompt(prompt, 100) if prompt else "",
                    "prompt_size": prompt_size,
                    "response_size": response_size,
                    "duration_ms": duration_ms,
                }

                if not success and error_msg:
                    detailed_data["error"] = error_msg

                detailed_json = json.dumps(detailed_data, ensure_ascii=False, separators=(",", ":"))
                detailed_logger.info(detailed_json)

        # 同时记录错误到错误日志
        if not success:
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