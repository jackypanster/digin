"""
Digin - AI-powered codebase archaeology tool
CLI entry point
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.tree import Tree

from . import analyzer
from . import config as cfg
from . import __version__

console = Console()


def print_banner():
    """Display the application banner"""
    banner_text = """
= [bold blue]Digin[/bold blue] - AI-powered codebase archaeology tool
[dim]Deep dive into your code and understand it like never before[/dim]
    """
    console.print(Panel(banner_text.strip(), style="blue"))


def print_version():
    """Display version information"""
    console.print(f"[bold]digin[/bold] version [green]{__version__.__version__}[/green]")


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["claude", "gemini"], case_sensitive=False),
    default="claude",
    help="AI provider to use for analysis (claude or gemini)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom configuration file",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force refresh, ignore cache",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be analyzed without actually running",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "tree", "summary"], case_sensitive=False),
    default="summary",
    help="Output format",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress non-essential output",
)
@click.version_option(version=__version__.__version__, prog_name="digin")
def main(
    path: Path,
    provider: str,
    config: Optional[Path],
    force: bool,
    verbose: bool,
    dry_run: bool,
    output_format: str,
    quiet: bool,
) -> None:
    """
    Analyze a codebase and generate structured understanding.
    
    PATH: Directory to analyze (defaults to current directory)
    """
    try:
        # Configure console output
        if quiet:
            console.quiet = True
        
        if not quiet:
            print_banner()
        
        if verbose:
            console.print(f"[dim]Analyzing path: {path.absolute()}[/dim]")
            console.print(f"[dim]Provider: {provider}[/dim]")
            console.print(f"[dim]Force refresh: {force}[/dim]")
        
        # Load configuration
        config_manager = cfg.ConfigManager(config_file=config)
        settings = config_manager.load_config()
        
        # Override settings with CLI options
        if provider:
            settings.api_provider = provider.lower()
        if verbose:
            settings.verbose = True
        if force:
            settings.cache_enabled = False
        
        # Validate target directory
        if not path.is_dir():
            console.print(f"[red]Error: {path} is not a directory[/red]")
            sys.exit(1)
        
        # Check if AI CLI tool is available
        if not _check_ai_cli_available(settings.api_provider):
            console.print(
                f"[red]Error: {settings.api_provider} CLI not found. "
                f"Please install {settings.api_provider} CLI tool.[/red]"
            )
            sys.exit(1)
        
        if verbose:
            console.print(f"[dim]Configuration loaded successfully[/dim]")
        
        # Initialize analyzer
        code_analyzer = analyzer.CodebaseAnalyzer(settings)
        
        if dry_run:
            _show_dry_run(code_analyzer, path, verbose)
            return
        
        # Run analysis
        if not quiet:
            console.print(f"\n[bold]Starting analysis of [green]{path.name}[/green]...[/bold]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=quiet or verbose,
        ) as progress:
            task = progress.add_task("Analyzing codebase...", total=None)
            
            try:
                results = code_analyzer.analyze(path)
                progress.update(task, description="Analysis complete")
            except KeyboardInterrupt:
                progress.update(task, description="Analysis interrupted")
                console.print("\n[yellow]Analysis interrupted by user[/yellow]")
                sys.exit(1)
            except Exception as e:
                progress.update(task, description="Analysis failed")
                console.print(f"\n[red]Analysis failed: {e}[/red]")
                if verbose:
                    import traceback
                    console.print(f"[red]{traceback.format_exc()}[/red]")
                sys.exit(1)
        
        # Display results
        if not quiet:
            _display_results(results, output_format, verbose)
        
        # Show summary statistics
        if not quiet and results:
            _show_statistics(results)
        
        console.print("\n[green] Analysis complete![/green]")
        
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
        sys.exit(1)


def _check_ai_cli_available(provider: str) -> bool:
    """Check if the specified AI CLI tool is available"""
    import subprocess
    
    try:
        result = subprocess.run(
            [provider, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _show_dry_run(analyzer: "analyzer.CodebaseAnalyzer", path: Path, verbose: bool) -> None:
    """Show what would be analyzed in dry-run mode"""
    console.print("\n[bold yellow]= Dry Run - Analysis Plan[/bold yellow]")
    
    try:
        # Get directories that would be analyzed
        traverser = analyzer.get_traverser()
        directories = traverser.get_analysis_order(path)
        
        tree = Tree(f"[bold]{path.name}[/bold] ([dim]{len(directories)} directories[/dim])")
        
        for directory in directories[:10]:  # Show first 10
            rel_path = directory.relative_to(path)
            tree.add(f"[green]{rel_path}[/green]")
        
        if len(directories) > 10:
            tree.add(f"[dim]... and {len(directories) - 10} more directories[/dim]")
        
        console.print(tree)
        
        if verbose:
            console.print(f"\n[dim]Configuration:[/dim]")
            settings = analyzer.settings
            console.print(f"  Provider: [cyan]{settings.api_provider}[/cyan]")
            console.print(f"  Cache enabled: [cyan]{settings.cache_enabled}[/cyan]")
            console.print(f"  Ignored directories: [dim]{', '.join(settings.ignore_dirs)}[/dim]")
        
        console.print(f"\n[yellow]Would analyze {len(directories)} directories[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error during dry-run: {e}[/red]")


def _display_results(results: dict, format_type: str, verbose: bool) -> None:
    """Display analysis results in the specified format"""
    if not results:
        console.print("[yellow]No results to display[/yellow]")
        return
    
    console.print(f"\n[bold]Analysis Results[/bold]")
    
    if format_type == "json":
        import json
        console.print_json(json.dumps(results, indent=2, ensure_ascii=False))
    
    elif format_type == "tree":
        _display_results_as_tree(results)
    
    else:  # summary
        _display_results_summary(results, verbose)


def _display_results_as_tree(results: dict) -> None:
    """Display results as a tree structure"""
    tree = Tree(f"[bold]{results.get('name', 'Project')}[/bold]")
    
    if "summary" in results:
        tree.add(f"[green]Summary:[/green] {results['summary']}")
    
    if "kind" in results:
        tree.add(f"[blue]Type:[/blue] {results['kind']}")
    
    if "capabilities" in results and results["capabilities"]:
        capabilities_node = tree.add("[yellow]Capabilities:[/yellow]")
        for cap in results["capabilities"][:5]:  # Show first 5
            capabilities_node.add(f"" {cap}")
    
    console.print(tree)


def _display_results_summary(results: dict, verbose: bool) -> None:
    """Display results as a formatted summary"""
    if "name" in results:
        console.print(f"[bold blue]=Á {results['name']}[/bold blue]")
    
    if "summary" in results:
        console.print(f"[green]Summary:[/green] {results['summary']}")
    
    if "kind" in results:
        console.print(f"[blue]Type:[/blue] [cyan]{results['kind']}[/cyan]")
    
    if "capabilities" in results and results["capabilities"]:
        console.print(f"[yellow]Capabilities:[/yellow]")
        for cap in results["capabilities"]:
            console.print(f"  " {cap}")
    
    if verbose and "confidence" in results:
        confidence = results["confidence"]
        color = "green" if confidence >= 80 else "yellow" if confidence >= 60 else "red"
        console.print(f"[{color}]Confidence:[/{color}] {confidence}%")


def _show_statistics(results: dict) -> None:
    """Show analysis statistics"""
    stats = []
    
    if "analyzed_at" in results:
        stats.append(f"Analyzed: {results['analyzed_at']}")
    
    if "evidence" in results and "files" in results["evidence"]:
        file_count = len(results["evidence"]["files"])
        stats.append(f"Files analyzed: {file_count}")
    
    if stats:
        console.print(f"\n[dim]{' | '.join(stats)}[/dim]")


if __name__ == "__main__":
    main()