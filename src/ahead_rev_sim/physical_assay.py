"""Task assay for harvested-world and reservoir compute substrates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Sequence

from .physical_constants import DynamicsClass, EvidenceClass, RealizationClass
from .physical_descriptor import PhysicalSubstrateDescriptor
from .physical_serialization import is_sha256, jsonable, sha256_json

ASSAY_SCHEMA_VERSION = "ahead.physical-reservoir-assay/v0.1"


class EpisodeSplit(str, Enum):
    TRAIN = "train"
    TEST = "test"


@dataclass(frozen=True)
class ReservoirEpisode:
    episode_id: str
    label: str
    split: EpisodeSplit
    stimulus: tuple[int, ...]
    response: tuple[int, ...]
    calibration_sha256: str
    environment_sha256: str
    evidence_class: EvidenceClass = EvidenceClass.SIMULATED
    fallback_used: bool = True

    def __post_init__(self) -> None:
        if not self.episode_id or not self.label or not self.stimulus or not self.response:
            raise ValueError("episode identity, label, stimulus, and response are required")
        for digest in (self.calibration_sha256, self.environment_sha256):
            if not is_sha256(digest):
                raise ValueError("calibration and environment hashes must be SHA-256")

    @property
    def sha256(self) -> str:
        return sha256_json(jsonable(self))


@dataclass(frozen=True)
class ReservoirAssayContract:
    assay_id: str
    accepted_work_unit: str
    expected_labels: tuple[str, ...]
    minimum_test_accuracy: float = 1.0
    minimum_compute_gain: float = 0.0
    minimum_response_margin: float = 0.0
    minimum_train_per_label: int = 1

    def __post_init__(self) -> None:
        if not self.assay_id or not self.accepted_work_unit:
            raise ValueError("assay identity and accepted work are required")
        if len(self.expected_labels) < 2 or len(set(self.expected_labels)) != len(self.expected_labels):
            raise ValueError("at least two unique labels are required")
        if not 0 <= self.minimum_test_accuracy <= 1:
            raise ValueError("minimum_test_accuracy must be within [0, 1]")
        if not -1 <= self.minimum_compute_gain <= 1:
            raise ValueError("minimum_compute_gain must be within [-1, 1]")
        if self.minimum_train_per_label < 1:
            raise ValueError("minimum_train_per_label must be positive")

    @property
    def sha256(self) -> str:
        return sha256_json(jsonable(self))


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def _readout(
    train: Sequence[ReservoirEpisode],
    test: Sequence[ReservoirEpisode],
    vector_name: str,
    labels: Sequence[str],
) -> dict[str, Any]:
    centroids: dict[str, tuple[float, ...]] = {}
    for label in labels:
        vectors = [getattr(item, vector_name) for item in train if item.label == label]
        width = len(vectors[0])
        centroids[label] = tuple(
            sum(float(vector[index]) for vector in vectors) / len(vectors)
            for index in range(width)
        )

    predictions = []
    for item in test:
        vector = tuple(float(value) for value in getattr(item, vector_name))
        distances = {label: _distance(vector, centroid) for label, centroid in centroids.items()}
        predicted = min(distances, key=lambda label: (distances[label], label))
        predictions.append(
            {
                "episode_id": item.episode_id,
                "expected": item.label,
                "predicted": predicted,
                "distance": round(distances[predicted], 9),
            }
        )

    accuracy = sum(row["expected"] == row["predicted"] for row in predictions) / len(predictions)
    radius = max(
        _distance(
            tuple(float(value) for value in getattr(item, vector_name)),
            centroids[item.label],
        )
        for item in train
    )
    label_order = sorted(centroids)
    inter = [
        _distance(centroids[left], centroids[right])
        for index, left in enumerate(label_order)
        for right in label_order[index + 1 :]
    ]
    margin = min(inter) - radius
    return {
        "vector": vector_name,
        "centroids": {label: list(values) for label, values in sorted(centroids.items())},
        "test_accuracy": round(accuracy, 9),
        "separation_margin": round(margin, 9),
        "predictions": predictions,
    }


def run_reservoir_assay(
    descriptor: PhysicalSubstrateDescriptor,
    episodes: Sequence[ReservoirEpisode],
    contract: ReservoirAssayContract,
) -> dict[str, Any]:
    ordered = tuple(sorted(episodes, key=lambda item: item.episode_id))
    blockers: list[str] = []

    if descriptor.dynamics_class != DynamicsClass.RESERVOIR:
        blockers.append("DYNAMICS_CLASS_NOT_RESERVOIR")
    if len({item.episode_id for item in ordered}) != len(ordered):
        blockers.append("EPISODE_ID_DUPLICATE")
    if {item.label for item in ordered} - set(contract.expected_labels):
        blockers.append("UNKNOWN_LABEL")
    if len({len(item.stimulus) for item in ordered}) != 1:
        blockers.append("STIMULUS_DIMENSION_MISMATCH")
    if len({len(item.response) for item in ordered}) != 1:
        blockers.append("RESPONSE_DIMENSION_MISMATCH")

    train = tuple(item for item in ordered if item.split == EpisodeSplit.TRAIN)
    test = tuple(item for item in ordered if item.split == EpisodeSplit.TEST)
    for label in contract.expected_labels:
        if sum(item.label == label for item in train) < contract.minimum_train_per_label:
            blockers.append("TRAINING_EPISODES_MISSING")
    if not test:
        blockers.append("TEST_EPISODES_MISSING")

    baseline: dict[str, Any] = {}
    substrate: dict[str, Any] = {}
    if not blockers:
        baseline = _readout(train, test, "stimulus", contract.expected_labels)
        substrate = _readout(train, test, "response", contract.expected_labels)

    baseline_accuracy = float(baseline.get("test_accuracy", 0))
    substrate_accuracy = float(substrate.get("test_accuracy", 0))
    compute_gain = substrate_accuracy - baseline_accuracy
    response_margin = float(substrate.get("separation_margin", 0))

    if not blockers:
        if substrate_accuracy < contract.minimum_test_accuracy:
            blockers.append("TASK_ACCURACY_BELOW_THRESHOLD")
        if compute_gain < contract.minimum_compute_gain:
            blockers.append("COMPUTE_GAIN_BELOW_THRESHOLD")
        if response_margin < contract.minimum_response_margin:
            blockers.append("RESPONSE_SEPARATION_BELOW_THRESHOLD")

    quality_pass = not blockers
    all_measured = bool(ordered) and all(
        item.evidence_class == EvidenceClass.MEASURED for item in ordered
    )
    no_fallback = bool(ordered) and all(not item.fallback_used for item in ordered)
    physical_compute = (
        quality_pass
        and all_measured
        and no_fallback
        and descriptor.realization_class != RealizationClass.VIRTUAL_REFERENCE
    )

    claim_blockers = list(blockers)
    if not all_measured:
        claim_blockers.append("EPISODE_EVIDENCE_NOT_MEASURED")
    if not no_fallback:
        claim_blockers.append("SOFTWARE_FALLBACK_USED")
    if not descriptor.energy_contract.physical_energy_claim_allowed:
        claim_blockers.append("ENERGY_BOUNDARY_UNMEASURED")
    claim_blockers.extend(("OCCUPIED_VOLUME_UNMEASURED", "TIMING_AND_THERMAL_CLOSURE_UNMEASURED"))

    receipt = {
        "schema_version": ASSAY_SCHEMA_VERSION,
        "artifact_type": "physical_reservoir_assay",
        "contract": {
            "assay_id": contract.assay_id,
            "contract_sha256": contract.sha256,
            "accepted_work_unit": contract.accepted_work_unit,
            "minimum_test_accuracy": contract.minimum_test_accuracy,
            "minimum_compute_gain": contract.minimum_compute_gain,
            "minimum_response_margin": contract.minimum_response_margin,
        },
        "substrate": {
            "descriptor_sha256": descriptor.sha256,
            "substrate_id": descriptor.substrate_id,
            "realization_class": descriptor.realization_class.value,
            "environment_boundary": descriptor.environment_boundary,
        },
        "dataset": {
            "episode_sha256": [item.sha256 for item in ordered],
            "dataset_sha256": sha256_json([jsonable(item) for item in ordered]),
            "all_measured": all_measured,
            "no_fallback": no_fallback,
        },
        "baseline_readout": baseline,
        "substrate_readout": substrate,
        "evaluation": {
            "baseline_test_accuracy": round(baseline_accuracy, 9),
            "substrate_test_accuracy": round(substrate_accuracy, 9),
            "compute_gain": round(compute_gain, 9),
            "response_separation_margin": round(response_margin, 9),
        },
        "qualification": {
            "status": (
                "physical_compute_candidate"
                if physical_compute
                else "software_assay_pass"
                if quality_pass
                else "refused"
            ),
            "quality_pass": quality_pass,
            "physical_compute_claim_allowed": physical_compute,
            "end_to_end_advantage_claim_allowed": False,
            "blockers": list(dict.fromkeys(claim_blockers)),
        },
        "claim_boundary": (
            "The assay proves held-out task separation over the raw-stimulus baseline. "
            "Physical compute requires measured non-fallback episodes; energy, timing, "
            "thermal, volume, and end-to-end advantage remain outside this receipt."
        ),
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    return receipt
