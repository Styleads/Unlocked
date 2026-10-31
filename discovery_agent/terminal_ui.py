"""
Terminal UI for displaying discovered schemes.

Uses the Rich library for formatted console output.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()


def show_header():
    """Display the Unlocked header banner."""
    console.print(
        Panel(
            "[bold cyan]UNLOCKED[/bold cyan]\n"
            "[white]Government Benefit Discovery Engine[/white]\n"
            "[dim]Official-source discovery system[/dim]",
            border_style="bright_blue",
            box=box.DOUBLE,
            padding=1,
        )
    )


def show_scheme_card(scheme, index):
    """
    Display a single scheme as a formatted card.

    Args:
        scheme: A dict or SchemeRecord.model_dump() dict.
        index: Display index number.
    """
    # Handle both dicts and SchemeRecord objects
    if hasattr(scheme, "model_dump"):
        scheme = scheme.model_dump()

    name = scheme.get("name", "Unknown Scheme")
    description = scheme.get("description", "No description available.")

    table = Table(box=box.ROUNDED, show_header=False, expand=True)
    table.add_column("Field", style="cyan", width=18)
    table.add_column("Details", style="white")

    table.add_row("Description", description)
    table.add_row(
        "Target groups",
        ", ".join(scheme.get("target_groups", [])) or "Not specified"
    )
    table.add_row(
        "Benefits",
        "\n".join("• " + item for item in scheme.get("benefits", []))
        or "Not specified"
    )

    criteria = scheme.get("eligibility_criteria", [])
    criterion_text = "\n".join(
        "• " + item.get("description", "")
        for item in criteria
        if isinstance(item, dict)
    ) or "Not specified"

    table.add_row("Eligibility", criterion_text)

    # Documents
    documents = scheme.get("required_documents", [])
    doc_text = "\n".join(
        "• " + doc for doc in documents
    ) or "Not specified"
    table.add_row("Documents", doc_text)

    # Government level and department
    gov_level = scheme.get("government_level", "unknown")
    department = scheme.get("department")
    if department:
        table.add_row("Department", f"{department} ({gov_level})")
    elif gov_level != "unknown":
        table.add_row("Level", gov_level.title())

    # Verification status
    status = scheme.get("verification_status", "unverified")
    status_display = {
        "verified": "[green]Verified[/green]",
        "partially_verified": "[yellow]Partially Verified[/yellow]",
        "unverified": "[red]Unverified[/red]",
    }.get(status, status)
    table.add_row("Verification", status_display)

    # Discovery source
    source = scheme.get("discovery_source", "live_search")
    if source == "fallback":
        table.add_row(
            "Source",
            "[yellow]Fallback data (verify on official portal)[/yellow]"
        )

    # Source links
    sources = scheme.get("source_evidence", [])
    source_text = "\n".join(
        f"[link={item.get('url', '')}]{item.get('title', 'Official source')}[/link]"
        for item in sources
        if isinstance(item, dict) and item.get("url")
    ) or "No source links"

    table.add_row("Sources", source_text)

    # Missing information
    missing = scheme.get("missing_information", [])
    if missing:
        table.add_row(
            "Missing info",
            "\n".join("• " + m for m in missing)
        )

    console.print(
        Panel(
            table,
            title=f"[bold white]{index:02d}. {name}[/bold white]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=1,
        )
    )


def show_discovery_results(
    schemes,
    search_scope="guided",
    query_count=0,
    source_count=0,
):
    """
    Display the full discovery results.

    Args:
        schemes: List of SchemeRecord objects or dicts.
        search_scope: 'guided' or 'all'.
        query_count: Number of search queries executed.
        source_count: Number of official sources found.
    """
    show_header()

    summary = Table(box=box.SIMPLE, expand=True)
    summary.add_column("Search scope", justify="center")
    summary.add_column("Queries", justify="center")
    summary.add_column("Official sources", justify="center")
    summary.add_column("Schemes", justify="center")

    summary.add_row(
        search_scope.upper(),
        str(query_count),
        str(source_count),
        str(len(schemes)),
    )

    console.print(summary)

    if not schemes:
        console.print("[yellow]No schemes discovered.[/yellow]")
        return

    for index, scheme in enumerate(schemes, start=1):
        show_scheme_card(scheme, index)

    console.print(
        Panel(
            "[bold green]DISCOVERY COMPLETED[/bold green]\n"
            "[dim]Check official portals before applying.[/dim]",
            border_style="green",
        )
    )

