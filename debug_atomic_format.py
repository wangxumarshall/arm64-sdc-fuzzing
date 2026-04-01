#!/usr/bin/env python
"""Debug script to check ATOMIC format fields."""

import sys
import logging
logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, 'microprobe/src')

from microprobe.target import import_definition

target = import_definition('armv8_common-armv8_common-aarch64_linux_gcc')

# 检查 ATOMIC 格式的字段
atomic_format = None
for name, instr in target.isa.instructions.items():
    if instr.format.name == 'ATOMIC':
        atomic_format = instr.format
        break

if atomic_format:
    print('ATOMIC format fields:')
    for field in atomic_format.fields:
        print(f'  {field.name}: default_operand={field.default_operand}, default_io={field.default_io}')
else:
    print('ATOMIC format not found')

# 检查 LDADD 指令
ldadd = target.isa.instructions.get('LDADD_X_V0')
if ldadd:
    print(f'\nLDADD_X_V0 operands:')
    for name, operand in ldadd.operands.items():
        print(f'  {name}: {operand[0].name}, {operand[1]}')
