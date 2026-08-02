from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.chipyard_cli import main as chipyard_main
from ahead_rev_sim.chipyard_elaboration import (
    CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION,
)
from ahead_rev_sim.chipyard_lifecycle import (
    CHIPYARD_LIFECYCLE_EXPECTED_NAME,
    CHIPYARD_LIFECYCLE_MANIFEST_NAME,
    CHIPYARD_LIFECYCLE_MANIFEST_SCHEMA_VERSION,
    CHIPYARD_LIFECYCLE_PROOF_SCHEMA_VERSION,
    CHIPYARD_LIFECYCLE_SOURCE_NAME,
    CHIPYARD_LIFECYCLE_TRACE_PREFIX,
    LIFECYCLE_BLOCKERS,
    build_chipyard_lifecycle_manifest,
    build_chipyard_lifecycle_proof,
    parse_chipyard_lifecycle_trace,
    render_chipyard_lifecycle_source,
    render_chipyard_lifecycle_trace,
    write_chipyard_lifecycle_bundle,
    write_chipyard_lifecycle_proof,
)
from ahead_rev_sim.chipyard_subsystem import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    DEFAULT_BASE_ADDRESS,
    build_chipyard_manifest,
)
from ahead_rev_sim.mmio_abi import canonical_json


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = (
    ROOT / "schemas" / "chipyard-rv64gc-lifecycle-manifest.schema.json"
)
PROOF_SCHEMA = ROOT / "schemas" / "chipyard-rv64gc-lifecycle-proof.schema.json"
WORKFLOW = ROOT / ".github" / "workflows" / "chipyard-lifecycle.yml"


def _sealed_elaboration_proof(
    integration_manifest: dict[str, object],
) -> dict[str, object]:
    proof: dict[str, object] = {
        "schema_version": CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION,
        "chipyard": {
            "commit": CHIPYARD_COMMIT,
            "manifest_sha256": integration_manifest["manifest_sha256"],
        },
        "target": {"config_class": CHIPYARD_CONFIG_CLASS},
        "observations": {"loopback_fallback_retained": True},
        "qualification": {
            "accepted": True,
            "status": "chipyard_subsystem_elaboration_proved",
        },
    }
    proof["proof_sha256"] = sha256(
        canonical_json(proof).encode("utf-8")
    ).hexdigest()
    return proof


def _proof_fixture(tmp_path: Path) -> dict[str, object]:
    lifecycle_dir = tmp_path / "lifecycle"
    bundle = write_chipyard_lifecycle_bundle(lifecycle_dir)
    integration = build_chipyard_manifest()
    integration_path = tmp_path / "chipyard-physical-compute-integration.json"
    integration_path.write_text(
        json.dumps(integration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    elaboration_path = tmp_path / "chipyard-subsystem-elaboration-proof.json"
    elaboration_path.write_text(
        json.dumps(
            _sealed_elaboration_proof(integration),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    binary = tmp_path / "physical-compute-lifecycle.riscv"
    binary.write_bytes(b"\x7fELFchipyard-rv64gc-fixture")
    simulator = tmp_path / f"simulator-{CHIPYARD_CONFIG_CLASS}"
    simulator.write_bytes(b"verilator-simulator-fixture")
    simulator_build_log = tmp_path / "simulator-build.log"
    simulator_build_log.write_text("Verilator build fixture passed\n", encoding="utf-8")
    raw_log = tmp_path / "chipyard-lifecycle.raw.log"
    raw_log.write_text(
        "Chipyard boot fixture\n"
        + bundle["expected"].read_text(encoding="utf-8")
        + "Chipyard exit fixture\n",
        encoding="utf-8",
    )
    trace = tmp_path / "chipyard-lifecycle.trace"
    trace.write_bytes(bundle["expected"].read_bytes())
    return {
        "integration_manifest_path": integration_path,
        "lifecycle_manifest_path": bundle["manifest"],
        "elaboration_proof_path": elaboration_path,
        "source_path": bundle["source"],
        "expected_trace_path": bundle["expected"],
        "binary_path": binary,
        "simulator_path": simulator,
        "simulator_build_log_path": simulator_build_log,
        "raw_log_path": raw_log,
        "trace_path": trace,
        "compiler_version": "riscv64-unknown-elf-gcc fixture\n",
        "readelf_output": (
            "GNU readelf fixture\n"
            "  Class:                             ELF64\n"
            "  Machine:                           RISC-V\n"
        ),
        "verilator_version": "Verilator 5.022 fixture\n",
        "build_command": "make -C chipyard/sims/verilator default",
        "run_command": "make -C chipyard/sims/verilator run-binary-fast",
    }


def test_lifecycle_source_exercises_every_mmio_terminal_state() -> None:
    source = render_chipyard_lifecycle_source()
    assert f"PHYS_BASE UINT64_C(0x{DEFAULT_BASE_ADDRESS:08X})" in source
    assert "fence iorw, iorw" in source
    assert "CMD_RESET | CMD_READ" in source
    for command in ("CMD_RESET", "CMD_LOAD", "CMD_EVOLVE", "CMD_READ", "CMD_CAPTURE"):
        assert f"submit({command});" in source
    for stage in ("ambiguous", "reset", "load", "evolve", "read", "capture"):
        assert f'emit_stage("{stage}", observed);' in source
    assert 'printf(TRACE_PREFIX "result=pass\\n");' in source
    with pytest.raises(ValueError, match="4 KiB aligned"):
        render_chipyard_lifecycle_source(base_address=DEFAULT_BASE_ADDRESS + 4)


def test_lifecycle_trace_is_exact_ordered_and_semantically_checked() -> None:
    trace = render_chipyard_lifecycle_trace()
    observations = parse_chipyard_lifecycle_trace(trace)
    assert observations["line_count"] == 9
    assert all(observations["checks"].values())
    assert observations["stages"]["ambiguous"]["status"] == 0x00000009
    assert observations["stages"]["capture"]["status"] == 0x00000025

    reordered = trace.replace(
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}reset status",
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}temporary status",
        1,
    ).replace(
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}load status",
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}reset status",
        1,
    ).replace(
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}temporary status",
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}load status",
        1,
    )
    with pytest.raises(ValueError, match="out of order"):
        parse_chipyard_lifecycle_trace(reordered)

    wrong_status = trace.replace(
        "capture status=00000025",
        "capture status=00000031",
    )
    with pytest.raises(ValueError, match="semantic checks failed"):
        parse_chipyard_lifecycle_trace(wrong_status)


def test_lifecycle_manifest_is_deterministic_sealed_and_schema_valid() -> None:
    first = build_chipyard_lifecycle_manifest()
    second = build_chipyard_lifecycle_manifest()
    assert first == second
    assert first["schema_version"] == CHIPYARD_LIFECYCLE_MANIFEST_SCHEMA_VERSION
    assert first["chipyard"]["integration_manifest_sha256"] == (
        build_chipyard_manifest()["manifest_sha256"]
    )
    assert first["qualification"]["chipyard_rtl_simulation_claim_allowed"] is False

    claimed = first.pop("manifest_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()
    first["manifest_sha256"] = claimed

    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first)


def test_lifecycle_bundle_matches_manifest_and_uses_lf(tmp_path: Path) -> None:
    outputs = write_chipyard_lifecycle_bundle(tmp_path)
    assert outputs["source"].name == CHIPYARD_LIFECYCLE_SOURCE_NAME
    assert outputs["expected"].name == CHIPYARD_LIFECYCLE_EXPECTED_NAME
    assert outputs["manifest"].name == CHIPYARD_LIFECYCLE_MANIFEST_NAME
    manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    for key, name in (
        ("source", CHIPYARD_LIFECYCLE_SOURCE_NAME),
        ("expected", CHIPYARD_LIFECYCLE_EXPECTED_NAME),
    ):
        payload = outputs[key].read_bytes()
        record = manifest["generated_artifacts"][name]
        assert record["sha256"] == sha256(payload).hexdigest()
        assert record["bytes"] == len(payload)
        assert b"\r\n" not in payload


def test_lifecycle_proof_is_deterministic_sealed_and_schema_valid(
    tmp_path: Path,
) -> None:
    kwargs = _proof_fixture(tmp_path)
    first = build_chipyard_lifecycle_proof(**kwargs)
    second = build_chipyard_lifecycle_proof(**kwargs)
    assert first == second
    assert first["schema_version"] == CHIPYARD_LIFECYCLE_PROOF_SCHEMA_VERSION
    assert first["qualification"]["status"] == (
        "chipyard_rv64gc_lifecycle_execution_proved"
    )
    assert first["qualification"]["chipyard_rtl_simulation_claim_allowed"] is True
    assert first["qualification"]["external_cartridge_claim_allowed"] is False
    assert first["qualification"]["blockers"] == LIFECYCLE_BLOCKERS
    assert first["observations"]["accepted_trace_exact"] is True
    assert first["observations"]["raw_trace_embedded"] is True

    claimed = first.pop("proof_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()
    first["proof_sha256"] = claimed

    schema = json.loads(PROOF_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first)
    output = write_chipyard_lifecycle_proof(tmp_path / "proof.json", first)
    assert json.loads(output.read_text(encoding="utf-8")) == first
    assert b"\r\n" not in output.read_bytes()


def test_lifecycle_proof_refuses_forged_trace_source_or_raw_log(
    tmp_path: Path,
) -> None:
    kwargs = _proof_fixture(tmp_path)
    trace_path = Path(kwargs["trace_path"])
    trace_path.write_text(
        render_chipyard_lifecycle_trace().replace(
            "result=pass",
            "result=fail",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="diverges from accepted trace"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "source")
    source_path = Path(kwargs["source_path"])
    source_path.write_text("// forged\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source diverges"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "raw")
    raw_log_path = Path(kwargs["raw_log_path"])
    raw_log_path.write_text("simulator completed without a trace\n", encoding="utf-8")
    with pytest.raises(ValueError, match="raw simulation log"):
        build_chipyard_lifecycle_proof(**kwargs)


def test_chipyard_cli_exposes_lifecycle_bundle_and_proof(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "bundle"
    assert chipyard_main(["lifecycle-bundle", "--out-dir", str(output)]) == 0
    assert (output / CHIPYARD_LIFECYCLE_SOURCE_NAME).is_file()
    assert (output / CHIPYARD_LIFECYCLE_EXPECTED_NAME).is_file()
    assert (output / CHIPYARD_LIFECYCLE_MANIFEST_NAME).is_file()

    with pytest.raises(SystemExit) as exc:
        chipyard_main(["lifecycle-proof", "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--elaboration-proof" in help_text
    assert "--simulator-build-log" in help_text
    assert "--raw-log" in help_text


def test_lifecycle_workflow_builds_and_executes_the_exact_target() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in workflow
    assert "riscv64-unknown-elf-gcc" in workflow
    assert "-march=rv64gc" in workflow
    assert "-mabi=lp64d" in workflow
    assert "-specs=htif_nano.specs" in workflow
    assert "CONFIG=\"$CHIPYARD_CONFIG\"" in workflow
    assert "CONFIG_PACKAGE=\"$CHIPYARD_CONFIG_PACKAGE\"" in workflow
    assert "run-binary-fast" in workflow
    assert "timeout 300s" in workflow
    assert "grep '^ahead-chipyard:'" in workflow
    assert "lifecycle-proof" in workflow
    assert "chipyard-rv64gc-lifecycle-proof.schema.json" in workflow
    assert "2>&1 | tee" in workflow
    assert "if: always()" in workflow
    assert (
        "$GITHUB_WORKSPACE/artifacts/chipyard-lifecycle/generated-src.tar.gz"
        in workflow
    )
