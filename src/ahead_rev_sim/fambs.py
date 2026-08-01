"""Deterministic intake and result-contract validation for FAMBS.

The importer binds a Future AI Microbench Suite source tree to one Git commit
and keeps source identity, source-emission shape, reference prose, observed
result streams, and accepted-output custody separate. A timing row proves that
a benchmark reported. It becomes accepted work only after the row matches a
versioned semantic result contract.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

FAMBS_SOURCE_MANIFEST_SCHEMA_VERSION = "ahead.fambs-source-manifest/v0.1"
FAMBS_IMPORT_SCHEMA_VERSION = "ahead.fambs-import/v0.2"
FAMBS_IMPORT_ARTIFACT_TYPE = "fambs_workload_intake"

_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RESULT_RE = re.compile(r"^[0-9a-f]{16}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FambsResultRow:
    bench: str
    cycles: int
    iters: int
    notes: str
    schema: str | None = None
    suite_version: str | None = None
    contract_id: str | None = None
    clock_kind: str | None = None
    result: str | None = None
    result_kind: str | None = None
    accepted: bool | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FambsResultRow":
        required = ("bench", "cycles", "iters", "notes")
        missing = [field for field in required if field not in value]
        if missing:
            raise ValueError(f"result row missing fields: {', '.join(missing)}")

        bench = str(value["bench"])
        cycles = int(value["cycles"])
        iters = int(value["iters"])
        notes = str(value["notes"])
        if not bench:
            raise ValueError("result row bench must be non-empty")
        if cycles < 0 or iters < 0:
            raise ValueError("result row cycles and iters must be non-negative")

        optional_strings: dict[str, str | None] = {}
        for field_name in (
            "schema",
            "suite_version",
            "contract_id",
            "clock_kind",
            "result",
            "result_kind",
        ):
            raw = value.get(field_name)
            if raw is None:
                optional_strings[field_name] = None
            elif not isinstance(raw, str) or not raw:
                raise ValueError(f"result row {field_name} must be a non-empty string")
            else:
                optional_strings[field_name] = raw

        result = optional_strings["result"]
        if result is not None and _RESULT_RE.fullmatch(result) is None:
            raise ValueError("result row result must be 16 lowercase hexadecimal characters")

        accepted_raw = value.get("accepted")
        if accepted_raw is not None and not isinstance(accepted_raw, bool):
            raise ValueError("result row accepted must be boolean when present")

        return cls(
            bench=bench,
            cycles=cycles,
            iters=iters,
            notes=notes,
            schema=optional_strings["schema"],
            suite_version=optional_strings["suite_version"],
            contract_id=optional_strings["contract_id"],
            clock_kind=optional_strings["clock_kind"],
            result=result,
            result_kind=optional_strings["result_kind"],
            accepted=accepted_raw,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "bench": self.bench,
            "cycles": self.cycles,
            "iters": self.iters,
            "notes": self.notes,
        }
        for field_name in (
            "schema",
            "suite_version",
            "contract_id",
            "clock_kind",
            "result",
            "result_kind",
            "accepted",
        ):
            item = getattr(self, field_name)
            if item is not None:
                payload[field_name] = item
        return payload


@dataclass
class FambsImportArtifact:
    schema_version: str
    artifact_type: str
    generated_by: str
    source: dict[str, Any]
    config: dict[str, Any]
    workloads: list[dict[str, Any]]
    source_emission: dict[str, Any]
    result_contract: dict[str, Any] | None
    reference_results: dict[str, Any]
    observed_result_stream: dict[str, Any]
    coverage: dict[str, Any]
    qualification: dict[str, Any]
    claim_boundary: str
    control_question: str
    artifact_sha256: str | None = None

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_hash:
            payload.pop("artifact_sha256", None)
        return payload

    def seal(self) -> str:
        self.artifact_sha256 = sha256_json(self.to_dict(include_hash=False))
        return self.artifact_sha256

    def to_json(self, *, indent: int = 2) -> str:
        if self.artifact_sha256 is None:
            self.seal()
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"


def load_manifest(source: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        manifest = deepcopy(dict(source))
    else:
        manifest = json.loads(Path(source).read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    return manifest


def _expected_standalone_identities(manifest: Mapping[str, Any]) -> list[tuple[str, str]]:
    identities: list[tuple[str, str]] = []
    for record in manifest["workloads"]:
        bench_id = str(record["bench_id"])
        emission = record["emission"]
        standalone_rows = int(emission["standalone_rows"])
        notes = [str(note) for note in emission.get("notes", [])]
        if standalone_rows != len(notes):
            raise ValueError(
                f"workload {bench_id} standalone_rows must equal the number of emitted notes"
            )
        identities.extend((bench_id, note) for note in notes)
    return identities


def _validate_result_contract(
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    for field_name in ("schema", "suite_version", "contract_id"):
        value = contract.get(field_name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"result_contract.{field_name} must be a non-empty string")

    rows = contract.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("result_contract.rows must be a non-empty array")

    expected_identities = _expected_standalone_identities(manifest)
    if len(rows) != len(expected_identities):
        raise ValueError("result_contract row count does not match standalone source emission")

    observed_identities: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"result_contract row {index} must be an object")
        for field_name in ("bench", "notes", "iters", "result", "result_kind"):
            if field_name not in row:
                raise ValueError(f"result_contract row {index} missing {field_name}")
        bench = str(row["bench"])
        notes = str(row["notes"])
        iters = int(row["iters"])
        result = str(row["result"])
        result_kind = str(row["result_kind"])
        if not bench or not result_kind or iters < 0:
            raise ValueError(f"result_contract row {index} contains an invalid identity")
        if _RESULT_RE.fullmatch(result) is None:
            raise ValueError(
                f"result_contract row {index} result must be 16 lowercase hexadecimal characters"
            )
        observed_identities.append((bench, notes))

    if observed_identities != expected_identities:
        raise ValueError("result_contract row order or emitted note identity does not match source")


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != FAMBS_SOURCE_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported FAMBS source manifest schema")

    source = manifest.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("manifest source must be an object")
    commit = str(source.get("commit", ""))
    if _SHA1_RE.fullmatch(commit) is None:
        raise ValueError("manifest source.commit must be a lowercase Git SHA-1")

    config = manifest.get("config")
    workloads = manifest.get("workloads")
    expected_ids = manifest.get("expected_workload_ids")
    if not isinstance(config, Mapping):
        raise ValueError("manifest config must be an object")
    if not isinstance(workloads, list) or not workloads:
        raise ValueError("manifest workloads must be a non-empty array")
    if not isinstance(expected_ids, list) or not expected_ids:
        raise ValueError("manifest expected_workload_ids must be a non-empty array")

    ids: list[str] = []
    for record in workloads:
        if not isinstance(record, Mapping):
            raise ValueError("each workload record must be an object")
        bench_id = str(record.get("bench_id", ""))
        if not bench_id:
            raise ValueError("workload bench_id must be non-empty")
        ids.append(bench_id)
        blob_sha = str(record.get("source_git_blob_sha1", ""))
        if _SHA1_RE.fullmatch(blob_sha) is None:
            raise ValueError(f"workload {bench_id} source_git_blob_sha1 is invalid")
        if not record.get("source_path") or not record.get("workload_class"):
            raise ValueError(f"workload {bench_id} is missing source_path or workload_class")

    if len(ids) != len(set(ids)):
        raise ValueError("manifest workload identifiers must be unique")
    if ids != [str(item) for item in expected_ids]:
        raise ValueError("workload order must match expected_workload_ids")

    declared = manifest.get("source_emission_model")
    if not isinstance(declared, Mapping):
        raise ValueError("manifest source_emission_model must be an object")
    derived = derive_source_emission(manifest)
    if int(declared.get("expected_total_rows", -1)) != derived["expected_total_rows"]:
        raise ValueError("declared source emission total does not match derived total")
    declared_counts = {
        str(key): int(value)
        for key, value in dict(declared.get("expected_bench_counts", {})).items()
    }
    if declared_counts != derived["expected_bench_counts"]:
        raise ValueError("declared source emission bench counts do not match derived counts")

    result_contract = manifest.get("result_contract")
    if result_contract is not None:
        if not isinstance(result_contract, Mapping):
            raise ValueError("result_contract must be an object when present")
        _validate_result_contract(result_contract, manifest)


def parse_jsonl(text: str) -> tuple[list[FambsResultRow], list[dict[str, Any]]]:
    rows: list[FambsResultRow] = []
    errors: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError("JSONL row must be an object")
            rows.append(FambsResultRow.from_mapping(value))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            errors.append(
                {
                    "line": line_number,
                    "error": str(exc),
                    "text_sha256": sha256(line.encode("utf-8")).hexdigest(),
                }
            )
    return rows, errors


def derive_source_emission(manifest: Mapping[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    standalone_rows: dict[str, int] = {}
    for record in manifest["workloads"]:
        bench_id = str(record["bench_id"])
        rows = int(record["emission"]["standalone_rows"])
        if rows < 0:
            raise ValueError(f"workload {bench_id} standalone_rows must be non-negative")
        standalone_rows[bench_id] = rows
        counts[bench_id] += rows

    nested_expansion: list[dict[str, Any]] = []
    for expansion in manifest["source_emission_model"].get("nested_expansions", []):
        parent = str(expansion["parent"])
        iterations = int(expansion["iterations"])
        if iterations < 0:
            raise ValueError(f"nested expansion for {parent} has negative iterations")
        children = {str(key): int(value) for key, value in expansion["children"].items()}
        for child, rows_per_iteration in children.items():
            if rows_per_iteration < 0:
                raise ValueError(f"nested expansion for {child} has negative rows")
            counts[child] += iterations * rows_per_iteration
        nested_expansion.append(
            {
                "parent": parent,
                "iterations": iterations,
                "children": children,
                "expanded_rows": iterations * sum(children.values()),
            }
        )

    expected_ids = [str(item) for item in manifest["expected_workload_ids"]]
    ordered_counts = {bench_id: int(counts.get(bench_id, 0)) for bench_id in expected_ids}
    return {
        "top_level_order": expected_ids,
        "standalone_rows": standalone_rows,
        "nested_expansions": nested_expansion,
        "expected_bench_counts": ordered_counts,
        "expected_total_rows": sum(ordered_counts.values()),
    }


def _rows_summary(rows: Sequence[FambsResultRow]) -> dict[str, Any]:
    counts = Counter(row.bench for row in rows)
    notes: dict[str, list[str]] = defaultdict(list)
    clock_kinds: set[str] = set()
    result_identities: list[dict[str, Any]] = []
    accepted_rows = 0
    rich_rows = 0
    for row in rows:
        if row.notes not in notes[row.bench]:
            notes[row.bench].append(row.notes)
        if row.clock_kind is not None:
            clock_kinds.add(row.clock_kind)
        if row.result is not None:
            result_identities.append(
                {
                    "bench": row.bench,
                    "notes": row.notes,
                    "iters": row.iters,
                    "result": row.result,
                    "result_kind": row.result_kind,
                }
            )
        if row.accepted is True:
            accepted_rows += 1
        if all(
            item is not None
            for item in (
                row.schema,
                row.suite_version,
                row.contract_id,
                row.clock_kind,
                row.result,
                row.result_kind,
                row.accepted,
            )
        ):
            rich_rows += 1
    return {
        "row_count": len(rows),
        "bench_counts": dict(sorted(counts.items())),
        "notes_by_bench": {key: value for key, value in sorted(notes.items())},
        "clock_kinds": sorted(clock_kinds),
        "accepted_rows": accepted_rows,
        "rich_rows": rich_rows,
        "result_identities": result_identities,
        "stream_sha256": sha256_json([row.to_dict() for row in rows]),
    }


def _reference_rows(manifest: Mapping[str, Any]) -> list[FambsResultRow]:
    rows = manifest.get("reference_results", {}).get("rows", [])
    return [FambsResultRow.from_mapping(row) for row in rows]


def _shape_blockers(
    *,
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    prefix: str,
) -> list[str]:
    blockers: list[str] = []
    if int(observed["row_count"]) != int(expected["expected_total_rows"]):
        blockers.append(f"{prefix}_ROW_COUNT_DIVERGES")
    expected_counts = {
        str(key): int(value) for key, value in expected["expected_bench_counts"].items()
    }
    observed_counts = {str(key): int(value) for key, value in observed["bench_counts"].items()}
    if observed_counts != expected_counts:
        blockers.append(f"{prefix}_BENCH_DISTRIBUTION_DIVERGES")
    return blockers


def _result_contract_validation(
    rows: Sequence[FambsResultRow],
    contract: Mapping[str, Any] | None,
    *,
    prefix: str,
    require_clock: bool,
) -> tuple[dict[str, Any], list[str]]:
    if contract is None:
        return {
            "bound": False,
            "status": "unbound",
            "qualified_rows": 0,
            "expected_rows": 0,
            "first_divergence": None,
        }, []

    expected_rows = contract["rows"]
    blockers: list[str] = []
    divergences: list[dict[str, Any]] = []
    if len(rows) != len(expected_rows):
        blockers.append(f"{prefix}_CONTRACT_ROW_COUNT_MISMATCH")

    identity = {
        "schema": contract["schema"],
        "suite_version": contract["suite_version"],
        "contract_id": contract["contract_id"],
    }
    qualified_rows = 0
    for index, (row, expected) in enumerate(zip(rows, expected_rows)):
        row_divergences: list[dict[str, Any]] = []
        for field_name, expected_value in identity.items():
            actual_value = getattr(row, field_name)
            if actual_value != expected_value:
                blockers.append(f"{prefix}_{field_name.upper()}_MISMATCH")
                row_divergences.append(
                    {
                        "field": field_name,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )

        for field_name in ("bench", "notes", "iters"):
            expected_value = expected[field_name]
            actual_value = getattr(row, field_name)
            if actual_value != expected_value:
                blockers.append(f"{prefix}_IDENTITY_MISMATCH")
                row_divergences.append(
                    {
                        "field": field_name,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )

        if row.result != expected["result"]:
            blockers.append(f"{prefix}_VALUE_MISMATCH")
            row_divergences.append(
                {
                    "field": "result",
                    "expected": expected["result"],
                    "actual": row.result,
                }
            )
        if row.result_kind != expected["result_kind"]:
            blockers.append(f"{prefix}_RESULT_KIND_MISMATCH")
            row_divergences.append(
                {
                    "field": "result_kind",
                    "expected": expected["result_kind"],
                    "actual": row.result_kind,
                }
            )
        if row.accepted is not True:
            blockers.append(f"{prefix}_ROW_REJECTED")
            row_divergences.append(
                {"field": "accepted", "expected": True, "actual": row.accepted}
            )
        if require_clock and not row.clock_kind:
            blockers.append(f"{prefix}_CLOCK_KIND_MISSING")
            row_divergences.append(
                {"field": "clock_kind", "expected": "non-empty", "actual": row.clock_kind}
            )

        if row_divergences:
            divergences.append({"row": index, "divergences": row_divergences})
        else:
            qualified_rows += 1

    if require_clock:
        clock_kinds = {row.clock_kind for row in rows if row.clock_kind}
        if len(clock_kinds) > 1:
            blockers.append(f"{prefix}_CLOCK_KIND_MIXED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "bound": True,
        "status": "pass" if not blockers else "fail",
        "qualified_rows": qualified_rows,
        "expected_rows": len(expected_rows),
        "first_divergence": divergences[0] if divergences else None,
        "divergence_count": len(divergences),
    }, blockers


def import_fambs(
    manifest_source: str | Path | Mapping[str, Any],
    *,
    result_stream_text: str | None = None,
) -> FambsImportArtifact:
    manifest = load_manifest(manifest_source)
    source_emission = derive_source_emission(manifest)
    result_contract_raw = manifest.get("result_contract")
    result_contract = deepcopy(result_contract_raw) if result_contract_raw is not None else None

    reference_rows = _reference_rows(manifest)
    reference_summary = _rows_summary(reference_rows)
    reference_blockers = _shape_blockers(
        expected=source_emission,
        observed=reference_summary,
        prefix="REFERENCE_RESULT",
    )

    expected_ids = set(str(item) for item in manifest["expected_workload_ids"])
    expected_notes = {
        str(record["bench_id"]): set(str(note) for note in record["emission"]["notes"])
        for record in manifest["workloads"]
    }
    reference_unknown = sorted(set(reference_summary["bench_counts"]) - expected_ids)
    reference_note_mismatches = {
        bench: notes
        for bench, notes in reference_summary["notes_by_bench"].items()
        if bench in expected_notes and not set(notes).issubset(expected_notes[bench])
    }
    if reference_unknown:
        reference_blockers.append("REFERENCE_RESULT_UNKNOWN_BENCH")
    if reference_note_mismatches:
        reference_blockers.append("REFERENCE_RESULT_NOTES_DIVERGE")

    reference_contract_validation, reference_contract_blockers = _result_contract_validation(
        reference_rows,
        result_contract,
        prefix="REFERENCE_RESULT",
        require_clock=False,
    )
    reference_blockers.extend(reference_contract_blockers)
    reference_blockers = list(dict.fromkeys(reference_blockers))

    observed_rows: list[FambsResultRow] = []
    parse_errors: list[dict[str, Any]] = []
    observed_blockers: list[str] = []
    observed_summary: dict[str, Any]
    observed_contract_validation: dict[str, Any]
    if result_stream_text is None:
        observed_contract_validation = {
            "bound": result_contract is not None,
            "status": "not_observed",
            "qualified_rows": 0,
            "expected_rows": len(result_contract["rows"]) if result_contract else 0,
            "first_divergence": None,
        }
        observed_summary = {
            "provided": False,
            "row_count": 0,
            "bench_counts": {},
            "notes_by_bench": {},
            "clock_kinds": [],
            "accepted_rows": 0,
            "rich_rows": 0,
            "result_identities": [],
            "stream_sha256": None,
            "parse_errors": [],
            "shape_status": "not_provided",
        }
    else:
        observed_rows, parse_errors = parse_jsonl(result_stream_text)
        observed_summary = {"provided": True, **_rows_summary(observed_rows)}
        observed_summary["parse_errors"] = parse_errors
        if parse_errors:
            observed_blockers.append("OBSERVED_RESULT_PARSE_ERRORS")
        unknown = sorted(set(observed_summary["bench_counts"]) - expected_ids)
        if unknown:
            observed_blockers.append("OBSERVED_RESULT_UNKNOWN_BENCH")
            observed_summary["unknown_benches"] = unknown
        observed_blockers.extend(
            _shape_blockers(
                expected=source_emission,
                observed=observed_summary,
                prefix="OBSERVED_RESULT",
            )
        )
        observed_contract_validation, contract_blockers = _result_contract_validation(
            observed_rows,
            result_contract,
            prefix="OBSERVED_RESULT",
            require_clock=True,
        )
        observed_blockers.extend(contract_blockers)
        observed_blockers = list(dict.fromkeys(observed_blockers))
        observed_summary["shape_status"] = "match" if not _shape_blockers(
            expected=source_emission,
            observed=observed_summary,
            prefix="OBSERVED_RESULT",
        ) else "diverges"

    workload_records = deepcopy(manifest["workloads"])
    missing_acceptance = [
        str(record["bench_id"])
        for record in workload_records
        if not record.get("accepted_output_contract")
    ]
    placeholder_checks = [
        str(record["bench_id"])
        for record in workload_records
        if "SELF_CHECK_PLACEHOLDER" in record.get("gaps", [])
    ]

    blockers: list[str] = []
    blockers.extend(reference_blockers)
    blockers.extend(observed_blockers)
    if missing_acceptance:
        blockers.append("ACCEPTED_OUTPUT_CONTRACTS_UNBOUND")
    if placeholder_checks:
        blockers.append("WORKLOAD_SELF_CHECKS_PLACEHOLDER")
    if manifest["source_emission_model"].get("timed_region_contamination"):
        blockers.append("MAL_TIMED_REGION_INCLUDES_CHILD_REPORTING")
    blockers = list(dict.fromkeys(blockers))

    result_contract_bound = result_contract is not None and not missing_acceptance
    observed_result_qualified = (
        result_stream_text is not None
        and not blockers
        and result_contract_bound
        and observed_contract_validation["status"] == "pass"
    )
    if blockers:
        status = "captured_blocked"
    elif observed_result_qualified:
        status = "captured_result_qualified"
    else:
        status = "captured_shape_closed"

    classes = Counter(str(record["workload_class"]) for record in workload_records)
    manifest_sha256 = sha256_json(manifest)
    source = {
        **deepcopy(manifest["source"]),
        "manifest_sha256": manifest_sha256,
        "source_custody": "git_commit_and_blob_sha1_pinned",
    }
    artifact = FambsImportArtifact(
        schema_version=FAMBS_IMPORT_SCHEMA_VERSION,
        artifact_type=FAMBS_IMPORT_ARTIFACT_TYPE,
        generated_by="ahead-rev-sim/fambs-intake-v0.9-draft",
        source=source,
        config=deepcopy(manifest["config"]),
        workloads=workload_records,
        source_emission={
            **source_emission,
            "declared_reference_shape": deepcopy(manifest["source_emission_model"]),
        },
        result_contract=result_contract,
        reference_results={
            **reference_summary,
            "source_path": manifest["reference_results"]["path"],
            "source_git_blob_sha1": manifest["reference_results"]["git_blob_sha1"],
            "shape_status": "match" if not _shape_blockers(
                expected=source_emission,
                observed=reference_summary,
                prefix="REFERENCE_RESULT",
            ) else "diverges",
            "unknown_benches": reference_unknown,
            "note_mismatches": reference_note_mismatches,
            "result_contract_validation": reference_contract_validation,
            "blockers": reference_blockers,
        },
        observed_result_stream={
            **observed_summary,
            "result_contract_validation": observed_contract_validation,
            "blockers": observed_blockers,
        },
        coverage={
            "expected_workloads": len(manifest["expected_workload_ids"]),
            "imported_workloads": len(workload_records),
            "all_expected_workloads_present": (
                [record["bench_id"] for record in workload_records]
                == manifest["expected_workload_ids"]
            ),
            "workload_classes": dict(sorted(classes.items())),
            "missing_accepted_output_contracts": missing_acceptance,
            "placeholder_self_checks": placeholder_checks,
        },
        qualification={
            "status": status,
            "blockers": blockers,
            "result_contract_bound": result_contract_bound,
            "observed_result_qualified": observed_result_qualified,
            "performance_claim_allowed": False,
            "energy_claim_allowed": False,
            "accepted_work_claim_allowed": observed_result_qualified,
        },
        claim_boundary=(
            "This artifact establishes pinned source and configuration custody, workload taxonomy, "
            "source-emission shape, reference reconciliation, and a versioned result contract when "
            "present. Accepted work is established only for an observed stream that matches that "
            "contract. It does not establish comparable performance, physical energy, timing closure, "
            "or architecture advantage."
        ),
        control_question=(
            "Does the observed harness stream match the pinned source shape and every contracted "
            "semantic result before timing, energy, or substrate performance is compared?"
        ),
    )
    artifact.seal()
    return artifact
