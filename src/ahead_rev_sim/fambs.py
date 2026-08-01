"""Deterministic intake and source-shape reconciliation for FAMBS.

The importer binds the Future AI Microbench Suite to a pinned Git commit and
keeps workload identity, source emission shape, reference prose, observed
result streams, and accepted-output custody separate.  A cycle row is evidence
that a benchmark reported, not evidence that a useful result was accepted.
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
FAMBS_IMPORT_SCHEMA_VERSION = "ahead.fambs-import/v0.1"
FAMBS_IMPORT_ARTIFACT_TYPE = "fambs_workload_intake"

_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
        return cls(bench=bench, cycles=cycles, iters=iters, notes=notes)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FambsImportArtifact:
    schema_version: str
    artifact_type: str
    generated_by: str
    source: dict[str, Any]
    config: dict[str, Any]
    workloads: list[dict[str, Any]]
    source_emission: dict[str, Any]
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


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != FAMBS_SOURCE_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported FAMBS source manifest schema")

    source = manifest.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("manifest source must be an object")
    commit = str(source.get("commit", ""))
    if not _SHA1_RE.fullmatch(commit):
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
        if not _SHA1_RE.fullmatch(blob_sha):
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
    for row in rows:
        if row.notes not in notes[row.bench]:
            notes[row.bench].append(row.notes)
    return {
        "row_count": len(rows),
        "bench_counts": dict(sorted(counts.items())),
        "notes_by_bench": {key: value for key, value in sorted(notes.items())},
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


def import_fambs(
    manifest_source: str | Path | Mapping[str, Any],
    *,
    result_stream_text: str | None = None,
) -> FambsImportArtifact:
    manifest = load_manifest(manifest_source)
    source_emission = derive_source_emission(manifest)
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

    observed_rows: list[FambsResultRow] = []
    parse_errors: list[dict[str, Any]] = []
    observed_blockers: list[str] = []
    observed_summary: dict[str, Any]
    if result_stream_text is None:
        observed_summary = {
            "provided": False,
            "row_count": 0,
            "bench_counts": {},
            "notes_by_bench": {},
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
        observed_summary["shape_status"] = (
            "match" if not observed_blockers else "diverges"
        )

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
        reference_results={
            **reference_summary,
            "source_path": manifest["reference_results"]["path"],
            "source_git_blob_sha1": manifest["reference_results"]["git_blob_sha1"],
            "shape_status": "match" if not reference_blockers else "diverges",
            "unknown_benches": reference_unknown,
            "note_mismatches": reference_note_mismatches,
            "blockers": reference_blockers,
        },
        observed_result_stream={
            **observed_summary,
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
            "status": "captured_blocked" if blockers else "captured_shape_closed",
            "blockers": blockers,
            "performance_claim_allowed": False,
            "energy_claim_allowed": False,
            "accepted_work_claim_allowed": not missing_acceptance,
        },
        claim_boundary=(
            "This artifact establishes pinned source and configuration custody, workload taxonomy, "
            "source-emission shape, reference-result reconciliation, and optional observed-stream "
            "shape. It does not establish accepted workload output, comparable performance, physical "
            "energy, timing closure, or architecture advantage."
        ),
        control_question=(
            "Does the observed harness stream match the pinned source emission shape, and does every "
            "benchmark bind a result digest or quality rule before cycles are compared?"
        ),
    )
    artifact.seal()
    return artifact
