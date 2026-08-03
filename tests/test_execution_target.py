from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
import pytest

from ahead_rev_sim.execution_target import (
    EXECUTION_TARGET_ATTEMPT_SCHEMA_VERSION,
    EXECUTION_TARGET_INVOCATION_SCHEMA_VERSION,
    PHYSICAL_BLOCKERS,
    ReferenceSoftwareTargetAdapter,
    TargetDescriptor,
    TargetFault,
    TargetStageResult,
    UnboundPhysicalTargetAdapter,
    build_execution_target_invocation,
    canonical_json,
    execute_target_attempt,
    verify_execution_target_attempt,
    verify_execution_target_invocation,
)
from ahead_rev_sim.execution_target_cli import main as target_main


ROOT = Path(__file__).resolve().parents[1]
INVOCATION_SCHEMA = ROOT / "schemas" / "execution-target-invocation.schema.json"
ATTEMPT_SCHEMA = ROOT / "schemas" / "execution-target-attempt.schema.json"
WORKFLOW = ROOT / ".github" / "workflows" / "execution-target.yml"


def source_contract() -> dict:
    return {
        "invocation_id": "reference-capsule-attempt-v1",
        "capsule": {
            "capsule_id": "physical-compute-lifecycle-v1",
            "workload_sha256": "1" * 64,
            "descriptor_sha256": "2" * 64,
            "input_sha256": "3" * 64,
            "accepted_output_sha256": "4" * 64,
        },
        "interface": {
            "abi": "physical-compute-mmio/v1",
            "commands": ["reset", "load", "evolve", "read", "capture"],
            "required_capabilities": [
                "physical-compute-mmio/v1",
                "exact",
                "software_fallback",
            ],
        },
        "policy": {
            "software_fallback_id": "ahead.reference-software-target/v1",
            "timeout_seconds": 30,
            "cleanup_required_after_prepare": True,
        },
    }


def invocation() -> dict:
    return build_execution_target_invocation(source_contract())


def test_invocation_is_content_addressed_and_keeps_acceptance_local() -> None:
    packet = invocation()
    assert packet["schema_version"] == EXECUTION_TARGET_INVOCATION_SCHEMA_VERSION
    assert packet["policy"]["acceptance_authority"] == "local"
    assert packet["policy"]["provider_authority"] == "execution_only"
    assert packet["interface"]["abi"] == "physical-compute-mmio/v1"
    capsule = dict(packet["capsule"])
    claimed_capsule = capsule.pop("capsule_sha256")
    assert claimed_capsule == sha256(canonical_json(capsule).encode("utf-8")).hexdigest()
    unsigned = dict(packet)
    claimed = unsigned.pop("invocation_sha256")
    assert claimed == sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    verify_execution_target_invocation(packet)


def test_reference_target_proves_full_stage_prefix_and_cleanup() -> None:
    packet = invocation()
    receipt = execute_target_attempt(
        packet,
        ReferenceSoftwareTargetAdapter(packet["capsule"]["accepted_output_sha256"]),
    )
    assert receipt["schema_version"] == EXECUTION_TARGET_ATTEMPT_SCHEMA_VERSION
    assert receipt["terminal_state"] == "accepted"
    assert [item["stage"] for item in receipt["stage_history"]] == [
        "discover",
        "prepare",
        "execute",
        "observe",
        "collect",
        "cleanup",
    ]
    assert all(item["state"] == "completed" for item in receipt["stage_history"])
    assert receipt["observations"] == {
        "expected_output_sha256": "4" * 64,
        "observed_output_sha256": "4" * 64,
        "output_matches": True,
        "target_receipt_sha256": receipt["stage_history"][4]["observations"][
            "target_receipt_sha256"
        ],
        "fallback_used": True,
        "cleanup_attempted": True,
        "cleanup_completed": True,
    }
    qualification = receipt["qualification"]
    assert qualification["status"] == "reference_target_execution_proved"
    assert qualification["accepted"] is True
    assert qualification["execution_claim_allowed"] is True
    assert qualification["physical_execution_claim_allowed"] is False
    assert qualification["complete_system_advantage_claim_allowed"] is False
    assert qualification["blockers"] == list(PHYSICAL_BLOCKERS)
    verify_execution_target_attempt(receipt)


def test_unbound_fpga_refuses_at_discovery_without_cleanup_fiction() -> None:
    receipt = execute_target_attempt(invocation(), UnboundPhysicalTargetAdapter())
    assert receipt["terminal_state"] == "refused"
    assert receipt["target"]["target_class"] == "fpga"
    assert receipt["stage_history"] == [
        {
            "stage": "discover",
            "state": "refused",
            "detail": "no physical target transport or programming authority is bound",
            "blocker": "TARGET_UNAVAILABLE",
            "observations": {"available": False},
            "artifacts": [],
        }
    ]
    assert receipt["observations"]["cleanup_attempted"] is False
    assert receipt["observations"]["cleanup_completed"] is False
    assert receipt["qualification"]["accepted"] is False
    assert receipt["qualification"]["blockers"] == [
        "TARGET_UNAVAILABLE",
        "TARGET_EXECUTION_NOT_ACCEPTED",
        *PHYSICAL_BLOCKERS,
    ]
    verify_execution_target_attempt(receipt)


def test_output_mismatch_refuses_after_cleanup_and_preserves_observation() -> None:
    receipt = execute_target_attempt(
        invocation(),
        ReferenceSoftwareTargetAdapter("f" * 64),
    )
    assert receipt["terminal_state"] == "refused"
    assert receipt["observations"]["observed_output_sha256"] == "f" * 64
    assert receipt["observations"]["output_matches"] is False
    assert receipt["observations"]["cleanup_completed"] is True
    assert "ACCEPTED_OUTPUT_MISMATCH_OR_MISSING" in receipt["qualification"][
        "blockers"
    ]
    verify_execution_target_attempt(receipt)


class CleanupFaultAdapter(ReferenceSoftwareTargetAdapter):
    def cleanup(self, invocation: dict) -> TargetStageResult:
        raise TargetFault("TARGET_RESET_FAILED", "target cleanup reset failed")


class MissingCapabilityAdapter(ReferenceSoftwareTargetAdapter):
    def __init__(self) -> None:
        super().__init__("4" * 64)
        self.discover_called = False
        self.descriptor = TargetDescriptor(
            target_id="incomplete-target",
            target_class="reference_software",
            implementation="ahead.incomplete-target/v1",
            evidence_tier="deterministic_reference",
            capabilities=("physical-compute-mmio/v1", "exact"),
            fallback_used=True,
            cleanup_required=True,
        )

    def discover(self, invocation: dict) -> TargetStageResult:
        self.discover_called = True
        return super().discover(invocation)


def test_cleanup_fault_overrides_successful_execution() -> None:
    receipt = execute_target_attempt(invocation(), CleanupFaultAdapter("4" * 64))
    assert receipt["terminal_state"] == "faulted"
    assert receipt["stage_history"][-1]["stage"] == "cleanup"
    assert receipt["stage_history"][-1]["state"] == "faulted"
    assert receipt["stage_history"][-1]["blocker"] == "TARGET_RESET_FAILED"
    assert "TARGET_CLEANUP_FAILED" in receipt["qualification"]["blockers"]
    verify_execution_target_attempt(receipt)


def test_missing_capability_refuses_before_adapter_discovery() -> None:
    adapter = MissingCapabilityAdapter()
    receipt = execute_target_attempt(invocation(), adapter)
    assert adapter.discover_called is False
    assert receipt["stage_history"][0]["stage"] == "discover"
    assert receipt["stage_history"][0]["state"] == "refused"
    assert receipt["stage_history"][0]["blocker"] == "TARGET_CAPABILITY_MISSING"
    assert receipt["stage_history"][0]["observations"] == {
        "missing_capability_count": 1
    }


def test_tampering_is_rejected_at_capsule_invocation_and_attempt_layers() -> None:
    packet = invocation()
    bad_capsule = deepcopy(packet)
    bad_capsule["capsule"]["input_sha256"] = "9" * 64
    unsigned = dict(bad_capsule)
    unsigned.pop("invocation_sha256")
    bad_capsule["invocation_sha256"] = sha256(
        canonical_json(unsigned).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="capsule seal mismatch"):
        verify_execution_target_invocation(bad_capsule)

    receipt = execute_target_attempt(
        packet,
        ReferenceSoftwareTargetAdapter("4" * 64),
    )
    receipt["qualification"]["physical_execution_claim_allowed"] = True
    unsigned_receipt = dict(receipt)
    unsigned_receipt.pop("attempt_sha256")
    receipt["attempt_sha256"] = sha256(
        canonical_json(unsigned_receipt).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="cannot self-authorize physical"):
        verify_execution_target_attempt(receipt)


def test_execution_target_schemas_accept_reference_and_refusal_receipts() -> None:
    invocation_schema = json.loads(INVOCATION_SCHEMA.read_text(encoding="utf-8"))
    attempt_schema = json.loads(ATTEMPT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(invocation_schema)
    Draft202012Validator.check_schema(attempt_schema)
    registry = Registry().with_resource(
        invocation_schema["$id"],
        Resource.from_contents(invocation_schema),
    )
    packet = invocation()
    Draft202012Validator(invocation_schema).validate(packet)
    validator = Draft202012Validator(attempt_schema, registry=registry)
    validator.validate(
        execute_target_attempt(packet, ReferenceSoftwareTargetAdapter("4" * 64))
    )
    validator.validate(execute_target_attempt(packet, UnboundPhysicalTargetAdapter()))


def test_execution_target_cli_seals_accepts_refuses_and_verifies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    packet = tmp_path / "invocation.json"
    accepted = tmp_path / "accepted.json"
    refused = tmp_path / "refused.json"
    source.write_text(json.dumps(source_contract()), encoding="utf-8")

    assert target_main(["seal", str(source), "--out", str(packet)]) == 0
    assert target_main(
        [
            "attempt",
            str(packet),
            "--target",
            "reference-software",
            "--observed-output-sha256",
            "4" * 64,
            "--out",
            str(accepted),
        ]
    ) == 0
    assert target_main(["verify", str(accepted), "--require-accepted"]) == 0
    assert target_main(
        [
            "attempt",
            str(packet),
            "--target",
            "unbound-fpga",
            "--out",
            str(refused),
        ]
    ) == 2
    assert target_main(["verify", str(refused)]) == 0
    assert target_main(["verify", str(refused), "--require-accepted"]) == 2


def test_execution_target_workflow_preserves_both_acceptance_and_refusal() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "ahead-rev-target seal" in workflow
    assert "--target reference-software" in workflow
    assert "--target unbound-fpga" in workflow
    assert "test \"$refusal_rc\" -eq 2" in workflow
    assert "tampered attempt unexpectedly verified" in workflow
    assert "sha256sum --check --strict SHA256SUMS" in workflow
