"""Provider-neutral execution-target orchestration and attempt receipts.

An execution target may discover, prepare, execute, observe, collect, and clean
up a sealed capsule invocation. The target receives execution authority only.
Accepted work, fallback, refusal, evidence boundaries, and qualification remain
under local repository authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence

from .physical_serialization import is_sha256, sha256_json

EXECUTION_TARGET_INVOCATION_SCHEMA_VERSION = "ahead.execution-target-invocation/v0.1"
EXECUTION_TARGET_ATTEMPT_SCHEMA_VERSION = "ahead.execution-target-attempt/v0.1"
EXECUTION_TARGET_INVOCATION_ARTIFACT_TYPE = "execution_target_invocation"
EXECUTION_TARGET_ATTEMPT_ARTIFACT_TYPE = "execution_target_attempt_receipt"
EXECUTION_TARGET_ABI = "physical-compute-mmio/v1"

TARGET_STAGES = (
    "discover",
    "prepare",
    "execute",
    "observe",
    "collect",
    "cleanup",
)
TERMINAL_STATES = frozenset({"accepted", "refused", "faulted"})
STAGE_STATES = frozenset({"completed", "refused", "faulted"})
TARGET_CLASSES = frozenset(
    {
        "reference_software",
        "rtl_simulator",
        "fpga",
        "silicon",
        "physical_substrate",
        "remote_venue",
    }
)
BLOCKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")

PHYSICAL_BLOCKERS = (
    "PHYSICAL_EXECUTION_UNPROVEN",
    "PHYSICAL_ENERGY_UNMEASURED",
    "TIMING_THERMAL_VOLUME_UNMEASURED",
    "COMPLETE_SYSTEM_EVP_UNMEASURED",
    "INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING",
)

JsonScalar = str | int | float | bool | None


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _text(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _sha(value: Any, field_name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    digest = _text(value, field_name)
    if not is_sha256(digest):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return digest


def _positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return int(value)


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be boolean")
    return value


def _strings(value: Any, field_name: str, *, minimum: int = 1) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be an array")
    values = [_text(item, f"{field_name}[]") for item in value]
    if len(values) < minimum:
        raise ValueError(f"{field_name} must contain at least {minimum} entries")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} entries must be unique")
    return values


def _blocker(value: Any, field_name: str) -> str:
    blocker = _text(value, field_name)
    if BLOCKER_PATTERN.fullmatch(blocker) is None:
        raise ValueError(f"{field_name} must be an uppercase blocker code")
    return blocker


def _seal(payload: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    result = dict(payload)
    result[field_name] = sha256(canonical_json(result).encode("utf-8")).hexdigest()
    return result


def _verify_seal(
    artifact: Mapping[str, Any],
    *,
    field_name: str,
    artifact_name: str,
) -> None:
    claimed = _sha(artifact.get(field_name), f"{artifact_name}.{field_name}")
    unsigned = dict(artifact)
    unsigned.pop(field_name, None)
    actual = sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    if claimed != actual:
        raise ValueError(f"{artifact_name} seal mismatch")


@dataclass(frozen=True)
class TargetArtifact:
    path: str
    role: str
    sha256: str
    size_bytes: int

    def as_dict(self) -> dict[str, Any]:
        path = _text(self.path, "target artifact path")
        if path.startswith("/") or ".." in Path(path).parts:
            raise ValueError("target artifact path must be relative and traversal-free")
        return {
            "path": path,
            "role": _text(self.role, "target artifact role"),
            "sha256": _sha(self.sha256, "target artifact sha256"),
            "size_bytes": _positive_integer(
                self.size_bytes,
                "target artifact size_bytes",
            ),
        }


@dataclass(frozen=True)
class TargetStageResult:
    observations: Mapping[str, JsonScalar] = field(default_factory=dict)
    artifacts: tuple[TargetArtifact, ...] = ()


@dataclass(frozen=True)
class TargetDescriptor:
    target_id: str
    target_class: str
    implementation: str
    evidence_tier: str
    capabilities: tuple[str, ...]
    fallback_used: bool
    cleanup_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        target_class = _text(self.target_class, "target.target_class")
        if target_class not in TARGET_CLASSES:
            raise ValueError(
                f"target.target_class must be one of {sorted(TARGET_CLASSES)}"
            )
        capabilities = _strings(self.capabilities, "target.capabilities")
        return {
            "target_id": _text(self.target_id, "target.target_id"),
            "target_class": target_class,
            "implementation": _text(self.implementation, "target.implementation"),
            "evidence_tier": _text(self.evidence_tier, "target.evidence_tier"),
            "capabilities": sorted(capabilities),
            "fallback_used": _boolean(self.fallback_used, "target.fallback_used"),
            "cleanup_required": _boolean(
                self.cleanup_required,
                "target.cleanup_required",
            ),
        }


class ExecutionTargetAdapter(Protocol):
    descriptor: TargetDescriptor

    def discover(self, invocation: Mapping[str, Any]) -> TargetStageResult: ...

    def prepare(self, invocation: Mapping[str, Any]) -> TargetStageResult: ...

    def execute(self, invocation: Mapping[str, Any]) -> TargetStageResult: ...

    def observe(self, invocation: Mapping[str, Any]) -> TargetStageResult: ...

    def collect(self, invocation: Mapping[str, Any]) -> TargetStageResult: ...

    def cleanup(self, invocation: Mapping[str, Any]) -> TargetStageResult: ...


class TargetRefusal(Exception):
    """Expected target refusal with one stable blocker code."""

    def __init__(
        self,
        blocker: str,
        detail: str,
        *,
        observations: Mapping[str, JsonScalar] | None = None,
        artifacts: tuple[TargetArtifact, ...] = (),
    ) -> None:
        self.blocker = _blocker(blocker, "target refusal blocker")
        self.detail = _text(detail, "target refusal detail")
        self.observations = dict(observations or {})
        self.artifacts = artifacts
        super().__init__(self.detail)


class TargetFault(Exception):
    """Target fault that prevents attempt acceptance."""

    def __init__(
        self,
        blocker: str,
        detail: str,
        *,
        observations: Mapping[str, JsonScalar] | None = None,
        artifacts: tuple[TargetArtifact, ...] = (),
    ) -> None:
        self.blocker = _blocker(blocker, "target fault blocker")
        self.detail = _text(detail, "target fault detail")
        self.observations = dict(observations or {})
        self.artifacts = artifacts
        super().__init__(self.detail)


def _normalize_observations(
    observations: Mapping[str, JsonScalar],
    field_name: str,
) -> dict[str, JsonScalar]:
    result: dict[str, JsonScalar] = {}
    for raw_key, value in sorted(observations.items(), key=lambda pair: str(pair[0])):
        key = _text(raw_key, f"{field_name} key")
        if isinstance(value, float) and (
            value != value or value in {float("inf"), float("-inf")}
        ):
            raise ValueError(f"{field_name}.{key} must be finite")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError(f"{field_name}.{key} must be a JSON scalar")
        result[key] = value
    return result


def _normalize_stage_result(result: TargetStageResult, stage: str) -> dict[str, Any]:
    if not isinstance(result, TargetStageResult):
        raise ValueError(f"target {stage} must return TargetStageResult")
    artifacts = [artifact.as_dict() for artifact in result.artifacts]
    paths = [str(item["path"]) for item in artifacts]
    if len(paths) != len(set(paths)):
        raise ValueError(f"target {stage} returned duplicate artifact paths")
    return {
        "observations": _normalize_observations(
            result.observations,
            f"target {stage} observations",
        ),
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"])),
    }


def _stage_record(
    *,
    stage: str,
    state: str,
    detail: str,
    blocker: str | None,
    observations: Mapping[str, JsonScalar],
    artifacts: tuple[TargetArtifact, ...] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if stage not in TARGET_STAGES:
        raise ValueError(f"unsupported target stage: {stage}")
    if state not in STAGE_STATES:
        raise ValueError(f"unsupported target stage state: {state}")
    if blocker is not None:
        blocker = _blocker(blocker, f"stage {stage} blocker")
    normalized_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        if isinstance(artifact, TargetArtifact):
            normalized_artifacts.append(artifact.as_dict())
        else:
            raw = _mapping(artifact, f"stage {stage} artifact")
            normalized_artifacts.append(
                TargetArtifact(
                    path=_text(raw.get("path"), "stage artifact path"),
                    role=_text(raw.get("role"), "stage artifact role"),
                    sha256=_text(raw.get("sha256"), "stage artifact sha256"),
                    size_bytes=_positive_integer(
                        raw.get("size_bytes"),
                        "stage artifact size_bytes",
                    ),
                ).as_dict()
            )
    return {
        "stage": stage,
        "state": state,
        "detail": _text(detail, f"stage {stage} detail"),
        "blocker": blocker,
        "observations": _normalize_observations(
            observations,
            f"stage {stage} observations",
        ),
        "artifacts": sorted(
            normalized_artifacts,
            key=lambda item: str(item["path"]),
        ),
    }


def build_execution_target_invocation(source: Mapping[str, Any]) -> dict[str, Any]:
    """Seal one provider-neutral capsule invocation."""

    capsule_source = _mapping(source.get("capsule"), "capsule")
    capsule: dict[str, Any] = {
        "capsule_id": _text(capsule_source.get("capsule_id"), "capsule.capsule_id"),
        "workload_sha256": _sha(
            capsule_source.get("workload_sha256"),
            "capsule.workload_sha256",
        ),
        "descriptor_sha256": _sha(
            capsule_source.get("descriptor_sha256"),
            "capsule.descriptor_sha256",
        ),
        "input_sha256": _sha(
            capsule_source.get("input_sha256"),
            "capsule.input_sha256",
        ),
        "accepted_output_sha256": _sha(
            capsule_source.get("accepted_output_sha256"),
            "capsule.accepted_output_sha256",
        ),
    }
    capsule["capsule_sha256"] = sha256_json(capsule)

    interface_source = _mapping(source.get("interface"), "interface")
    abi = _text(interface_source.get("abi", EXECUTION_TARGET_ABI), "interface.abi")
    if abi != EXECUTION_TARGET_ABI:
        raise ValueError(f"interface.abi must be {EXECUTION_TARGET_ABI}")
    commands = _strings(interface_source.get("commands"), "interface.commands")
    required_capabilities = _strings(
        interface_source.get("required_capabilities"),
        "interface.required_capabilities",
    )
    if abi not in required_capabilities:
        raise ValueError("interface.required_capabilities must include the MMIO ABI")

    policy_source = _mapping(source.get("policy"), "policy")
    payload: dict[str, Any] = {
        "schema_version": EXECUTION_TARGET_INVOCATION_SCHEMA_VERSION,
        "artifact_type": EXECUTION_TARGET_INVOCATION_ARTIFACT_TYPE,
        "invocation_id": _text(source.get("invocation_id"), "invocation_id"),
        "capsule": capsule,
        "interface": {
            "abi": abi,
            "commands": commands,
            "required_capabilities": sorted(required_capabilities),
        },
        "policy": {
            "acceptance_authority": "local",
            "provider_authority": "execution_only",
            "software_fallback_id": _text(
                policy_source.get("software_fallback_id"),
                "policy.software_fallback_id",
            ),
            "timeout_seconds": _positive_integer(
                policy_source.get("timeout_seconds"),
                "policy.timeout_seconds",
            ),
            "cleanup_required_after_prepare": _boolean(
                policy_source.get("cleanup_required_after_prepare", True),
                "policy.cleanup_required_after_prepare",
            ),
        },
        "control_question": (
            "Can this exact content-addressed capsule move to another execution "
            "target while command, refusal, fallback, cleanup, output acceptance, "
            "and receipt semantics remain under local authority?"
        ),
    }
    return _seal(payload, "invocation_sha256")


def verify_execution_target_invocation(invocation: Mapping[str, Any]) -> None:
    if invocation.get("schema_version") != EXECUTION_TARGET_INVOCATION_SCHEMA_VERSION:
        raise ValueError("unsupported execution-target invocation schema")
    if invocation.get("artifact_type") != EXECUTION_TARGET_INVOCATION_ARTIFACT_TYPE:
        raise ValueError("execution-target invocation artifact_type is invalid")
    _verify_seal(
        invocation,
        field_name="invocation_sha256",
        artifact_name="execution-target invocation",
    )

    capsule = _mapping(invocation.get("capsule"), "invocation.capsule")
    capsule_unsigned = {
        "capsule_id": _text(capsule.get("capsule_id"), "invocation.capsule.capsule_id"),
        "workload_sha256": _sha(
            capsule.get("workload_sha256"),
            "invocation.capsule.workload_sha256",
        ),
        "descriptor_sha256": _sha(
            capsule.get("descriptor_sha256"),
            "invocation.capsule.descriptor_sha256",
        ),
        "input_sha256": _sha(
            capsule.get("input_sha256"),
            "invocation.capsule.input_sha256",
        ),
        "accepted_output_sha256": _sha(
            capsule.get("accepted_output_sha256"),
            "invocation.capsule.accepted_output_sha256",
        ),
    }
    capsule_sha = _sha(
        capsule.get("capsule_sha256"),
        "invocation.capsule.capsule_sha256",
    )
    if capsule_sha != sha256_json(capsule_unsigned):
        raise ValueError("execution-target capsule seal mismatch")

    interface = _mapping(invocation.get("interface"), "invocation.interface")
    if interface.get("abi") != EXECUTION_TARGET_ABI:
        raise ValueError("execution-target invocation ABI mismatch")
    required = _strings(
        interface.get("required_capabilities"),
        "invocation.interface.required_capabilities",
    )
    if EXECUTION_TARGET_ABI not in required:
        raise ValueError("execution-target invocation omits ABI capability")
    _strings(interface.get("commands"), "invocation.interface.commands")

    policy = _mapping(invocation.get("policy"), "invocation.policy")
    if policy.get("acceptance_authority") != "local":
        raise ValueError("execution-target acceptance authority must remain local")
    if policy.get("provider_authority") != "execution_only":
        raise ValueError("execution-target provider authority must be execution_only")
    _text(policy.get("software_fallback_id"), "invocation.policy.software_fallback_id")
    _positive_integer(policy.get("timeout_seconds"), "invocation.policy.timeout_seconds")
    _boolean(
        policy.get("cleanup_required_after_prepare"),
        "invocation.policy.cleanup_required_after_prepare",
    )


def _exception_record(stage: str, exc: TargetRefusal | TargetFault) -> dict[str, Any]:
    state = "refused" if isinstance(exc, TargetRefusal) else "faulted"
    return _stage_record(
        stage=stage,
        state=state,
        detail=exc.detail,
        blocker=exc.blocker,
        observations=exc.observations,
        artifacts=exc.artifacts,
    )


def _unexpected_fault(stage: str, exc: Exception) -> TargetFault:
    detail = f"{type(exc).__name__}: {exc}".strip()
    return TargetFault(
        "TARGET_ADAPTER_EXCEPTION",
        detail or type(exc).__name__,
    )


def _append_completed(
    history: list[dict[str, Any]],
    *,
    stage: str,
    result: TargetStageResult,
) -> None:
    normalized = _normalize_stage_result(result, stage)
    history.append(
        _stage_record(
            stage=stage,
            state="completed",
            detail=f"{stage} completed",
            blocker=None,
            observations=normalized["observations"],
            artifacts=normalized["artifacts"],
        )
    )


def _observation(history: Sequence[Mapping[str, Any]], name: str) -> JsonScalar:
    for record in reversed(history):
        observations = _mapping(record.get("observations", {}), "stage observations")
        if name in observations:
            value = observations[name]
            if isinstance(value, (str, int, float, bool, type(None))):
                return value
    return None


def execute_target_attempt(
    invocation: Mapping[str, Any],
    adapter: ExecutionTargetAdapter,
) -> dict[str, Any]:
    """Execute one target attempt while preserving refusal and cleanup custody."""

    verify_execution_target_invocation(invocation)
    target = adapter.descriptor.as_dict()
    required_capabilities = set(invocation["interface"]["required_capabilities"])
    target_capabilities = set(target["capabilities"])
    missing_capabilities = sorted(required_capabilities - target_capabilities)

    history: list[dict[str, Any]] = []
    blockers: list[str] = []
    terminal_state = "accepted"
    prepared = False
    cleanup_attempted = False
    cleanup_completed = False

    if missing_capabilities:
        blocker = "TARGET_CAPABILITY_MISSING"
        blockers.append(blocker)
        terminal_state = "refused"
        history.append(
            _stage_record(
                stage="discover",
                state="refused",
                detail=(
                    "target is missing required capabilities: "
                    + ", ".join(missing_capabilities)
                ),
                blocker=blocker,
                observations={"missing_capability_count": len(missing_capabilities)},
                artifacts=(),
            )
        )
    else:
        methods = (
            ("discover", adapter.discover),
            ("prepare", adapter.prepare),
            ("execute", adapter.execute),
            ("observe", adapter.observe),
            ("collect", adapter.collect),
        )
        for stage, method in methods:
            try:
                result = method(invocation)
                _append_completed(history, stage=stage, result=result)
                if stage == "prepare":
                    prepared = True
            except TargetRefusal as exc:
                history.append(_exception_record(stage, exc))
                blockers.append(exc.blocker)
                terminal_state = "refused"
                break
            except TargetFault as exc:
                history.append(_exception_record(stage, exc))
                blockers.append(exc.blocker)
                terminal_state = "faulted"
                break
            except Exception as exc:  # pragma: no cover - adapter product boundary
                fault = _unexpected_fault(stage, exc)
                history.append(_exception_record(stage, fault))
                blockers.append(fault.blocker)
                terminal_state = "faulted"
                break

    cleanup_required = bool(
        target["cleanup_required"]
        and invocation["policy"]["cleanup_required_after_prepare"]
    )
    if prepared and cleanup_required:
        cleanup_attempted = True
        try:
            cleanup_result = adapter.cleanup(invocation)
            _append_completed(history, stage="cleanup", result=cleanup_result)
            cleanup_completed = True
        except TargetRefusal as exc:
            history.append(_exception_record("cleanup", exc))
            blockers.append(exc.blocker)
            blockers.append("TARGET_CLEANUP_FAILED")
            terminal_state = "faulted"
        except TargetFault as exc:
            history.append(_exception_record("cleanup", exc))
            blockers.append(exc.blocker)
            blockers.append("TARGET_CLEANUP_FAILED")
            terminal_state = "faulted"
        except Exception as exc:  # pragma: no cover - adapter product boundary
            fault = _unexpected_fault("cleanup", exc)
            history.append(_exception_record("cleanup", fault))
            blockers.extend((fault.blocker, "TARGET_CLEANUP_FAILED"))
            terminal_state = "faulted"

    observed_output = _observation(history, "observed_output_sha256")
    observed_output_sha256 = (
        _sha(
            observed_output,
            "attempt observed_output_sha256",
            optional=True,
        )
        if observed_output is not None
        else None
    )
    expected_output_sha256 = str(invocation["capsule"]["accepted_output_sha256"])
    output_matches = observed_output_sha256 == expected_output_sha256
    target_receipt = _observation(history, "target_receipt_sha256")
    target_receipt_sha256 = (
        _sha(target_receipt, "attempt target_receipt_sha256", optional=True)
        if target_receipt is not None
        else None
    )

    if terminal_state == "accepted" and not output_matches:
        blockers.append("ACCEPTED_OUTPUT_MISMATCH_OR_MISSING")
        terminal_state = "refused"
    if terminal_state == "accepted" and target_receipt_sha256 is None:
        blockers.append("TARGET_RECEIPT_MISSING")
        terminal_state = "refused"
    if terminal_state == "accepted" and cleanup_required and not cleanup_completed:
        blockers.append("TARGET_CLEANUP_INCOMPLETE")
        terminal_state = "faulted"
    if terminal_state != "accepted":
        blockers.append("TARGET_EXECUTION_NOT_ACCEPTED")

    blockers.extend(PHYSICAL_BLOCKERS)
    deduplicated_blockers = list(dict.fromkeys(blockers))
    accepted = terminal_state == "accepted"
    status = (
        "reference_target_execution_proved"
        if accepted and target["target_class"] == "reference_software"
        else "target_execution_proved"
        if accepted
        else terminal_state
    )

    payload: dict[str, Any] = {
        "schema_version": EXECUTION_TARGET_ATTEMPT_SCHEMA_VERSION,
        "artifact_type": EXECUTION_TARGET_ATTEMPT_ARTIFACT_TYPE,
        "invocation": dict(invocation),
        "target": target,
        "stage_history": history,
        "terminal_state": terminal_state,
        "observations": {
            "expected_output_sha256": expected_output_sha256,
            "observed_output_sha256": observed_output_sha256,
            "output_matches": output_matches,
            "target_receipt_sha256": target_receipt_sha256,
            "fallback_used": bool(target["fallback_used"]),
            "cleanup_attempted": cleanup_attempted,
            "cleanup_completed": cleanup_completed,
        },
        "qualification": {
            "status": status,
            "accepted": accepted,
            "execution_claim_allowed": accepted,
            "physical_execution_claim_allowed": False,
            "complete_system_advantage_claim_allowed": False,
            "blockers": deduplicated_blockers,
        },
        "claim_boundary": (
            "This receipt qualifies only the sealed capsule, target identity, stage "
            "history, output digest, fallback state, and cleanup transaction recorded "
            "here. Physical execution, energy, timing, thermal, volume, fabrication, "
            "and complete-system advantage remain separate evidence transactions."
        ),
        "control_question": invocation["control_question"],
    }
    return _seal(payload, "attempt_sha256")


def verify_execution_target_attempt(attempt: Mapping[str, Any]) -> None:
    if attempt.get("schema_version") != EXECUTION_TARGET_ATTEMPT_SCHEMA_VERSION:
        raise ValueError("unsupported execution-target attempt schema")
    if attempt.get("artifact_type") != EXECUTION_TARGET_ATTEMPT_ARTIFACT_TYPE:
        raise ValueError("execution-target attempt artifact_type is invalid")
    _verify_seal(
        attempt,
        field_name="attempt_sha256",
        artifact_name="execution-target attempt",
    )

    invocation = _mapping(attempt.get("invocation"), "attempt.invocation")
    verify_execution_target_invocation(invocation)
    target = TargetDescriptor(
        target_id=_text(
            _mapping(attempt.get("target"), "attempt.target").get("target_id"),
            "attempt.target.target_id",
        ),
        target_class=_text(attempt["target"].get("target_class"), "target_class"),
        implementation=_text(
            attempt["target"].get("implementation"),
            "target implementation",
        ),
        evidence_tier=_text(
            attempt["target"].get("evidence_tier"),
            "target evidence_tier",
        ),
        capabilities=tuple(
            _strings(attempt["target"].get("capabilities"), "target capabilities")
        ),
        fallback_used=_boolean(
            attempt["target"].get("fallback_used"),
            "target fallback_used",
        ),
        cleanup_required=_boolean(
            attempt["target"].get("cleanup_required"),
            "target cleanup_required",
        ),
    ).as_dict()
    if target != attempt["target"]:
        raise ValueError("execution-target descriptor is not canonical")

    history_raw = attempt.get("stage_history")
    if not isinstance(history_raw, Sequence) or isinstance(
        history_raw,
        (str, bytes, bytearray),
    ) or not history_raw:
        raise ValueError("execution-target stage_history must be a non-empty array")
    history = [_mapping(item, "attempt.stage_history[]") for item in history_raw]
    stage_names = [_text(item.get("stage"), "attempt stage") for item in history]
    if len(stage_names) != len(set(stage_names)):
        raise ValueError("execution-target stages must be unique")
    non_cleanup = [stage for stage in stage_names if stage != "cleanup"]
    expected_prefix = list(TARGET_STAGES[: len(non_cleanup)])
    if non_cleanup != expected_prefix:
        raise ValueError("execution-target stages must form the declared prefix")
    if "cleanup" in stage_names and stage_names[-1] != "cleanup":
        raise ValueError("execution-target cleanup must be the final stage")

    for index, record in enumerate(history):
        stage = _text(record.get("stage"), "attempt stage")
        state = _text(record.get("state"), f"attempt stage {stage} state")
        if stage not in TARGET_STAGES or state not in STAGE_STATES:
            raise ValueError("execution-target stage or state is invalid")
        blocker = record.get("blocker")
        if state == "completed" and blocker is not None:
            raise ValueError("completed execution-target stage cannot carry a blocker")
        if state != "completed" and blocker is None:
            raise ValueError("refused or faulted execution-target stage needs a blocker")
        if blocker is not None:
            _blocker(blocker, f"attempt stage {stage} blocker")
        if state != "completed" and stage != "cleanup":
            later_non_cleanup = [
                item
                for item in history[index + 1 :]
                if item.get("stage") != "cleanup"
            ]
            if later_non_cleanup:
                raise ValueError("execution-target cannot advance after refusal or fault")
        _text(record.get("detail"), f"attempt stage {stage} detail")
        _normalize_observations(
            _mapping(record.get("observations", {}), "stage observations"),
            f"attempt stage {stage} observations",
        )
        artifacts = record.get("artifacts", [])
        if not isinstance(artifacts, Sequence) or isinstance(
            artifacts,
            (str, bytes, bytearray),
        ):
            raise ValueError("execution-target stage artifacts must be an array")
        artifact_paths: list[str] = []
        for artifact in artifacts:
            raw = _mapping(artifact, "attempt stage artifact")
            normalized = TargetArtifact(
                path=_text(raw.get("path"), "attempt stage artifact path"),
                role=_text(raw.get("role"), "attempt stage artifact role"),
                sha256=_text(raw.get("sha256"), "attempt stage artifact sha256"),
                size_bytes=_positive_integer(
                    raw.get("size_bytes"),
                    "attempt stage artifact size_bytes",
                ),
            ).as_dict()
            artifact_paths.append(str(normalized["path"]))
        if len(artifact_paths) != len(set(artifact_paths)):
            raise ValueError("execution-target stage artifact paths must be unique")

    terminal_state = _text(attempt.get("terminal_state"), "attempt.terminal_state")
    if terminal_state not in TERMINAL_STATES:
        raise ValueError("execution-target terminal_state is invalid")
    last_non_cleanup = next(
        record for record in reversed(history) if record["stage"] != "cleanup"
    )
    cleanup_record = history[-1] if history[-1]["stage"] == "cleanup" else None
    if cleanup_record is not None and cleanup_record["state"] != "completed":
        expected_terminal = "faulted"
    elif last_non_cleanup["state"] == "refused":
        expected_terminal = "refused"
    elif last_non_cleanup["state"] == "faulted":
        expected_terminal = "faulted"
    else:
        expected_terminal = terminal_state
    if terminal_state != expected_terminal:
        raise ValueError("execution-target terminal state contradicts stage history")

    observations = _mapping(attempt.get("observations"), "attempt.observations")
    expected_output = _sha(
        observations.get("expected_output_sha256"),
        "attempt.observations.expected_output_sha256",
    )
    if expected_output != invocation["capsule"]["accepted_output_sha256"]:
        raise ValueError("execution-target expected output contradicts invocation")
    observed_output = _sha(
        observations.get("observed_output_sha256"),
        "attempt.observations.observed_output_sha256",
        optional=True,
    )
    stage_observed_output = _observation(history, "observed_output_sha256")
    if observed_output != stage_observed_output:
        raise ValueError("execution-target observed output contradicts stage history")
    output_matches = observations.get("output_matches")
    if not isinstance(output_matches, bool) or output_matches != (
        observed_output == expected_output
    ):
        raise ValueError("execution-target output match observation is invalid")
    target_receipt = _sha(
        observations.get("target_receipt_sha256"),
        "attempt.observations.target_receipt_sha256",
        optional=True,
    )
    if target_receipt != _observation(history, "target_receipt_sha256"):
        raise ValueError("execution-target receipt digest contradicts stage history")
    fallback_used = _boolean(
        observations.get("fallback_used"),
        "attempt.observations.fallback_used",
    )
    if fallback_used != target["fallback_used"]:
        raise ValueError("execution-target fallback observation contradicts target")
    cleanup_attempted = _boolean(
        observations.get("cleanup_attempted"),
        "attempt.observations.cleanup_attempted",
    )
    cleanup_completed = _boolean(
        observations.get("cleanup_completed"),
        "attempt.observations.cleanup_completed",
    )
    cleanup_in_history = cleanup_record is not None
    cleanup_history_completed = bool(
        cleanup_record is not None and cleanup_record["state"] == "completed"
    )
    if cleanup_attempted != cleanup_in_history:
        raise ValueError("execution-target cleanup attempt contradicts stage history")
    if cleanup_completed != cleanup_history_completed:
        raise ValueError("execution-target cleanup completion contradicts stage history")

    qualification = _mapping(attempt.get("qualification"), "attempt.qualification")
    accepted = qualification.get("accepted")
    if not isinstance(accepted, bool) or accepted != (terminal_state == "accepted"):
        raise ValueError("execution-target acceptance contradicts terminal state")
    execution_claim_allowed = _boolean(
        qualification.get("execution_claim_allowed"),
        "attempt.qualification.execution_claim_allowed",
    )
    if execution_claim_allowed != accepted:
        raise ValueError("execution-target execution claim contradicts acceptance")
    if qualification.get("physical_execution_claim_allowed") is not False:
        raise ValueError("execution-target attempt cannot self-authorize physical execution")
    if qualification.get("complete_system_advantage_claim_allowed") is not False:
        raise ValueError("execution-target attempt cannot self-authorize system advantage")
    status = _text(qualification.get("status"), "attempt.qualification.status")
    expected_status = (
        "reference_target_execution_proved"
        if accepted and target["target_class"] == "reference_software"
        else "target_execution_proved"
        if accepted
        else terminal_state
    )
    if status != expected_status:
        raise ValueError("execution-target qualification status is invalid")
    blockers = _strings(
        qualification.get("blockers"),
        "attempt.qualification.blockers",
        minimum=len(PHYSICAL_BLOCKERS),
    )
    for index, blocker in enumerate(blockers):
        _blocker(blocker, f"attempt.qualification.blockers[{index}]")
    if not set(PHYSICAL_BLOCKERS).issubset(blockers):
        raise ValueError("execution-target attempt omits retained physical blockers")
    if not accepted and "TARGET_EXECUTION_NOT_ACCEPTED" not in blockers:
        raise ValueError("refused execution-target attempt omits refusal blocker")
    if accepted and (not output_matches or target_receipt is None):
        raise ValueError("accepted execution-target attempt lacks accepted evidence")
    required_cleanup = bool(
        target["cleanup_required"]
        and invocation["policy"]["cleanup_required_after_prepare"]
    )
    if accepted and required_cleanup and not cleanup_completed:
        raise ValueError("accepted execution-target attempt lacks completed cleanup")
    if accepted:
        expected_stages = list(TARGET_STAGES)
        if stage_names != expected_stages:
            raise ValueError("accepted execution-target attempt lacks complete stages")
        if any(record["state"] != "completed" for record in history):
            raise ValueError("accepted execution-target attempt contains failed stage")
    if attempt.get("control_question") != invocation["control_question"]:
        raise ValueError("execution-target control question drifted from invocation")
    _text(attempt.get("claim_boundary"), "attempt.claim_boundary")


class ReferenceSoftwareTargetAdapter:
    """Deterministic reference adapter used to qualify the orchestration seam."""

    def __init__(
        self,
        observed_output_sha256: str,
        *,
        target_id: str = "reference-software-loopback",
    ) -> None:
        self.observed_output_sha256 = _sha(
            observed_output_sha256,
            "reference observed_output_sha256",
        )
        self.descriptor = TargetDescriptor(
            target_id=target_id,
            target_class="reference_software",
            implementation="ahead.reference-software-target/v1",
            evidence_tier="deterministic_reference",
            capabilities=(EXECUTION_TARGET_ABI, "exact", "software_fallback"),
            fallback_used=True,
            cleanup_required=True,
        )

    def discover(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        return TargetStageResult(observations={"available": True})

    def prepare(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        return TargetStageResult(
            observations={
                "prepared_invocation_sha256": str(invocation["invocation_sha256"]),
            }
        )

    def execute(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        dispatch_sha = sha256_json(
            {
                "target_id": self.descriptor.target_id,
                "invocation_sha256": invocation["invocation_sha256"],
                "commands": invocation["interface"]["commands"],
            }
        )
        return TargetStageResult(observations={"dispatch_sha256": dispatch_sha})

    def observe(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        trace_sha = sha256_json(
            {
                "invocation_sha256": invocation["invocation_sha256"],
                "observed_output_sha256": self.observed_output_sha256,
                "terminal": "done",
            }
        )
        return TargetStageResult(
            observations={
                "observed_output_sha256": self.observed_output_sha256,
                "raw_trace_sha256": trace_sha,
            }
        )

    def collect(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        receipt_sha = sha256_json(
            {
                "target_id": self.descriptor.target_id,
                "invocation_sha256": invocation["invocation_sha256"],
                "observed_output_sha256": self.observed_output_sha256,
                "fallback_used": True,
            }
        )
        return TargetStageResult(
            observations={"target_receipt_sha256": receipt_sha}
        )

    def cleanup(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        cleanup_sha = sha256_json(
            {
                "target_id": self.descriptor.target_id,
                "invocation_sha256": invocation["invocation_sha256"],
                "cleanup": "complete",
            }
        )
        return TargetStageResult(
            observations={"cleanup_receipt_sha256": cleanup_sha}
        )


class UnboundPhysicalTargetAdapter:
    """Physical-target placeholder that refuses before preparation."""

    def __init__(
        self,
        *,
        target_id: str = "unbound-fpga-target",
    ) -> None:
        self.descriptor = TargetDescriptor(
            target_id=target_id,
            target_class="fpga",
            implementation="ahead.unbound-physical-target/v1",
            evidence_tier="unbound",
            capabilities=(EXECUTION_TARGET_ABI, "exact", "software_fallback"),
            fallback_used=False,
            cleanup_required=True,
        )

    def discover(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        raise TargetRefusal(
            "TARGET_UNAVAILABLE",
            "no physical target transport or programming authority is bound",
            observations={"available": False},
        )

    def prepare(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        raise AssertionError("prepare must be unreachable after discovery refusal")

    def execute(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        raise AssertionError("execute must be unreachable after discovery refusal")

    def observe(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        raise AssertionError("observe must be unreachable after discovery refusal")

    def collect(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        raise AssertionError("collect must be unreachable after discovery refusal")

    def cleanup(self, invocation: Mapping[str, Any]) -> TargetStageResult:
        raise AssertionError("cleanup must be unreachable before preparation")


def write_json_artifact(
    output_path: str | Path,
    artifact: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
