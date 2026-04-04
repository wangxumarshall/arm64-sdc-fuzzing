# pypat Integration

This directory adapts the workflow from
`https://github.com/alexmanle/pypat.git` into this repository without
duplicating McPAT's C++ source tree.

What it adds:

- Read gem5 `config.json`
- Read gem5 `stats.txt` or `stats.h5`
- Render an McPAT XML input file
- Invoke the local `./mcpat` binary
- Provide optional helpers for searching HDF5 stats and merging results

Basic usage:

```bash
python3 -m pypat /path/to/m5out
```

Useful options:

```bash
python3 -m pypat /path/to/m5out \
  --template gem5_mcpat_parser/template_x86.xml \
  --outfile /path/to/m5out/conv.xml \
  --print-level 2 \
  --opt-for-clk 0
```

ARM64 / Kunpeng920-like template selection:

```bash
python3 -m pypat /path/to/m5out \
  --template-profile arm64-kunpeng920 \
  --outfile /path/to/m5out/conv.xml
```

Dependencies:

- Python 3
- `h5py` for `.h5` input support

The default template path is the repository's existing
`gem5_mcpat_parser/template_x86.xml`, so this wrapper and the older
`run_mcpat.sh` flow can share the same template base.

Kunpeng920 notes:

- `arm64-kunpeng920` now carries explicit topology fields for L3 slices, NoCs,
  memory channels, and controller blocks.
- Kunpeng920-specific custom blocks for HCCS, HPRE, SEC, and ZIP are emitted in
  the XML template so accelerator/coherency modeling is no longer invisible.
- Derived McPAT counters are recorded with provenance in the normalized
  Kunpeng920 model so fallback/aggregated values are visible.
- The wrapper now treats common fatal McPAT log lines as hard failures even if
  the legacy binary exits with status `0`.
- Architectural support status and remaining approximations are documented in
  `docs/kunpeng920_support.md`.
