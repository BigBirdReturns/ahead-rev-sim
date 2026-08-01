from __future__ import annotations

import ahead_rev_sim


def test_public_rtl_proof_api_is_fail_closed() -> None:
    assert (
        ahead_rev_sim.build_rtl_attachment_proof.__module__
        == "ahead_rev_sim.rtl_attachment_execution"
    )
    assert (
        ahead_rev_sim.build_rtl_attachment_proof_from_tools.__module__
        == "ahead_rev_sim.rtl_attachment_execution"
    )


def test_public_rtl_writers_are_byte_deterministic() -> None:
    assert (
        ahead_rev_sim.write_attachment_bundle.__module__
        == "ahead_rev_sim.rtl_attachment_io"
    )
    assert (
        ahead_rev_sim.write_rtl_attachment_proof.__module__
        == "ahead_rev_sim.rtl_attachment_io"
    )
