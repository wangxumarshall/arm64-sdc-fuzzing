#!/usr/bin/env python
"""Debug script to check LDSMAX instruction loading with detailed error."""

import sys
import logging
logging.basicConfig(level=logging.DEBUG)

sys.path.insert(0, 'microprobe/src')

from microprobe.target import import_definition

try:
    target = import_definition('armv8_common-armv8_common-aarch64_linux_gcc')
    print(f'Total instructions: {len(target.isa.instructions)}')
    
    # 检查 LDSMAX 是否存在
    ldsmax = target.isa.instructions.get('LDSMAX_X_V0')
    print(f'\nLDSMAX_X_V0: {ldsmax}')
    
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'Error: {e}')
