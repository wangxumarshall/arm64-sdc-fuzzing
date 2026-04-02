#!/usr/bin/env python
"""Debug script to check LDSMAX instruction loading with detailed error."""

import sys
import logging
logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, 'microprobe/src')

from microprobe.target.isa import register as register_mod
from microprobe.target.isa import register_type as register_type_mod
from microprobe.target.isa import instruction_field as ifield_mod
from microprobe.target.isa import instruction_format as iformat_mod
from microprobe.target.isa import instruction as instruction_mod
from microprobe.target.isa import operand as operand_mod
from microprobe.utils.yaml import read_yaml
from microprobe.target.isa.instruction import SCHEMA as INSTR_SCHEMA
from microprobe.target.isa.instruction import _merge_operands

# 导入寄存器类型
regtypes = register_type_mod.import_definition(
    None,
    ['microprobe/targets/arm64/isa/armv8-common/register_type.yaml'],
    None
)
print(f'Loaded {len(regtypes)} register types')

# 导入寄存器
regs = register_mod.import_definition(
    None,
    ['microprobe/targets/arm64/isa/armv8-common/register.yaml'],
    regtypes
)
print(f'Loaded {len(regs)} registers')

# 导入操作数
ops = operand_mod.import_definition(
    None,
    ['microprobe/targets/arm64/isa/armv8-common/operand.yaml'],
    regs
)
print(f'Loaded {len(ops)} operands')

# 导入指令字段
ifields = ifield_mod.import_definition(
    None,
    ['microprobe/targets/arm64/isa/armv8-common/instruction_field.yaml'],
    ops
)
print(f'Loaded {len(ifields)} instruction fields')

# 导入指令格式
iformats = iformat_mod.import_definition(
    None,
    ['microprobe/targets/arm64/isa/armv8-common/instruction_format.yaml'],
    ifields
)
print(f'Loaded {len(iformats)} instruction formats')

# 尝试加载 LDSMAX
data = read_yaml('microprobe/targets/arm64/isa/armv8-common/instruction_props/atomic.yaml', INSTR_SCHEMA)
print(f'\nLDSMAX instruction data:')
for item in data:
    if item.get('Name') == 'LDSMAX_X_V0':
        print(f'  Name: {item.get("Name")}')
        print(f'  Format: {item.get("Format")}')
        print(f'  Operands: {item.get("Operands")}')
        
        # 检查格式是否存在
        if item.get('Format') in iformats:
            fmt = iformats[item.get('Format')]
            print(f'  Format fields: {[f.name for f in fmt.fields]}')
            
            # 尝试合并操作数
            try:
                operands = _merge_operands(
                    item.get('Name'),
                    'atomic.yaml',
                    item.get('Operands', {}),
                    fmt,
                    ops
                )
                print(f'  Merged operands: {list(operands.keys())}')
            except Exception as e:
                print(f'  Error merging operands: {e}')
                import traceback
                traceback.print_exc()
        break

# 对比 LDADD
print(f'\nLDADD instruction data:')
for item in data:
    if item.get('Name') == 'LDADD_X_V0':
        print(f'  Name: {item.get("Name")}')
        print(f'  Format: {item.get("Format")}')
        print(f'  Operands: {item.get("Operands")}')
        
        if item.get('Format') in iformats:
            fmt = iformats[item.get('Format')]
            print(f'  Format fields: {[f.name for f in fmt.fields]}')
            
            try:
                operands = _merge_operands(
                    item.get('Name'),
                    'atomic.yaml',
                    item.get('Operands', {}),
                    fmt,
                    ops
                )
                print(f'  Merged operands: {list(operands.keys())}')
            except Exception as e:
                print(f'  Error merging operands: {e}')
                import traceback
                traceback.print_exc()
        break
