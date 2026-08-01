"""Cardinality-safe PCK frontier construction.

The first PCK lowering used a fixed retained-state sampling ladder intended for
the 256-iteration default contract. Nondefault diagnostic contracts with fewer
iterations must preserve their own cardinality instead of attempting impossible
retained-state counts. This module wraps the original semantic proof, bounds the
sampling ladder to the workload, removes duplicate terminal points, and patches
the public submodule entry point during package initialization.
"""

from __future__ import annotations

from threading import RLock

from . import fambs_pck_lowering as _base

_ORIGINAL_ANALYZE_PCK = _base.analyze_pck
_ORIGINAL_PROVE_STRATEGY = _base._prove_strategy
_FRONTIER_LOCK = RLock()


def _bounded_prove_strategy(
    *,
    retained_count: int,
    pool: _base.PCKPool,
    config: _base.PCKConfig,
    pool_round_trip: bool,
    conventional_operations: int,
) -> _base.PCKStrategyPoint:
    """Map fixed sampling-ladder points onto the legal workload domain."""

    return _ORIGINAL_PROVE_STRATEGY(
        retained_count=min(retained_count, config.iterations),
        pool=pool,
        config=config,
        pool_round_trip=pool_round_trip,
        conventional_operations=conventional_operations,
    )


def analyze_pck(
    config: _base.PCKConfig = _base.PCKConfig(),
) -> _base.PCKLoweringArtifact:
    """Analyze PCK with a unique frontier bounded by ``config.iterations``."""

    with _FRONTIER_LOCK:
        previous = _base._prove_strategy
        _base._prove_strategy = _bounded_prove_strategy
        try:
            artifact = _ORIGINAL_ANALYZE_PCK(config)
        finally:
            _base._prove_strategy = previous

    unique: dict[int, _base.PCKStrategyPoint] = {}
    for point in artifact.frontier:
        unique.setdefault(point.retained_final_states, point)
    artifact.frontier = [unique[count] for count in sorted(unique)]
    artifact.seal()
    return artifact


# Python executes the package initializer before satisfying a direct import of
# ``ahead_rev_sim.fambs_pck_lowering``. Patching the already-loaded module keeps
# that established import path stable while the lowering is split into focused
# source files.
_base.analyze_pck = analyze_pck

__all__ = ["analyze_pck"]
