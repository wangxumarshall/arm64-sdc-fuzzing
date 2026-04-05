# Kunpeng920 Support Status

## Summary

This repository now supports Kunpeng920-oriented McPAT runs through both of the
paths used in the project:

- `gem5 -> pypat -> McPAT`
- hand-authored or externally generated McPAT XML based on
  `template_arm64_kunpeng920.xml`

The support is engineered to be structurally faithful to the public
Kunpeng920/TaiShan V110 description while remaining explicit about the parts
that McPAT still approximates.

## Modeled Directly

- 64 homogeneous ARMv8.2-A OoO cores
- 4 cores per cluster, 16 clusters total
- private 512 KiB L2 per core
- 16 homogeneous L3 slices derived from a 64 MiB LLC
- 2 homogeneous NoCs representing the 2 compute dies
- 8 DDR4-2933 channels represented as 2 memory controllers with 4 channels each
- PCIe and NIU/RoCE controller blocks exposed through the McPAT XML interface
- explicit custom-block placeholders for HCCS, HPRE, SEC, and ZIP accelerators

## Explicit Approximations

- TaiShan V110 execution resources are mapped onto McPAT's generic OoO core
  model; this is structural, not silicon-calibrated.
- Kunpeng920's bufferless dual-ring/mesh interconnect is approximated as a
  homogeneous `2d-mesh` NoC with explicit node geometry and chip coverage.
- Die-to-die coherence, HCCS details, hardware accelerators, and RoCE traffic
  behavior are represented as McPAT-visible topology/controller/custom-block
  parameters, not cycle-accurate micro-models.
- The Kunpeng-specific custom blocks default to zero static/dynamic contribution
  until calibrated values are provided through the profile or an external XML.
- McPAT technology remains driven by the repository's available 22 nm McPAT
  technology tables even though the public Kunpeng920 implementation is 7 nm +
  16 nm chiplet-based silicon.

## Validation

Current regression coverage lives in:

- `mcpat/tests/test_arm64_kunpeng920_model.py`
- `mcpat/tests/test_arm64_kunpeng920_conversion.py`

The tests verify:

- topology/profile derivation
- XML emission for Kunpeng920 NoC/L3 parameters
- stats provenance for derived McPAT counters
- end-to-end execution of the local `mcpat` binary
- wrapper detection of fatal McPAT log output even when the binary exits with
  status `0`

## Debugging Notes

- `pypat` now records derived-stat provenance in the normalized Kunpeng920 model
  so it is clear which outputs came from direct gem5 stats and which came from
  fallback/aggregated inference.
- Kunpeng920 custom blocks are parsed generically, so additional named custom
  blocks can be appended after the fixed `flashc` section in the XML template.
- `pypat` can now auto-apply Kunpeng920 calibration overrides from either an
  existing `kunpeng920_calibration.json` or a raw collection dataset directory.
- `pypat` treats common McPAT fatal log patterns as hard failures even when the
  legacy McPAT binary reports success via exit code `0`.
- The C++ side now emits more specific hierarchy and topology mismatch messages
  for private L2, L3, NoC, and controller-order parsing failures.
