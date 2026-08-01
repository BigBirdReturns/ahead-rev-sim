"""Compatibility wrapper for the installed release-preflight implementation."""

from __future__ import annotations

from ahead_rev_sim.release_preflight import main


if __name__ == "__main__":
    raise SystemExit(main())
