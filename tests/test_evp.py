from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ahead_rev_sim.evp import (
    EVP_ARTIFACT_TYPE,
    EVP_SCHEMA_VERSION,
    build_evp_receipt,
    canonical_json,
)
from ahead_rev_sim.evp_cli import main as evp_main


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "evp-receipt.schema.json"
H = "a" * 64


def measured_contract() -> dict:
    return {
        "workload": {
            "contract_id": "fambs-svk/accepted-dot-v1",
            "artifact_sha256": H,
            "accepted_work_unit": "accepted sparse-vector dot product",
            "accepted_work_units": 100,
            "result": {"digest": "svk-result-v1"},
            "quality_rule": "exact result digest match",
            "accepted": True,
        },
        "boundary": {
            "boundary_id": "complete-system-rack-slot-v1",
            "claim_scope": "complete_system",
            "included_components": [
                "riscv host",
                "memory",
                "physical cartridge",
                "interconnect",
                "conversion",
                "control",
                "sensing and readout",
                "cooling",
            ],
            "excluded_components": [],
            "allocation_rule": "exclusive measured fixture",
            "measurement_start_ns": 0,
            "measurement_end_ns": 1_000_000_000,
            "concurrency": 1,
        },
        "energy": {
            "evidence_class": "measured",
            "instrument_refs": ["power-meter:cal-2026-07"],
            "uncertainty_fraction": 0.01,
            "external_supply_joules": 10,
            "ambient_harvested_joules": 2,
            "signal_coupled_joules": 0,
            "recovered_joules": 1,
            "measurement_overhead_joules": 0.1,
            "breakdown_joules": {
                "riscv host": 3,
                "memory": 1,
                "physical cartridge": 4,
                "interconnect and conversion": 1,
                "sensing and readout": 1,
                "cooling": 2,
            },
        },
        "volume": {
            "evidence_class": "measured",
            "instrument_refs": ["mechanical-envelope:rev-a"],
            "uncertainty_fraction": 0.01,
            "allocation_rule": "exclusive occupied bounding volumes",
            "components_mm3": {
                "host": 700,
                "cartridge": 100,
                "interconnect": 100,
                "cooling": 700,
            },
        },
        "performance": {
            "evidence_class": "measured",
            "instrument_refs": ["monotonic-clock:trace-a"],
            "uncertainty_fraction": 0.01,
            "clock_kind": "monotonic_raw",
            "clock_ref": "monotonic-clock:trace-a",
            "elapsed_seconds": 1,
            "latency_seconds": 0.01,
            "p95_latency_seconds": 0.02,
        },
        "provenance": {
            "implementation_id": "ahead-host-plus-vaire-cartridge-candidate",
            "implementation_class": "heterogeneous complete system",
            "substrate_receipt_sha256": H,
            "host_proof_sha256": H,
            "compiler_artifact_sha256": H,
            "measurement_manifest_sha256": H,
            "environment_manifest_sha256": H,
            "calibration_manifest_sha256": H,
            "supplier_chain": [
                {
                    "actor": "AheadComputing",
                    "component_role": "RISC-V host candidate",
                    "implementation_id": "ahead-host-unqualified",
                    "artifact_sha256": None,
                },
                {
                    "actor": "Vaire Computing",
                    "component_role": "reversible cartridge candidate",
                    "implementation_id": "vaire-cartridge-unqualified",
                    "artifact_sha256": None,
                },
            ],
        },
        "baseline": {
            "receipt_sha256": H,
            "workload_contract_id": "fambs-svk/accepted-dot-v1",
            "boundary_id": "complete-system-rack-slot-v1",
            "claim_scope": "complete_system",
            "environment_manifest_sha256": H,
            "net_physical_joules_per_accepted_work_unit": 0.2,
            "occupied_mm3": 2000,
            "throughput_accepted_work_units_per_second": 90,
            "latency_seconds": 0.02,
        },
    }


def test_measured_evp_receipt_is_vector_sealed_and_pareto_qualified() -> None:
    receipt = build_evp_receipt(measured_contract())
    assert receipt["schema_version"] == EVP_SCHEMA_VERSION
    assert receipt["artifact_type"] == EVP_ARTIFACT_TYPE
    assert receipt["energy"]["net_physical_joules_per_accepted_work_unit"] == 0.11
    assert receipt["volume"]["occupied_mm3"] == 1600
    assert receipt["performance"]["throughput_accepted_work_units_per_second"] == 100
    assert receipt["comparison"]["pareto_dominates_baseline"] is True
    assert receipt["comparison"]["scalar_score_allowed"] is False
    assert "score" not in receipt
    assert receipt["qualification"] == {
        "status": "measured_evp_vector",
        "measured_evp_vector_allowed": True,
        "complete_system_measurement_allowed": True,
        "advantage_claim_allowed": True,
        "blockers": [],
    }

    claimed = receipt.pop("receipt_sha256")
    assert claimed == sha256(canonical_json(receipt).encode("utf-8")).hexdigest()


def test_modeled_component_receipt_preserves_evp_but_refuses_advantage() -> None:
    contract = measured_contract()
    contract["boundary"]["claim_scope"] = "component"
    contract["boundary"]["boundary_id"] = "cartridge-only-v1"
    contract["energy"]["evidence_class"] = "reference_model"
    contract["energy"]["instrument_refs"] = []
    contract["volume"]["evidence_class"] = "simulated"
    contract["volume"]["instrument_refs"] = []
    contract["performance"]["evidence_class"] = "simulated"
    contract["performance"]["instrument_refs"] = []
    contract["provenance"]["measurement_manifest_sha256"] = None
    contract["provenance"]["calibration_manifest_sha256"] = None
    contract["baseline"] = None

    receipt = build_evp_receipt(contract)
    qualification = receipt["qualification"]
    assert qualification["status"] == "modeled_evp_vector"
    assert qualification["measured_evp_vector_allowed"] is False
    assert qualification["advantage_claim_allowed"] is False
    assert {
        "ENERGY_UNMEASURED",
        "VOLUME_UNMEASURED",
        "PERFORMANCE_UNMEASURED",
        "COMPLETE_SYSTEM_BOUNDARY_NOT_DECLARED",
        "INSTRUMENT_CUSTODY_INCOMPLETE",
        "MEASUREMENT_MANIFEST_MISSING",
        "CALIBRATION_MANIFEST_MISSING",
        "BASELINE_MISSING_FOR_ADVANTAGE",
    } <= set(qualification["blockers"])


def test_baseline_workload_boundary_or_environment_mismatch_blocks_advantage() -> None:
    for key, value in (
        ("workload_contract_id", "other-workload"),
        ("boundary_id", "other-boundary"),
        ("environment_manifest_sha256", "b" * 64),
    ):
        contract = measured_contract()
        contract["baseline"][key] = value
        receipt = build_evp_receipt(contract)
        assert receipt["comparison"]["comparable"] is False
        assert receipt["comparison"]["pareto_dominates_baseline"] is False
        assert receipt["qualification"]["advantage_claim_allowed"] is False
        assert "BASELINE_BOUNDARY_MISMATCH" in receipt["qualification"]["blockers"]


def test_energy_recovery_cannot_exceed_declared_physical_input() -> None:
    contract = measured_contract()
    contract["energy"]["recovered_joules"] = 13
    try:
        build_evp_receipt(contract)
    except ValueError as exc:
        assert "cannot exceed declared physical energy inputs" in str(exc)
    else:
        raise AssertionError("over-recovery must be rejected")


def test_energy_breakdown_and_timing_interval_are_completion_gates() -> None:
    contract = measured_contract()
    contract["energy"]["breakdown_joules"] = {"device": 1}
    contract["performance"]["elapsed_seconds"] = 0.5
    receipt = build_evp_receipt(contract)
    blockers = set(receipt["qualification"]["blockers"])
    assert "ENERGY_BREAKDOWN_INCOMPLETE" in blockers
    assert "PERFORMANCE_INTERVAL_MISMATCH" in blockers
    assert receipt["qualification"]["complete_system_measurement_allowed"] is False
    assert receipt["qualification"]["advantage_claim_allowed"] is False


def test_evp_schema_accepts_generated_receipt() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(build_evp_receipt(measured_contract()))


def test_evp_cli_writes_receipt_and_enforces_advantage(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    output = tmp_path / "receipt.json"
    source.write_text(json.dumps(measured_contract()), encoding="utf-8")
    assert evp_main(
        [
            str(source),
            "--out",
            str(output),
            "--require-measured",
            "--require-advantage",
            "--quiet",
        ]
    ) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["qualification"]["advantage_claim_allowed"] is True
    assert len(payload["receipt_sha256"]) == 64

    refused = deepcopy(measured_contract())
    refused["workload"]["accepted"] = False
    source.write_text(json.dumps(refused), encoding="utf-8")
    assert evp_main([str(source), "--out", str(output), "--quiet"]) == 2
