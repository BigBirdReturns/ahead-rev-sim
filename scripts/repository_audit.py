"""Compatibility wrapper for the installed repository-audit implementation."""

from __future__ import annotations

from ahead_rev_sim.repository_audit import main


if __name__ == "__main__":
    raise SystemExit(main())
