# Shortcut audit

These are reviewer-side checks only; the `cheat/` directory is never mounted in the agent container.

- `carrier-rounding` independently rounds the 18 float ambiguities. Five cycle origins change and the refitted carrier weighted sum rises from 37.76500166 to 52.53540456. The verifier rejects it.
- `carrier-first-map` accepts the first target assignment that satisfies the commissioning-distance screen instead of solving the joint mapping/ambiguity problem. Its best refitted carrier score is 166.48863455 rather than 37.76500166. The verifier rejects it.
- `closing-wrong-sense` flips the two recovered circle-sense signs while leaving the rest of the correct artifact untouched. The exact semantic check rejects it.
- `closing-wrong-model` substitutes a different archived circle model code while keeping the correct continuous values. The exact model-selection check rejects it.

The closing calibration was also ablated during construction. Restarting reversal memory on every row gives 0.01918850 m Cartesian closure RMS, using the stored wrapped circle directly as the motion state gives 0.03501997 m, and reversing the sense convention while allowing the target assignment to refit gives 19.42338858 m. The accepted closure is 0.00174649 m.
