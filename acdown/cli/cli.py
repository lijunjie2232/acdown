"""ACDown Client - Command-line download client for ACDown Server."""

import asyncio
import time
from pathlib import Path
from traceback import print_exc
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from acdown.auth import AuthManager
from acdown.downloader import Downloader
from acdown.utils import validate_url, format_size, format_duration, setup_logging

app = typer.Typer(
    name="acdown",
    help="A command-line download client for ACDown Server",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def get_auth_manager() -> AuthManager:
    """Get authentication manager instance."""
    return AuthManager()


def check_server_url_configured(auth_manager: AuthManager) -> bool:
    """Check if server URL is configured and prompt user if not.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if URL is configured, False otherwise
    """
    if not auth_manager.is_server_url_configured():
        console.print("[yellow]⚠ Server URL not configured[/yellow]")
        console.print("\nPlease configure your ACDown server URL first:")
        console.print("  [cyan]acdown config set server_url http://your-server:3000[/cyan]\n")
        console.print("Example:")
        console.print("  [cyan]acdown config set server_url http://localhost:3000[/cyan]\n")
        return False
    return True


@app.command()
def download(
    url: str = typer.Argument(..., help="URL to download"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: extract from URL)"
    ),
    concurrent: Optional[int] = typer.Option(
        None, "--concurrent", "-c", help="Number of concurrent downloads (default: from config or 3)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    individual_progress: bool = typer.Option(
        False, "--individual-progress", "-ip", help="Show individual progress for each download thread"
    ),
):
    """Download a file from URL using ACDown Server."""
    
    # Setup logging
    logger = setup_logging(verbose)
    
    auth_manager = get_auth_manager()
    
    # Check if server URL is configured
    if not check_server_url_configured(auth_manager):
        raise typer.Exit(code=1)
    
    # Validate URL
    if not validate_url(url):
        console.print("[red]✗ Invalid URL[/red]")
        raise typer.Exit(code=1)
    
    # Check authentication
    if not auth_manager.is_token_valid():
        console.print("[yellow]⚠ Not authenticated. Please run 'acdown auth <code>' first.[/yellow]")
        raise typer.Exit(code=1)
    
    token = auth_manager.get_token()
    config = auth_manager.get_config()
    
    # Override config with command-line options
    if concurrent is not None:
        config['parallel'] = concurrent
    if verbose:
        config['verbose'] = True
    
    try:
        start_time = time.time()
        
        # Create downloader and start download
        downloader = Downloader(config)
        output_file = asyncio.run(downloader.download(url, output, token, show_individual_progress=individual_progress))
        
        elapsed = time.time() - start_time
        file_size = output_file.stat().st_size
        
        # Show success message
        console.print(Panel.fit(
            f"[green]✓ Download complete![/green]\n\n"
            f"[bold]File:[/bold] {output_file}\n"
            f"[bold]Size:[/bold] {format_size(file_size)}\n"
            f"[bold]Time:[/bold] {format_duration(elapsed)}\n"
            f"[bold]Average Speed:[/bold] {format_size(int(file_size / elapsed))}/s" if elapsed > 0 else "N/A",
            title="Success",
            border_style="green"
        ))
        
    except Exception as e:
        print_exc()
        console.print(f"[red]✗ Download failed[/red]")
        console.print(f"[red]  Error: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def auth(
    totp_code: str = typer.Argument(..., help="6-digit TOTP code")
):
    """Authenticate with ACDown Server using TOTP code."""
    
    auth_manager = get_auth_manager()
    
    # Check if server URL is configured
    if not check_server_url_configured(auth_manager):
        raise typer.Exit(code=1)
    
    try:
        result = asyncio.run(auth_manager.login(totp_code))
        
        config = auth_manager.get_config()
        server_url = config.get('server_url', '')
        expires_at = result['expiresAt']
        
        # Convert timestamp to readable date
        from datetime import datetime
        expires_date = datetime.fromtimestamp(expires_at / 1000).strftime('%Y-%m-%d %H:%M:%S')
        
        console.print(Panel.fit(
            f"[green]✓ Authentication successful[/green]\n\n"
            f"[bold]Server URL:[/bold] {server_url}\n"
            f"[bold]Token saved to:[/bold] data.bin\n"
            f"[bold]Expires:[/bold] {expires_date}",
            title="Authentication",
            border_style="green"
        ))
        
    except Exception as e:
        console.print(f"[red]✗ Authentication failed[/red]")
        console.print(f"[red]  Error: {str(e)}[/red]")
        console.print("[yellow]  Hint: TOTP codes expire every 30 seconds[/yellow]")
        raise typer.Exit(code=1)


@app.command()
def config(
    action: str = typer.Argument(..., help="Action: set or get"),
    key: Optional[str] = typer.Argument(None, help="Configuration key (server_url, parallel, verbose, output)"),
    value: Optional[str] = typer.Argument(None, help="Configuration value (for set action)"),
):
    """Manage server configuration."""
    
    auth_manager = get_auth_manager()
    
    if action == "set":
        if not key or not value:
            console.print("[red]✗ Usage: acdown config set <key> <value>[/red]")
            console.print("[yellow]  Keys: server_url, parallel, verbose, output[/yellow]")
            raise typer.Exit(code=1)
        
        valid_keys = ['server_url', 'parallel', 'verbose', 'output']
        if key not in valid_keys:
            console.print(f"[red]✗ Invalid key: {key}[/red]")
            console.print(f"[yellow]  Valid keys: {', '.join(valid_keys)}[/yellow]")
            raise typer.Exit(code=1)
        
        try:
            auth_manager.set_config(key, value)
            console.print(Panel.fit(
                f"[green]✓ Configuration updated[/green]\n\n"
                f"[bold]{key}:[/bold] {value}\n"
                f"[bold]Saved to:[/bold] data.bin",
                title="Config Set",
                border_style="green"
            ))
        except Exception as e:
            console.print(f"[red]✗ Failed to set config: {str(e)}[/red]")
            raise typer.Exit(code=1)
    
    elif action == "get":
        if not key:
            # Show all config
            config = auth_manager.get_config()
            console.print(Panel.fit(
                f"[bold]Current Configuration:[/bold]\n\n"
                f"[bold]server_url:[/bold] {config.get('server_url', 'N/A')}\n"
                f"[bold]parallel:[/bold] {config.get('parallel', 'N/A')}\n"
                f"[bold]verbose:[/bold] {config.get('verbose', 'N/A')}\n"
                f"[bold]output:[/bold] {config.get('output', 'N/A')}",
                title="Config Get",
                border_style="blue"
            ))
        else:
            config_value = auth_manager.get_config_value(key)
            if config_value is not None:
                console.print(f"[bold]{key}:[/bold] {config_value}")
            else:
                console.print(f"[yellow]Key '{key}' not found[/yellow]")
    
    else:
        console.print(f"[red]✗ Invalid action: {action}[/red]")
        console.print("[yellow]  Use 'set' or 'get'[/yellow]")
        raise typer.Exit(code=1)


@app.command()
def logout():
    """Clear saved authentication token."""
    
    auth_manager = get_auth_manager()
    
    try:
        auth_manager.logout()
        console.print(Panel.fit(
            "[green]✓ Logged out successfully[/green]\n\n"
            "Authentication token has been cleared.",
            title="Logout",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]✗ Logout failed: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def test(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """Test server connection and authentication status."""
    
    import httpx
    from datetime import datetime
    
    auth_manager = get_auth_manager()
    
    # Check if server URL is configured
    if not check_server_url_configured(auth_manager):
        raise typer.Exit(code=1)
    
    config = auth_manager.get_config()
    server_url = config.get('server_url', '')
    
    console.print(Panel.fit(
        f"[bold]Testing Configuration[/bold]\n\n"
        f"[bold]Server URL:[/bold] {server_url}",
        title="Test Start",
        border_style="blue"
    ))
    
    # Test 1: Server Connection
    console.print("\n[cyan][1/2] Testing server connection...[/cyan]")
    try:
        async def test_connection():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{server_url}/health")
                return response.status_code == 200
        
        is_connected = asyncio.run(test_connection())
        
        if is_connected:
            console.print("  [green]✓ Server is reachable[/green]")
        else:
            console.print("  [red]✗ Server returned error status[/red]")
            raise typer.Exit(code=1)
    except httpx.ConnectError:
        console.print("  [red]✗ Cannot connect to server[/red]")
        console.print(f"  [yellow]Hint: Check if the server is running at {server_url}[/yellow]")
        raise typer.Exit(code=1)
    except httpx.TimeoutException:
        console.print("  [red]✗ Connection timed out[/red]")
        console.print(f"  [yellow]Hint: Server may be slow or unreachable[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"  [red]✗ Connection test failed: {str(e)}[/red]")
        raise typer.Exit(code=1)
    
    # Test 2: Authentication Token
    console.print("\n[cyan][2/2] Testing authentication token...[/cyan]")
    
    if not auth_manager.is_token_valid():
        console.print("  [red]✗ No valid authentication token found[/red]")
        console.print("  [yellow]Hint: Run 'acdown auth <code>' to authenticate[/yellow]")
        raise typer.Exit(code=1)
    
    token = auth_manager.get_token()
    data = auth_manager._load_data()
    expires_at = data.get('expiresAt', 0)
    
    # Calculate expiration time
    expires_date = datetime.fromtimestamp(expires_at / 1000).strftime('%Y-%m-%d %H:%M:%S')
    current_time = int(time.time() * 1000)
    remaining_ms = expires_at - current_time
    remaining_hours = remaining_ms / (1000 * 60 * 60)
    
    if verbose:
        console.print(f"  [green]✓ Token is valid[/green]")
        console.print(f"  [bold]Expires:[/bold] {expires_date}")
        console.print(f"  [bold]Remaining:[/bold] {remaining_hours:.1f} hours")
    else:
        console.print(f"  [green]✓ Token is valid (expires: {expires_date})[/green]")
    
    # Show summary
    console.print()  # Empty line for spacing
    console.print(Panel.fit(
        "[green]✓ All tests passed![/green]\n\n"
        "Server connection and authentication are working correctly.",
        title="Test Result",
        border_style="green"
    ))


if __name__ == "__main__":
    app()
