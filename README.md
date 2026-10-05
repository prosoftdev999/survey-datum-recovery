# Survey Datum Recovery

A scientific-computing and surveying reconstruction project focused on recovering a monitoring datum from incomplete carrier observations and reducing a coupled closing resection.

The task combines target-identity recovery, integer ambiguity resolution, deformation estimation, instrument calibration, and two-setup geometric resection into one continuous numerical workflow.

## Overview

The project represents a survey-monitoring handoff in which earlier control work has already been accepted, but part of the later observation history has lost important identity and ambiguity information.

The reconstruction has two connected stages:

```text
accepted control state
        ↓
carrier observation recovery
        ↓
target assignment
        ↓
integer cycle ambiguity resolution
        ↓
final monument displacements
        ↓
closing resection
        ↓
instrument/model calibration
        ↓
two-setup coordinate solution
        ↓
closure assessment
```

The second stage depends on the monument geometry recovered by the first stage, so the two problems cannot be treated as unrelated calculations.

## Repository Structure

```text
survey-datum-recovery/
├── cheat/
├── environment/
├── solution/
├── tests/
├── instruction.md
└── task.toml
```

### `instruction.md`

Defines the survey-reconstruction contract, input evidence, required numerical quantities, tolerances, and output schema.

### `environment/`

Contains the reproducible runtime and solver-visible field and control data.

### `solution/`

Contains the reference reconstruction implementation.

### `tests/`

Contains the independent verifier.

### `task.toml`

Contains task metadata and execution configuration.

## Carrier Reconstruction

The first stage begins from an accepted control state and a low-coherence carrier campaign.

The surviving observations retain:

- temporary target tags
- continuous lock-arc identifiers
- carrier epochs
- observation measurements

but have lost:

- the stable monument assignment
- integer cycle origins

The objective is to recover one joint fixed solution that is consistent across the entire campaign.

## Target Assignment

Temporary observation tags must be mapped back to the six known monument identities.

Conceptually:

```text
temporary target tag
        ↓
candidate monument
        ↓
joint observation fit
        ↓
globally consistent mapping
```

The mapping cannot be chosen independently for each measurement because the observations participate in one common geometric and ambiguity solution.

The task also requires the next distinct runner-up assignment rather than only the best candidate.

## Integer Ambiguity Recovery

Carrier observations contain integer cycle ambiguities.

For each lock arc, the reconstruction must determine an integer cycle origin compatible with the continuous geometric model.

This creates a mixed discrete/continuous inverse problem:

```text
continuous parameters
        +
integer cycle origins
        +
target permutation
        ↓
weighted joint fit
```

Independent rounding of ambiguity values is not generally equivalent to solving the coupled problem.

## Final Monument Displacements

Once the winning carrier solution is recovered, the final carrier epoch is identified from the observation timeline.

The project then reports total horizontal displacement for each monument:

```text
d_east_m
d_north_m
```

in metres.

These recovered final monument positions become the control geometry for the closing survey. :chatgpt-content-reference{index="3"}

## Closing Resection

A closing resection was observed immediately after the carrier campaign.

Its evidence includes:

- thermometer checks
- circle references
- range references
- state seeds
- setup registers
- instrument model sheets
- field observations
- reduction notes

The closing archive must be reduced against the recovered carrier-final monument coordinates.

## Instrument Model Selection

The closing reduction contains competing models for angular and range observations.

The reconstruction determines:

```text
angle_model_code
range_model_code
```

using the model codes supplied by the archived model sheets.

The selected models must participate in the same minimum-closure solution as the target mapping and setup reductions.

## Circle Sense

The two setups use archived circle-sense codes whose relationship to physical angle direction must be recovered.

The output records the resulting crosswalk using:

```text
+1
-1
```

for the two setup sense codes.

This convention affects the geometry and therefore cannot be chosen independently from the final resection.

## Setup Reduction

The closing survey contains two setups:

```text
S3
S8
```

For each setup the reconstruction reports:

```text
east_m
north_m
orientation_rad
rms_m
```

The orientation is angular and therefore periodic modulo `2π`.

Equivalent angular representations that differ by complete revolutions describe the same physical orientation. :chatgpt-content-reference{index="4"}

## Resection Geometry

The closing solution simultaneously determines:

- temporary X-tag assignments
- setup coordinates
- setup orientations
- instrument-model choices
- circle-sense convention
- interstation geometry

The resulting interstation quantities include:

```text
interstation_baseline_m
interstation_azimuth_rad
```

The solution is evaluated through Cartesian closure residuals.

## Runner-Up Solutions

Both reconstruction stages preserve meaningful alternatives.

The carrier stage records:

```text
runner_up_target_mapping
runner_up_ambiguities
runner_up_weighted_ss
```

while the closing stage reports:

```text
runner_up_closure_rms_m
```

This provides a quantitative distinction between the accepted interpretation and the next distinct fitted solution.

## Output

The solver writes:

```text
/app/output.json
```

with exactly two top-level sections:

```json
{
  "carrier_reconstruction": {},
  "closing_resection": {}
}
```

### Carrier reconstruction

The carrier section contains:

```text
final_epoch_id
target_mapping
runner_up_target_mapping
ambiguities
runner_up_ambiguities
fixed_weighted_ss
runner_up_weighted_ss
ambiguity_gap
final_total_displacements
```

### Closing resection

The closing section contains:

```text
angle_model_code
range_model_code
angle_weighted_ss
range_weighted_ss
circle_sense
target_mapping
setups
interstation_baseline_m
interstation_azimuth_rad
closure_rms_m
runner_up_closure_rms_m
```

See `instruction.md` for the authoritative numerical tolerances and exact schema. :chatgpt-content-reference{index="5"}

## Numerical Concepts

This project exercises:

- survey adjustment
- geodetic coordinate reconstruction
- weighted least squares
- integer least-squares reasoning
- phase and carrier ambiguity resolution
- combinatorial target assignment
- rigid-transform fitting
- resection
- angular periodicity
- displacement estimation
- model selection
- nonlinear numerical optimization

## Coupled Reconstruction

The important design feature is that the stages are dependent.

```text
carrier solution
      ↓
final monument coordinates
      ↓
closing control geometry
      ↓
resection solution
```

An incorrect carrier interpretation therefore propagates into the closing survey instead of remaining an isolated error.

This makes the project a coupled inverse problem rather than a collection of independent calculations.

## Validation

A valid reconstruction must satisfy both the discrete and continuous parts of the problem.

That includes agreement on:

- target mappings
- carrier ambiguity integers
- model selections
- circle-sense convention
- fitted coordinates
- orientations
- displacement components
- weighted residuals
- closure statistics

The repository verifier evaluates the resulting `/app/output.json` against the task's documented tolerances.

## Goal

The goal of Survey Datum Recovery is to reconstruct a coherent survey datum from incomplete identity and phase information and then carry that recovered geometry forward into an independent closing resection.

The central principle is:

> Recover the discrete identities and ambiguities together with the continuous geometry, then validate the resulting datum through the closing survey.

## License

No license is currently specified.
