#!/usr/bin/env python3
"""
AI 命令日志分析工具

分析 Digin 的 AI 命令日志文件，生成统计报告和成本分析。

Usage:
    python scripts/analyze_logs.py [logs_dir]
    python scripts/analyze_logs.py logs/ --output stats.json
    python scripts/analyze_logs.py logs/ --provider gemini --csv costs.csv
"""

import argparse
import csv
import json
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys


class LogAnalyzer:
    """AI 命令日志分析器。"""

    def __init__(self, logs_dir: str):
        """初始化日志分析器。

        Args:
            logs_dir: 日志目录路径
        """
        self.logs_dir = Path(logs_dir)
        self.stats = {
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0,
            "providers": Counter(),
            "models": Counter(),
            "directories": Counter(),
            "total_prompt_chars": 0,
            "total_response_chars": 0,
            "total_duration_ms": 0,
            "average_duration_ms": 0,
            "commands_by_hour": defaultdict(int),
            "commands_by_day": defaultdict(int),
            "slow_commands": [],  # Commands over 60 seconds
            "errors": Counter(),
        }
        self.commands = []

    def analyze(self) -> Dict[str, Any]:
        """执行日志分析。

        Returns:
            分析结果字典
        """
        # 分析 JSONL 详细日志（如果存在）
        jsonl_file = self.logs_dir / "ai_commands_detailed.jsonl"
        if jsonl_file.exists():
            self._analyze_jsonl_log(jsonl_file)
        else:
            # 分析人类可读格式日志
            readable_file = self.logs_dir / "ai_commands.log"
            if readable_file.exists():
                self._analyze_readable_log(readable_file)

        # 计算统计信息
        self._calculate_stats()
        return self.stats

    def _analyze_jsonl_log(self, log_file: Path) -> None:
        """分析 JSONL 格式的详细日志。"""
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    command = json.loads(line)
                    self.commands.append(command)
                    self._update_stats_from_command(command)
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse JSONL line: {e}")

    def _analyze_readable_log(self, log_file: Path) -> None:
        """分析人类可读格式的日志。"""
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 使用正则表达式解析可读格式的日志
        pattern = r"""
            \[([^\]]+)\]\s+AI\s+COMMAND:\s+(\w+).*?
            Status:\s+([^\\n]+).*?
            Directory:\s+([^\\n]+).*?
            Model:\s+([^\\n]+).*?
            Duration:\s+([^\\n]+).*?
            Prompt:\s+\[(\d+)\s+chars\].*?
            Response:\s+\[(\d+)\s+chars\].*?
            Hash:\s+([^\\n]+).*?
            (?:Error:\s+([^\\n]+))?
        """

        matches = re.findall(pattern, content, re.DOTALL | re.VERBOSE)
        for match in matches:
            timestamp_str, provider, status, directory, model, duration_str, prompt_size, response_size, hash_val, error = match

            # 解析时间戳
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    timestamp = datetime.now()

            # 解析持续时间
            duration_ms = 0
            if "seconds" in duration_str:
                seconds = float(duration_str.split()[0])
                duration_ms = int(seconds * 1000)

            command = {
                "timestamp": timestamp.isoformat(),
                "provider": provider.lower(),
                "status": "success" if "SUCCESS" in status else "failed",
                "directory": directory,
                "model": model,
                "prompt_size": int(prompt_size),
                "response_size": int(response_size),
                "duration_ms": duration_ms,
                "prompt_hash": hash_val,
                "error": error if error else None,
            }

            self.commands.append(command)
            self._update_stats_from_command(command)

    def _update_stats_from_command(self, command: Dict[str, Any]) -> None:
        """从命令数据更新统计信息。"""
        self.stats["total_commands"] += 1

        if command["status"] == "success":
            self.stats["successful_commands"] += 1
        else:
            self.stats["failed_commands"] += 1
            if command.get("error"):
                self.stats["errors"][command["error"]] += 1

        self.stats["providers"][command["provider"]] += 1
        self.stats["models"][command.get("model", "default")] += 1
        self.stats["directories"][command["directory"]] += 1

        self.stats["total_prompt_chars"] += command.get("prompt_size", 0)
        self.stats["total_response_chars"] += command.get("response_size", 0)
        self.stats["total_duration_ms"] += command.get("duration_ms", 0)

        # 时间分析
        try:
            timestamp = datetime.fromisoformat(command["timestamp"])
            hour_key = timestamp.strftime("%H")
            day_key = timestamp.strftime("%Y-%m-%d")
            self.stats["commands_by_hour"][hour_key] += 1
            self.stats["commands_by_day"][day_key] += 1
        except (ValueError, KeyError):
            pass

        # 慢命令检测
        if command.get("duration_ms", 0) > 60000:  # > 60 seconds
            self.stats["slow_commands"].append({
                "directory": command["directory"],
                "provider": command["provider"],
                "duration_ms": command["duration_ms"],
                "timestamp": command["timestamp"],
            })

    def _calculate_stats(self) -> None:
        """计算派生统计信息。"""
        if self.stats["total_commands"] > 0:
            self.stats["average_duration_ms"] = (
                self.stats["total_duration_ms"] / self.stats["total_commands"]
            )
            self.stats["success_rate"] = (
                self.stats["successful_commands"] / self.stats["total_commands"]
            )
        else:
            self.stats["average_duration_ms"] = 0
            self.stats["success_rate"] = 0

        # 转换 Counter 对象为普通字典
        self.stats["providers"] = dict(self.stats["providers"])
        self.stats["models"] = dict(self.stats["models"])
        self.stats["directories"] = dict(self.stats["directories"])
        self.stats["errors"] = dict(self.stats["errors"])

    def generate_report(self) -> str:
        """生成人类可读的分析报告。"""
        report = []
        report.append("=" * 60)
        report.append("AI 命令日志分析报告")
        report.append("=" * 60)

        # 基本统计
        report.append(f"总命令数: {self.stats['total_commands']}")
        report.append(f"成功命令: {self.stats['successful_commands']}")
        report.append(f"失败命令: {self.stats['failed_commands']}")
        report.append(f"成功率: {self.stats['success_rate']:.1%}")
        report.append("")

        # 性能统计
        avg_duration = self.stats["average_duration_ms"] / 1000
        total_duration = self.stats["total_duration_ms"] / 1000
        report.append(f"平均执行时间: {avg_duration:.2f} 秒")
        report.append(f"总执行时间: {total_duration:.2f} 秒")
        report.append(f"慢命令数 (>60s): {len(self.stats['slow_commands'])}")
        report.append("")

        # 使用统计
        report.append("AI 提供商使用情况:")
        for provider, count in self.stats["providers"].items():
            percentage = (count / self.stats["total_commands"]) * 100
            report.append(f"  {provider}: {count} ({percentage:.1f}%)")
        report.append("")

        report.append("模型使用情况:")
        for model, count in sorted(self.stats["models"].items(), key=lambda x: x[1], reverse=True)[:5]:
            percentage = (count / self.stats["total_commands"]) * 100
            report.append(f"  {model}: {count} ({percentage:.1f}%)")
        report.append("")

        # 错误统计
        if self.stats["errors"]:
            report.append("主要错误类型:")
            for error, count in sorted(self.stats["errors"].items(), key=lambda x: x[1], reverse=True)[:5]:
                report.append(f"  {error}: {count}")
            report.append("")

        # 使用模式
        report.append("每小时使用分布:")
        for hour in sorted(self.stats["commands_by_hour"].keys()):
            count = self.stats["commands_by_hour"][hour]
            bar = "█" * (count // max(1, max(self.stats["commands_by_hour"].values()) // 20))
            report.append(f"  {hour}:00 - {count:3d} {bar}")

        return "\\n".join(report)

    def export_csv(self, output_file: Path) -> None:
        """导出命令数据为 CSV 格式。"""
        if not self.commands:
            print("No commands to export")
            return

        fieldnames = [
            "timestamp", "provider", "status", "directory", "model",
            "prompt_size", "response_size", "duration_ms", "duration_seconds", "error"
        ]

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for command in self.commands:
                row = command.copy()
                row["duration_seconds"] = command.get("duration_ms", 0) / 1000
                writer.writerow(row)

        print(f"Exported {len(self.commands)} commands to {output_file}")

    def estimate_costs(self) -> Dict[str, Any]:
        """估算 AI 使用成本。

        Returns:
            成本估算字典
        """
        # 简化的成本估算（实际价格可能不同）
        cost_per_1k_chars = {
            "gemini": {"input": 0.00015, "output": 0.0006},  # Gemini 1.5 Pro 估算
            "claude": {"input": 0.003, "output": 0.015},    # Claude 3 Sonnet 估算
        }

        costs = {"total": 0, "by_provider": {}}

        for command in self.commands:
            provider = command.get("provider", "unknown")
            if provider not in cost_per_1k_chars:
                continue

            input_cost = (command.get("prompt_size", 0) / 1000) * cost_per_1k_chars[provider]["input"]
            output_cost = (command.get("response_size", 0) / 1000) * cost_per_1k_chars[provider]["output"]
            command_cost = input_cost + output_cost

            costs["total"] += command_cost
            if provider not in costs["by_provider"]:
                costs["by_provider"][provider] = {"cost": 0, "commands": 0}
            costs["by_provider"][provider]["cost"] += command_cost
            costs["by_provider"][provider]["commands"] += 1

        return costs


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description="分析 AI 命令日志")
    parser.add_argument("logs_dir", nargs="?", default="logs", help="日志目录路径")
    parser.add_argument("--output", "-o", help="输出 JSON 统计文件")
    parser.add_argument("--csv", help="导出 CSV 文件")
    parser.add_argument("--provider", help="过滤特定 AI 提供商")
    parser.add_argument("--costs", action="store_true", help="显示成本估算")

    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    if not logs_dir.exists():
        print(f"Error: Logs directory {logs_dir} does not exist")
        sys.exit(1)

    print(f"Analyzing logs in: {logs_dir}")
    analyzer = LogAnalyzer(str(logs_dir))
    stats = analyzer.analyze()

    if stats["total_commands"] == 0:
        print("No AI commands found in logs")
        return

    # 显示报告
    print(analyzer.generate_report())

    # 成本估算
    if args.costs:
        costs = analyzer.estimate_costs()
        print("\\n" + "=" * 60)
        print("成本估算 (USD)")
        print("=" * 60)
        print(f"总估算成本: ${costs['total']:.4f}")
        for provider, data in costs["by_provider"].items():
            avg_cost = data["cost"] / data["commands"] if data["commands"] > 0 else 0
            print(f"{provider}: ${data['cost']:.4f} ({data['commands']} 命令, 平均 ${avg_cost:.4f}/命令)")

    # 导出文件
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"\\nStats exported to: {args.output}")

    if args.csv:
        analyzer.export_csv(Path(args.csv))


if __name__ == "__main__":
    main()