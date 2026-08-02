from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from ahead_rev_sim.chipyard_cli import main as chipyard_main
from ahead_rev_sim.chipyard_elaboration import (
    CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION,
)
from ahead_rev_sim.chipyard_lifecycle import (
    CHIPYARD_LIFECYCLE_EXPECTED_NAME,
    CHIPYARD_LIFECYCLE_MANIFEST_NAME,
    CHIPYARD_LIFECYCLE_MANIFEST_SCHEMA_VERSION,
    CHIPYARD_LIFECYCLE_PROOF_SCHEMA_VERSION,
    CHIPYARD_LIFECYCLE_SOURCE_NAME,
    CHIPYARD_LIFECYCLE_TRACE_PREFIX,
    CIRCT_ASSET_NAME,
    CIRCT_COMMIT,
    CIRCT_INSTALLER_COMMIT,
    CIRCT_INSTALLER_REPOSITORY,
    CIRCT_INSTALLER_REVISION_NAME,
    CIRCT_RELEASE,
    CIRCT_REPOSITORY,
    CIRCT_TAG_REVISION_NAME,
    CIRCT_VERSION_FILE_NAME,
    COMPILER_SEARCH_DIRS_NAME,
    FIRTOOL_AUTHORITY_REPORT_NAME,
    FIRTOOL_VERSION_NAME,
    FESVR_HEADER_NAME,
    FESVR_HEADERS_MANIFEST_NAME,
    FESVR_HOST_RUNTIME_REPORT_NAME,
    FESVR_LIBRARY_NAME,
    FESVR_STATIC_LOG_NAME,
    HTIF_RUNTIME_REPORT_NAME,
    LIBGLOSS_HTIF_BUILD_LOG_NAME,
    LIBGLOSS_HTIF_COMMIT,
    LIBGLOSS_HTIF_CONFIGURE_LOG_NAME,
    LIBGLOSS_HTIF_INSTALL_LOG_NAME,
    LIBGLOSS_HTIF_LIBRARY_NAME,
    LIBGLOSS_HTIF_LINKER_SCRIPT_NAME,
    LIBGLOSS_HTIF_REPOSITORY,
    LIBGLOSS_HTIF_REVISION_NAME,
    LIBGLOSS_HTIF_SPECS_NAME,
    RISCV_ISA_SIM_BUILD_LOG_NAME,
    RISCV_ISA_SIM_COMMIT,
    RISCV_ISA_SIM_CONFIGURE_LOG_NAME,
    RISCV_ISA_SIM_INSTALL_LOG_NAME,
    RISCV_ISA_SIM_REPOSITORY,
    RISCV_ISA_SIM_REVISION_NAME,
    RISCV_LIBRARY_NAME,
    LIFECYCLE_BLOCKERS,
    build_chipyard_lifecycle_manifest,
    build_chipyard_lifecycle_proof,
    parse_chipyard_lifecycle_trace,
    render_chipyard_lifecycle_source,
    render_chipyard_lifecycle_trace,
    write_chipyard_lifecycle_bundle,
    write_chipyard_lifecycle_proof,
)
from ahead_rev_sim.chipyard_subsystem import (
    CHIPYARD_COMMIT,
    CHIPYARD_CONFIG_CLASS,
    DEFAULT_BASE_ADDRESS,
    build_chipyard_manifest,
)
from ahead_rev_sim.mmio_abi import canonical_json


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = (
    ROOT / "schemas" / "chipyard-rv64gc-lifecycle-manifest.schema.json"
)
PROOF_SCHEMA = ROOT / "schemas" / "chipyard-rv64gc-lifecycle-proof.schema.json"
WORKFLOW = ROOT / ".github" / "workflows" / "chipyard-lifecycle.yml"


def _sealed_elaboration_proof(
    integration_manifest: dict[str, object],
) -> dict[str, object]:
    proof: dict[str, object] = {
        "schema_version": CHIPYARD_ELABORATION_PROOF_SCHEMA_VERSION,
        "chipyard": {
            "commit": CHIPYARD_COMMIT,
            "manifest_sha256": integration_manifest["manifest_sha256"],
        },
        "target": {"config_class": CHIPYARD_CONFIG_CLASS},
        "observations": {"loopback_fallback_retained": True},
        "qualification": {
            "accepted": True,
            "status": "chipyard_subsystem_elaboration_proved",
        },
    }
    proof["proof_sha256"] = sha256(
        canonical_json(proof).encode("utf-8")
    ).hexdigest()
    return proof


def _proof_fixture(tmp_path: Path) -> dict[str, object]:
    lifecycle_dir = tmp_path / "lifecycle"
    bundle = write_chipyard_lifecycle_bundle(lifecycle_dir)
    integration = build_chipyard_manifest()
    integration_path = tmp_path / "chipyard-physical-compute-integration.json"
    integration_path.write_text(
        json.dumps(integration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    elaboration_path = tmp_path / "chipyard-subsystem-elaboration-proof.json"
    elaboration_path.write_text(
        json.dumps(
            _sealed_elaboration_proof(integration),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    binary = tmp_path / "physical-compute-lifecycle.riscv"
    binary.write_bytes(b"\x7fELFchipyard-rv64gc-fixture")
    simulator = tmp_path / f"simulator-{CHIPYARD_CONFIG_CLASS}"
    simulator.write_bytes(b"verilator-simulator-fixture")
    firtool = tmp_path / "firtool"
    firtool.write_bytes(b"\x7fELFfirtool-fixture")
    firtool_version = "firtool version 1.75.0 fixture\n"
    simulator_build_log = tmp_path / "simulator-build.log"
    simulator_build_log.write_text("Verilator build fixture passed\n", encoding="utf-8")
    raw_log = tmp_path / "chipyard-lifecycle.raw.log"
    raw_log.write_text(
        "Chipyard boot fixture\n"
        + bundle["expected"].read_text(encoding="utf-8")
        + "Chipyard exit fixture\n",
        encoding="utf-8",
    )
    trace = tmp_path / "chipyard-lifecycle.trace"
    trace.write_bytes(bundle["expected"].read_bytes())

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / LIBGLOSS_HTIF_REVISION_NAME).write_text(
        LIBGLOSS_HTIF_COMMIT + "\n",
        encoding="utf-8",
    )
    (runtime_dir / LIBGLOSS_HTIF_SPECS_NAME).write_text(
        "%include <nano.specs>\n"
        "*link:\n"
        "-lgloss_htif -dT htif.ld -static\n",
        encoding="utf-8",
    )
    (runtime_dir / LIBGLOSS_HTIF_LINKER_SCRIPT_NAME).write_text(
        'OUTPUT_ARCH ("riscv")\n'
        "ENTRY (_start)\n"
        "SECTIONS { . = 0x80000000; .htif : { *(.htif) } }\n",
        encoding="utf-8",
    )
    (runtime_dir / LIBGLOSS_HTIF_LIBRARY_NAME).write_bytes(
        b"!<arch>\nlibgloss-fixture"
    )
    circt_version_payload = (
        json.dumps({"version": CIRCT_RELEASE}, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (runtime_dir / CIRCT_VERSION_FILE_NAME).write_bytes(circt_version_payload)
    (runtime_dir / CIRCT_TAG_REVISION_NAME).write_text(
        CIRCT_COMMIT + "\n",
        encoding="utf-8",
    )
    (runtime_dir / CIRCT_INSTALLER_REVISION_NAME).write_text(
        CIRCT_INSTALLER_COMMIT + "\n",
        encoding="utf-8",
    )
    (runtime_dir / FIRTOOL_VERSION_NAME).write_text(
        firtool_version,
        encoding="utf-8",
    )
    (runtime_dir / FIRTOOL_AUTHORITY_REPORT_NAME).write_text(
        f"circt_repository={CIRCT_REPOSITORY}\n"
        f"circt_release={CIRCT_RELEASE}\n"
        f"circt_commit={CIRCT_COMMIT}\n"
        f"circt_asset={CIRCT_ASSET_NAME}\n"
        f"installer_repository={CIRCT_INSTALLER_REPOSITORY}\n"
        f"installer_commit={CIRCT_INSTALLER_COMMIT}\n"
        f"firtool_source_path={firtool}\n"
        f"firtool_sealed_path={firtool}\n"
        f"{sha256(firtool.read_bytes()).hexdigest()}  {firtool}\n"
        f"{sha256(circt_version_payload).hexdigest()}  "
        f"{runtime_dir / CIRCT_VERSION_FILE_NAME}\n",
        encoding="utf-8",
    )

    fesvr_header = (
        "#ifndef __MEMIF_H\n"
        "#define __MEMIF_H\n"
        "class chunked_memif_t { public: virtual void read_chunk() = 0; };\n"
        "class memif_t { public: virtual void read() = 0; };\n"
        "#endif\n"
    ).encode("utf-8")
    fesvr_library = b"!<arch>\nfesvr-fixture"
    riscv_library = b"\x7fELFriscv-host-fixture"
    (runtime_dir / RISCV_ISA_SIM_REVISION_NAME).write_text(
        RISCV_ISA_SIM_COMMIT + "\n",
        encoding="utf-8",
    )
    (runtime_dir / FESVR_HEADER_NAME).write_bytes(fesvr_header)
    (runtime_dir / FESVR_LIBRARY_NAME).write_bytes(fesvr_library)
    (runtime_dir / RISCV_LIBRARY_NAME).write_bytes(riscv_library)
    (runtime_dir / FESVR_HEADERS_MANIFEST_NAME).write_text(
        "/fixture/include/fesvr/memif.h\n",
        encoding="utf-8",
    )
    (runtime_dir / FESVR_HOST_RUNTIME_REPORT_NAME).write_text(
        f"riscv_isa_sim_repository={RISCV_ISA_SIM_REPOSITORY}\n"
        f"riscv_isa_sim_commit={RISCV_ISA_SIM_COMMIT}\n"
        "fesvr_header=/fixture/fesvr-memif.h\n"
        "fesvr_library=/fixture/libfesvr.a\n"
        "riscv_library=/fixture/libriscv.so\n"
        f"{sha256(fesvr_header).hexdigest()}  /fixture/fesvr-memif.h\n"
        f"{sha256(fesvr_library).hexdigest()}  /fixture/libfesvr.a\n"
        f"{sha256(riscv_library).hexdigest()}  /fixture/libriscv.so\n",
        encoding="utf-8",
    )

    for name, content in (
        (RISCV_ISA_SIM_CONFIGURE_LOG_NAME, "configure passed\n"),
        (RISCV_ISA_SIM_BUILD_LOG_NAME, "build passed\n"),
        (RISCV_ISA_SIM_INSTALL_LOG_NAME, "install passed\n"),
        (FESVR_STATIC_LOG_NAME, "libfesvr.a is current\n"),
        (LIBGLOSS_HTIF_CONFIGURE_LOG_NAME, "configure passed\n"),
        (LIBGLOSS_HTIF_BUILD_LOG_NAME, "build passed\n"),
        (LIBGLOSS_HTIF_INSTALL_LOG_NAME, "install passed\n"),
        (COMPILER_SEARCH_DIRS_NAME, "libraries: =/fixture/lib\n"),
        (
            HTIF_RUNTIME_REPORT_NAME,
            f"libgloss_commit={LIBGLOSS_HTIF_COMMIT}\n"
            "htif_nano_specs=/fixture/htif_nano.specs\n"
            "htif_linker_script=/fixture/htif.ld\n"
            "htif_runtime_library=/fixture/libgloss_htif.a\n"
            f"{sha256((runtime_dir / LIBGLOSS_HTIF_SPECS_NAME).read_bytes()).hexdigest()}  "
            "/fixture/htif_nano.specs\n"
            f"{sha256((runtime_dir / LIBGLOSS_HTIF_LINKER_SCRIPT_NAME).read_bytes()).hexdigest()}  "
            "/fixture/htif.ld\n"
            f"{sha256((runtime_dir / LIBGLOSS_HTIF_LIBRARY_NAME).read_bytes()).hexdigest()}  "
            "/fixture/libgloss_htif.a\n",
        ),
    ):
        (runtime_dir / name).write_text(content, encoding="utf-8")

    return {
        "integration_manifest_path": integration_path,
        "lifecycle_manifest_path": bundle["manifest"],
        "elaboration_proof_path": elaboration_path,
        "source_path": bundle["source"],
        "expected_trace_path": bundle["expected"],
        "binary_path": binary,
        "simulator_path": simulator,
        "firtool_path": firtool,
        "simulator_build_log_path": simulator_build_log,
        "raw_log_path": raw_log,
        "trace_path": trace,
        "runtime_dir": runtime_dir,
        "compiler_version": "riscv64-unknown-elf-gcc fixture\n",
        "readelf_output": (
            "GNU readelf fixture\n"
            "  Class:                             ELF64\n"
            "  Machine:                           RISC-V\n"
        ),
        "verilator_version": "Verilator 5.022 fixture\n",
        "firtool_version": firtool_version,
        "build_command": "make -C chipyard/sims/verilator default",
        "run_command": "make -C chipyard/sims/verilator run-binary-fast",
    }


def test_lifecycle_source_exercises_every_mmio_terminal_state() -> None:
    source = render_chipyard_lifecycle_source()
    assert f"PHYS_BASE UINT64_C(0x{DEFAULT_BASE_ADDRESS:08X})" in source
    assert "fence iorw, iorw" in source
    assert "CMD_RESET | CMD_READ" in source
    for command in ("CMD_RESET", "CMD_LOAD", "CMD_EVOLVE", "CMD_READ", "CMD_CAPTURE"):
        assert f"submit({command});" in source
    for stage in ("ambiguous", "reset", "load", "evolve", "read", "capture"):
        assert f'emit_stage("{stage}", observed);' in source
    assert 'printf(TRACE_PREFIX "result=pass\\n");' in source
    with pytest.raises(ValueError, match="4 KiB aligned"):
        render_chipyard_lifecycle_source(base_address=DEFAULT_BASE_ADDRESS + 4)


def test_lifecycle_trace_is_exact_ordered_and_semantically_checked() -> None:
    trace = render_chipyard_lifecycle_trace()
    observations = parse_chipyard_lifecycle_trace(trace)
    assert observations["line_count"] == 9
    assert all(observations["checks"].values())
    assert observations["stages"]["ambiguous"]["status"] == 0x00000009
    assert observations["stages"]["capture"]["status"] == 0x00000025

    reordered = trace.replace(
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}reset status",
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}temporary status",
        1,
    ).replace(
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}load status",
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}reset status",
        1,
    ).replace(
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}temporary status",
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}load status",
        1,
    )
    with pytest.raises(ValueError, match="out of order"):
        parse_chipyard_lifecycle_trace(reordered)

    wrong_status = trace.replace(
        "capture status=00000025",
        "capture status=00000031",
    )
    with pytest.raises(ValueError, match="semantic checks failed"):
        parse_chipyard_lifecycle_trace(wrong_status)


def test_lifecycle_manifest_is_deterministic_sealed_and_schema_valid() -> None:
    first = build_chipyard_lifecycle_manifest()
    second = build_chipyard_lifecycle_manifest()
    assert first == second
    assert first["schema_version"] == CHIPYARD_LIFECYCLE_MANIFEST_SCHEMA_VERSION
    assert first["chipyard"]["integration_manifest_sha256"] == (
        build_chipyard_manifest()["manifest_sha256"]
    )
    assert first["qualification"]["chipyard_rtl_simulation_claim_allowed"] is False
    assert first["simulator_runtime"] == {
        "repository": RISCV_ISA_SIM_REPOSITORY,
        "commit": RISCV_ISA_SIM_COMMIT,
        "header": "fesvr/memif.h",
        "fesvr_library": FESVR_LIBRARY_NAME,
        "riscv_library": RISCV_LIBRARY_NAME,
    }
    assert first["runtime"] == {
        "repository": LIBGLOSS_HTIF_REPOSITORY,
        "commit": LIBGLOSS_HTIF_COMMIT,
        "specs": LIBGLOSS_HTIF_SPECS_NAME,
        "linker_script": LIBGLOSS_HTIF_LINKER_SCRIPT_NAME,
        "library": LIBGLOSS_HTIF_LIBRARY_NAME,
    }
    assert first["lowering"] == {
        "repository": CIRCT_REPOSITORY,
        "release": CIRCT_RELEASE,
        "commit": CIRCT_COMMIT,
        "asset": CIRCT_ASSET_NAME,
        "tool": "firtool",
        "version_file": CIRCT_VERSION_FILE_NAME,
        "installer_repository": CIRCT_INSTALLER_REPOSITORY,
        "installer_commit": CIRCT_INSTALLER_COMMIT,
    }

    claimed = first.pop("manifest_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()
    first["manifest_sha256"] = claimed

    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first)


def test_lifecycle_bundle_matches_manifest_and_uses_lf(tmp_path: Path) -> None:
    outputs = write_chipyard_lifecycle_bundle(tmp_path)
    assert outputs["source"].name == CHIPYARD_LIFECYCLE_SOURCE_NAME
    assert outputs["expected"].name == CHIPYARD_LIFECYCLE_EXPECTED_NAME
    assert outputs["manifest"].name == CHIPYARD_LIFECYCLE_MANIFEST_NAME
    manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
    for key, name in (
        ("source", CHIPYARD_LIFECYCLE_SOURCE_NAME),
        ("expected", CHIPYARD_LIFECYCLE_EXPECTED_NAME),
    ):
        payload = outputs[key].read_bytes()
        record = manifest["generated_artifacts"][name]
        assert record["sha256"] == sha256(payload).hexdigest()
        assert record["bytes"] == len(payload)
        assert b"\r\n" not in payload


def test_lifecycle_proof_is_deterministic_sealed_and_schema_valid(
    tmp_path: Path,
) -> None:
    kwargs = _proof_fixture(tmp_path)
    first = build_chipyard_lifecycle_proof(**kwargs)
    second = build_chipyard_lifecycle_proof(**kwargs)
    assert first == second
    assert first["schema_version"] == CHIPYARD_LIFECYCLE_PROOF_SCHEMA_VERSION
    assert first["qualification"]["status"] == (
        "chipyard_rv64gc_lifecycle_execution_proved"
    )
    assert first["qualification"]["chipyard_rtl_simulation_claim_allowed"] is True
    assert first["qualification"]["external_cartridge_claim_allowed"] is False
    assert first["qualification"]["blockers"] == LIFECYCLE_BLOCKERS
    assert first["observations"]["accepted_trace_exact"] is True
    assert first["observations"]["raw_trace_embedded"] is True
    assert first["observations"]["riscv_isa_sim_revision_exact"] is True
    assert first["observations"]["fesvr_host_runtime_bound"] is True
    assert first["observations"]["fesvr_header_contract_checked"] is True
    assert first["observations"]["fesvr_library_archive_checked"] is True
    assert first["observations"]["riscv_library_elf_checked"] is True
    assert first["observations"]["libgloss_revision_exact"] is True
    assert first["observations"]["htif_runtime_bound"] is True
    assert first["observations"]["circt_release_exact"] is True
    assert first["observations"]["circt_tag_revision_exact"] is True
    assert first["observations"]["circt_installer_revision_exact"] is True
    assert first["observations"]["firtool_binary_bound"] is True
    assert first["simulator_runtime"]["commit"] == RISCV_ISA_SIM_COMMIT
    assert first["runtime"]["commit"] == LIBGLOSS_HTIF_COMMIT
    assert first["lowering"]["release"] == CIRCT_RELEASE
    assert first["lowering"]["commit"] == CIRCT_COMMIT
    assert first["lowering"]["asset"] == CIRCT_ASSET_NAME
    assert first["tools"]["firtool"] == "firtool version 1.75.0 fixture"
    assert first["artifacts"]["fesvr_header"]["name"] == FESVR_HEADER_NAME
    assert first["artifacts"]["fesvr_library"]["name"] == FESVR_LIBRARY_NAME
    assert first["artifacts"]["riscv_library"]["name"] == RISCV_LIBRARY_NAME
    assert first["artifacts"]["htif_runtime_library"]["name"] == (
        LIBGLOSS_HTIF_LIBRARY_NAME
    )
    assert first["artifacts"]["circt_version_file"]["name"] == (
        CIRCT_VERSION_FILE_NAME
    )
    assert first["artifacts"]["circt_tag_revision"]["name"] == (
        CIRCT_TAG_REVISION_NAME
    )
    assert first["artifacts"]["firtool_binary"]["name"] == "firtool"

    claimed = first.pop("proof_sha256")
    assert claimed == sha256(canonical_json(first).encode("utf-8")).hexdigest()
    first["proof_sha256"] = claimed

    schema = json.loads(PROOF_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first)
    output = write_chipyard_lifecycle_proof(tmp_path / "proof.json", first)
    assert json.loads(output.read_text(encoding="utf-8")) == first
    assert b"\r\n" not in output.read_bytes()


def test_lifecycle_proof_refuses_forged_trace_source_or_raw_log(
    tmp_path: Path,
) -> None:
    kwargs = _proof_fixture(tmp_path)
    trace_path = Path(kwargs["trace_path"])
    trace_path.write_text(
        render_chipyard_lifecycle_trace().replace(
            "result=pass",
            "result=fail",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="diverges from accepted trace"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "source")
    source_path = Path(kwargs["source_path"])
    source_path.write_text("// forged\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source diverges"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "raw")
    raw_log_path = Path(kwargs["raw_log_path"])
    raw_log_path.write_text("simulator completed without a trace\n", encoding="utf-8")
    with pytest.raises(ValueError, match="raw simulation log"):
        build_chipyard_lifecycle_proof(**kwargs)


def test_lifecycle_proof_refuses_forged_htif_runtime(tmp_path: Path) -> None:
    kwargs = _proof_fixture(tmp_path / "revision")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / LIBGLOSS_HTIF_REVISION_NAME).write_text(
        "0" * 40 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="revision mismatch"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "specs")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / LIBGLOSS_HTIF_SPECS_NAME).write_text(
        "%include <nano.specs>\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="specs contract"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "archive")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / LIBGLOSS_HTIF_LIBRARY_NAME).write_bytes(b"forged")
    with pytest.raises(ValueError, match="static archive"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "digest")
    runtime_dir = Path(kwargs["runtime_dir"])
    specs_path = runtime_dir / LIBGLOSS_HTIF_SPECS_NAME
    specs_path.write_text(
        specs_path.read_text(encoding="utf-8") + "# drift\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="HTIF runtime report is incomplete"):
        build_chipyard_lifecycle_proof(**kwargs)


def test_lifecycle_proof_refuses_forged_fesvr_host_runtime(tmp_path: Path) -> None:
    kwargs = _proof_fixture(tmp_path / "revision")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / RISCV_ISA_SIM_REVISION_NAME).write_text(
        "0" * 40 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="riscv-isa-sim revision mismatch"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "header")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / FESVR_HEADER_NAME).write_text("#define forged\n", encoding="utf-8")
    with pytest.raises(ValueError, match="memif header contract"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "fesvr")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / FESVR_LIBRARY_NAME).write_bytes(b"forged")
    with pytest.raises(ValueError, match="FESVR library is not a static archive"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "riscv")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / RISCV_LIBRARY_NAME).write_bytes(b"forged")
    with pytest.raises(ValueError, match="riscv simulator library is not identified"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "digest")
    runtime_dir = Path(kwargs["runtime_dir"])
    header_path = runtime_dir / FESVR_HEADER_NAME
    header_path.write_text(
        header_path.read_text(encoding="utf-8") + "// drift\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="FESVR host-runtime report is incomplete"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "report")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / FESVR_HOST_RUNTIME_REPORT_NAME).write_text(
        f"riscv_isa_sim_repository={RISCV_ISA_SIM_REPOSITORY}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="FESVR host-runtime report is incomplete"):
        build_chipyard_lifecycle_proof(**kwargs)


def test_lifecycle_proof_refuses_forged_circt_lowering(tmp_path: Path) -> None:
    kwargs = _proof_fixture(tmp_path / "release")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / CIRCT_VERSION_FILE_NAME).write_text(
        json.dumps({"version": "firtool-forged"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="CIRCT release authority mismatch"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "tag")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / CIRCT_TAG_REVISION_NAME).write_text(
        "0" * 40 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="CIRCT tag revision mismatch"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "installer")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / CIRCT_INSTALLER_REVISION_NAME).write_text(
        "0" * 40 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="CIRCT installer revision mismatch"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "binary")
    Path(kwargs["firtool_path"]).write_bytes(b"forged")
    with pytest.raises(ValueError, match="firtool binary is not identified as ELF"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "version")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / FIRTOOL_VERSION_NAME).write_text(
        "firtool forged\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="firtool version evidence mismatch"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "digest")
    firtool_path = Path(kwargs["firtool_path"])
    firtool_path.write_bytes(firtool_path.read_bytes() + b"drift")
    with pytest.raises(ValueError, match="firtool authority report is incomplete"):
        build_chipyard_lifecycle_proof(**kwargs)

    kwargs = _proof_fixture(tmp_path / "report")
    runtime_dir = Path(kwargs["runtime_dir"])
    (runtime_dir / FIRTOOL_AUTHORITY_REPORT_NAME).write_text(
        "circt_repository=llvm/circt\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="firtool authority report is incomplete"):
        build_chipyard_lifecycle_proof(**kwargs)


def test_chipyard_cli_exposes_lifecycle_bundle_and_proof(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "bundle"
    assert chipyard_main(["lifecycle-bundle", "--out-dir", str(output)]) == 0
    assert (output / CHIPYARD_LIFECYCLE_SOURCE_NAME).is_file()
    assert (output / CHIPYARD_LIFECYCLE_EXPECTED_NAME).is_file()
    assert (output / CHIPYARD_LIFECYCLE_MANIFEST_NAME).is_file()

    with pytest.raises(SystemExit) as exc:
        chipyard_main(["lifecycle-proof", "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--elaboration-proof" in help_text
    assert "--simulator-build-log" in help_text
    assert "--raw-log" in help_text
    assert "--runtime-dir" in help_text
    assert "--firtool" in help_text
    assert "--firtool-version-file" in help_text


def test_lifecycle_workflow_builds_and_executes_the_exact_target() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in workflow
    assert "riscv64-unknown-elf-gcc" in workflow
    assert "-march=rv64gc" in workflow
    assert "-mabi=lp64d" in workflow
    assert "-specs=htif_nano.specs" in workflow
    assert "libgloss_htif.a" in workflow
    assert 'cp "$RUNTIME_LIBRARY" "$ROOT/libgloss_htif.a"' in workflow
    assert (
        "RISCV_ISA_SIM_COMMIT: "
        "9c190a07c6838f6392bafa4ad83acea462c7f759"
    ) in workflow
    assert "Build and verify the pinned FESVR host runtime" in workflow
    assert 'SEALED_FESVR_HEADER="$ROOT/fesvr-memif.h"' in workflow
    assert 'SEALED_FESVR_LIBRARY="$ROOT/libfesvr.a"' in workflow
    assert 'SEALED_RISCV_LIBRARY="$ROOT/libriscv.so"' in workflow
    assert 'cmp "$FESVR_HEADER" "$SEALED_FESVR_HEADER"' in workflow
    assert 'cmp "$FESVR_LIBRARY" "$SEALED_FESVR_LIBRARY"' in workflow
    assert 'cmp "$RISCV_LIBRARY" "$SEALED_RISCV_LIBRARY"' in workflow
    assert '--runtime-dir "$ROOT"' in workflow
    assert "CIRCT_RELEASE: firtool-1.75.0" in workflow
    assert "CIRCT_COMMIT: 481cb60add7358934414a3c6b396f5d29ad934fe" in workflow
    assert "CIRCT_ASSET_NAME: circt-full-static-linux-x64.tar.gz" in workflow
    assert (
        "CIRCT_INSTALLER_COMMIT: "
        "3f8dda6e1c1965537b5801a43c81c287bac4eae4"
    ) in workflow
    assert "--skip-circt" not in workflow
    assert "Verify the pinned CIRCT lowering authority" in workflow
    assert 'FIRTOOL="$(command -v firtool)"' in workflow
    assert 'TAG_REPO="$GITHUB_WORKSPACE/chipyard/.circt-tag"' in workflow
    assert 'test "$CIRCT_TAG_COMMIT" = "$CIRCT_COMMIT"' in workflow
    assert 'SEALED_FIRTOOL="$ROOT/firtool"' in workflow
    assert 'cmp "$FIRTOOL" "$SEALED_FIRTOOL"' in workflow
    assert 'firtool --version 2>&1 | tee "$ROOT/firtool-version.txt"' in workflow
    assert '--firtool "$ROOT/firtool"' in workflow
    assert '--firtool-version-file "$ROOT/firtool-version.txt"' in workflow
    assert "CONFIG=\"$CHIPYARD_CONFIG\"" in workflow
    assert "CONFIG_PACKAGE=\"$CHIPYARD_CONFIG_PACKAGE\"" in workflow
    assert "run-binary-fast" in workflow
    assert "timeout 300s" in workflow
    assert "grep '^ahead-chipyard:'" in workflow
    assert "lifecycle-proof" in workflow
    assert "chipyard-rv64gc-lifecycle-proof.schema.json" in workflow
    assert "2>&1 | tee" in workflow
    assert "if: always()" in workflow
    assert "! -name SHA256SUMS" in workflow
    assert 'sha256sum "$ROOT/SHA256SUMS" > "$ROOT/SHA256SUMS.sha256"' in workflow
    assert 'sha256sum -c "$ROOT/SHA256SUMS"' in workflow
    assert 'sha256sum -c "$ROOT/SHA256SUMS.sha256"' in workflow
    assert (
        "$GITHUB_WORKSPACE/artifacts/chipyard-lifecycle/generated-src.tar.gz"
        in workflow
    )
