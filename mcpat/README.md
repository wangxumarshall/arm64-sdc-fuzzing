### McPAT 1.3 Modified.

Kunpeng920 one-stop flow
========================

This repository supports exactly two Kunpeng920 calibration modes:

1. Manual explicit calibration
2. Automatic calibration

The overall workflow is:

1. Collect real-hardware counters on Kunpeng920
2. Build or auto-synthesize `kunpeng920_calibration.json`
3. Run `pypat` or `run_mcpat.sh` with the calibrated profile

One-shot batch collection
-------------------------

Use the provided matrix runner to collect a standard workload set:

```bash
sudo mcpat/tools/collect_kunpeng920_matrix.sh \
  --out-dir artifacts/kunpeng920-runs \
  --matrix-file mcpat/tools/kunpeng920_collection_matrix.tsv
```

Each matrix row calls:

```bash
sudo mcpat/tools/collect_kunpeng920_counters.sh \
  --out-dir artifacts/kunpeng920-runs/<workload> \
  --label "<label>" \
  --perf-events "<perf events>" \
  --cmd "<workload command>"
```

Manual explicit calibration
---------------------------

Generate the calibration JSON explicitly:

```bash
python3 mcpat/tools/build_kunpeng920_calibration.py \
  artifacts/kunpeng920-runs \
  -o artifacts/kunpeng920-runs/kunpeng920_calibration.json
```

Then run `pypat` with that file:

```bash
python3 -m pypat /path/to/m5out \
  --template-profile arm64-kunpeng920 \
  --calibration-file artifacts/kunpeng920-runs/kunpeng920_calibration.json
```

Or through the legacy wrapper:

```bash
cd mcpat
MCPAT_TEMPLATE_PROFILE=arm64-kunpeng920 \
MCPAT_KUNPENG920_CALIBRATION=../artifacts/kunpeng920-runs/kunpeng920_calibration.json \
bash run_mcpat.sh 2 0 McPAT_out
```

Automatic calibration
---------------------

Skip manual JSON generation and let runtime synthesize it from the dataset:

```bash
python3 -m pypat /path/to/m5out \
  --template-profile arm64-kunpeng920 \
  --calibration-dataset artifacts/kunpeng920-runs
```

Or:

```bash
cd mcpat
MCPAT_TEMPLATE_PROFILE=arm64-kunpeng920 \
MCPAT_KUNPENG920_CALIBRATION_DATASET=../artifacts/kunpeng920-runs \
bash run_mcpat.sh 2 0 McPAT_out
```

What gets calibrated
--------------------

The calibration flow currently fits the Kunpeng920 custom-block fields:

- `custom_hccs_*`
- `custom_hpre_*`
- `custom_sec_*`
- `custom_zip_*`

Where:

- `switch_energy` is fitted from workload power delta and observed operations
- `static_power` can be fitted when dedicated idle-tagged samples exist
- `area` is injected from optional `area_overrides.json`

Supporting references:

- [docs/kunpeng920_support.md](docs/kunpeng920_support.md)
- [docs/kunpeng920_real_hardware_collection.md](docs/kunpeng920_real_hardware_collection.md)
- [pypat/README.md](pypat/README.md)
- [gem5_mcpat_parser/README](gem5_mcpat_parser/README)

What's modified?

1. Initialization phase and computation phase are decoupled.
   
   - Initialization of a processor is done directly in the instantiation of it.
   
   - Area computing is left unchanged in initialization (a chip is just a chip, not a transformer)
   
   - Power computing is picked out into a new function, `compute`.

2. Consecutive simulation is enabled.
   
   - Modified McPAT can initialize for just once and keep computing new power stats upon new XML files.

3. **2025.2.10** Output Format is Modified for Hotspot
   
   All power breakdowns are summarized. 

4. **2025.2.11** Interface for Custom Blocks.
   
   A very simple interface added. You can see two new files "custom_block.cc" & "custom_block.h", which contains a very simple definition. An example is instantiated as "CIM_SRAM" under "processor" at "processor.h" & "processor.cc".
   
   

How to use?

- The command of original McPAT is **still supported**.
  
  ```shell
  mcpat -infile <name> -print_level <0~5> -opt_for_clk <0/1>
  ```

- To enable consecutive simulation, use command `-trace`.
  
  So the command becomes:
  
  ```shell
  mcpat -trace -infile <name> -print_level <0~5> -opt_for_clk <0/1>
  ```
  
  After simulating upon the initial XML file, McPAT waits for you to input a new filename. This continues until you input "exit" and ends the program.
  
  If you input "repeat", McPAT computes upon the last XML interface.

- Cutsom Blocks
  
  Now, you can already see the power stat of "CIM_SRAM" whatever benchmark you're using (but the value is crazy, since the detailed computation is not specified).
  
  To write a more realistic computation for it, you have to read three parts:
  
  1. The simple definition in "custom_block.h".
  
  2. The instantiation of it in "processor.h".
  
  3. The calculation for it in "processor.cc". It's at the beginning of `void Processor::compute(ParseXML *fresh_XML)`. 



