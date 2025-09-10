"""
Digin - AI-powered codebase archaeology tool
CLI entry point
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich.text import Text

from .config import ConfigManager
from .analyzer import CodebaseAnalyzer, AnalysisError
from .__version__ import __version__

console = Console()


def print_banner() -> None:
    """Display the application banner."""
    banner_text = """
🔍 [bold blue]Digin[/bold blue] - AI-powered codebase archaeology tool
[dim]Deep dive into your code and understand it like never before[/dim]
    """
    console.print(Panel(banner_text.strip(), style="blue"))


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")
@click.option(
    "--provider", "-p",
    type=click.Choice(["claude", "gemini"], case_sensitive=False),
    help="AI provider to use for analysis"
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom configuration file"
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Force refresh, ignore cache"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be analyzed without running"
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "tree", "summary"], case_sensitive=False),
    default="summary",
    help="Output format"
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Suppress non-essential output"
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear cache before analysis"
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
) -> None:
    """
    Analyze a codebase and generate structured understanding.
    
    PATH: Directory to analyze (defaults to current directory)
    """
    try:
        # Configure console
        if quiet:
            console.quiet = True
        
        if not quiet:
            print_banner()
        
        # Load configuration
        config_manager = ConfigManager(config_file=config)
        settings = config_manager.load_config()
        
        # Override settings with CLI options
        if provider:
            settings.api_provider = provider.lower()
        if verbose:
            settings.verbose = True
        if force:
            settings.cache_enabled = False
        
        if verbose and not quiet:
            console.print(f"[dim]Analyzing: {path.absolute()}[/dim]")
            console.print(f"[dim]Provider: {settings.api_provider}[/dim]")
            console.print(f"[dim]Cache enabled: {settings.cache_enabled}[/dim]")
        
        # Validate target directory
        if not path.is_dir():
            console.print(f"[red]Error: {path} is not a directory[/red]")
            sys.exit(1)
        
        # Initialize analyzer
        analyzer = CodebaseAnalyzer(settings)
        
        # Clear cache if requested
        if clear_cache:
            analyzer.clear_cache(path)
            if not quiet:
                console.print("[yellow]Cache cleared[/yellow]")
        
        # Check AI CLI availability
        if not analyzer.ai_client.is_available():
            console.print(
                f"[red]Error: {settings.api_provider} CLI not found.[/red]\n"
                f"Please install the {settings.api_provider} CLI tool."
            )
            sys.exit(1)
        
        # Handle dry run
        if dry_run:
            _show_dry_run(analyzer, path, verbose)
            return
        
        # Run analysis
        if not quiet:
            console.print(f"\n[bold]Starting analysis of [green]{path.name}[/green]...[/bold]")
        
        # Progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn() if not verbose else BarColumn(bar_width=None),
            TaskProgressColumn(),
            console=console,
            disable=quiet or verbose,
        ) as progress:
            task = progress.add_task("Initializing...", total=100)
            
            try:
                # Get analysis plan
                dry_run_info = analyzer.dry_run(path)
                total_dirs = dry_run_info["total_directories"]
                
                progress.update(task, description=f"Analyzing {total_dirs} directories...", total=total_dirs)
                
                # Run analysis with progress updates
                class ProgressAnalyzer(CodebaseAnalyzer):
                    def _analyze_directory(self, directory, root_path, completed_digests):
                        # Update progress
                        completed = len(completed_digests)
                        progress.update(task, completed=completed, 
                                      description=f"Analyzing {directory.name}...")
                        return super()._analyze_directory(directory, root_path, completed_digests)
                
                # Use progress-aware analyzer
                progress_analyzer = ProgressAnalyzer(settings)
                progress_analyzer.ai_client = analyzer.ai_client
                progress_analyzer.cache_manager = analyzer.cache_manager
                
                results = progress_analyzer.analyze(path)
                progress.update(task, completed=total_dirs, description="Analysis complete")
                
                # Update stats
                analyzer.stats = progress_analyzer.stats
                
            except KeyboardInterrupt:
                progress.update(task, description="Analysis interrupted")
                console.print("\n[yellow]Analysis interrupted by user[/yellow]")
                sys.exit(1)
            except AnalysisError as e:
                progress.update(task, description="Analysis failed")
                console.print(f"\n[red]Analysis failed: {e}[/red]")
                if verbose:
                    import traceback
                    console.print(f"[red]{traceback.format_exc()}[/red]")
                sys.exit(1)
        
        # Display results
        if not quiet and results:
            _display_results(results, output_format, verbose)
        
        # Show statistics
        if not quiet:
            _show_statistics(analyzer.get_analysis_stats())
        
        if not quiet:
            console.print("\n✅ [green]Analysis complete![/green]")
        
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
        sys.exit(1)


def _show_dry_run(analyzer: CodebaseAnalyzer, path: Path, verbose: bool) -> None:
    """Show dry run analysis plan."""
    console.print("\n[bold yellow]🔍 Dry Run - Analysis Plan[/bold yellow]")
    
    try:
        dry_run_info = analyzer.dry_run(path)
        
        # Create summary table
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
        
        # Show directory tree (first 10 directories)
        if verbose and dry_run_info["analysis_order"]:
            console.print("\n[bold]Analysis Order (first 10):[/bold]")
            tree = Tree(f"📁 {path.name}")
            
            for i, dir_path in enumerate(dry_run_info["analysis_order"][:10]):
                rel_path = Path(dir_path).relative_to(path) if Path(dir_path) != path else Path(".")
                if i < dry_run_info["leaf_directories"]:
                    tree.add(f"🍃 [green]{rel_path}[/green] (leaf)")
                else:
                    tree.add(f"📂 [blue]{rel_path}[/blue] (parent)")
            
            if len(dry_run_info["analysis_order"]) > 10:
                tree.add(f"[dim]... and {len(dry_run_info['analysis_order']) - 10} more[/dim]")
            
            console.print(tree)
        
        console.print(f"\n[yellow]Would analyze {dry_run_info['total_directories']} directories with {dry_run_info['leaf_directories']} AI calls[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error during dry-run: {e}[/red]")


def _display_results(results: dict, format_type: str, verbose: bool) -> None:
    """Display analysis results."""
    if not results:
        console.print("[yellow]No results to display[/yellow]")
        return
    
    console.print(f"\n[bold]📊 Analysis Results[/bold]")
    
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
            "service": "⚙️", "lib": "📚", "ui": "🎨", "infra": "🏗️",
            "config": "⚙️", "test": "🧪", "docs": "📖"
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
            "service": "bold red", "lib": "bold blue", "ui": "bold magenta",
            "infra": "bold yellow", "config": "bold cyan", "test": "bold green"
        }
        style = kind_styles.get(results["kind"], "bold white")
        console.print(f"🏷️  [blue]Type:[/blue] [{style}]{results['kind']}[/{style}]")
    
    if "capabilities" in results and results["capabilities"]:
        console.print(f"\n🎯 [yellow]Capabilities:[/yellow]")
        for cap in results["capabilities"]:
            console.print(f"   • {cap}")
    
    if "dependencies" in results and results["dependencies"]:
        deps = results["dependencies"]
        if deps.get("external"):
            console.print(f"\n📦 [cyan]External Dependencies:[/cyan]")
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
            console.print(f"\n{icon} [blue]Confidence:[/blue] [{color}]{confidence}%[/{color}]")
        
        if "risks" in results and results["risks"]:
            console.print(f"\n⚠️  [red]Potential Risks:[/red]")
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