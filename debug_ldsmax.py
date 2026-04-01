#!/usr/bin/env python
"""Debug script to check LDSMAX instruction loading with detailed error."""

import sys
import logging
logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, 'microprobe/src')

from microprobe.target import import_definition

try:
    target = import_definition('armv8_common-armv8_common-aarch64_linux_gcc')
    print(f'Total instructions: {len(target.isa.instructions)}')
    
    # 检查所有 atomic 相关指令
    atomic_instrs = [name for name in target.isa.instructions.keys() 
                     if 'LDADD' in name or 'CAS_' in name or 'SWP_' in name 
                     or 'LDSMAX' in name or 'LDSMIN' in name or 'LDUMAX' in name 
                     or 'LDUMIN' in name or 'LDSET' in name or 'LDEOR' in name
                     or 'LDOR' in name or 'LDAND' in name]
    print(f'Atomic instructions found: {len(atomic_instrs)}')
    for name in sorted(atomic_instrs):
        instr = target.isa.instructions.get(name)
        print(f'  {name}: format={instr.format.name}')
    
    # 检查 LDSMAX 是否存在
    ldsmax = target.isa.instructions.get('LDSMAX_X_V0')
    print(f'\nLDSMAX_X_V0: {ldsmax}')
    
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'Error: {e}')
