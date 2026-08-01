from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim._version import __version__
from ahead_rev_sim.mmio_abi import canonical_json, render_systemverilog
from ahead_rev_sim.rtl_attachment import (
    EXPECTED_TRACE,
    RTL_ATTACHMENT_CONTRACT_SCHEMA_VERSION,
    RTL_ATTACHMENT_LINK,
    RTL_ATTACHMENT_MANIFEST_SCHEMA_VERSION,
    RTL_ATTACHMENT_PROOF_SCHEMA_VERSION,
    RTL_ATTACHMENT_RESOLVER,
    build_attachment_contract,
    build_attachment_manifest,
    build_rtl_attachment_proof,
    parse_rtl_attachment_trace,
    write_attachment_bundle,
    write_rtl_attachment_proof,
)
from ahead_rev_sim.rtl_attachment_cli import main as rtl_main


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SCHEMA = ROOT / "schemas" / "rtl-attachment-contract.schema.json"
MANIFEST_SCHEMA = ROOT / "schemas" / "rtl-attachment-manifest.schema.json"
PROOF_SCHEMA = ROOT / "schemas" / "rtl-attachment-proof.schema.json"
WORKFLOW = ROOT / ".github" / "workflows" / "rtl-attachment.yml"

CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_SHA = "a309ff8b426b58ec0e2a45f0f869d46889d02405"
UPLOAD_ARTIFACT_SHA = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"


def _schema(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(payload)
    return payload


def _fixture(
    root: Path,
) -> tuple[Path, Path, Path, Path, list[Path], dict[str, Path]]:
    root.mkdir(parents=True, exist_ok=True)
    outputs = write_attachment_bundle(root)
    mmio = root / "ahead_physical_compute_mmio_v1.sv"
    mmio.write_text(render_systemverilog(), encoding="utf-8")
    executable = root / "rtl-attachment.vvp"
    executable.write_bytes(b"#! /usr/bin/vvp\nrtl-attachment-fixture\n")
    trace = root / "rtl-attachment.trace"
    trace.write_text(EXPECTED_TRACE, encoding="utf-8")
    expected = outputs["rtl-attachment.expected"]
    manifest = outputs["rtl-attachment-manifest.json"]
    sources = [
        mmio,
        outputs["ahead_reference_handle_resolver_v1.sv"],
        outputs["ahead_reference_reversible_cartridge_v1.sv"],
        outputs["ahead_physical_compute_attachment_tb.sv"],
    ]
    return executable, trace, expected, manifest, sources, outputs


def test_contract_and_manifest_are_deterministic_sealed_and_schema_valid(
    tmp_path: Path,
) -> None:
    contract = build_attachment_contract()
    assert contract == build_attachment_contract()
    assert contract["schema_version"] == RTL_ATTACHMENT_CONTRACT_SCHEMA_VERSION
    assert contract["link_id"] == RTL_ATTACHMENT_LINK
    assert contract["resolver_id"] == RTL_ATTACHMENT_RESOLVER
    claimed_contract = contract.pop("contract_sha256")
    assert claimed_contract == sha256(
        canonical_json(contract).encode("utf-8")
    ).hexdigest()
    contract["contract_sha256"] = claimed_contract
    Draft202012Validator(_schema(CONTRACT_SCHEMA)).validate(contract)

    manifest = build_attachment_manifest()
    assert manifest == build_attachment_manifest()
    assert manifest["schema_version"] == RTL_ATTACHMENT_MANIFEST_SCHEMA_VERSION
    claimed_manifest = manifest.pop("manifest_sha256")
    assert claimed_manifest == sha256(
        canonical_json(manifest).encode("utf-8")
    ).hexdigest()
    manifest["manifest_sha256"] = claimed_manifest
    Draft202012Validator(_schema(MANIFEST_SCHEMA)).validate(manifest)

    outputs = write_attachment_bundle(tmp_path)
    written_manifest = json.loads(
        outputs["rtl-attachment-manifest.json"].read_text(encoding="utf-8")
    )
    assert written_manifest == manifest
    for name, record in manifest["files"].items():
        payload = outputs[name].read_bytes()
        assert len(payload) == record["bytes"]
        assert sha256(payload).hexdigest() == record["sha256"]


def test_trace_parser_proves_admission_refusal_fault_and_receipts() -> None:
    observations = parse_rtl_attachment_trace(EXPECTED_TRACE)
    assert observations["line_count"] == 11
    assert all(observations["checks"].values())
    assert observations["checks"]["ambiguous_refused_without_receipt"] is True
    assert observations["checks"]["invalid_descriptor_refused"] is True
    assert observations["checks"]["resolver_fault_propagated"] is True
    assert observations["checks"]["evolve_done"] is True
    assert observations["checks"]["capture_done"] is True


def test_rtl_proof_is_deterministic_sealed_and_schema_valid(tmp_path: Path) -> None:
    executable, trace, expected, manifest, sources, _outputs = _fixture(tmp_path)
    first = build_rtl_attachment_proof(
        executable,
        trace,
        expected,
        manifest,
        sources,
        iverilog_version="Icarus Verilog version 12.0 (fixture)",
        vvp_version="Icarus Verilog runtime version 12.0 (fixture)",
    )
    second = build_rtl_attachment_proof(
        executable,
        trace,
        expected,
        manifest,
        sources,
        iverilog_version="Icarus Verilog version 12.0 (fixture)",
        vvp_version="Icarus Verilog runtime version 12.0 (fixture)",
    )
    assert first == second
    assert first["schema_version"] == RTL_ATTACHMENT_PROOF_SCHEMA_VERSION
    assert first["qualification"]["status"] == "rtl_attachment_execution_proved"
    assert first["qualification"]["accepted"] is True
    assert first["qualification"]["chipyard_subsystem_claim_allowed"] is False
    assert first["qualification"]["physical_claim_allowed"] is False
    assert first["qualification"]["complete_system_advantage_claim_allowed"] is False

    claimed = first.pop("proof_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()
    first["proof_sha256"] = claimed
    Draft202012Validator(_schema(PROOF_SCHEMA)).validate(first)

    output = write_rtl_attachment_proof(tmp_path / "proof.json", first)
    assert json.loads(output.read_text(encoding="utf-8")) == first


def test_rtl_proof_refuses_trace_manifest_and_source_divergence(
    tmp_path: Path,
) -> None:
    trace_root = tmp_path / "trace"
    executable, trace, expected, manifest, sources, _outputs = _fixture(trace_root)
    trace.write_text("result=pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="trace diverges"):
        build_rtl_attachment_proof(
            executable,
            trace,
            expected,
            manifest,
            sources,
            iverilog_version="iverilog fixture",
            vvp_version="vvp fixture",
        )

    manifest_root = tmp_path / "manifest"
    executable, trace, expected, manifest, sources, outputs = _fixture(manifest_root)
    outputs["ahead_reference_handle_resolver_v1.sv"].write_text(
        "// tampered\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        build_rtl_attachment_proof(
            executable,
            trace,
            expected,
            manifest,
            sources,
            iverilog_version="iverilog fixture",
            vvp_version="vvp fixture",
        )

    source_root = tmp_path / "sources"
    executable, trace, expected, manifest, sources, _outputs = _fixture(source_root)
    with pytest.raises(ValueError, match="requires exactly"):
        build_rtl_attachment_proof(
            executable,
            trace,
            expected,
            manifest,
            sources[:-1],
            iverilog_version="iverilog fixture",
            vvp_version="vvp fixture",
        )


def test_trace_parser_refuses_duplicate_or_reordered_lifecycle() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        parse_rtl_attachment_trace(EXPECTED_TRACE + "result=pass\n")

    lines = EXPECTED_TRACE.splitlines()
    lines[2], lines[3] = lines[3], lines[2]
    with pytest.raises(ValueError, match="out of order"):
        parse_rtl_attachment_trace("\n".join(lines) + "\n")


def test_rtl_cli_generates_bundle_and_reports_version(
    tmp_path: Path,
    capsys,
) -> None:
    assert rtl_main(["bundle", "--out-dir", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "rtl-attachment-manifest.json" in output
    assert (tmp_path / "ahead_physical_compute_attachment_tb.sv").is_file()

    with pytest.raises(SystemExit) as exc:
        rtl_main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"ahead-rev-rtl {__version__}"


def test_workflow_executes_real_iverilog_attachment_and_pins_actions() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "iverilog" in workflow
    assert "vvp" in workflow
    assert "ahead-rev-mmio" in workflow
    assert "ahead-rev-rtl bundle" in workflow
    assert "ahead-rev-rtl proof" in workflow
    assert "diff -u" in workflow
    assert "rtl-attachment-proof.schema.json" in workflow
    assert f"actions/checkout@{CHECKOUT_SHA}" in workflow
    assert f"actions/setup-python@{SETUP_PYTHON_SHA}" in workflow
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in workflow
    assert "persist-credentials: false" in workflow
    assert "timeout-minutes:" in workflow
