from __future__ import annotations

from dataclasses import replace

from ahead_rev_sim.physical_assay import (
    EpisodeSplit,
    ReservoirAssayContract,
    ReservoirEpisode,
    run_reservoir_assay,
)
from ahead_rev_sim.physical_cartridges import harvested_world_descriptor
from ahead_rev_sim.physical_constants import EnergySourceClass, EvidenceClass
from ahead_rev_sim.physical_descriptor import EnergyContract

CALIBRATION = "a" * 64
ENVIRONMENT = "b" * 64


def _episodes(
    *,
    evidence_class: EvidenceClass = EvidenceClass.SIMULATED,
    fallback_used: bool = True,
) -> tuple[ReservoirEpisode, ...]:
    rows = (
        ("s0", "same", EpisodeSplit.TRAIN, (0, 0), (0, 0, 0)),
        ("s1", "same", EpisodeSplit.TRAIN, (10, 10), (0, 1, 0)),
        ("d0", "different", EpisodeSplit.TRAIN, (0, 10), (10, 9, 10)),
        ("d1", "different", EpisodeSplit.TRAIN, (10, 0), (10, 10, 9)),
        ("s2", "same", EpisodeSplit.TEST, (1, 1), (0, 0, 1)),
        ("s3", "same", EpisodeSplit.TEST, (9, 9), (1, 0, 0)),
        ("d2", "different", EpisodeSplit.TEST, (1, 9), (9, 10, 10)),
        ("d3", "different", EpisodeSplit.TEST, (9, 1), (10, 9, 9)),
    )
    return tuple(
        ReservoirEpisode(
            episode_id=episode_id,
            label=label,
            split=split,
            stimulus=stimulus,
            response=response,
            calibration_sha256=CALIBRATION,
            environment_sha256=ENVIRONMENT,
            evidence_class=evidence_class,
            fallback_used=fallback_used,
        )
        for episode_id, label, split, stimulus, response in rows
    )


def _contract() -> ReservoirAssayContract:
    return ReservoirAssayContract(
        assay_id="xor-separation-reference-v1",
        accepted_work_unit="one held-out binary classification",
        expected_labels=("same", "different"),
        minimum_test_accuracy=1.0,
        minimum_compute_gain=0.5,
        minimum_response_margin=5.0,
        minimum_train_per_label=2,
    )


def test_assay_requires_gain_over_raw_stimulus() -> None:
    receipt = run_reservoir_assay(
        harvested_world_descriptor(),
        _episodes(),
        _contract(),
    )

    assert receipt["evaluation"] == {
        "baseline_test_accuracy": 0.5,
        "substrate_test_accuracy": 1.0,
        "compute_gain": 0.5,
        "response_separation_margin": 15.762562311,
    }
    assert receipt["qualification"]["status"] == "software_assay_pass"
    assert receipt["qualification"]["physical_compute_claim_allowed"] is False
    assert "EPISODE_EVIDENCE_NOT_MEASURED" in receipt["qualification"]["blockers"]
    assert "SOFTWARE_FALLBACK_USED" in receipt["qualification"]["blockers"]


def test_assay_receipt_is_order_independent() -> None:
    descriptor = harvested_world_descriptor()
    episodes = _episodes()
    first = run_reservoir_assay(descriptor, episodes, _contract())
    second = run_reservoir_assay(descriptor, tuple(reversed(episodes)), _contract())

    assert first == second
    assert len(first["receipt_sha256"]) == 64


def test_no_substrate_gain_is_refused() -> None:
    episodes = tuple(replace(item, response=item.stimulus) for item in _episodes())
    receipt = run_reservoir_assay(
        harvested_world_descriptor(),
        episodes,
        _contract(),
    )

    assert receipt["evaluation"]["compute_gain"] == 0.0
    assert receipt["qualification"]["status"] == "refused"
    assert "TASK_ACCURACY_BELOW_THRESHOLD" in receipt["qualification"]["blockers"]
    assert "COMPUTE_GAIN_BELOW_THRESHOLD" in receipt["qualification"]["blockers"]


def test_measured_nonfallback_assay_can_admit_physical_compute_only() -> None:
    descriptor = replace(
        harvested_world_descriptor(),
        energy_contract=EnergyContract(
            source_class=EnergySourceClass.AMBIENT_HARVESTED,
            evidence_class=EvidenceClass.MEASURED,
            measurement_boundary="sensor, substrate, readout, and controller",
            instrument_ref="power-analyzer:reference",
            supplied_joules=0.75,
            recovered_or_harvested_joules=0.05,
        ),
    )
    receipt = run_reservoir_assay(
        descriptor,
        _episodes(evidence_class=EvidenceClass.MEASURED, fallback_used=False),
        _contract(),
    )

    assert receipt["qualification"]["status"] == "physical_compute_candidate"
    assert receipt["qualification"]["physical_compute_claim_allowed"] is True
    assert receipt["qualification"]["end_to_end_advantage_claim_allowed"] is False
    assert "EPISODE_EVIDENCE_NOT_MEASURED" not in receipt["qualification"]["blockers"]
    assert "SOFTWARE_FALLBACK_USED" not in receipt["qualification"]["blockers"]
    assert "OCCUPIED_VOLUME_UNMEASURED" in receipt["qualification"]["blockers"]


def test_response_dimension_mismatch_is_named() -> None:
    episodes = list(_episodes())
    episodes[-1] = replace(episodes[-1], response=(10, 9))
    receipt = run_reservoir_assay(
        harvested_world_descriptor(),
        tuple(episodes),
        _contract(),
    )

    assert receipt["qualification"]["status"] == "refused"
    assert "RESPONSE_DIMENSION_MISMATCH" in receipt["qualification"]["blockers"]
    assert receipt["baseline_readout"] == {}
    assert receipt["substrate_readout"] == {}
