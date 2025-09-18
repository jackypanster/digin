"""
Digin 命令行入口。

職責與業務邏輯：
- 讀取與合併配置（default.json → CLI 覆蓋）。
- 驗證目標路徑與 AI CLI 可用性（Claude/Gemini）。
- 支持 dry-run 預覽：顯示葉/父目錄數、分析順序與粗略文件量估算。
- 非 dry-run：用進度條執行“自底向上”分析，最後按 summary/tree/json 輸出並展示統計。
- 常用開關：--force 取消緩存、--clear-cache 清理緩存、--provider 切換供應商、--verbose 詳細輸出。

設計動機：將「人類上手陌生代碼」的路徑流程化、可視化，降低首次理解成本。
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from rich.tree import Tree

from .__version__ import __version__
from .ai_client import is_cli_available
from .analyzer import CodebaseAnalyzer
from .config import ConfigManager, DigginSettings
from .logger import get_logger, setup_logging

console = Console()


def print_banner() -> None:
    """Display the application banner."""
    banner_text = """
🔍 [bold blue]Digin[/bold blue] - AI-powered codebase archaeology tool
[dim]Deep dive into your code and understand it like never before[/dim]
    """
    console.print(Panel(banner_text.strip(), style="blue"))


def load_and_configure_settings(
    config_path: Optional[Path], provider: Optional[str], verbose: bool, force: bool, narrative: bool
) -> DigginSettings:
    """Load configuration and apply CLI overrides."""
    config_manager = ConfigManager(config_file=config_path)
    settings = config_manager.load_config()

    if provider:
        settings.api_provider = provider.lower()
    if verbose:
        settings.verbose = True
    if force:
        settings.cache_enabled = False
    settings.narrative_enabled = narrative

    return settings


def initialize_logging(settings: DigginSettings) -> None:
    """Initialize logging based on settings."""
    if settings.logging.enabled:
        setup_logging(
            log_dir=settings.logging.log_dir,
            log_level=settings.logging.level,
            max_file_size=settings.logging.max_file_size,
            backup_count=settings.logging.backup_count,
            log_format=settings.logging.format,
            ai_command_logging=settings.logging.ai_command_logging,
            ai_log_format=settings.logging.ai_log_format,
            ai_log_detail_level=settings.logging.ai_log_detail_level,
            ai_log_prompt_max_chars=settings.logging.ai_log_prompt_max_chars,
        )
        logger = get_logger("main")
        logger.info(f"Digin v{__version__} starting up")
        logger.info(
            f"Logging initialized: level={settings.logging.level}, dir={settings.logging.log_dir}"
        )
    else:
        # Even if disabled, we might want basic console logging for errors
        get_logger("main").info("Logging is disabled")


def validate_target_path(path: Path) -> None:
    """Validate that target path is a directory."""
    if not path.is_dir():
        console.print(f"[red]Error: {path} is not a directory[/red]")
        sys.exit(1)


def show_dry_run_plan(analyzer: CodebaseAnalyzer, path: Path, verbose: bool) -> None:
    """Show dry run analysis plan."""
    console.print("\n[bold yellow]🔍 Dry Run - Analysis Plan[/bold yellow]")

    try:
        dry_run_info = analyzer.dry_run(path)
        _display_dry_run_table(dry_run_info)
        _display_dry_run_tree(dry_run_info, path, verbose)
        _display_dry_run_summary(dry_run_info)

    except Exception as e:
        console.print(f"[red]Error during dry-run: {e}[/red]")


def _display_dry_run_table(dry_run_info: dict) -> None:
    """Display dry run overview table."""
    table = Table(title="Analysis Overview", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim", width=20)
    table.add_column("Value", style="bold")

    table.add_row("Total Directories", str(dry_run_info["total_directories"]))
    table.add_row("Leaf Directories", str(dry_run_info["leaf_directories"]))
    table.add_row("Parent Directories", str(dry_run_info["parent_directories"]))
    table.add_row("Estimated Files", str(dry_run_info["estimated_files"]))
    table.add_row("AI Provider", dry_run_info["ai_provider"])
    table.add_row("Cache Enabled", "Yes" if dry_run_info["cache_enabled"] else "No")

    console.print(table)


def _display_dry_run_tree(dry_run_info: dict, path: Path, verbose: bool) -> None:
    """Display analysis order tree if verbose."""
    if not (verbose and dry_run_info["analysis_order"]):
        return

    console.print("\n[bold]Analysis Order (first 10):[/bold]")
    tree = Tree(f"📁 {path.name}")

    for i, dir_path in enumerate(dry_run_info["analysis_order"][:10]):
        rel_path = (
            Path(dir_path).relative_to(path) if Path(dir_path) != path else Path(".")
        )
        if i < dry_run_info["leaf_directories"]:
            tree.add(f"🍃 [green]{rel_path}[/green] (leaf)")
        else:
            tree.add(f"📂 [blue]{rel_path}[/blue] (parent)")

    if len(dry_run_info["analysis_order"]) > 10:
        tree.add(f"[dim]... and {len(dry_run_info['analysis_order']) - 10} more[/dim]")

    console.print(tree)


def _display_dry_run_summary(dry_run_info: dict) -> None:
    """Display dry run summary."""
    total_dirs = dry_run_info["total_directories"]
    leaf_dirs = dry_run_info["leaf_directories"]
    console.print(
        f"\n[yellow]Would analyze {total_dirs} directories "
        f"with {leaf_dirs} AI calls[/yellow]"
    )


def run_analysis_with_progress(
    analyzer: CodebaseAnalyzer, path: Path, quiet: bool, verbose: bool
) -> Dict[str, Any]:
    """Execute analysis with progress tracking."""
    if not quiet:
        console.print(
            f"\n[bold]Starting analysis of [green]{path.name}[/green]...[/bold]"
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn() if not verbose else BarColumn(bar_width=None),
        TaskProgressColumn(),
        console=console,
        disable=quiet or verbose,
    ) as progress:
        task = progress.add_task("Initializing...", total=100)

        # Get analysis plan
        dry_run_info = analyzer.dry_run(path)
        total_dirs = dry_run_info["total_directories"]
        progress.update(
            task, description=f"Analyzing {total_dirs} directories...", total=total_dirs
        )

        # Create progress-aware analyzer
        progress_analyzer = _create_progress_analyzer(analyzer, progress, task)

        # Execute analysis
        results = progress_analyzer.analyze(path)
        progress.update(task, completed=total_dirs, description="Analysis complete")

        # Transfer stats back to original analyzer
        analyzer.stats = progress_analyzer.stats

        return results


def _create_progress_analyzer(
    analyzer: CodebaseAnalyzer, progress: Progress, task
) -> CodebaseAnalyzer:
    """Create analyzer that updates progress during analysis."""

    class ProgressAnalyzer(CodebaseAnalyzer):
        def _analyze_directory(self, directory, root_path, completed_digests):
            completed = len(completed_digests)
            progress.update(
                task, completed=completed, description=f"Analyzing {directory.name}..."
            )
            return super()._analyze_directory(directory, root_path, completed_digests)

    progress_analyzer = ProgressAnalyzer(analyzer.settings)
    progress_analyzer.cache_manager = analyzer.cache_manager

    return progress_analyzer


def load_and_validate_config(
    config: Optional[Path], provider: Optional[str], verbose: bool, force: bool, narrative: bool
) -> DigginSettings:
    """Load configuration and validate settings."""
    settings = load_and_configure_settings(config, provider, verbose, force, narrative)
    initialize_logging(settings)
    return settings


def validate_environment(
    path: Path, settings: DigginSettings, verbose: bool, quiet: bool
) -> None:
    """Validate target path and log environment info."""
    validate_target_path(path)
    logger = get_logger("main")
    logger.info(f"Target path validated: {path.absolute()}")

    if verbose and not quiet:
        console.print(f"[dim]Analyzing: {path.absolute()}[/dim]")
        console.print(f"[dim]Provider: {settings.api_provider}[/dim]")
        console.print(f"[dim]Cache enabled: {settings.cache_enabled}[/dim]")


def execute_dry_run(analyzer: CodebaseAnalyzer, path: Path, verbose: bool) -> None:
    """Execute dry run analysis and display plan."""
    logger = get_logger("main")
    logger.info("Running in dry-run mode")
    show_dry_run_plan(analyzer, path, verbose)


def execute_analysis(
    analyzer: CodebaseAnalyzer, path: Path, quiet: bool, verbose: bool
) -> Dict[str, Any]:
    """Execute full analysis with progress tracking."""
    logger = get_logger("main")
    logger.info("Starting full analysis")
    results = run_analysis_with_progress(analyzer, path, quiet, verbose)
    logger.info("Analysis completed successfully")
    return results


def display_results(
    results: Dict[str, Any],
    output_format: str,
    verbose: bool,
    analyzer: CodebaseAnalyzer,
    quiet: bool,
) -> None:
    """Display analysis results and statistics."""
    if not quiet and results:
        _display_results(results, output_format, verbose)

    if not quiet:
        _show_statistics(analyzer.get_analysis_stats())
        console.print("\n✅ [green]Analysis complete![/green]")


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["claude", "gemini"], case_sensitive=False),
    help="AI provider to use for analysis",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom configuration file",
)
@click.option("--force", "-f", is_flag=True, help="Force refresh, ignore cache")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be analyzed without running"
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "tree", "summary"], case_sensitive=False),
    default="summary",
    help="Output format",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.option("--clear-cache", is_flag=True, help="Clear cache before analysis")
@click.option(
    "--narrative/--no-narrative",
    default=True,
    help="Enable/disable narrative summaries for conversational style output",
)
@click.version_option(version=__version__, prog_name="digin")
def main(
    path: Path,
    provider: Optional[str],
    config: Optional[Path],
    force: bool,
    verbose: bool,
    dry_run: bool,
    output_format: str,
    quiet: bool,
    clear_cache: bool,
    narrative: bool,
) -> None:
    """
    Analyze a codebase and generate structured understanding.

    PATH: Directory to analyze (defaults to current directory)
    """
    try:
        if not quiet:
            print_banner()

        settings = load_and_validate_config(config, provider, verbose, force, narrative)
        validate_environment(path, settings, verbose, quiet)

        analyzer = setup_analyzer(settings, path, clear_cache, quiet)

        if dry_run:
            execute_dry_run(analyzer, path, verbose)
            return

        results = execute_analysis(analyzer, path, quiet, verbose)
        display_results(results, output_format, verbose, analyzer, quiet)

    except Exception as e:
        error_msg = f"Fatal error: {e}"
        console.print(f"[red]{error_msg}[/red]")

        if "logger" in locals():
            get_logger("main").error(error_msg)

        if verbose:
            import traceback

            traceback_str = traceback.format_exc()
            console.print(f"[red]{traceback_str}[/red]")
            if "logger" in locals():
                get_logger("main").error(f"Full traceback: {traceback_str}")
        sys.exit(1)


def setup_analyzer(
    settings: DigginSettings, path: Path, clear_cache: bool, quiet: bool
) -> CodebaseAnalyzer:
    """Initialize and configure analyzer."""
    analyzer = CodebaseAnalyzer(settings)

    if clear_cache:
        analyzer.clear_cache(path)
        if not quiet:
            console.print("[yellow]Cache cleared[/yellow]")

    if not is_cli_available(settings.api_provider):
        console.print(
            f"[red]Error: {settings.api_provider} CLI not found.[/red]\n"
            f"Please install the {settings.api_provider} CLI tool."
        )
        sys.exit(1)

    return analyzer


def _display_results(results: dict, format_type: str, verbose: bool) -> None:
    """Display analysis results."""
    if not results:
        console.print("[yellow]No results to display[/yellow]")
        return

    console.print("\n[bold]📊 Analysis Results[/bold]")

    if format_type == "json":
        import json

        console.print_json(json.dumps(results, indent=2, ensure_ascii=False))

    elif format_type == "tree":
        _display_results_as_tree(results)

    else:  # summary
        _display_results_summary(results, verbose)


def _display_results_as_tree(results: dict) -> None:
    """Display results as tree structure."""
    project_name = results.get("name", "Project")
    tree = Tree(f"📁 [bold]{project_name}[/bold]")

    if "summary" in results:
        tree.add(f"📝 [green]Summary:[/green] {results['summary']}")

    if "kind" in results:
        kind_emoji = {
            "service": "⚙️",
            "lib": "📚",
            "ui": "🎨",
            "infra": "🏗️",
            "config": "⚙️",
            "test": "🧪",
            "docs": "📖",
        }
        emoji = kind_emoji.get(results["kind"], "❓")
        tree.add(f"{emoji} [blue]Type:[/blue] {results['kind']}")

    if "capabilities" in results and results["capabilities"]:
        caps_node = tree.add("🎯 [yellow]Capabilities:[/yellow]")
        for cap in results["capabilities"][:5]:  # Show first 5
            caps_node.add(f"• {cap}")

    if "dependencies" in results:
        deps = results["dependencies"]
        if deps.get("external"):
            deps_node = tree.add("📦 [cyan]External Dependencies:[/cyan]")
            for dep in deps["external"][:5]:  # Show first 5
                deps_node.add(f"• {dep}")

    console.print(tree)


def _display_results_summary(results: dict, verbose: bool) -> None:
    """Display results as formatted summary."""
    if "name" in results:
        console.print(f"📁 [bold blue]{results['name']}[/bold blue]")

    if "summary" in results:
        console.print(f"\n📝 [green]Summary:[/green] {results['summary']}")

    if "kind" in results:
        kind_styles = {
            "service": "bold red",
            "lib": "bold blue",
            "ui": "bold magenta",
            "infra": "bold yellow",
            "config": "bold cyan",
            "test": "bold green",
        }
        style = kind_styles.get(results["kind"], "bold white")
        console.print(f"🏷️  [blue]Type:[/blue] [{style}]{results['kind']}[/{style}]")

    if "capabilities" in results and results["capabilities"]:
        console.print("\n🎯 [yellow]Capabilities:[/yellow]")
        for cap in results["capabilities"]:
            console.print(f"   • {cap}")

    if "dependencies" in results and results["dependencies"]:
        deps = results["dependencies"]
        if deps.get("external"):
            console.print("\n📦 [cyan]External Dependencies:[/cyan]")
            for dep in deps["external"][:10]:  # Show first 10
                console.print(f"   • {dep}")

    if verbose:
        if "confidence" in results:
            confidence = results["confidence"]
            if confidence >= 80:
                color = "green"
                icon = "✅"
            elif confidence >= 60:
                color = "yellow"
                icon = "⚠️"
            else:
                color = "red"
                icon = "❌"
            console.print(
                f"\n{icon} [blue]Confidence:[/blue] [{color}]{confidence}%[/{color}]"
            )

        if "risks" in results and results["risks"]:
            console.print("\n⚠️  [red]Potential Risks:[/red]")
            for risk in results["risks"][:5]:
                console.print(f"   • {risk}")


def _show_statistics(stats: dict) -> None:
    """Show analysis statistics."""
    if not stats:
        return

    # Create stats table
    table = Table(title="📈 Analysis Statistics", show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")

    if stats.get("directories_analyzed"):
        table.add_row("Directories analyzed", str(stats["directories_analyzed"]))

    if stats.get("total_files"):
        table.add_row("Files processed", str(stats["total_files"]))

    if stats.get("ai_calls"):
        table.add_row("AI calls made", str(stats["ai_calls"]))

    if stats.get("cache_hits") or stats.get("cache_misses"):
        cache_rate = stats.get("cache_hit_rate", 0)
        table.add_row("Cache hit rate", f"{cache_rate:.1f}%")

    if stats.get("duration_seconds"):
        duration = stats["duration_seconds"]
        if duration < 60:
            table.add_row("Duration", f"{duration:.1f} seconds")
        else:
            table.add_row("Duration", f"{duration/60:.1f} minutes")

    if stats.get("errors"):
        table.add_row("Errors", str(stats["errors"]))

    console.print(table)


if __name__ == "__main__":
    main()
