"""
Project Aura - Security Hooks Main Entry

Allows running hooks as:
    python -m scripts.security_hooks.secrets_hook
    python -m scripts.security_hooks.config_hook
"""

import sys


def main():
    """Print usage information."""
    print("Project Aura Security Hooks")
    print()
    print("Available hooks:")
    print("  python -m scripts.security_hooks.secrets_hook [files...]")
    print("  python -m scripts.security_hooks.config_hook [files...]")
    print()
    print("Or install via pre-commit:")
    print("  pip install pre-commit")
    print("  pre-commit install")


if __name__ == "__main__":
    main()
