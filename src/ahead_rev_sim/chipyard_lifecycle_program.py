"""Generated RV64GC lifecycle program and accepted Chipyard trace."""

from __future__ import annotations

from hashlib import sha256

from .chipyard_subsystem import DEFAULT_BASE_ADDRESS
from .mmio_abi import (
    CAPABILITY_BITS,
    COMMAND_BITS,
    STATUS_BITS,
    bit_mask,
)
from .physical_constants import PHYSICAL_COMPUTE_MMIO_V1, PORTABLE_BINDING

CHIPYARD_LIFECYCLE_MANIFEST_SCHEMA_VERSION = (
    "ahead.chipyard-rv64gc-lifecycle-manifest/v0.2"
)
CHIPYARD_LIFECYCLE_PROOF_SCHEMA_VERSION = (
    "ahead.chipyard-rv64gc-lifecycle-proof/v0.2"
)
CHIPYARD_LIFECYCLE_TRACE_PREFIX = "ahead-chipyard:"
CHIPYARD_LIFECYCLE_SOURCE_NAME = "physical_compute_chipyard_lifecycle.c"
CHIPYARD_LIFECYCLE_EXPECTED_NAME = "physical_compute_chipyard_lifecycle.expected"
CHIPYARD_LIFECYCLE_MANIFEST_NAME = "chipyard-rv64gc-lifecycle-manifest.json"
CHIPYARD_LIFECYCLE_PROOF_NAME = "chipyard-rv64gc-lifecycle-proof.json"

LIBGLOSS_HTIF_REPOSITORY = "ucb-bar/libgloss-htif"
LIBGLOSS_HTIF_COMMIT = "39234a16247ab1fa234821b251f1f1870c3de343"
LIBGLOSS_HTIF_SPECS_NAME = "htif_nano.specs"
LIBGLOSS_HTIF_LINKER_SCRIPT_NAME = "htif.ld"
LIBGLOSS_HTIF_LIBRARY_NAME = "libgloss_htif.a"
LIBGLOSS_HTIF_REVISION_NAME = "libgloss-revision.txt"
LIBGLOSS_HTIF_CONFIGURE_LOG_NAME = "libgloss-configure.log"
LIBGLOSS_HTIF_BUILD_LOG_NAME = "libgloss-build.log"
LIBGLOSS_HTIF_INSTALL_LOG_NAME = "libgloss-install.log"
COMPILER_SEARCH_DIRS_NAME = "compiler-search-dirs.txt"
HTIF_RUNTIME_REPORT_NAME = "htif-runtime.txt"

CIRCT_REPOSITORY = "llvm/circt"
CIRCT_RELEASE = "firtool-1.75.0"
CIRCT_COMMIT = "481cb60add7358934414a3c6b396f5d29ad934fe"
CIRCT_ASSET_NAME = "circt-full-static-linux-x64.tar.gz"
CIRCT_VERSION_FILE_NAME = "circt.json"
CIRCT_TAG_REVISION_NAME = "circt-tag-revision.txt"
CIRCT_INSTALLER_REPOSITORY = "circt/install-circt"
CIRCT_INSTALLER_COMMIT = "3f8dda6e1c1965537b5801a43c81c287bac4eae4"
CIRCT_INSTALLER_REVISION_NAME = "install-circt-revision.txt"
FIRTOOL_VERSION_NAME = "firtool-version.txt"
FIRTOOL_AUTHORITY_REPORT_NAME = "firtool-authority.txt"

RISCV_ISA_SIM_REPOSITORY = "riscv-software-src/riscv-isa-sim"
RISCV_ISA_SIM_COMMIT = "9c190a07c6838f6392bafa4ad83acea462c7f759"
RISCV_ISA_SIM_REVISION_NAME = "riscv-isa-sim-revision.txt"
RISCV_ISA_SIM_CONFIGURE_LOG_NAME = "riscv-isa-sim-configure.log"
RISCV_ISA_SIM_BUILD_LOG_NAME = "riscv-isa-sim-build.log"
RISCV_ISA_SIM_INSTALL_LOG_NAME = "riscv-isa-sim-install.log"
FESVR_STATIC_LOG_NAME = "libfesvr-static.log"
FESVR_HEADER_SOURCE = "fesvr/memif.h"
FESVR_HEADER_NAME = "fesvr-memif.h"
FESVR_LIBRARY_NAME = "libfesvr.a"
RISCV_LIBRARY_NAME = "libriscv.so"
FESVR_HEADERS_MANIFEST_NAME = "fesvr-headers.txt"
FESVR_HOST_RUNTIME_REPORT_NAME = "fesvr-host-runtime.txt"

LIFECYCLE_STAGES = ("ambiguous", "reset", "load", "evolve", "read", "capture")
SUCCESS_STAGES = ("reset", "load", "evolve", "read", "capture")

LIFECYCLE_BLOCKERS = [
    "CHIPYARD_EXTERNAL_CARTRIDGE_BINDING_UNRUN",
    "FPGA_OR_SILICON_EXECUTION_UNRUN",
    "PHYSICAL_SUBSTRATE_UNMEASURED",
    "PHYSICAL_ENERGY_UNMEASURED",
    "TIMING_THERMAL_VOLUME_UNMEASURED",
    "COMPLETE_SYSTEM_EVP_UNMEASURED",
    "INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING",
]


def sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08X}"


def render_chipyard_lifecycle_trace() -> str:
    return (
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}abi={PORTABLE_BINDING} isa=rv64gc\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}identity=41504859 capabilities=00000009\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}ambiguous status=00000009 "
        "result=refused receipt=absent\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}reset status=00000025 "
        "result=done receipt=valid\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}load status=00000025 "
        "result=done receipt=valid\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}evolve status=00000025 "
        "result=done receipt=valid\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}read status=00000025 "
        "result=done receipt=valid\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}capture status=00000025 "
        "result=done receipt=valid\n"
        f"{CHIPYARD_LIFECYCLE_TRACE_PREFIX}result=pass\n"
    )


def render_chipyard_lifecycle_source(
    *,
    base_address: int = DEFAULT_BASE_ADDRESS,
) -> str:
    if base_address < 0 or base_address % 0x1000:
        raise ValueError("Chipyard base address must be non-negative and 4 KiB aligned")

    off = PHYSICAL_COMPUTE_MMIO_V1
    command = {name: bit_mask(bit) for name, bit in COMMAND_BITS.items()}
    status = {name: bit_mask(bit) for name, bit in STATUS_BITS.items()}
    capabilities = {
        name: bit_mask(bit) for name, bit in CAPABILITY_BITS.items()
    }
    expected_caps = capabilities["exact"] | capabilities["software_fallback"]

    return f"""/* Generated Chipyard/Verilator lifecycle for {PORTABLE_BINDING}. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#define TRACE_PREFIX "{CHIPYARD_LIFECYCLE_TRACE_PREFIX}"
#define PHYS_BASE UINT64_C(0x{base_address:08X})
#define REG32(offset) (*(volatile uint32_t *)(uintptr_t)(PHYS_BASE + (offset)))

#define REG_IDENTITY 0x{off['identity']:02X}u
#define REG_CAPABILITIES 0x{off['capabilities']:02X}u
#define REG_COMMAND 0x{off['command']:02X}u
#define REG_STATUS 0x{off['status']:02X}u
#define REG_DESCRIPTOR_LO 0x{off['descriptor_ptr_lo']:02X}u
#define REG_DESCRIPTOR_HI 0x{off['descriptor_ptr_hi']:02X}u
#define REG_INPUT_LO 0x{off['input_queue_ptr_lo']:02X}u
#define REG_INPUT_HI 0x{off['input_queue_ptr_hi']:02X}u
#define REG_OUTPUT_LO 0x{off['output_queue_ptr_lo']:02X}u
#define REG_OUTPUT_HI 0x{off['output_queue_ptr_hi']:02X}u
#define REG_RECEIPT_LO 0x{off['receipt_ptr_lo']:02X}u
#define REG_RECEIPT_HI 0x{off['receipt_ptr_hi']:02X}u
#define REG_DOORBELL 0x{off['doorbell']:02X}u

#define CMD_RESET UINT32_C({_hex32(command['reset'])})
#define CMD_LOAD UINT32_C({_hex32(command['load'])})
#define CMD_EVOLVE UINT32_C({_hex32(command['evolve'])})
#define CMD_READ UINT32_C({_hex32(command['read'])})
#define CMD_CAPTURE UINT32_C({_hex32(command['capture'])})

#define STATUS_READY UINT32_C({_hex32(status['ready'])})
#define STATUS_BUSY UINT32_C({_hex32(status['busy'])})
#define STATUS_DONE UINT32_C({_hex32(status['done'])})
#define STATUS_REFUSED UINT32_C({_hex32(status['refused'])})
#define STATUS_FAULT UINT32_C({_hex32(status['fault'])})
#define STATUS_RECEIPT_VALID UINT32_C({_hex32(status['receipt_valid'])})

#define EXPECTED_IDENTITY UINT32_C(0x41504859)
#define EXPECTED_CAPABILITIES UINT32_C({_hex32(expected_caps)})

static uint32_t descriptor_words[16] __attribute__((aligned(64)));
static uint32_t input_words[16] __attribute__((aligned(64)));
static uint32_t output_words[16] __attribute__((aligned(64)));
static uint32_t receipt_words[32] __attribute__((aligned(64)));

static inline void mmio_fence(void) {{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}}

static void write_ptr(uint32_t lo_offset, uint32_t hi_offset, uintptr_t value) {{
    REG32(lo_offset) = (uint32_t)value;
    REG32(hi_offset) = (uint32_t)(((uint64_t)value) >> 32);
    mmio_fence();
}}

static void submit(uint32_t command) {{
    REG32(REG_COMMAND) = command;
    mmio_fence();
    REG32(REG_DOORBELL) = 1;
    mmio_fence();
}}

static uint32_t wait_terminal(uint32_t limit) {{
    while (limit-- != 0) {{
        uint32_t observed = REG32(REG_STATUS);
        if ((observed & STATUS_BUSY) == 0 &&
            (observed & (STATUS_DONE | STATUS_REFUSED | STATUS_FAULT)) != 0) {{
            return observed;
        }}
    }}
    return 0;
}}

static const char *terminal_result(uint32_t observed) {{
    if ((observed & STATUS_REFUSED) != 0) return "refused";
    if ((observed & STATUS_FAULT) != 0) return "fault";
    if ((observed & STATUS_DONE) != 0) return "done";
    return "timeout";
}}

static const char *receipt_state(uint32_t observed) {{
    return (observed & STATUS_RECEIPT_VALID) != 0 ? "valid" : "absent";
}}

static void emit_stage(const char *stage, uint32_t observed) {{
    printf(
        TRACE_PREFIX "%s status=%08" PRIx32 " result=%s receipt=%s\\n",
        stage,
        observed,
        terminal_result(observed),
        receipt_state(observed));
}}

static int fail(int code) {{
    printf(TRACE_PREFIX "result=fail code=%d\\n", code);
    return code;
}}

static int accepted_status(uint32_t observed) {{
    const uint32_t required = STATUS_READY | STATUS_DONE | STATUS_RECEIPT_VALID;
    const uint32_t forbidden = STATUS_BUSY | STATUS_REFUSED | STATUS_FAULT;
    return (observed & required) == required && (observed & forbidden) == 0;
}}

int main(void) {{
    printf(TRACE_PREFIX "abi={PORTABLE_BINDING} isa=rv64gc\\n");

    const uint32_t identity = REG32(REG_IDENTITY);
    const uint32_t caps = REG32(REG_CAPABILITIES);
    printf(
        TRACE_PREFIX "identity=%08" PRIx32 " capabilities=%08" PRIx32 "\\n",
        identity,
        caps);
    if (identity != EXPECTED_IDENTITY || caps != EXPECTED_CAPABILITIES) {{
        return fail(1);
    }}

    submit(CMD_RESET | CMD_READ);
    uint32_t observed = wait_terminal(4096);
    emit_stage("ambiguous", observed);
    if (observed != (STATUS_READY | STATUS_REFUSED)) return fail(2);

    submit(CMD_RESET);
    observed = wait_terminal(4096);
    emit_stage("reset", observed);
    if (!accepted_status(observed)) return fail(3);

    write_ptr(REG_DESCRIPTOR_LO, REG_DESCRIPTOR_HI, (uintptr_t)descriptor_words);
    write_ptr(REG_INPUT_LO, REG_INPUT_HI, (uintptr_t)input_words);
    write_ptr(REG_OUTPUT_LO, REG_OUTPUT_HI, (uintptr_t)output_words);
    write_ptr(REG_RECEIPT_LO, REG_RECEIPT_HI, (uintptr_t)receipt_words);

    submit(CMD_LOAD);
    observed = wait_terminal(4096);
    emit_stage("load", observed);
    if (!accepted_status(observed)) return fail(4);

    submit(CMD_EVOLVE);
    observed = wait_terminal(4096);
    emit_stage("evolve", observed);
    if (!accepted_status(observed)) return fail(5);

    submit(CMD_READ);
    observed = wait_terminal(4096);
    emit_stage("read", observed);
    if (!accepted_status(observed)) return fail(6);

    submit(CMD_CAPTURE);
    observed = wait_terminal(4096);
    emit_stage("capture", observed);
    if (!accepted_status(observed)) return fail(7);

    printf(TRACE_PREFIX "result=pass\\n");
    return 0;
}}
"""
