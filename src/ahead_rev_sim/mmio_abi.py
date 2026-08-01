"""Portable RISC-V MMIO ABI and generated control-plane artifacts.

The ABI keeps ordinary MMIO as the portability floor.  A future Xphys
extension may accelerate the same queue and state operations, but it cannot
change register semantics, accepted work, fallback execution, or receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .physical_constants import (
    OPTIONAL_RISCV_EXTENSION,
    PHYSICAL_COMPUTE_MMIO_V1,
    PORTABLE_BINDING,
)

MMIO_ABI_SCHEMA_VERSION = "ahead.physical-compute-mmio-abi/v0.1"
MMIO_APERTURE_BYTES = 0x100
MMIO_WORD_BYTES = 4

COMMAND_BITS: Mapping[str, int] = {
    "reset": 0,
    "load": 1,
    "evolve": 2,
    "read": 3,
    "capture": 4,
}

STATUS_BITS: Mapping[str, int] = {
    "ready": 0,
    "busy": 1,
    "done": 2,
    "refused": 3,
    "fault": 4,
    "receipt_valid": 5,
}

CAPABILITY_BITS: Mapping[str, int] = {
    "exact": 0,
    "trace_replay": 1,
    "distributional": 2,
    "software_fallback": 3,
    "measured_energy": 4,
    "xphys_acceleration": 5,
}

REGISTER_ACCESS: Mapping[str, str] = {
    "identity": "ro",
    "capabilities": "ro",
    "command": "rw",
    "status": "ro",
    "descriptor_ptr_lo": "rw",
    "descriptor_ptr_hi": "rw",
    "input_queue_ptr_lo": "rw",
    "input_queue_ptr_hi": "rw",
    "output_queue_ptr_lo": "rw",
    "output_queue_ptr_hi": "rw",
    "receipt_ptr_lo": "rw",
    "receipt_ptr_hi": "rw",
    "doorbell": "wo",
}

REGISTER_SEMANTICS: Mapping[str, str] = {
    "identity": "Implementation identity and ABI compatibility word.",
    "capabilities": "Determinism, fallback, energy-evidence, and optional acceleration capabilities.",
    "command": "Exactly one command bit selected before ringing the doorbell.",
    "status": "Ready, busy, terminal result, and receipt-valid state.",
    "descriptor_ptr_lo": "Low 32 bits of the substrate descriptor pointer.",
    "descriptor_ptr_hi": "High 32 bits of the substrate descriptor pointer.",
    "input_queue_ptr_lo": "Low 32 bits of the input queue pointer.",
    "input_queue_ptr_hi": "High 32 bits of the input queue pointer.",
    "output_queue_ptr_lo": "Low 32 bits of the output queue pointer.",
    "output_queue_ptr_hi": "High 32 bits of the output queue pointer.",
    "receipt_ptr_lo": "Low 32 bits of the execution receipt pointer.",
    "receipt_ptr_hi": "High 32 bits of the execution receipt pointer.",
    "doorbell": "Write any value to submit the selected command.",
}

COMMAND_POINTER_REQUIREMENTS: Mapping[str, tuple[str, ...]] = {
    "reset": (),
    "load": ("descriptor_ptr", "input_queue_ptr"),
    "evolve": ("input_queue_ptr", "output_queue_ptr"),
    "read": ("output_queue_ptr",),
    "capture": ("receipt_ptr",),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def bit_mask(bit: int) -> int:
    return 1 << bit


def build_mmio_abi() -> dict[str, Any]:
    registers = [
        {
            "name": name,
            "offset": offset,
            "offset_hex": f"0x{offset:02X}",
            "width_bits": 32,
            "access": REGISTER_ACCESS[name],
            "reset": 0,
            "semantics": REGISTER_SEMANTICS[name],
        }
        for name, offset in sorted(
            PHYSICAL_COMPUTE_MMIO_V1.items(), key=lambda item: item[1]
        )
    ]
    payload: dict[str, Any] = {
        "schema_version": MMIO_ABI_SCHEMA_VERSION,
        "artifact_type": "physical_compute_mmio_abi",
        "portable_binding": PORTABLE_BINDING,
        "optional_riscv_extension": OPTIONAL_RISCV_EXTENSION,
        "byte_order": "little",
        "word_bytes": MMIO_WORD_BYTES,
        "aperture_bytes": MMIO_APERTURE_BYTES,
        "registers": registers,
        "command_bits": dict(COMMAND_BITS),
        "status_bits": dict(STATUS_BITS),
        "capability_bits": dict(CAPABILITY_BITS),
        "command_pointer_requirements": {
            command: list(requirements)
            for command, requirements in COMMAND_POINTER_REQUIREMENTS.items()
        },
        "invariants": [
            "ordinary RISC-V MMIO remains sufficient for every operation",
            "exactly one command bit is submitted per doorbell",
            "pointer and command registers remain stable while busy",
            "done, refused, and fault terminal states are mutually exclusive",
            "a receipt-valid indication belongs to a terminal execution",
            "Xphys may accelerate the ABI but cannot alter it",
        ],
        "claim_boundary": (
            "The ABI and generated reference control plane establish register, queue, "
            "command, refusal, reset, and receipt semantics. They do not establish "
            "physical execution, measured energy, timing closure, occupied volume, "
            "thermal closure, or manufacturable silicon."
        ),
    }
    payload["abi_sha256"] = sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


def render_abi_json(*, indent: int = 2) -> str:
    return json.dumps(build_mmio_abi(), indent=indent, sort_keys=True) + "\n"


def _macro(name: str) -> str:
    return name.upper().replace("-", "_")


def render_c_header() -> str:
    abi = build_mmio_abi()
    lines = [
        "/* Generated by ahead-rev-sim. Do not hand-edit. */",
        "#ifndef AHEAD_PHYSICAL_COMPUTE_MMIO_V1_H",
        "#define AHEAD_PHYSICAL_COMPUTE_MMIO_V1_H",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        f'#define AHEAD_PHYS_MMIO_BINDING "{PORTABLE_BINDING}"',
        f'#define AHEAD_PHYS_OPTIONAL_RISCV_EXTENSION "{OPTIONAL_RISCV_EXTENSION}"',
        f"#define AHEAD_PHYS_MMIO_APERTURE_BYTES 0x{MMIO_APERTURE_BYTES:03X}u",
        "",
    ]
    for register in abi["registers"]:
        lines.append(
            f"#define AHEAD_PHYS_REG_{_macro(register['name'])} "
            f"0x{register['offset']:02X}u"
        )
    lines.append("")
    for name, bit in COMMAND_BITS.items():
        lines.append(
            f"#define AHEAD_PHYS_CMD_{_macro(name)} (UINT32_C(1) << {bit})"
        )
    lines.append("")
    for name, bit in STATUS_BITS.items():
        lines.append(
            f"#define AHEAD_PHYS_STATUS_{_macro(name)} (UINT32_C(1) << {bit})"
        )
    lines.append("")
    for name, bit in CAPABILITY_BITS.items():
        lines.append(
            f"#define AHEAD_PHYS_CAP_{_macro(name)} (UINT32_C(1) << {bit})"
        )
    lines.extend(
        [
            "",
            "typedef struct ahead_phys_mmio_v1 {",
            "    volatile uint32_t identity;",
            "    volatile uint32_t capabilities;",
            "    volatile uint32_t command;",
            "    volatile uint32_t status;",
            "    volatile uint32_t descriptor_ptr_lo;",
            "    volatile uint32_t descriptor_ptr_hi;",
            "    volatile uint32_t input_queue_ptr_lo;",
            "    volatile uint32_t input_queue_ptr_hi;",
            "    volatile uint32_t output_queue_ptr_lo;",
            "    volatile uint32_t output_queue_ptr_hi;",
            "    volatile uint32_t receipt_ptr_lo;",
            "    volatile uint32_t receipt_ptr_hi;",
            "    volatile uint32_t doorbell;",
            "} ahead_phys_mmio_v1_t;",
            "",
            "static inline void ahead_phys_write_ptr(",
            "    volatile uint32_t *lo, volatile uint32_t *hi, uint64_t value)",
            "{",
            "    *lo = (uint32_t)value;",
            "    *hi = (uint32_t)(value >> 32);",
            "}",
            "",
            "static inline uint64_t ahead_phys_read_ptr(",
            "    volatile const uint32_t *lo, volatile const uint32_t *hi)",
            "{",
            "    return ((uint64_t)(*hi) << 32) | (uint64_t)(*lo);",
            "}",
            "",
        ]
    )
    for register in abi["registers"]:
        lines.append(
            f"_Static_assert(offsetof(ahead_phys_mmio_v1_t, {register['name']}) "
            f"== AHEAD_PHYS_REG_{_macro(register['name'])}, "
            f'"{register["name"]} offset drift");'
        )
    lines.extend(("", "#endif", ""))
    return "\n".join(lines)


def render_systemverilog() -> str:
    offsets = {name: f"8'h{offset:02X}" for name, offset in PHYSICAL_COMPUTE_MMIO_V1.items()}
    command_masks = {name: f"32'h{bit_mask(bit):08X}" for name, bit in COMMAND_BITS.items()}
    status_masks = {name: f"32'h{bit_mask(bit):08X}" for name, bit in STATUS_BITS.items()}
    return f"""// Generated by ahead-rev-sim. Portable floor: {PORTABLE_BINDING}.
// {OPTIONAL_RISCV_EXTENSION} may accelerate this interface but cannot change it.
module ahead_physical_compute_mmio_v1 #(
    parameter logic [31:0] IDENTITY = 32'h41504859,
    parameter logic [31:0] CAPABILITIES = 32'h00000008
) (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic        req_valid_i,
    input  logic        req_write_i,
    input  logic [7:0]  req_addr_i,
    input  logic [31:0] req_wdata_i,
    output logic        req_ready_o,
    output logic [31:0] rsp_rdata_o,
    output logic        rsp_error_o,
    output logic        command_valid_o,
    output logic [31:0] command_o,
    output logic [63:0] descriptor_ptr_o,
    output logic [63:0] input_queue_ptr_o,
    output logic [63:0] output_queue_ptr_o,
    output logic [63:0] receipt_ptr_o,
    input  logic        command_ready_i,
    input  logic        command_done_i,
    input  logic        command_refused_i,
    input  logic        command_fault_i,
    input  logic        receipt_valid_i
);

    localparam logic [31:0] CMD_RESET   = {command_masks['reset']};
    localparam logic [31:0] CMD_LOAD    = {command_masks['load']};
    localparam logic [31:0] CMD_EVOLVE  = {command_masks['evolve']};
    localparam logic [31:0] CMD_READ    = {command_masks['read']};
    localparam logic [31:0] CMD_CAPTURE = {command_masks['capture']};

    localparam logic [31:0] STATUS_READY         = {status_masks['ready']};
    localparam logic [31:0] STATUS_BUSY          = {status_masks['busy']};
    localparam logic [31:0] STATUS_DONE          = {status_masks['done']};
    localparam logic [31:0] STATUS_REFUSED       = {status_masks['refused']};
    localparam logic [31:0] STATUS_FAULT         = {status_masks['fault']};
    localparam logic [31:0] STATUS_RECEIPT_VALID = {status_masks['receipt_valid']};

    logic [31:0] command_q;
    logic [31:0] status_q;
    logic [63:0] descriptor_ptr_q;
    logic [63:0] input_queue_ptr_q;
    logic [63:0] output_queue_ptr_q;
    logic [63:0] receipt_ptr_q;
    logic command_valid_q;

    function automatic logic command_onehot(input logic [31:0] command);
        logic [31:0] supported;
        supported = CMD_RESET | CMD_LOAD | CMD_EVOLVE | CMD_READ | CMD_CAPTURE;
        command_onehot = (command != 32'b0) && ((command & (command - 1'b1)) == 32'b0)
                         && ((command & ~supported) == 32'b0);
    endfunction

    function automatic logic command_pointers_ready(input logic [31:0] command);
        case (command)
            CMD_RESET:   command_pointers_ready = 1'b1;
            CMD_LOAD:    command_pointers_ready = (descriptor_ptr_q != 64'b0)
                                                  && (input_queue_ptr_q != 64'b0);
            CMD_EVOLVE:  command_pointers_ready = (input_queue_ptr_q != 64'b0)
                                                  && (output_queue_ptr_q != 64'b0);
            CMD_READ:    command_pointers_ready = (output_queue_ptr_q != 64'b0);
            CMD_CAPTURE: command_pointers_ready = (receipt_ptr_q != 64'b0);
            default:     command_pointers_ready = 1'b0;
        endcase
    endfunction

    assign req_ready_o = 1'b1;
    assign command_valid_o = command_valid_q;
    assign command_o = command_q;
    assign descriptor_ptr_o = descriptor_ptr_q;
    assign input_queue_ptr_o = input_queue_ptr_q;
    assign output_queue_ptr_o = output_queue_ptr_q;
    assign receipt_ptr_o = receipt_ptr_q;

    always_comb begin
        rsp_rdata_o = 32'b0;
        rsp_error_o = 1'b0;
        unique case (req_addr_i)
            {offsets['identity']}: rsp_rdata_o = IDENTITY;
            {offsets['capabilities']}: rsp_rdata_o = CAPABILITIES;
            {offsets['command']}: rsp_rdata_o = command_q;
            {offsets['status']}: rsp_rdata_o = status_q;
            {offsets['descriptor_ptr_lo']}: rsp_rdata_o = descriptor_ptr_q[31:0];
            {offsets['descriptor_ptr_hi']}: rsp_rdata_o = descriptor_ptr_q[63:32];
            {offsets['input_queue_ptr_lo']}: rsp_rdata_o = input_queue_ptr_q[31:0];
            {offsets['input_queue_ptr_hi']}: rsp_rdata_o = input_queue_ptr_q[63:32];
            {offsets['output_queue_ptr_lo']}: rsp_rdata_o = output_queue_ptr_q[31:0];
            {offsets['output_queue_ptr_hi']}: rsp_rdata_o = output_queue_ptr_q[63:32];
            {offsets['receipt_ptr_lo']}: rsp_rdata_o = receipt_ptr_q[31:0];
            {offsets['receipt_ptr_hi']}: rsp_rdata_o = receipt_ptr_q[63:32];
            {offsets['doorbell']}: rsp_rdata_o = 32'b0;
            default: rsp_error_o = req_valid_i;
        endcase
        if (req_valid_i && req_write_i) begin
            if (req_addr_i == {offsets['identity']}
                || req_addr_i == {offsets['capabilities']}
                || req_addr_i == {offsets['status']}) begin
                rsp_error_o = 1'b1;
            end
            if ((status_q & STATUS_BUSY) != 32'b0
                && req_addr_i != {offsets['doorbell']}) begin
                rsp_error_o = 1'b1;
            end
        end
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            command_q <= 32'b0;
            status_q <= STATUS_READY;
            descriptor_ptr_q <= 64'b0;
            input_queue_ptr_q <= 64'b0;
            output_queue_ptr_q <= 64'b0;
            receipt_ptr_q <= 64'b0;
            command_valid_q <= 1'b0;
        end else begin
            if (command_valid_q && command_ready_i) begin
                command_valid_q <= 1'b0;
            end

            if (req_valid_i && req_write_i && !rsp_error_o) begin
                unique case (req_addr_i)
                    {offsets['command']}: command_q <= req_wdata_i;
                    {offsets['descriptor_ptr_lo']}: descriptor_ptr_q[31:0] <= req_wdata_i;
                    {offsets['descriptor_ptr_hi']}: descriptor_ptr_q[63:32] <= req_wdata_i;
                    {offsets['input_queue_ptr_lo']}: input_queue_ptr_q[31:0] <= req_wdata_i;
                    {offsets['input_queue_ptr_hi']}: input_queue_ptr_q[63:32] <= req_wdata_i;
                    {offsets['output_queue_ptr_lo']}: output_queue_ptr_q[31:0] <= req_wdata_i;
                    {offsets['output_queue_ptr_hi']}: output_queue_ptr_q[63:32] <= req_wdata_i;
                    {offsets['receipt_ptr_lo']}: receipt_ptr_q[31:0] <= req_wdata_i;
                    {offsets['receipt_ptr_hi']}: receipt_ptr_q[63:32] <= req_wdata_i;
                    {offsets['doorbell']}: begin
                        if (command_onehot(command_q) && command_pointers_ready(command_q)) begin
                            command_valid_q <= 1'b1;
                            status_q <= STATUS_BUSY;
                        end else begin
                            status_q <= STATUS_READY | STATUS_REFUSED;
                        end
                    end
                    default: begin end
                endcase
            end

            if (command_done_i) begin
                status_q <= STATUS_READY | STATUS_DONE
                            | (receipt_valid_i ? STATUS_RECEIPT_VALID : 32'b0);
            end else if (command_refused_i) begin
                status_q <= STATUS_READY | STATUS_REFUSED
                            | (receipt_valid_i ? STATUS_RECEIPT_VALID : 32'b0);
            end else if (command_fault_i) begin
                status_q <= STATUS_READY | STATUS_FAULT
                            | (receipt_valid_i ? STATUS_RECEIPT_VALID : 32'b0);
            end
        end
    end
endmodule
"""


def render_sva() -> str:
    return f"""// Generated assertions for {PORTABLE_BINDING}.
module ahead_physical_compute_mmio_v1_sva (
    input logic clk_i,
    input logic rst_ni,
    input logic command_valid_i,
    input logic [31:0] command_i,
    input logic [31:0] status_i,
    input logic [63:0] descriptor_ptr_i,
    input logic [63:0] input_queue_ptr_i,
    input logic [63:0] output_queue_ptr_i,
    input logic [63:0] receipt_ptr_i
);
    localparam logic [31:0] STATUS_READY         = 32'h{bit_mask(STATUS_BITS['ready']):08X};
    localparam logic [31:0] STATUS_BUSY          = 32'h{bit_mask(STATUS_BITS['busy']):08X};
    localparam logic [31:0] STATUS_DONE          = 32'h{bit_mask(STATUS_BITS['done']):08X};
    localparam logic [31:0] STATUS_REFUSED       = 32'h{bit_mask(STATUS_BITS['refused']):08X};
    localparam logic [31:0] STATUS_FAULT         = 32'h{bit_mask(STATUS_BITS['fault']):08X};
    localparam logic [31:0] STATUS_RECEIPT_VALID = 32'h{bit_mask(STATUS_BITS['receipt_valid']):08X};

    default clocking cb @(posedge clk_i); endclocking
    default disable iff (!rst_ni);

    assert property (command_valid_i |-> $onehot(command_i));
    assert property ((status_i & STATUS_BUSY) != 0 |-> (status_i & STATUS_READY) == 0);
    assert property ($onehot0({{(status_i & STATUS_DONE) != 0,
                               (status_i & STATUS_REFUSED) != 0,
                               (status_i & STATUS_FAULT) != 0}}));
    assert property ((status_i & STATUS_RECEIPT_VALID) != 0
                     |-> ((status_i & (STATUS_DONE | STATUS_REFUSED | STATUS_FAULT)) != 0));
    assert property ((status_i & STATUS_BUSY) != 0
                     |=> $stable({{descriptor_ptr_i, input_queue_ptr_i,
                                  output_queue_ptr_i, receipt_ptr_i}}));
endmodule
"""


def write_bundle(output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "abi": root / "physical-compute-mmio-v1.json",
        "c_header": root / "ahead_physical_compute_mmio_v1.h",
        "systemverilog": root / "ahead_physical_compute_mmio_v1.sv",
        "sva": root / "ahead_physical_compute_mmio_v1_sva.sv",
    }
    outputs["abi"].write_text(render_abi_json(), encoding="utf-8")
    outputs["c_header"].write_text(render_c_header(), encoding="utf-8")
    outputs["systemverilog"].write_text(render_systemverilog(), encoding="utf-8")
    outputs["sva"].write_text(render_sva(), encoding="utf-8")
    return outputs


@dataclass
class PhysicalComputeMMIOReference:
    """Executable refusal and lifecycle model for the generated MMIO block."""

    identity: int = 0x41504859
    capabilities: int = bit_mask(CAPABILITY_BITS["software_fallback"])
    _registers: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._registers = {name: 0 for name in PHYSICAL_COMPUTE_MMIO_V1}
        self._registers["identity"] = self.identity & 0xFFFFFFFF
        self._registers["capabilities"] = self.capabilities & 0xFFFFFFFF
        self._registers["status"] = bit_mask(STATUS_BITS["ready"])

    @property
    def busy(self) -> bool:
        return bool(self._registers["status"] & bit_mask(STATUS_BITS["busy"]))

    def read(self, offset: int) -> int:
        return self._registers[self._name_for_offset(offset)]

    def write(self, offset: int, value: int) -> None:
        name = self._name_for_offset(offset)
        access = REGISTER_ACCESS[name]
        if access == "ro":
            raise PermissionError(f"{name} is read-only")
        if self.busy and name != "doorbell":
            raise RuntimeError("MMIO control state is immutable while busy")
        if name == "doorbell":
            self._ring_doorbell()
            return
        self._registers[name] = value & 0xFFFFFFFF

    def pointer(self, base_name: str) -> int:
        return (
            (self._registers[f"{base_name}_hi"] << 32)
            | self._registers[f"{base_name}_lo"]
        )

    def complete(
        self,
        *,
        outcome: str = "done",
        receipt_valid: bool = True,
    ) -> None:
        if not self.busy:
            raise RuntimeError("cannot complete an idle command")
        terminal = {
            "done": "done",
            "refused": "refused",
            "fault": "fault",
        }.get(outcome)
        if terminal is None:
            raise ValueError(f"unknown terminal outcome: {outcome}")
        status = bit_mask(STATUS_BITS["ready"]) | bit_mask(STATUS_BITS[terminal])
        if receipt_valid:
            status |= bit_mask(STATUS_BITS["receipt_valid"])
        self._registers["status"] = status

    def snapshot(self) -> dict[str, int]:
        return dict(self._registers)

    def _ring_doorbell(self) -> None:
        if self.busy:
            raise RuntimeError("doorbell refused while busy")
        command = self._registers["command"]
        command_name = self._decode_command(command)
        if command_name is None:
            self._refuse()
            return
        missing = [
            pointer
            for pointer in COMMAND_POINTER_REQUIREMENTS[command_name]
            if self.pointer(pointer) == 0
        ]
        if missing:
            self._refuse()
            return
        self._registers["status"] = bit_mask(STATUS_BITS["busy"])

    def _refuse(self) -> None:
        self._registers["status"] = (
            bit_mask(STATUS_BITS["ready"])
            | bit_mask(STATUS_BITS["refused"])
        )

    @staticmethod
    def _decode_command(command: int) -> str | None:
        supported = {
            bit_mask(bit): name
            for name, bit in COMMAND_BITS.items()
        }
        return supported.get(command & 0xFFFFFFFF)

    @staticmethod
    def _name_for_offset(offset: int) -> str:
        if offset % MMIO_WORD_BYTES:
            raise ValueError(f"unaligned MMIO offset: 0x{offset:X}")
        for name, candidate in PHYSICAL_COMPUTE_MMIO_V1.items():
            if candidate == offset:
                return name
        raise KeyError(f"unknown MMIO offset: 0x{offset:X}")
