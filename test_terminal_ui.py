"""
Demonstration and test script for terminal_ui module.
"""

from discovery_agent.terminal_ui import (
    show_discovery_results,
    show_header,
    show_scheme_card,
)
from discovery_agent.fallback_schemes import get_fallback_schemes


def run_demo():
    """Run a terminal UI demonstration using verified fallback schemes."""
    schemes = get_fallback_schemes()[:2]
    show_discovery_results(
        schemes,
        search_scope="guided",
        query_count=2,
        source_count=2,
    )


if __name__ == "__main__":
    run_demo()
