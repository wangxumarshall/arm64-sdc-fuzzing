from sdc_agent.phase2_validation import render_semihost_validation_source


def test_render_semihost_validation_source_uses_defined_state_harness():
    source = render_semihost_validation_source("mov x0, x1\nfmov d0, d1", "phase2-seed")

    assert "Phase2 validation source for phase2-seed" in source
    assert "static void sdc_prepare_memory(void)" in source
    assert "static uint8_t sdc_memory[8192]" in source
    assert "str x30, [x16, #240]" in source
    assert "adrp x18, sdc_memory" in source
