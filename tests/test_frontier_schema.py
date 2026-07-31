from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ahead_rev_sim.frontier import analyze_assembly


ROOT = Path(__file__).resolve().parents[1]


def test_frontier_schema_accepts_generated_artifact() -> None:
    schema_path = ROOT / "schemas" / "reversibility-frontier.schema.json"
    source_path = ROOT / "examples" / "asm" / "mixed_frontier.asm"
    contract_path = ROOT / "examples" / "asm" / "accepted-output.json"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    artifact = analyze_assembly(
        source_path.read_text(encoding="utf-8"),
        source_name=source_path.name,
        accepted_output_contract=json.loads(contract_path.read_text(encoding="utf-8")),
    )

    Draft202012Validator(schema).validate(artifact.to_dict())
