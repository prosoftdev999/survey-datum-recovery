# Survey datum recovery

The office reduction for the earlier monitoring campaigns has already been signed off. Its accepted control state is in `/app/data/control_handoff.json`; the older field records remain beside it for provenance and do not need to be reduced again.

The work starts with the low-coherence carrier handoff. The `carrier_*.csv` files and `/app/data/carrier_model.txt` contain the surviving observations. The recorder kept temporary target tags and continuous lock-arc IDs, but lost the stable target assignment and integer cycle origins. Recover the joint fixed solution for that campaign, the distinct runner-up, and the total displacement of each monument at the final carrier epoch. The final epoch is the row of `carrier_epochs.csv` with the largest `elapsed_day`.

A closing resection was recorded immediately after that campaign. Its thermometer checks, circle and range references, state seeds, setup register, model sheets, field observations, and reduction note are also in `/app/data`. Reduce the closing archive against the carrier-final monument positions. The selected angle model, range model, circle-sense crosswalk, temporary-target assignment, and both setup reductions must belong to one common minimum-closure solution. The runner-up closure is the next distinct target-assignment/sense solution after refitting both setup transforms.

Write `/app/output.json` with exactly two top-level fields.

`carrier_reconstruction` must contain:
- `final_epoch_id`;
- `target_mapping` and `runner_up_target_mapping`, each mapping every temporary target tag in `carrier_arcs.csv` to one of the six monument IDs in the control handoff;
- `ambiguities` and `runner_up_ambiguities`, each keyed by every `arc_id` in `carrier_arcs.csv`, with integer cycle origins;
- numeric `fixed_weighted_ss`, `runner_up_weighted_ss`, and `ambiguity_gap = runner_up_weighted_ss - fixed_weighted_ss`;
- `final_total_displacements`, containing all six monument IDs with numeric `d_east_m` and `d_north_m` values in metres.

`closing_resection` must contain:
- `angle_model_code` and `range_model_code` using the codes in the two model-sheet files;
- numeric `angle_weighted_ss` and `range_weighted_ss`;
- `circle_sense`, mapping both setup sense codes to integer `+1` or `-1`;
- `target_mapping`, mapping every temporary X-tag to one monument ID;
- `setups`, containing `S3` and `S8`, each with numeric `east_m`, `north_m`, `orientation_rad`, and `rms_m`;
- numeric `interstation_baseline_m`, `interstation_azimuth_rad`, `closure_rms_m`, and `runner_up_closure_rms_m`.

Carrier ambiguity integers and both carrier mappings must match exactly. Carrier weighted sums and their gap have tolerance 0.05, and carrier total displacement components have tolerance 0.022 m. For the closing resection, angle and range weighted sums have tolerances 0.75 and 0.30 respectively; setup east/north coordinates have tolerance 0.010 m, setup orientations 0.00012 rad, setup RMS values 0.0010 m, interstation baseline 0.015 m, interstation azimuth 0.00012 rad, closing RMS 0.0010 m, and runner-up closing RMS 0.050 m. Model codes, circle-sense values, and the closing target assignment must match exactly.

Angular orientation and azimuth values are periodic, so values differing by an integer multiple of 2*pi are equivalent. Each setup `rms_m` is `sqrt(mean(dx^2 + dy^2))` over that setup's target observations; the two closure RMS fields use the same Cartesian-vector convention over all closing observations. JSON key order is not significant.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
