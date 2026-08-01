"""Provider-neutral SystemVerilog attachment and execution proof.

The attachment executes the generated physical-compute MMIO block against an
independent handle resolver and cartridge state machine. It closes actual RTL
lifecycle evidence while preserving Chipyard, FPGA, silicon, physical-substrate,
and complete-system EVP boundaries.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from .mmio_abi import build_mmio_abi, canonical_json
from .physical_constants import OPTIONAL_RISCV_EXTENSION, PORTABLE_BINDING

RTL_ATTACHMENT_CONTRACT_SCHEMA_VERSION = "ahead.rtl-attachment-contract/v0.1"
RTL_ATTACHMENT_MANIFEST_SCHEMA_VERSION = "ahead.rtl-attachment-manifest/v0.1"
RTL_ATTACHMENT_PROOF_SCHEMA_VERSION = "ahead.rtl-attachment-proof/v0.1"
RTL_ATTACHMENT_LINK = "physical-cartridge-link/v1"
RTL_ATTACHMENT_RESOLVER = "physical-cartridge-handle-resolver/v1"

EXPECTED_TRACE = """abi=physical-compute-mmio/v1 rtl=iverilog link=physical-cartridge-link/v1 resolver=physical-cartridge-handle-resolver/v1
identity=41504859 capabilities=00000009
ambiguous status=00000009 result=refused
reset status=00000025 result=done receipt=valid
bad_descriptor status=00000029 result=refused receipt=valid descriptor_word=bad0bad0bad0bad0
memory_fault status=00000031 result=fault receipt=valid descriptor=0000000010004000
load status=00000025 result=done receipt=valid descriptor=0000000010001000 input=0000000010002000 descriptor_word=a11ea11e00000001
 evolve status=00000025 result=done receipt=valid input_word=000000000000002a output_word=0000000000000054
read status=00000025 result=done receipt=valid output_word=0000000000000054
capture status=00000025 result=done receipt=valid receipt_word=52544c50524f4f46
result=pass
""".replace("\n evolve", "\nevolve")


def sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def _first_line(value: str) -> str:
    return value.strip().splitlines()[0] if value.strip() else ""


def command_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "-V"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    result = _first_line(completed.stdout)
    if not result:
        raise ValueError(f"{executable}: version output is empty")
    return result


def build_attachment_contract() -> dict[str, Any]:
    contract: dict[str, Any] = {
        "schema_version": RTL_ATTACHMENT_CONTRACT_SCHEMA_VERSION,
        "artifact_type": "physical_compute_rtl_attachment_contract",
        "portable_binding": PORTABLE_BINDING,
        "optional_riscv_extension": OPTIONAL_RISCV_EXTENSION,
        "link_id": RTL_ATTACHMENT_LINK,
        "resolver_id": RTL_ATTACHMENT_RESOLVER,
        "command_surface": ["reset", "load", "evolve", "read", "capture"],
        "terminal_surface": ["done", "refused", "fault", "receipt_valid"],
        "memory_request": {
            "fields": ["valid", "write", "opaque_handle", "write_data"],
            "response_fields": ["valid", "fault", "read_data"],
            "address_authority": "resolver_only",
        },
        "invariants": [
            "the MMIO bridge and cartridge are independently replaceable",
            "opaque handles cross the cartridge boundary instead of host pointers",
            "exactly one terminal outcome is emitted per accepted command",
            "ambiguous MMIO commands refuse before cartridge dispatch",
            "resolver failure becomes a cartridge fault with a receipt",
            "invalid descriptor content becomes a refusal with a receipt",
            "software fallback and accepted work remain outside the cartridge",
        ],
        "claim_boundary": (
            "The contract defines a provider-neutral RTL attachment. It does not "
            "establish Chipyard subsystem elaboration, FPGA or silicon execution, "
            "physical substrate work, measured energy, occupied volume, timing, "
            "thermal closure, fabrication, or complete-system advantage."
        ),
        "control_question": (
            "Can a host bridge, resolver, or cartridge be replaced independently "
            "while command, state, refusal, fault, receipt, and accepted trace "
            "semantics remain unchanged?"
        ),
    }
    contract["contract_sha256"] = sha256_text(canonical_json(contract))
    return contract


def render_contract_json() -> str:
    return json.dumps(build_attachment_contract(), indent=2, sort_keys=True) + "\n"


def render_resolver_systemverilog() -> str:
    return """// Provider-neutral reference resolver for opaque physical-cartridge handles.
module ahead_reference_handle_resolver_v1 (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic        req_valid_i,
    input  logic        req_write_i,
    input  logic [63:0] req_handle_i,
    input  logic [63:0] req_wdata_i,
    output logic        req_ready_o,
    output logic        rsp_valid_o,
    output logic        rsp_fault_o,
    output logic [63:0] rsp_rdata_o,
    output logic [63:0] output_word_o,
    output logic [63:0] receipt_word_o
);
    localparam logic [63:0] HANDLE_DESCRIPTOR_GOOD = 64'h0000000010001000;
    localparam logic [63:0] HANDLE_INPUT           = 64'h0000000010002000;
    localparam logic [63:0] HANDLE_DESCRIPTOR_BAD  = 64'h0000000010003000;
    localparam logic [63:0] HANDLE_DESCRIPTOR_FAULT= 64'h0000000010004000;
    localparam logic [63:0] HANDLE_OUTPUT          = 64'h0000000010005000;
    localparam logic [63:0] HANDLE_RECEIPT         = 64'h0000000010006000;

    localparam logic [63:0] WORD_DESCRIPTOR_GOOD = 64'hA11EA11E00000001;
    localparam logic [63:0] WORD_DESCRIPTOR_BAD  = 64'hBAD0BAD0BAD0BAD0;
    localparam logic [63:0] WORD_INPUT           = 64'h000000000000002A;

    logic        pending_q;
    logic        pending_write_q;
    logic [63:0] pending_handle_q;
    logic [63:0] pending_wdata_q;
    logic [63:0] output_word_q;
    logic [63:0] receipt_word_q;

    assign req_ready_o = !pending_q;
    assign output_word_o = output_word_q;
    assign receipt_word_o = receipt_word_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            pending_q <= 1'b0;
            pending_write_q <= 1'b0;
            pending_handle_q <= 64'b0;
            pending_wdata_q <= 64'b0;
            rsp_valid_o <= 1'b0;
            rsp_fault_o <= 1'b0;
            rsp_rdata_o <= 64'b0;
            output_word_q <= 64'b0;
            receipt_word_q <= 64'b0;
        end else begin
            rsp_valid_o <= 1'b0;
            rsp_fault_o <= 1'b0;
            rsp_rdata_o <= 64'b0;

            if (pending_q) begin
                pending_q <= 1'b0;
                rsp_valid_o <= 1'b1;
                unique case (pending_handle_q)
                    HANDLE_DESCRIPTOR_GOOD: begin
                        if (pending_write_q) begin
                            rsp_fault_o <= 1'b1;
                        end else begin
                            rsp_rdata_o <= WORD_DESCRIPTOR_GOOD;
                        end
                    end
                    HANDLE_DESCRIPTOR_BAD: begin
                        if (pending_write_q) begin
                            rsp_fault_o <= 1'b1;
                        end else begin
                            rsp_rdata_o <= WORD_DESCRIPTOR_BAD;
                        end
                    end
                    HANDLE_DESCRIPTOR_FAULT: begin
                        rsp_fault_o <= 1'b1;
                    end
                    HANDLE_INPUT: begin
                        if (pending_write_q) begin
                            rsp_fault_o <= 1'b1;
                        end else begin
                            rsp_rdata_o <= WORD_INPUT;
                        end
                    end
                    HANDLE_OUTPUT: begin
                        if (pending_write_q) begin
                            output_word_q <= pending_wdata_q;
                        end else begin
                            rsp_rdata_o <= output_word_q;
                        end
                    end
                    HANDLE_RECEIPT: begin
                        if (pending_write_q) begin
                            receipt_word_q <= pending_wdata_q;
                        end else begin
                            rsp_rdata_o <= receipt_word_q;
                        end
                    end
                    default: begin
                        rsp_fault_o <= 1'b1;
                    end
                endcase
            end

            if (req_valid_i && req_ready_o) begin
                pending_q <= 1'b1;
                pending_write_q <= req_write_i;
                pending_handle_q <= req_handle_i;
                pending_wdata_q <= req_wdata_i;
            end
        end
    end
endmodule
"""


def render_cartridge_systemverilog() -> str:
    return """// Replaceable reference cartridge behind physical-cartridge-link/v1.
module ahead_reference_reversible_cartridge_v1 (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic        command_valid_i,
    input  logic [31:0] command_i,
    input  logic [63:0] descriptor_handle_i,
    input  logic [63:0] input_handle_i,
    input  logic [63:0] output_handle_i,
    input  logic [63:0] receipt_handle_i,
    output logic        command_ready_o,
    output logic        command_done_o,
    output logic        command_refused_o,
    output logic        command_fault_o,
    output logic        receipt_valid_o,
    output logic        mem_req_valid_o,
    output logic        mem_req_write_o,
    output logic [63:0] mem_req_handle_o,
    output logic [63:0] mem_req_wdata_o,
    input  logic        mem_req_ready_i,
    input  logic        mem_rsp_valid_i,
    input  logic        mem_rsp_fault_i,
    input  logic [63:0] mem_rsp_rdata_i,
    output logic [63:0] last_descriptor_word_o,
    output logic [63:0] last_input_word_o,
    output logic [63:0] state_word_o
);
    localparam logic [31:0] CMD_RESET   = 32'h00000001;
    localparam logic [31:0] CMD_LOAD    = 32'h00000002;
    localparam logic [31:0] CMD_EVOLVE  = 32'h00000004;
    localparam logic [31:0] CMD_READ    = 32'h00000008;
    localparam logic [31:0] CMD_CAPTURE = 32'h00000010;

    localparam logic [63:0] WORD_DESCRIPTOR_GOOD = 64'hA11EA11E00000001;
    localparam logic [63:0] WORD_RECEIPT = 64'h52544C50524F4F46;

    typedef enum logic [4:0] {
        ST_IDLE,
        ST_LOAD_DESCRIPTOR_REQUEST,
        ST_LOAD_DESCRIPTOR_WAIT,
        ST_LOAD_INPUT_REQUEST,
        ST_LOAD_INPUT_WAIT,
        ST_EVOLVE_INPUT_REQUEST,
        ST_EVOLVE_INPUT_WAIT,
        ST_EVOLVE_OUTPUT_REQUEST,
        ST_EVOLVE_OUTPUT_WAIT,
        ST_READ_OUTPUT_REQUEST,
        ST_READ_OUTPUT_WAIT,
        ST_CAPTURE_REQUEST,
        ST_CAPTURE_WAIT
    } state_t;

    state_t state_q;
    logic [63:0] descriptor_handle_q;
    logic [63:0] input_handle_q;
    logic [63:0] output_handle_q;
    logic [63:0] receipt_handle_q;
    logic [63:0] state_word_q;
    logic [63:0] last_descriptor_word_q;
    logic [63:0] last_input_word_q;

    assign command_ready_o = (state_q == ST_IDLE);
    assign last_descriptor_word_o = last_descriptor_word_q;
    assign last_input_word_o = last_input_word_q;
    assign state_word_o = state_word_q;

    always_comb begin
        mem_req_valid_o = 1'b0;
        mem_req_write_o = 1'b0;
        mem_req_handle_o = 64'b0;
        mem_req_wdata_o = 64'b0;
        unique case (state_q)
            ST_LOAD_DESCRIPTOR_REQUEST: begin
                mem_req_valid_o = 1'b1;
                mem_req_handle_o = descriptor_handle_q;
            end
            ST_LOAD_INPUT_REQUEST,
            ST_EVOLVE_INPUT_REQUEST: begin
                mem_req_valid_o = 1'b1;
                mem_req_handle_o = input_handle_q;
            end
            ST_EVOLVE_OUTPUT_REQUEST: begin
                mem_req_valid_o = 1'b1;
                mem_req_write_o = 1'b1;
                mem_req_handle_o = output_handle_q;
                mem_req_wdata_o = state_word_q;
            end
            ST_READ_OUTPUT_REQUEST: begin
                mem_req_valid_o = 1'b1;
                mem_req_handle_o = output_handle_q;
            end
            ST_CAPTURE_REQUEST: begin
                mem_req_valid_o = 1'b1;
                mem_req_write_o = 1'b1;
                mem_req_handle_o = receipt_handle_q;
                mem_req_wdata_o = WORD_RECEIPT;
            end
            default: begin end
        endcase
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q <= ST_IDLE;
            descriptor_handle_q <= 64'b0;
            input_handle_q <= 64'b0;
            output_handle_q <= 64'b0;
            receipt_handle_q <= 64'b0;
            state_word_q <= 64'b0;
            last_descriptor_word_q <= 64'b0;
            last_input_word_q <= 64'b0;
            command_done_o <= 1'b0;
            command_refused_o <= 1'b0;
            command_fault_o <= 1'b0;
            receipt_valid_o <= 1'b0;
        end else begin
            command_done_o <= 1'b0;
            command_refused_o <= 1'b0;
            command_fault_o <= 1'b0;
            receipt_valid_o <= 1'b0;

            unique case (state_q)
                ST_IDLE: begin
                    if (command_valid_i && command_ready_o) begin
                        descriptor_handle_q <= descriptor_handle_i;
                        input_handle_q <= input_handle_i;
                        output_handle_q <= output_handle_i;
                        receipt_handle_q <= receipt_handle_i;
                        unique case (command_i)
                            CMD_RESET: begin
                                state_word_q <= 64'b0;
                                last_descriptor_word_q <= 64'b0;
                                last_input_word_q <= 64'b0;
                                command_done_o <= 1'b1;
                                receipt_valid_o <= 1'b1;
                            end
                            CMD_LOAD: state_q <= ST_LOAD_DESCRIPTOR_REQUEST;
                            CMD_EVOLVE: state_q <= ST_EVOLVE_INPUT_REQUEST;
                            CMD_READ: state_q <= ST_READ_OUTPUT_REQUEST;
                            CMD_CAPTURE: state_q <= ST_CAPTURE_REQUEST;
                            default: begin
                                command_refused_o <= 1'b1;
                                receipt_valid_o <= 1'b1;
                            end
                        endcase
                    end
                end
                ST_LOAD_DESCRIPTOR_REQUEST: begin
                    if (mem_req_valid_o && mem_req_ready_i) begin
                        state_q <= ST_LOAD_DESCRIPTOR_WAIT;
                    end
                end
                ST_LOAD_DESCRIPTOR_WAIT: begin
                    if (mem_rsp_valid_i) begin
                        if (mem_rsp_fault_i) begin
                            command_fault_o <= 1'b1;
                            receipt_valid_o <= 1'b1;
                            state_q <= ST_IDLE;
                        end else begin
                            last_descriptor_word_q <= mem_rsp_rdata_i;
                            if (mem_rsp_rdata_i != WORD_DESCRIPTOR_GOOD) begin
                                command_refused_o <= 1'b1;
                                receipt_valid_o <= 1'b1;
                                state_q <= ST_IDLE;
                            end else begin
                                state_q <= ST_LOAD_INPUT_REQUEST;
                            end
                        end
                    end
                end
                ST_LOAD_INPUT_REQUEST: begin
                    if (mem_req_valid_o && mem_req_ready_i) begin
                        state_q <= ST_LOAD_INPUT_WAIT;
                    end
                end
                ST_LOAD_INPUT_WAIT: begin
                    if (mem_rsp_valid_i) begin
                        if (mem_rsp_fault_i) begin
                            command_fault_o <= 1'b1;
                        end else begin
                            last_input_word_q <= mem_rsp_rdata_i;
                            state_word_q <= mem_rsp_rdata_i;
                            command_done_o <= 1'b1;
                        end
                        receipt_valid_o <= 1'b1;
                        state_q <= ST_IDLE;
                    end
                end
                ST_EVOLVE_INPUT_REQUEST: begin
                    if (mem_req_valid_o && mem_req_ready_i) begin
                        state_q <= ST_EVOLVE_INPUT_WAIT;
                    end
                end
                ST_EVOLVE_INPUT_WAIT: begin
                    if (mem_rsp_valid_i) begin
                        if (mem_rsp_fault_i) begin
                            command_fault_o <= 1'b1;
                            receipt_valid_o <= 1'b1;
                            state_q <= ST_IDLE;
                        end else begin
                            last_input_word_q <= mem_rsp_rdata_i;
                            state_word_q <= state_word_q + mem_rsp_rdata_i;
                            state_q <= ST_EVOLVE_OUTPUT_REQUEST;
                        end
                    end
                end
                ST_EVOLVE_OUTPUT_REQUEST: begin
                    if (mem_req_valid_o && mem_req_ready_i) begin
                        state_q <= ST_EVOLVE_OUTPUT_WAIT;
                    end
                end
                ST_EVOLVE_OUTPUT_WAIT: begin
                    if (mem_rsp_valid_i) begin
                        if (mem_rsp_fault_i) begin
                            command_fault_o <= 1'b1;
                        end else begin
                            command_done_o <= 1'b1;
                        end
                        receipt_valid_o <= 1'b1;
                        state_q <= ST_IDLE;
                    end
                end
                ST_READ_OUTPUT_REQUEST: begin
                    if (mem_req_valid_o && mem_req_ready_i) begin
                        state_q <= ST_READ_OUTPUT_WAIT;
                    end
                end
                ST_READ_OUTPUT_WAIT: begin
                    if (mem_rsp_valid_i) begin
                        if (mem_rsp_fault_i) begin
                            command_fault_o <= 1'b1;
                        end else begin
                            state_word_q <= mem_rsp_rdata_i;
                            command_done_o <= 1'b1;
                        end
                        receipt_valid_o <= 1'b1;
                        state_q <= ST_IDLE;
                    end
                end
                ST_CAPTURE_REQUEST: begin
                    if (mem_req_valid_o && mem_req_ready_i) begin
                        state_q <= ST_CAPTURE_WAIT;
                    end
                end
                ST_CAPTURE_WAIT: begin
                    if (mem_rsp_valid_i) begin
                        if (mem_rsp_fault_i) begin
                            command_fault_o <= 1'b1;
                        end else begin
                            command_done_o <= 1'b1;
                        end
                        receipt_valid_o <= 1'b1;
                        state_q <= ST_IDLE;
                    end
                end
                default: begin
                    command_fault_o <= 1'b1;
                    receipt_valid_o <= 1'b1;
                    state_q <= ST_IDLE;
                end
            endcase
        end
    end
endmodule
"""


def render_testbench_systemverilog() -> str:
    return """`timescale 1ns/1ps
module ahead_physical_compute_attachment_tb;
    localparam logic [7:0] REG_IDENTITY          = 8'h00;
    localparam logic [7:0] REG_CAPABILITIES      = 8'h04;
    localparam logic [7:0] REG_COMMAND           = 8'h08;
    localparam logic [7:0] REG_STATUS            = 8'h0C;
    localparam logic [7:0] REG_DESCRIPTOR_LO     = 8'h10;
    localparam logic [7:0] REG_DESCRIPTOR_HI     = 8'h14;
    localparam logic [7:0] REG_INPUT_LO          = 8'h18;
    localparam logic [7:0] REG_INPUT_HI          = 8'h1C;
    localparam logic [7:0] REG_OUTPUT_LO         = 8'h20;
    localparam logic [7:0] REG_OUTPUT_HI         = 8'h24;
    localparam logic [7:0] REG_RECEIPT_LO        = 8'h28;
    localparam logic [7:0] REG_RECEIPT_HI        = 8'h2C;
    localparam logic [7:0] REG_DOORBELL          = 8'h30;

    localparam logic [31:0] CMD_RESET   = 32'h00000001;
    localparam logic [31:0] CMD_LOAD    = 32'h00000002;
    localparam logic [31:0] CMD_EVOLVE  = 32'h00000004;
    localparam logic [31:0] CMD_READ    = 32'h00000008;
    localparam logic [31:0] CMD_CAPTURE = 32'h00000010;

    localparam logic [31:0] STATUS_DONE     = 32'h00000004;
    localparam logic [31:0] STATUS_REFUSED  = 32'h00000008;
    localparam logic [31:0] STATUS_FAULT    = 32'h00000010;

    localparam logic [63:0] HANDLE_DESCRIPTOR_GOOD = 64'h0000000010001000;
    localparam logic [63:0] HANDLE_INPUT           = 64'h0000000010002000;
    localparam logic [63:0] HANDLE_DESCRIPTOR_BAD  = 64'h0000000010003000;
    localparam logic [63:0] HANDLE_DESCRIPTOR_FAULT= 64'h0000000010004000;
    localparam logic [63:0] HANDLE_OUTPUT          = 64'h0000000010005000;
    localparam logic [63:0] HANDLE_RECEIPT         = 64'h0000000010006000;

    logic clk;
    logic rst_n;
    logic req_valid;
    logic req_write;
    logic [7:0] req_addr;
    logic [31:0] req_wdata;
    logic req_ready;
    logic [31:0] rsp_rdata;
    logic rsp_error;

    logic command_valid;
    logic [31:0] command;
    logic [63:0] descriptor_ptr;
    logic [63:0] input_ptr;
    logic [63:0] output_ptr;
    logic [63:0] receipt_ptr;
    logic command_ready;
    logic command_done;
    logic command_refused;
    logic command_fault;
    logic receipt_valid;

    logic mem_req_valid;
    logic mem_req_write;
    logic [63:0] mem_req_handle;
    logic [63:0] mem_req_wdata;
    logic mem_req_ready;
    logic mem_rsp_valid;
    logic mem_rsp_fault;
    logic [63:0] mem_rsp_rdata;

    logic [63:0] last_descriptor_word;
    logic [63:0] last_input_word;
    logic [63:0] state_word;
    logic [63:0] output_word;
    logic [63:0] receipt_word;

    logic [31:0] identity_value;
    logic [31:0] capabilities_value;
    logic [31:0] status_ambiguous;
    logic [31:0] status_reset;
    logic [31:0] status_bad_descriptor;
    logic [31:0] status_memory_fault;
    logic [31:0] status_load;
    logic [31:0] status_evolve;
    logic [31:0] status_read;
    logic [31:0] status_capture;

    ahead_physical_compute_mmio_v1 #(
        .IDENTITY(32'h41504859),
        .CAPABILITIES(32'h00000009)
    ) mmio (
        .clk_i(clk),
        .rst_ni(rst_n),
        .req_valid_i(req_valid),
        .req_write_i(req_write),
        .req_addr_i(req_addr),
        .req_wdata_i(req_wdata),
        .req_ready_o(req_ready),
        .rsp_rdata_o(rsp_rdata),
        .rsp_error_o(rsp_error),
        .command_valid_o(command_valid),
        .command_o(command),
        .descriptor_ptr_o(descriptor_ptr),
        .input_queue_ptr_o(input_ptr),
        .output_queue_ptr_o(output_ptr),
        .receipt_ptr_o(receipt_ptr),
        .command_ready_i(command_ready),
        .command_done_i(command_done),
        .command_refused_i(command_refused),
        .command_fault_i(command_fault),
        .receipt_valid_i(receipt_valid)
    );

    ahead_reference_reversible_cartridge_v1 cartridge (
        .clk_i(clk),
        .rst_ni(rst_n),
        .command_valid_i(command_valid),
        .command_i(command),
        .descriptor_handle_i(descriptor_ptr),
        .input_handle_i(input_ptr),
        .output_handle_i(output_ptr),
        .receipt_handle_i(receipt_ptr),
        .command_ready_o(command_ready),
        .command_done_o(command_done),
        .command_refused_o(command_refused),
        .command_fault_o(command_fault),
        .receipt_valid_o(receipt_valid),
        .mem_req_valid_o(mem_req_valid),
        .mem_req_write_o(mem_req_write),
        .mem_req_handle_o(mem_req_handle),
        .mem_req_wdata_o(mem_req_wdata),
        .mem_req_ready_i(mem_req_ready),
        .mem_rsp_valid_i(mem_rsp_valid),
        .mem_rsp_fault_i(mem_rsp_fault),
        .mem_rsp_rdata_i(mem_rsp_rdata),
        .last_descriptor_word_o(last_descriptor_word),
        .last_input_word_o(last_input_word),
        .state_word_o(state_word)
    );

    ahead_reference_handle_resolver_v1 resolver (
        .clk_i(clk),
        .rst_ni(rst_n),
        .req_valid_i(mem_req_valid),
        .req_write_i(mem_req_write),
        .req_handle_i(mem_req_handle),
        .req_wdata_i(mem_req_wdata),
        .req_ready_o(mem_req_ready),
        .rsp_valid_o(mem_rsp_valid),
        .rsp_fault_o(mem_rsp_fault),
        .rsp_rdata_o(mem_rsp_rdata),
        .output_word_o(output_word),
        .receipt_word_o(receipt_word)
    );

    always #5 clk = ~clk;

    task automatic mmio_write(
        input logic [7:0] address,
        input logic [31:0] value
    );
        begin
            @(negedge clk);
            req_valid = 1'b1;
            req_write = 1'b1;
            req_addr = address;
            req_wdata = value;
            #1;
            if (rsp_error) begin
                $fatal(1, "MMIO write error at address %02x", address);
            end
            @(negedge clk);
            req_valid = 1'b0;
            req_write = 1'b0;
            req_addr = 8'b0;
            req_wdata = 32'b0;
        end
    endtask

    task automatic mmio_read(
        input logic [7:0] address,
        output logic [31:0] value
    );
        begin
            @(negedge clk);
            req_valid = 1'b1;
            req_write = 1'b0;
            req_addr = address;
            req_wdata = 32'b0;
            #1;
            if (rsp_error) begin
                $fatal(1, "MMIO read error at address %02x", address);
            end
            value = rsp_rdata;
            @(negedge clk);
            req_valid = 1'b0;
            req_addr = 8'b0;
        end
    endtask

    task automatic write_pointer(
        input logic [7:0] low_address,
        input logic [7:0] high_address,
        input logic [63:0] value
    );
        begin
            mmio_write(low_address, value[31:0]);
            mmio_write(high_address, value[63:32]);
        end
    endtask

    task automatic wait_terminal(output logic [31:0] terminal_status);
        integer index;
        begin : wait_loop
            terminal_status = 32'b0;
            for (index = 0; index < 128; index = index + 1) begin
                mmio_read(REG_STATUS, terminal_status);
                if ((terminal_status & (STATUS_DONE | STATUS_REFUSED | STATUS_FAULT)) != 0) begin
                    disable wait_loop;
                end
            end
            $fatal(1, "command did not reach a terminal state");
        end
    endtask

    task automatic submit(
        input logic [31:0] selected_command,
        output logic [31:0] terminal_status
    );
        begin
            mmio_write(REG_COMMAND, selected_command);
            mmio_write(REG_DOORBELL, 32'h1);
            wait_terminal(terminal_status);
        end
    endtask

    initial begin
        clk = 1'b0;
        rst_n = 1'b0;
        req_valid = 1'b0;
        req_write = 1'b0;
        req_addr = 8'b0;
        req_wdata = 32'b0;

        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        repeat (2) @(posedge clk);

        mmio_read(REG_IDENTITY, identity_value);
        mmio_read(REG_CAPABILITIES, capabilities_value);

        submit(CMD_RESET | CMD_READ, status_ambiguous);
        submit(CMD_RESET, status_reset);

        write_pointer(REG_DESCRIPTOR_LO, REG_DESCRIPTOR_HI, HANDLE_DESCRIPTOR_BAD);
        write_pointer(REG_INPUT_LO, REG_INPUT_HI, HANDLE_INPUT);
        submit(CMD_LOAD, status_bad_descriptor);

        write_pointer(REG_DESCRIPTOR_LO, REG_DESCRIPTOR_HI, HANDLE_DESCRIPTOR_FAULT);
        submit(CMD_LOAD, status_memory_fault);

        write_pointer(REG_DESCRIPTOR_LO, REG_DESCRIPTOR_HI, HANDLE_DESCRIPTOR_GOOD);
        write_pointer(REG_INPUT_LO, REG_INPUT_HI, HANDLE_INPUT);
        submit(CMD_LOAD, status_load);

        write_pointer(REG_OUTPUT_LO, REG_OUTPUT_HI, HANDLE_OUTPUT);
        submit(CMD_EVOLVE, status_evolve);
        submit(CMD_READ, status_read);

        write_pointer(REG_RECEIPT_LO, REG_RECEIPT_HI, HANDLE_RECEIPT);
        submit(CMD_CAPTURE, status_capture);

        if (identity_value != 32'h41504859) $fatal(1, "identity mismatch");
        if (capabilities_value != 32'h00000009) $fatal(1, "capability mismatch");
        if (status_ambiguous != 32'h00000009) $fatal(1, "ambiguous status mismatch");
        if (status_reset != 32'h00000025) $fatal(1, "reset status mismatch");
        if (status_bad_descriptor != 32'h00000029) $fatal(1, "bad descriptor status mismatch");
        if (status_memory_fault != 32'h00000031) $fatal(1, "memory fault status mismatch");
        if (status_load != 32'h00000025) $fatal(1, "load status mismatch");
        if (status_evolve != 32'h00000025) $fatal(1, "evolve status mismatch");
        if (status_read != 32'h00000025) $fatal(1, "read status mismatch");
        if (status_capture != 32'h00000025) $fatal(1, "capture status mismatch");
        if (last_descriptor_word != 64'hA11EA11E00000001) $fatal(1, "descriptor mismatch");
        if (last_input_word != 64'h000000000000002A) $fatal(1, "input mismatch");
        if (output_word != 64'h0000000000000054) $fatal(1, "output mismatch");
        if (state_word != 64'h0000000000000054) $fatal(1, "state mismatch");
        if (receipt_word != 64'h52544C50524F4F46) $fatal(1, "receipt mismatch");

        $display("abi=physical-compute-mmio/v1 rtl=iverilog link=physical-cartridge-link/v1 resolver=physical-cartridge-handle-resolver/v1");
        $display("identity=%08x capabilities=%08x", identity_value, capabilities_value);
        $display("ambiguous status=%08x result=refused", status_ambiguous);
        $display("reset status=%08x result=done receipt=valid", status_reset);
        $display("bad_descriptor status=%08x result=refused receipt=valid descriptor_word=%016x", status_bad_descriptor, 64'hBAD0BAD0BAD0BAD0);
        $display("memory_fault status=%08x result=fault receipt=valid descriptor=%016x", status_memory_fault, HANDLE_DESCRIPTOR_FAULT);
        $display("load status=%08x result=done receipt=valid descriptor=%016x input=%016x descriptor_word=%016x", status_load, HANDLE_DESCRIPTOR_GOOD, HANDLE_INPUT, last_descriptor_word);
        $display("evolve status=%08x result=done receipt=valid input_word=%016x output_word=%016x", status_evolve, last_input_word, output_word);
        $display("read status=%08x result=done receipt=valid output_word=%016x", status_read, output_word);
        $display("capture status=%08x result=done receipt=valid receipt_word=%016x", status_capture, receipt_word);
        $display("result=pass");
        $finish;
    end
endmodule
"""


def _bundle_sources() -> dict[str, str]:
    return {
        "physical-cartridge-link-v1.json": render_contract_json(),
        "ahead_reference_handle_resolver_v1.sv": render_resolver_systemverilog(),
        "ahead_reference_reversible_cartridge_v1.sv": render_cartridge_systemverilog(),
        "ahead_physical_compute_attachment_tb.sv": render_testbench_systemverilog(),
        "rtl-attachment.expected": EXPECTED_TRACE,
    }


def build_attachment_manifest() -> dict[str, Any]:
    contract = build_attachment_contract()
    sources = _bundle_sources()
    manifest: dict[str, Any] = {
        "schema_version": RTL_ATTACHMENT_MANIFEST_SCHEMA_VERSION,
        "artifact_type": "physical_compute_rtl_attachment_manifest",
        "portable_binding": PORTABLE_BINDING,
        "link_id": RTL_ATTACHMENT_LINK,
        "resolver_id": RTL_ATTACHMENT_RESOLVER,
        "abi_sha256": build_mmio_abi()["abi_sha256"],
        "contract_sha256": contract["contract_sha256"],
        "files": {
            name: {
                "sha256": sha256_text(content),
                "bytes": len(content.encode("utf-8")),
            }
            for name, content in sorted(sources.items())
        },
        "tool_floor": {
            "language": "SystemVerilog-2012",
            "reference_compiler": "iverilog",
            "reference_runtime": "vvp",
        },
        "qualification": {
            "status": "generated_unexecuted",
            "physical_claim_allowed": False,
            "blockers": [
                "RTL_COMPILATION_UNRUN",
                "RTL_EXECUTION_UNRUN",
                "CHIPYARD_SUBSYSTEM_ELABORATION_UNRUN",
                "PHYSICAL_SUBSTRATE_UNMEASURED",
                "COMPLETE_SYSTEM_EVP_UNMEASURED",
            ],
        },
        "claim_boundary": contract["claim_boundary"],
    }
    manifest["manifest_sha256"] = sha256_text(canonical_json(manifest))
    return manifest


def write_attachment_bundle(output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for name, content in _bundle_sources().items():
        path = root / name
        path.write_text(content, encoding="utf-8")
        outputs[name] = path
    manifest_path = root / "rtl-attachment-manifest.json"
    manifest_path.write_text(
        json.dumps(build_attachment_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    outputs["rtl-attachment-manifest.json"] = manifest_path
    return outputs


def parse_rtl_attachment_trace(trace: str) -> dict[str, Any]:
    lines = [line.strip() for line in trace.splitlines() if line.strip()]
    prefixes = (
        "abi=",
        "identity=",
        "ambiguous ",
        "reset ",
        "bad_descriptor ",
        "memory_fault ",
        "load ",
        "evolve ",
        "read ",
        "capture ",
        "result=",
    )
    positions: dict[str, int] = {}
    for prefix in prefixes:
        matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(
                f"RTL trace requires exactly one line beginning with {prefix!r}"
            )
        positions[prefix] = matches[0]
    if [positions[prefix] for prefix in prefixes] != sorted(positions.values()):
        raise ValueError("RTL attachment lifecycle lines are out of order")

    line = {prefix: lines[index] for prefix, index in positions.items()}
    checks = {
        "portable_binding": f"abi={PORTABLE_BINDING}" in line["abi="],
        "rtl_runtime": "rtl=iverilog" in line["abi="],
        "link_contract": f"link={RTL_ATTACHMENT_LINK}" in line["abi="],
        "resolver_contract": f"resolver={RTL_ATTACHMENT_RESOLVER}" in line["abi="],
        "identity": "identity=41504859" in line["identity="],
        "capabilities": "capabilities=00000009" in line["identity="],
        "ambiguous_refused_without_receipt": (
            "status=00000009" in line["ambiguous "]
            and "result=refused" in line["ambiguous "]
        ),
        "reset_done": (
            "status=00000025" in line["reset "]
            and "result=done" in line["reset "]
            and "receipt=valid" in line["reset "]
        ),
        "invalid_descriptor_refused": (
            "status=00000029" in line["bad_descriptor "]
            and "descriptor_word=bad0bad0bad0bad0" in line["bad_descriptor "]
        ),
        "resolver_fault_propagated": (
            "status=00000031" in line["memory_fault "]
            and "result=fault" in line["memory_fault "]
        ),
        "load_done": (
            "status=00000025" in line["load "]
            and "descriptor_word=a11ea11e00000001" in line["load "]
        ),
        "evolve_done": (
            "input_word=000000000000002a" in line["evolve "]
            and "output_word=0000000000000054" in line["evolve "]
        ),
        "read_done": "output_word=0000000000000054" in line["read "],
        "capture_done": "receipt_word=52544c50524f4f46" in line["capture "],
        "result_pass": line["result="] == "result=pass",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"RTL attachment semantic checks failed: {failed}")
    return {"line_count": len(lines), "checks": checks}


def _validate_manifest_files(
    manifest: Mapping[str, Any],
    bundle_dir: Path,
) -> None:
    expected_manifest = build_attachment_manifest()
    if manifest != expected_manifest:
        raise ValueError("RTL attachment manifest diverges from the generated contract")
    for name, record in manifest["files"].items():
        path = bundle_dir / name
        if not path.is_file():
            raise ValueError(f"RTL attachment bundle file is missing: {name}")
        payload = path.read_bytes()
        if sha256_bytes(payload) != record["sha256"]:
            raise ValueError(f"RTL attachment bundle file hash mismatch: {name}")
        if len(payload) != record["bytes"]:
            raise ValueError(f"RTL attachment bundle file size mismatch: {name}")


def build_rtl_attachment_proof(
    executable_path: str | Path,
    trace_path: str | Path,
    expected_trace_path: str | Path,
    manifest_path: str | Path,
    source_paths: Sequence[str | Path],
    *,
    iverilog_version: str,
    vvp_version: str,
) -> dict[str, Any]:
    executable = Path(executable_path).read_bytes()
    trace = Path(trace_path).read_bytes()
    expected = Path(expected_trace_path).read_bytes()
    if not executable:
        raise ValueError("RTL executable is empty")
    if trace != expected:
        raise ValueError("RTL attachment trace diverges from the accepted trace")
    if not iverilog_version.strip() or not vvp_version.strip():
        raise ValueError("Icarus compiler and runtime versions are required")

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("RTL attachment manifest must be a JSON object")
    _validate_manifest_files(manifest, manifest_file.parent)

    observations = parse_rtl_attachment_trace(trace.decode("utf-8"))
    source_records: dict[str, dict[str, Any]] = {}
    for raw_path in source_paths:
        path = Path(raw_path)
        payload = path.read_bytes()
        if not payload:
            raise ValueError(f"RTL source is empty: {path}")
        source_records[path.name] = {
            "sha256": sha256_bytes(payload),
            "bytes": len(payload),
        }
    required_sources = {
        "ahead_physical_compute_mmio_v1.sv",
        "ahead_reference_handle_resolver_v1.sv",
        "ahead_reference_reversible_cartridge_v1.sv",
        "ahead_physical_compute_attachment_tb.sv",
    }
    if set(source_records) != required_sources:
        raise ValueError(
            "RTL proof requires exactly the MMIO, resolver, cartridge, and testbench sources"
        )

    proof: dict[str, Any] = {
        "schema_version": RTL_ATTACHMENT_PROOF_SCHEMA_VERSION,
        "artifact_type": "physical_compute_rtl_attachment_execution_proof",
        "portable_binding": PORTABLE_BINDING,
        "link_id": RTL_ATTACHMENT_LINK,
        "resolver_id": RTL_ATTACHMENT_RESOLVER,
        "execution": {
            "language": "SystemVerilog-2012",
            "compiler": _first_line(iverilog_version),
            "runtime": _first_line(vvp_version),
            "test_class": "mmio_bridge_handle_resolver_and_replaceable_cartridge",
        },
        "artifacts": {
            "abi_sha256": build_mmio_abi()["abi_sha256"],
            "contract_sha256": build_attachment_contract()["contract_sha256"],
            "manifest_sha256": manifest["manifest_sha256"],
            "manifest_file_sha256": sha256_bytes(manifest_file.read_bytes()),
            "executable_sha256": sha256_bytes(executable),
            "executable_bytes": len(executable),
            "trace_sha256": sha256_bytes(trace),
            "expected_trace_sha256": sha256_bytes(expected),
            "sources": dict(sorted(source_records.items())),
        },
        "observations": observations,
        "qualification": {
            "status": "rtl_attachment_execution_proved",
            "accepted": True,
            "chipyard_subsystem_claim_allowed": False,
            "physical_claim_allowed": False,
            "complete_system_advantage_claim_allowed": False,
            "blockers": [
                "CHIPYARD_SUBSYSTEM_ELABORATION_UNRUN",
                "FPGA_OR_SILICON_EXECUTION_UNRUN",
                "PHYSICAL_SUBSTRATE_UNMEASURED",
                "PHYSICAL_ENERGY_UNMEASURED",
                "TIMING_THERMAL_VOLUME_UNMEASURED",
                "COMPLETE_SYSTEM_EVP_UNMEASURED",
                "INDEPENDENT_PHYSICAL_ACCEPTANCE_MISSING",
            ],
        },
        "claim_boundary": (
            "The proof establishes that generated SystemVerilog MMIO, an independent "
            "opaque-handle resolver, and a replaceable cartridge compiled and executed "
            "under Icarus Verilog, reproduced the accepted admission, refusal, fault, "
            "load, evolve, read, capture, and receipt trace, and retained software "
            "fallback authority. It does not establish Chipyard subsystem elaboration, "
            "FPGA or silicon execution, physical substrate work, measured EVP, "
            "fabrication, or independent physical acceptance."
        ),
        "control_question": (
            "Can the same accepted RTL trace survive replacement of the host bridge, "
            "resolver, or cartridge without changing command, refusal, fault, state, "
            "fallback, or receipt semantics?"
        ),
    }
    proof["proof_sha256"] = sha256_text(canonical_json(proof))
    return proof


def build_rtl_attachment_proof_from_tools(
    executable_path: str | Path,
    trace_path: str | Path,
    expected_trace_path: str | Path,
    manifest_path: str | Path,
    source_paths: Sequence[str | Path],
    *,
    iverilog: str = "iverilog",
    vvp: str = "vvp",
) -> dict[str, Any]:
    return build_rtl_attachment_proof(
        executable_path,
        trace_path,
        expected_trace_path,
        manifest_path,
        source_paths,
        iverilog_version=command_version(iverilog),
        vvp_version=command_version(vvp),
    )


def write_rtl_attachment_proof(
    output_path: str | Path,
    proof: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
