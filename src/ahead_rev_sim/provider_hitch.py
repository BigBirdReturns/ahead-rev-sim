"""Provider-neutral hitches for RISC-V hosts and physical-compute cartridges.

A hitch is an integration surface, not a partnership, endorsement, or transfer
of architectural authority.  Hosts and cartridges remain independently
replaceable behind the ordinary ``physical-compute-mmio/v1`` transaction.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .mmio_abi import (
    CAPABILITY_BITS,
    COMMAND_BITS,
    MMIO_WORD_BYTES,
    build_mmio_abi,
    canonical_json,
)
from .physical_constants import OPTIONAL_RISCV_EXTENSION, PORTABLE_BINDING
from .physical_serialization import is_sha256

HITCH_SCHEMA_VERSION = "ahead.physical-compute-provider-hitch/v0.1"
CONSIST_SCHEMA_VERSION = "ahead.physical-compute-consist/v0.1"

HITCH_ROLES = ("host", "cartridge")
MANIFEST_KINDS = ("offer", "reference", "submission")
REALIZATION_CLASSES = ("physical", "virtual_reference")
ARTIFACT_STATUSES = ("missing", "present", "not_applicable")
ARTIFACT_REQUIREMENTS = ("execution", "physical_claim", "optional")
EVIDENCE_CLASSES = (
    "public_signal",
    "source",
    "simulated",
    "target_observed",
    "measured",
    "independently_validated",
)
DIGEST_LENGTHS = {"sha256": 64, "git-sha1": 40}
DIGEST_SCOPES = ("content", "git_blob", "artifact_seal")

ROLE_ARTIFACT_SLOTS: Mapping[str, Mapping[str, str]] = {
    "host": {
        "riscv_implementation": "execution",
        "mmio_driver": "execution",
        "accepted_target_trace": "execution",
        "reset_refusal_receipt": "execution",
        "toolchain_receipt": "execution",
        "full_system_energy_receipt": "physical_claim",
        "timing_thermal_volume_receipt": "physical_claim",
        "independent_validation_receipt": "physical_claim",
    },
    "cartridge": {
        "substrate_descriptor": "execution",
        "software_fallback": "execution",
        "device_interface": "execution",
        "accepted_output_receipt": "execution",
        "reset_state_receipt": "execution",
        "complete_system_energy_receipt": "physical_claim",
        "timing_thermal_volume_receipt": "physical_claim",
        "independent_validation_receipt": "physical_claim",
    },
}

_RESERVED_AUTHORITY_KEYS = {
    "architecture_authority",
    "evidence_authority",
    "fallback_authority",
    "workload_authority",
    "acceptance_authority",
}


def _normalized_digest(digest: Mapping[str, Any]) -> tuple[str, str, str]:
    algorithm = str(digest.get("algorithm", ""))
    value = str(digest.get("value", "")).lower()
    scope = str(digest.get("scope", ""))
    expected_length = DIGEST_LENGTHS.get(algorithm)
    if expected_length is None:
        raise ValueError(f"unsupported artifact digest algorithm: {algorithm!r}")
    if len(value) != expected_length or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"invalid {algorithm} artifact digest")
    if scope not in DIGEST_SCOPES:
        raise ValueError(f"invalid artifact digest scope: {scope!r}")
    if algorithm == "git-sha1" and scope != "git_blob":
        raise ValueError("git-sha1 artifact digests must use git_blob scope")
    if algorithm == "sha256" and scope == "git_blob":
        raise ValueError("SHA-256 artifact digests cannot use git_blob scope")
    return algorithm, value, scope


def _without_seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    payload.pop(field, None)
    return payload


def seal_hitch(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical SHA-256-sealed copy of a hitch payload."""

    hitch = _without_seal(payload, "hitch_sha256")
    hitch["hitch_sha256"] = sha256(
        canonical_json(hitch).encode("utf-8")
    ).hexdigest()
    return hitch


def hitch_digest(hitch: Mapping[str, Any]) -> str:
    validate_hitch(hitch)
    return str(hitch["hitch_sha256"])


def load_hitch(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("provider hitch must be a JSON object")
    validate_hitch(payload)
    return payload


def validate_hitch(hitch: Mapping[str, Any]) -> None:
    if hitch.get("schema_version") != HITCH_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported provider hitch schema: {hitch.get('schema_version')!r}"
        )
    if hitch.get("artifact_type") != "physical_compute_provider_hitch":
        raise ValueError("provider hitch artifact_type is invalid")
    if hitch.get("dependency_mode") != "commodity_only":
        raise ValueError("provider hitch dependency_mode must be commodity_only")

    role = str(hitch.get("role", ""))
    manifest_kind = str(hitch.get("manifest_kind", ""))
    realization = str(hitch.get("realization_class", ""))
    if role not in HITCH_ROLES:
        raise ValueError(f"unsupported provider hitch role: {role!r}")
    if manifest_kind not in MANIFEST_KINDS:
        raise ValueError(f"unsupported provider hitch manifest kind: {manifest_kind!r}")
    if realization not in REALIZATION_CLASSES:
        raise ValueError(
            f"unsupported provider hitch realization class: {realization!r}"
        )

    for field in (
        "hitch_id",
        "issuer",
        "actor",
        "project",
        "commodity_record_id",
        "claim_boundary",
    ):
        if not str(hitch.get(field, "")).strip():
            raise ValueError(f"provider hitch {field} is required")
    if manifest_kind == "offer" and hitch.get("actor_acknowledged") is not False:
        raise ValueError("an integration offer must not imply actor acknowledgement")
    if manifest_kind == "submission" and hitch.get("actor_acknowledged") is not True:
        raise ValueError("an actor submission requires explicit actor acknowledgement")
    if not isinstance(hitch.get("actor_acknowledged"), bool):
        raise ValueError("provider hitch actor_acknowledged must be boolean")

    interface = hitch.get("interface")
    if not isinstance(interface, Mapping):
        raise ValueError("provider hitch interface must be an object")
    if interface.get("portable_binding") != PORTABLE_BINDING:
        raise ValueError(f"provider hitch must use {PORTABLE_BINDING}")
    packaged_abi = build_mmio_abi()
    if interface.get("abi_sha256") != packaged_abi["abi_sha256"]:
        raise ValueError(
            "provider hitch ABI digest does not match the packaged MMIO ABI"
        )
    if interface.get("byte_order") != "little":
        raise ValueError("provider hitch byte order must be little")
    if interface.get("word_bytes") != MMIO_WORD_BYTES:
        raise ValueError(f"provider hitch word_bytes must be {MMIO_WORD_BYTES}")
    if interface.get("optional_riscv_extension") != OPTIONAL_RISCV_EXTENSION:
        raise ValueError(
            f"optional RISC-V acceleration must be {OPTIONAL_RISCV_EXTENSION}"
        )
    if interface.get("xphys_policy") != "evidence_only":
        raise ValueError("Xphys policy must remain evidence_only")

    known_commands = set(COMMAND_BITS)
    required_commands = tuple(map(str, interface.get("required_commands", ())))
    declared_commands = tuple(map(str, interface.get("declared_commands", ())))
    if not required_commands or len(set(required_commands)) != len(required_commands):
        raise ValueError("required commands must be non-empty and unique")
    if len(set(declared_commands)) != len(declared_commands):
        raise ValueError("declared commands must be unique")
    if set(required_commands) - known_commands or set(declared_commands) - known_commands:
        raise ValueError("provider hitch contains an unknown MMIO command")
    if set(required_commands) != known_commands:
        raise ValueError(
            "every provider hitch must reserve the complete MMIO command surface"
        )

    known_capabilities = set(CAPABILITY_BITS)
    required_capabilities = tuple(
        map(str, interface.get("required_capabilities", ()))
    )
    declared_capabilities = tuple(
        map(str, interface.get("declared_capabilities", ()))
    )
    any_of_capabilities = tuple(map(str, interface.get("any_of_capabilities", ())))
    for name, values in (
        ("required_capabilities", required_capabilities),
        ("declared_capabilities", declared_capabilities),
        ("any_of_capabilities", any_of_capabilities),
    ):
        if len(set(values)) != len(values):
            raise ValueError(f"{name} must be unique")
        if set(values) - known_capabilities:
            raise ValueError(f"{name} contains an unknown capability")
    if "software_fallback" not in required_capabilities:
        raise ValueError("every provider hitch must require software fallback")
    if role == "cartridge" and set(any_of_capabilities) != {
        "exact",
        "trace_replay",
        "distributional",
    }:
        raise ValueError(
            "cartridge hitch must admit exactly one packaged determinism class"
        )
    if role == "host" and any_of_capabilities:
        raise ValueError("host hitch may not declare a cartridge determinism choice")
    if manifest_kind == "offer" and (declared_commands or declared_capabilities):
        raise ValueError(
            "an integration offer may reserve requirements but may not declare implementation"
        )
    declared_determinism = set(declared_capabilities).intersection(
        {"exact", "trace_replay", "distributional"}
    )
    if role == "cartridge" and len(declared_determinism) > 1:
        raise ValueError("a cartridge may declare only one determinism capability")

    sources = hitch.get("public_sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("provider hitch public_sources must be a non-empty array")
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("every provider hitch public source must be an object")
        if not str(source.get("url", "")).startswith("https://"):
            raise ValueError("every provider hitch public source must use HTTPS")
        if not str(source.get("title", "")).strip():
            raise ValueError("every provider hitch public source requires a title")
        if not str(source.get("completion_signal", "")).strip():
            raise ValueError(
                "every provider hitch public source requires a completion signal"
            )

    artifacts = hitch.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("provider hitch artifacts must be a non-empty array")
    slots: dict[str, Mapping[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise ValueError("every provider hitch artifact must be an object")
        slot = str(artifact.get("slot", ""))
        if not slot or slot in slots:
            raise ValueError(
                "provider hitch artifact slots must be non-empty and unique"
            )
        slots[slot] = artifact
        requirement = str(artifact.get("required_for", ""))
        status = str(artifact.get("status", ""))
        evidence_class = str(artifact.get("evidence_class", ""))
        if requirement not in ARTIFACT_REQUIREMENTS:
            raise ValueError(f"{slot}: invalid artifact requirement")
        if status not in ARTIFACT_STATUSES:
            raise ValueError(f"{slot}: invalid artifact status")
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"{slot}: invalid artifact evidence class")

        locator = artifact.get("locator")
        digest = artifact.get("digest")
        if status == "present":
            if not isinstance(locator, str) or not locator.startswith(
                ("https://", "repo://", "workflow://", "artifact://")
            ):
                raise ValueError(
                    f"{slot}: present artifacts require a supported locator"
                )
            if not isinstance(digest, Mapping):
                raise ValueError(f"{slot}: present artifacts require a digest")
            _normalized_digest(digest)
        else:
            if locator is not None or digest is not None:
                raise ValueError(
                    f"{slot}: absent artifacts cannot carry locator or digest"
                )
        if status == "not_applicable" and not (
            realization == "virtual_reference"
            and requirement == "physical_claim"
        ):
            raise ValueError(
                f"{slot}: only virtual-reference physical-claim artifacts "
                "may be not_applicable"
            )
        if (
            manifest_kind == "offer"
            and requirement in {"execution", "physical_claim"}
            and status != "missing"
        ):
            raise ValueError(
                f"{slot}: an integration offer cannot self-supply qualification evidence"
            )
        if (
            status == "present"
            and requirement == "physical_claim"
            and evidence_class not in {"measured", "independently_validated"}
        ):
            raise ValueError(
                f"{slot}: physical-claim evidence must be measured or independently validated"
            )
        if (
            status == "present"
            and slot
            in {
                "accepted_target_trace",
                "reset_refusal_receipt",
                "accepted_output_receipt",
                "reset_state_receipt",
            }
            and evidence_class
            not in {"target_observed", "measured", "independently_validated"}
        ):
            raise ValueError(
                f"{slot}: execution receipts require target-observed or stronger evidence"
            )

    expected_slots = ROLE_ARTIFACT_SLOTS[role]
    for slot, requirement in expected_slots.items():
        if slot not in slots:
            raise ValueError(
                f"{role} hitch is missing required artifact slot {slot!r}"
            )
        if slots[slot].get("required_for") != requirement:
            raise ValueError(f"{slot}: artifact requirement must be {requirement}")

    if "xphys_acceleration" in declared_capabilities:
        xphys = slots.get("xphys_bottleneck_receipt")
        if (
            xphys is None
            or xphys.get("status") != "present"
            or xphys.get("evidence_class")
            not in {"target_observed", "measured", "independently_validated"}
        ):
            raise ValueError(
                "Xphys acceleration requires a target-observed bottleneck receipt"
            )
    if "measured_energy" in declared_capabilities:
        energy_slot = (
            "full_system_energy_receipt"
            if role == "host"
            else "complete_system_energy_receipt"
        )
        energy = slots[energy_slot]
        if energy.get("status") != "present" or energy.get(
            "evidence_class"
        ) not in {"measured", "independently_validated"}:
            raise ValueError(
                "measured_energy capability requires measured complete-system energy evidence"
            )

    serialized = canonical_json(hitch)
    for key in _RESERVED_AUTHORITY_KEYS:
        if f'"{key}"' in serialized:
            raise ValueError(f"provider hitch may not claim {key}")

    claimed = str(hitch.get("hitch_sha256", ""))
    if not is_sha256(claimed):
        raise ValueError("provider hitch requires a lowercase SHA-256 seal")
    expected = sha256(
        canonical_json(_without_seal(hitch, "hitch_sha256")).encode("utf-8")
    ).hexdigest()
    if claimed != expected:
        raise ValueError(
            "provider hitch SHA-256 seal does not match its content"
        )


def _artifact_blockers(
    hitch: Mapping[str, Any],
    requirement: str,
) -> list[str]:
    blockers: list[str] = []
    role = str(hitch["role"]).upper()
    for artifact in hitch["artifacts"]:
        if artifact["required_for"] != requirement:
            continue
        if artifact["status"] == "missing":
            blockers.append(f"{role}_{str(artifact['slot']).upper()}_MISSING")
    return blockers


def _interface_submission_blockers(
    hitch: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    role = str(hitch["role"]).upper()
    interface = hitch["interface"]
    if hitch["manifest_kind"] == "offer":
        blockers.append(f"{role}_SUBMISSION_ABSENT")

    missing_commands = sorted(
        set(interface["required_commands"]) - set(interface["declared_commands"])
    )
    blockers.extend(
        f"{role}_COMMAND_{command.upper()}_UNDECLARED"
        for command in missing_commands
    )
    missing_capabilities = sorted(
        set(interface["required_capabilities"])
        - set(interface["declared_capabilities"])
    )
    blockers.extend(
        f"{role}_CAPABILITY_{capability.upper()}_UNDECLARED"
        for capability in missing_capabilities
    )
    any_of = set(interface["any_of_capabilities"])
    if any_of and not any_of.intersection(interface["declared_capabilities"]):
        blockers.append(f"{role}_DETERMINISM_CAPABILITY_UNDECLARED")
    return blockers


def build_consist(
    host: Mapping[str, Any],
    cartridge: Mapping[str, Any],
) -> dict[str, Any]:
    """Compose one host hitch and one cartridge hitch into a sealed consist."""

    validate_hitch(host)
    validate_hitch(cartridge)
    if host["role"] != "host":
        raise ValueError("consist host hitch must have role=host")
    if cartridge["role"] != "cartridge":
        raise ValueError("consist cartridge hitch must have role=cartridge")

    interface_blockers: list[str] = []
    host_interface = host["interface"]
    cartridge_interface = cartridge["interface"]
    for field, blocker in (
        ("portable_binding", "PORTABLE_BINDING_MISMATCH"),
        ("abi_sha256", "MMIO_ABI_MISMATCH"),
        ("byte_order", "BYTE_ORDER_MISMATCH"),
        ("word_bytes", "MMIO_WORD_SIZE_MISMATCH"),
        ("optional_riscv_extension", "OPTIONAL_EXTENSION_MISMATCH"),
        ("xphys_policy", "XPHYS_POLICY_MISMATCH"),
    ):
        if host_interface[field] != cartridge_interface[field]:
            interface_blockers.append(blocker)

    execution_blockers = list(interface_blockers)
    execution_blockers.extend(_interface_submission_blockers(host))
    execution_blockers.extend(_interface_submission_blockers(cartridge))
    execution_blockers.extend(_artifact_blockers(host, "execution"))
    execution_blockers.extend(_artifact_blockers(cartridge, "execution"))
    execution_blockers = list(dict.fromkeys(execution_blockers))

    claim_blockers: list[str] = []
    claim_blockers.extend(_artifact_blockers(host, "physical_claim"))
    claim_blockers.extend(_artifact_blockers(cartridge, "physical_claim"))
    if host["realization_class"] != "physical":
        claim_blockers.append("HOST_PHYSICAL_REALIZATION_ABSENT")
    if cartridge["realization_class"] != "physical":
        claim_blockers.append("CARTRIDGE_PHYSICAL_REALIZATION_ABSENT")
    claim_blockers = list(dict.fromkeys(claim_blockers))

    interface_state = "compatible" if not interface_blockers else "incompatible"
    execution_admission = "accepted" if not execution_blockers else "refused"
    if interface_state == "incompatible":
        qualification_state = "interface_refused"
    elif execution_admission == "accepted":
        qualification_state = "execution_admitted"
    else:
        qualification_state = "hitchable_unqualified"

    negotiated_commands = sorted(
        set(host_interface["declared_commands"]).intersection(
            cartridge_interface["declared_commands"]
        )
    )
    negotiated_capabilities = sorted(
        set(host_interface["declared_capabilities"]).intersection(
            cartridge_interface["declared_capabilities"]
        )
    )

    consist: dict[str, Any] = {
        "schema_version": CONSIST_SCHEMA_VERSION,
        "artifact_type": "physical_compute_consist",
        "portable_binding": PORTABLE_BINDING,
        "abi_sha256": build_mmio_abi()["abi_sha256"],
        "host": {
            "hitch_id": host["hitch_id"],
            "actor": host["actor"],
            "project": host["project"],
            "hitch_sha256": host["hitch_sha256"],
        },
        "cartridge": {
            "hitch_id": cartridge["hitch_id"],
            "actor": cartridge["actor"],
            "project": cartridge["project"],
            "hitch_sha256": cartridge["hitch_sha256"],
        },
        "interface_state": interface_state,
        "qualification_state": qualification_state,
        "execution_admission": execution_admission,
        "hitchable": interface_state == "compatible",
        "negotiated_commands": negotiated_commands,
        "negotiated_capabilities": negotiated_capabilities,
        "execution_blockers": execution_blockers,
        "physical_claim_blockers": claim_blockers,
        "physical_compute_claim_allowed": (
            execution_admission == "accepted" and not claim_blockers
        ),
        "physical_energy_claim_allowed": (
            execution_admission == "accepted" and not claim_blockers
        ),
        "substitution_contract": {
            "dependency_mode": "commodity_only",
            "host_replaceable": True,
            "cartridge_replaceable": True,
            "software_fallback_required": True,
            "provider_may_change": [
                "implementation",
                "microarchitecture",
                "physical_substrate",
                "packaging",
                "internal_compiler",
            ],
            "provider_may_not_change": [
                "portable_binding",
                "accepted_work",
                "refusal_semantics",
                "software_fallback",
                "receipt_schema",
                "evidence_boundary",
            ],
        },
        "claim_boundary": (
            "The consist establishes whether a host and cartridge can couple behind "
            "physical-compute-mmio/v1 while remaining independently replaceable. An "
            "integration offer reserves a compatible surface but does not assert actor "
            "participation, implementation readiness, target execution, physical work, "
            "energy advantage, timing, thermal closure, occupied volume, or silicon."
        ),
    }
    consist["consist_sha256"] = sha256(
        canonical_json(consist).encode("utf-8")
    ).hexdigest()
    return consist


def validate_consist(
    consist: Mapping[str, Any],
    *,
    host: Mapping[str, Any] | None = None,
    cartridge: Mapping[str, Any] | None = None,
) -> None:
    if consist.get("schema_version") != CONSIST_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported physical-compute consist schema: "
            f"{consist.get('schema_version')!r}"
        )
    if consist.get("artifact_type") != "physical_compute_consist":
        raise ValueError("physical-compute consist artifact_type is invalid")
    if consist.get("portable_binding") != PORTABLE_BINDING:
        raise ValueError("physical-compute consist portable binding is invalid")
    if consist.get("abi_sha256") != build_mmio_abi()["abi_sha256"]:
        raise ValueError("physical-compute consist ABI digest is invalid")

    claimed = str(consist.get("consist_sha256", ""))
    if not is_sha256(claimed):
        raise ValueError("physical-compute consist requires a SHA-256 seal")
    expected = sha256(
        canonical_json(_without_seal(consist, "consist_sha256")).encode("utf-8")
    ).hexdigest()
    if claimed != expected:
        raise ValueError(
            "physical-compute consist SHA-256 seal does not match its content"
        )

    if host is not None and cartridge is not None:
        rebuilt = build_consist(host, cartridge)
        if canonical_json(rebuilt) != canonical_json(consist):
            raise ValueError(
                "physical-compute consist does not match its provider hitches"
            )


def format_consist(consist: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "PHYSICAL-COMPUTE CONSIST",
            f"host: {consist['host']['actor']} / {consist['host']['project']}",
            (
                "cartridge: "
                f"{consist['cartridge']['actor']} / "
                f"{consist['cartridge']['project']}"
            ),
            f"interface: {consist['interface_state']}",
            f"qualification: {consist['qualification_state']}",
            f"execution: {consist['execution_admission']}",
            f"execution blockers: {len(consist['execution_blockers'])}",
            (
                "physical claim blockers: "
                f"{len(consist['physical_claim_blockers'])}"
            ),
            f"consist sha256: {consist['consist_sha256']}",
        )
    )


def write_consist(
    path: str | Path,
    consist: Mapping[str, Any],
) -> Path:
    validate_consist(consist)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(consist, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
