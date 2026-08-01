from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim._version import __version__
from ahead_rev_sim.chipyard_cli import main as chipyard_main
from ahead_rev_sim.chipyard_elaboration import (
    CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION,
    assemble_chipyard_elaboration_proof,
    git_blob_sha1,
    parse_submodule_status,
    validate_chipyard_checkout,
)
from ahead_rev_sim.chipyard_io import write_chipyard_bundle, write_chipyard_elaboration_proof
from ahead_rev_sim.chipyard_subsystem import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    CHIPYARD_REPOSITORY,
    CHIPYARD_SCALA_INSTALL_PATH,
    CHIPYARD_SOURCE_WITNESSES,
    CHIPYARD_SUBMODULE_WITNESSES,
    DEFAULT_BASE_ADDRESS,
    ELABORATION_WITNESS_NAME,
    render_chipyard_scala,
)
from ahead_rev_sim.mmio_abi import canonical_json


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "chipyard-subsystem-elaboration-proof.schema.json"
WORKFLOW = ROOT / ".github" / "workflows" / "chipyard-subsystem.yml"

CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_SHA = "a309ff8b426b58ec0e2a45f0f869d46889d02405"
SETUP_MINICONDA_SHA = "fc2d68f6413eb2d87b895e92f8584b5b94a10167"
UPLOAD_ARTIFACT_SHA = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"


def _sha(char: str, length: int) -> str:
    return char * length


def _synthetic_checkout_evidence() -> dict[str, object]:
    source_witnesses = {
        path: {
            "git_blob_sha1": contract["blob_sha"],
            "sha256": _sha(str(index + 1), 64),
            "bytes": 100 + index,
        }
        for index, (path, contract) in enumerate(
            sorted(CHIPYARD_SOURCE_WITNESSES.items())
        )
    }
    submodule_witnesses = {
        path: {
            "git_blob_sha1": _sha("a", 40),
            "sha256": _sha("b", 64),
            "bytes": 200,
        }
        for path in CHIPYARD_SUBMODULE_WITNESSES
    }
    return {
        "repository": CHIPYARD_REPOSITORY,
        "commit": CHIPYARD_COMMIT,
        "source_witnesses": source_witnesses,
        "submodule_status_sha256": _sha("c", 64),
        "submodule_count": 12,
        "critical_submodules": {
            "generators/rocket-chip": {
                "commit": _sha("d", 40),
                "state": "exact",
                "prefix": " ",
            },
            "generators/testchipip": {
                "commit": _sha("e", 40),
                "state": "exact",
                "prefix": " ",
            },
        },
        "submodule_witnesses": submodule_witnesses,
        "scala_source": {
            "path": CHIPYARD_SCALA_INSTALL_PATH,
            "sha256": _sha("f", 64),
            "bytes": 4096,
        },
        "manifest_sha256": _sha("1", 64),
        "manifest_file_sha256": _sha("2", 64),
        "base_address": DEFAULT_BASE_ADDRESS,
    }


def _elaboration_files(root: Path) -> tuple[Path, Path, Path, Path]:
    firrtl = root / f"chipyard.harness.TestHarness.{CHIPYARD_CONFIG_CLASS}.fir"
    annotations = root / f"chipyard.harness.TestHarness.{CHIPYARD_CONFIG_CLASS}.anno.json"
    chisel_log = root / f"chipyard.harness.TestHarness.{CHIPYARD_CONFIG_CLASS}.chisel.log"
    elaboration_log = root / "chipyard-elaboration.log"
    firrtl.write_text(
        "circuit TestHarness :\n"
        "  module TestHarness :\n"
        f"    wire {ELABORATION_WITNESS_NAME} : UInt<32>\n",
        encoding="utf-8",
    )
    annotations.write_text('[{"class":"fixture.Annotation"}]\n', encoding="utf-8")
    chisel_log.write_text("Chisel elaboration fixture\n", encoding="utf-8")
    elaboration_log.write_text("make firrtl fixture passed\n", encoding="utf-8")
    return firrtl, annotations, chisel_log, elaboration_log


def test_git_blob_hash_matches_the_git_object_contract() -> None:
    payload = b"hello\n"
    expected = sha256(payload).hexdigest()
    assert len(git_blob_sha1(payload)) == 40
    assert expected != git_blob_sha1(payload)
    assert git_blob_sha1(payload) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_submodule_status_parser_distinguishes_exact_and_uninitialized() -> None:
    status = (
        f" {_sha('a', 40)} generators/testchipip (heads/main)\n"
        f" {_sha('b', 40)} generators/rocket-chip\n"
        f"-{_sha('c', 40)} generators/gemmini\n"
    )
    records = parse_submodule_status(status)
    assert records["generators/testchipip"]["state"] == "exact"
    assert records["generators/rocket-chip"]["prefix"] == " "
    assert records["generators/gemmini"]["state"] == "uninitialized"


def test_submodule_status_parser_refuses_duplicate_or_malformed_rows() -> None:
    line = f" {_sha('a', 40)} generators/testchipip\n"
    with pytest.raises(ValueError, match="duplicate"):
        parse_submodule_status(line + line)
    with pytest.raises(ValueError, match="invalid"):
        parse_submodule_status("not-a-submodule-row\n")


def test_elaboration_proof_is_deterministic_sealed_and_schema_valid(
    tmp_path: Path,
) -> None:
    firrtl, annotations, chisel_log, elaboration_log = _elaboration_files(tmp_path)
    kwargs = {
        "checkout_evidence": _synthetic_checkout_evidence(),
        "firrtl_path": firrtl,
        "annotations_path": annotations,
        "chisel_log_path": chisel_log,
        "elaboration_log_path": elaboration_log,
        "java_version": 'openjdk version "17.0.12" fixture',
        "sbt_version": "sbt script version 1.11 fixture",
        "make_command": (
            "make -C sims/verilator CONFIG=PhysicalComputeRocketConfig "
            "CONFIG_PACKAGE=chipyard.physicalcompute firrtl"
        ),
    }
    first = assemble_chipyard_elaboration_proof(**kwargs)
    second = assemble_chipyard_elaboration_proof(**kwargs)
    assert first == second
    assert first["schema_version"] == CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION
    assert first["qualification"]["status"] == "chipyard_subsystem_elaboration_proved"
    assert first["qualification"]["chipyard_subsystem_claim_allowed"] is True
    assert first["qualification"]["chipyard_rtl_simulation_claim_allowed"] is False
    assert "CHIPYARD_SUBSYSTEM_ELABORATION_UNRUN" not in first["qualification"]["blockers"]
    assert "CHIPYARD_RTL_SIMULATION_UNRUN" in first["qualification"]["blockers"]

    claimed = first.pop("proof_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()
    first["proof_sha256"] = claimed

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first)

    output = write_chipyard_elaboration_proof(tmp_path / "proof.json", first)
    assert json.loads(output.read_text(encoding="utf-8")) == first
    assert b"\r\n" not in output.read_bytes()


def test_elaboration_proof_refuses_missing_witness_or_invalid_annotations(
    tmp_path: Path,
) -> None:
    firrtl, annotations, chisel_log, elaboration_log = _elaboration_files(tmp_path)
    firrtl.write_text("circuit TestHarness :\n  module TestHarness :\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing the physical-compute witness"):
        assemble_chipyard_elaboration_proof(
            checkout_evidence=_synthetic_checkout_evidence(),
            firrtl_path=firrtl,
            annotations_path=annotations,
            chisel_log_path=chisel_log,
            elaboration_log_path=elaboration_log,
            java_version="java fixture",
            sbt_version="sbt fixture",
            make_command="make firrtl",
        )

    firrtl.write_text(
        "circuit TestHarness :\n"
        "  module TestHarness :\n"
        f"    wire {ELABORATION_WITNESS_NAME} : UInt<32>\n",
        encoding="utf-8",
    )
    annotations.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        assemble_chipyard_elaboration_proof(
            checkout_evidence=_synthetic_checkout_evidence(),
            firrtl_path=firrtl,
            annotations_path=annotations,
            chisel_log_path=chisel_log,
            elaboration_log_path=elaboration_log,
            java_version="java fixture",
            sbt_version="sbt fixture",
            make_command="make firrtl",
        )


def test_checkout_validation_refuses_commit_manifest_and_source_drift(
    tmp_path: Path,
) -> None:
    bundle = write_chipyard_bundle(tmp_path / "bundle")
    checkout = tmp_path / "chipyard"
    scala = checkout / CHIPYARD_SCALA_INSTALL_PATH
    scala.parent.mkdir(parents=True)
    scala.write_text(render_chipyard_scala(), encoding="utf-8")

    with pytest.raises(ValueError, match="checkout commit mismatch"):
        validate_chipyard_checkout(
            checkout,
            bundle["manifest"],
            scala,
            checkout_commit=_sha("0", 40),
            submodule_status=f" {_sha('a', 40)} generators/testchipip\n",
        )

    manifest = json.loads(bundle["manifest"].read_text(encoding="utf-8"))
    manifest["qualification"]["status"] = "forged"
    bundle["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="manifest diverges"):
        validate_chipyard_checkout(
            checkout,
            bundle["manifest"],
            scala,
            checkout_commit=CHIPYARD_COMMIT,
            submodule_status=f" {_sha('a', 40)} generators/testchipip\n",
        )

    bundle = write_chipyard_bundle(tmp_path / "bundle-2")
    scala.write_text("// stale source\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source diverges"):
        validate_chipyard_checkout(
            checkout,
            bundle["manifest"],
            scala,
            checkout_commit=CHIPYARD_COMMIT,
            submodule_status=f" {_sha('a', 40)} generators/testchipip\n",
        )


def test_chipyard_cli_reports_version_and_proof_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        chipyard_main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"ahead-rev-chipyard {__version__}"

    with pytest.raises(SystemExit) as exc:
        chipyard_main(["proof", "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--checkout-root" in help_text
    assert "--firrtl" in help_text
    assert "--annotations" in help_text


def test_workflow_pins_checkout_and_runs_real_chipyard_elaboration() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert CHIPYARD_COMMIT in workflow
    assert "scripts/init-submodules-no-riscv-tools.sh" in workflow
    assert "submodule.software/spec2026.update none" in workflow
    assert "build-setup.sh" in workflow
    assert "CONFIG=PhysicalComputeRocketConfig" in workflow
    assert "CONFIG_PACKAGE=chipyard.physicalcompute" in workflow
    assert " firrtl" in workflow
    assert '"$pythonLocation/bin/ahead-rev-chipyard" proof' in workflow
    assert "chipyard-subsystem-elaboration-proof.schema.json" in workflow
    assert f"actions/checkout@{CHECKOUT_SHA}" in workflow
    assert f"actions/setup-python@{SETUP_PYTHON_SHA}" in workflow
    assert f"conda-incubator/setup-miniconda@{SETUP_MINICONDA_SHA}" in workflow
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in workflow
    assert "persist-credentials: false" in workflow
    assert "timeout-minutes:" in workflow
