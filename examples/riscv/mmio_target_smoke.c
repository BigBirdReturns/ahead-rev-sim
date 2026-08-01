#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "ahead_physical_compute_mmio_v1.h"

typedef struct target_model {
    ahead_phys_mmio_v1_t regs;
} target_model_t;

static int command_is_onehot_supported(uint32_t command)
{
    const uint32_t supported =
        AHEAD_PHYS_CMD_RESET |
        AHEAD_PHYS_CMD_LOAD |
        AHEAD_PHYS_CMD_EVOLVE |
        AHEAD_PHYS_CMD_READ |
        AHEAD_PHYS_CMD_CAPTURE;
    return command != 0u &&
           (command & (command - 1u)) == 0u &&
           (command & ~supported) == 0u;
}

static int pointer_requirements_met(const target_model_t *model, uint32_t command)
{
    const uint64_t descriptor = ahead_phys_read_ptr(
        &model->regs.descriptor_ptr_lo,
        &model->regs.descriptor_ptr_hi);
    const uint64_t input = ahead_phys_read_ptr(
        &model->regs.input_queue_ptr_lo,
        &model->regs.input_queue_ptr_hi);
    const uint64_t output = ahead_phys_read_ptr(
        &model->regs.output_queue_ptr_lo,
        &model->regs.output_queue_ptr_hi);
    const uint64_t receipt = ahead_phys_read_ptr(
        &model->regs.receipt_ptr_lo,
        &model->regs.receipt_ptr_hi);

    switch (command) {
    case AHEAD_PHYS_CMD_RESET:
        return 1;
    case AHEAD_PHYS_CMD_LOAD:
        return descriptor != 0u && input != 0u;
    case AHEAD_PHYS_CMD_EVOLVE:
        return input != 0u && output != 0u;
    case AHEAD_PHYS_CMD_READ:
        return output != 0u;
    case AHEAD_PHYS_CMD_CAPTURE:
        return receipt != 0u;
    default:
        return 0;
    }
}

static void model_reset(target_model_t *model)
{
    memset(model, 0, sizeof(*model));
    model->regs.identity = UINT32_C(0x41504859);
    model->regs.capabilities =
        AHEAD_PHYS_CAP_EXACT |
        AHEAD_PHYS_CAP_SOFTWARE_FALLBACK;
    model->regs.status = AHEAD_PHYS_STATUS_READY;
}

static void model_submit(target_model_t *model)
{
    const uint32_t command = model->regs.command;
    if (!command_is_onehot_supported(command) ||
        !pointer_requirements_met(model, command)) {
        model->regs.status =
            AHEAD_PHYS_STATUS_READY |
            AHEAD_PHYS_STATUS_REFUSED;
        return;
    }

    model->regs.status = AHEAD_PHYS_STATUS_BUSY;

    /*
     * This independent C implementation closes the RISC-V host lifecycle through
     * the software fallback. It does not stand in for Chipyard RTL or a physical
     * substrate.
     */
    model->regs.status =
        AHEAD_PHYS_STATUS_READY |
        AHEAD_PHYS_STATUS_DONE |
        AHEAD_PHYS_STATUS_RECEIPT_VALID;
}

static int require_status(uint32_t status, uint32_t mask)
{
    return (status & mask) == mask;
}

int main(void)
{
    target_model_t model;
    model_reset(&model);

    printf("abi=%s isa=rv64gc\n", AHEAD_PHYS_MMIO_BINDING);
    printf(
        "identity=%08" PRIx32 " capabilities=%08" PRIx32 "\n",
        model.regs.identity,
        model.regs.capabilities);

    model.regs.command = AHEAD_PHYS_CMD_RESET | AHEAD_PHYS_CMD_READ;
    model_submit(&model);
    printf(
        "ambiguous status=%08" PRIx32 " result=refused\n",
        model.regs.status);
    if (!require_status(
            model.regs.status,
            AHEAD_PHYS_STATUS_READY | AHEAD_PHYS_STATUS_REFUSED)) {
        return 10;
    }

    model.regs.command = AHEAD_PHYS_CMD_RESET;
    model_submit(&model);
    printf(
        "reset status=%08" PRIx32 " result=done receipt=valid\n",
        model.regs.status);
    if (!require_status(
            model.regs.status,
            AHEAD_PHYS_STATUS_READY |
                AHEAD_PHYS_STATUS_DONE |
                AHEAD_PHYS_STATUS_RECEIPT_VALID)) {
        return 11;
    }

    ahead_phys_write_ptr(
        &model.regs.descriptor_ptr_lo,
        &model.regs.descriptor_ptr_hi,
        UINT64_C(0x0000000010001000));
    ahead_phys_write_ptr(
        &model.regs.input_queue_ptr_lo,
        &model.regs.input_queue_ptr_hi,
        UINT64_C(0x0000000010002000));
    ahead_phys_write_ptr(
        &model.regs.output_queue_ptr_lo,
        &model.regs.output_queue_ptr_hi,
        UINT64_C(0x0000000010003000));
    ahead_phys_write_ptr(
        &model.regs.receipt_ptr_lo,
        &model.regs.receipt_ptr_hi,
        UINT64_C(0x0000000010004000));

    model.regs.command = AHEAD_PHYS_CMD_LOAD;
    model_submit(&model);
    printf(
        "load status=%08" PRIx32
        " result=done receipt=valid descriptor=%016" PRIx64
        " input=%016" PRIx64 "\n",
        model.regs.status,
        ahead_phys_read_ptr(
            &model.regs.descriptor_ptr_lo,
            &model.regs.descriptor_ptr_hi),
        ahead_phys_read_ptr(
            &model.regs.input_queue_ptr_lo,
            &model.regs.input_queue_ptr_hi));
    if (!require_status(
            model.regs.status,
            AHEAD_PHYS_STATUS_READY |
                AHEAD_PHYS_STATUS_DONE |
                AHEAD_PHYS_STATUS_RECEIPT_VALID)) {
        return 12;
    }

    printf("result=pass\n");
    return 0;
}
