from __future__ import annotations

from ahead_rev_sim.chipyard_elaboration import git_blob_sha1
from ahead_rev_sim.chipyard_subsystem import (
    CHIPYARD_SOURCE_WITNESSES,
    build_chipyard_manifest,
)


ROOT_SYMLINK_BLOB = "ec3e38ff72c3a9750cfc1074d5ac8e9999b4f394"
SETUP_SCRIPT_BLOB = "709fc4db6ea274094921a41de52a2ad6c7816fdb"
SETUP_SCRIPT_PATH = "scripts/build-setup.sh"


def test_setup_witness_addresses_the_executed_regular_file() -> None:
    assert git_blob_sha1(b"scripts/build-setup.sh") == ROOT_SYMLINK_BLOB
    assert "build-setup.sh" not in CHIPYARD_SOURCE_WITNESSES

    contract = CHIPYARD_SOURCE_WITNESSES[SETUP_SCRIPT_PATH]
    assert contract["blob_sha"] == SETUP_SCRIPT_BLOB
    assert ROOT_SYMLINK_BLOB != SETUP_SCRIPT_BLOB
    assert {
        "--use-lean-conda",
        "--skip-submodules",
        "--skip-toolchain",
        "--skip-precompile",
        "--skip-circt",
    } == set(contract["required_patterns"])


def test_manifest_carries_the_corrected_setup_witness() -> None:
    source_witnesses = build_chipyard_manifest()["chipyard_source_contract"][
        "source_witnesses"
    ]
    assert source_witnesses[SETUP_SCRIPT_PATH]["blob_sha"] == SETUP_SCRIPT_BLOB
    assert "build-setup.sh" not in source_witnesses
