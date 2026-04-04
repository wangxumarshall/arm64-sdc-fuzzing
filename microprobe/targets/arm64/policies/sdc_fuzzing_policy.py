# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""ARM64 SDC fuzzing policy tuned for Kunpeng920-style stress patterns."""

from __future__ import absolute_import, print_function

import microprobe.code
import microprobe.passes.address
import microprobe.passes.branch
import microprobe.passes.initialization
import microprobe.passes.instruction
import microprobe.passes.memory
import microprobe.passes.register
import microprobe.passes.structure
import microprobe.passes.sdc_analysis
from microprobe.exceptions import MicroprobePolicyError
from microprobe.utils.logger import get_logger
from microprobe.utils.misc import RND, RNDINT

__all__ = [
    "NAME",
    "DESCRIPTION",
    "SUPPORTED_TARGETS",
    "SDCSensitiveAnalyzer",
    "policy",
]

NAME = "sdc_fuzzing"
DESCRIPTION = "Static-score-first SDC fuzzing policy for ARM64"
SUPPORTED_TARGETS = ["all"]

LOG = get_logger(__name__)


def _target_looks_like_arm64(target):
    registers = getattr(target, "registers", {})
    return all(reg in registers for reg in ["X0", "SP", "V0", "LR"])


class SDCSensitiveAnalyzer(object):
    """Pick ARM64 instructions that are more likely to expose silent faults."""

    _SIM_SAFE_MNEMONICS = {
        "MOVZ", "MOVK", "MOVN",                 # Move
        "ADD", "SUB", "CMP", "CMN",             # Arithmetic
        "AND", "ORR", "EOR", "TST",             # Logical
        "LSL", "LSR", "ASR", "ROR",              # Shift
        "LDUR", "STUR", "LDR", "STR",            # Single register memory
        "B", "BL", "BEQ", "BNE", "BGT", "BLT",  # Branch
        "NOP",                                   # No-op
    }

    _HW_AGGRESSIVE_MNEMONICS = {
        "FMADD", "FMSUB", "FMLA", "FMLS",
        "LDP", "STP",
        "CAS", "CASA", "CASAL", "CASL",
        "LDADD", "LDADDA", "LDADDAL", "LDADDL",
        "LDCLR", "LDCLRA", "LDCLRAL", "LDCLRL",
        "LDSET", "LDSETA", "LDSETAL", "LDSETL",
        "SWP", "SWPA", "SWPAL", "SWPL",
        "LDAR", "STLR", "LDXR", "STXR", "LDAXR", "STLXR",
        "LD1", "ST1", "LD1R",
        "CRC32B", "CRC32H", "CRC32W", "CRC32X",
    }

    def __init__(self, target):
        self._target = target

    def collect(self, profile_name="SIM_SAFE"):
        instructions = list(self._target.isa.instructions.values())
        allowed = []
        normalized_profile = str(profile_name).strip().upper()
        aggressive = normalized_profile == "HW_AGGRESSIVE"
        selected_mnemonics = set(self._SIM_SAFE_MNEMONICS)
        if aggressive:
            selected_mnemonics |= self._HW_AGGRESSIVE_MNEMONICS

        for instr in instructions:
            mnemonic = instr.mnemonic.upper()
            if mnemonic in selected_mnemonics:
                allowed.append(instr)

        # Sort by name for deterministic ordering
        allowed.sort(key=lambda instr: instr.name)
        return allowed

    def default_sequence(self, limit=8, profile_name="SIM_SAFE"):
        sensitive = self.collect(profile_name=profile_name)
        if not sensitive:
            raise MicroprobePolicyError(
                "No ARM64 SDC-sensitive instructions were found in the target ISA"
            )

        if len(sensitive) >= limit:
            return sensitive[:limit]

        sequence = []
        while len(sequence) < limit:
            sequence.extend(sensitive)
        return sequence[:limit]


def policy(target, wrapper, **kwargs):
    """Compose a Microprobe synthesizer for ARM64 SDC fuzzing."""

    if not _target_looks_like_arm64(target):
        raise MicroprobePolicyError(
            f"Policy '{NAME}' not valid for target '{target.name}'. "
            "Expected an ARM64/AArch64 target with X/V register files."
        )

    benchmark_size = kwargs.get("benchmark_size", 64)
    dependency_distance = kwargs.get("dependency_distance", 1)
    memory_stream_size = kwargs.get("memory_stream_size", 32)
    memory_stream_stride = kwargs.get("memory_stream_stride", 8192)

    instructions = kwargs.get("instructions")
    if instructions is None:
        if "instruction" in kwargs:
            instructions = [kwargs["instruction"]]
        else:
            analyzer = SDCSensitiveAnalyzer(target)
            instructions = analyzer.default_sequence(
                limit=kwargs.get("sequence_length", 8),
                profile_name=kwargs.get("profile_name", "SIM_SAFE"),
            )

    synthesizer = microprobe.code.Synthesizer(target, wrapper, value=RNDINT)

    synthesizer.add_pass(
        microprobe.passes.initialization.InitializeRegistersPass(value=RNDINT)
    )
    synthesizer.add_pass(
        microprobe.passes.initialization.InitializeRegistersPass()
    )
    synthesizer.add_pass(
        microprobe.passes.structure.SimpleBuildingBlockPass(benchmark_size)
    )
    synthesizer.add_pass(
        microprobe.passes.instruction.SetInstructionTypeBySequencePass(
            instructions
        )
    )
    synthesizer.add_pass(microprobe.passes.address.UpdateInstructionAddressesPass())

    if dependency_distance < 1:
        synthesizer.add_pass(microprobe.passes.register.NoHazardsAllocationPass())

    synthesizer.add_pass(
        microprobe.passes.register.DefaultRegisterAllocationPass(
            RND, dd=dependency_distance
        )
    )
    synthesizer.add_pass(microprobe.passes.address.UpdateInstructionAddressesPass())
    synthesizer.add_pass(microprobe.passes.sdc_analysis.StaticACECalculatorPass())
    synthesizer.add_pass(microprobe.passes.sdc_analysis.StaticIBRCoveragePass())
    synthesizer.add_pass(
        microprobe.passes.sdc_analysis.Kunpeng920MemoryPressurePass()
    )
    synthesizer.add_pass(
        microprobe.passes.sdc_analysis.CapstoneValidationPass(
            strict=kwargs.get("strict_validation", False)
        )
    )

    return synthesizer
