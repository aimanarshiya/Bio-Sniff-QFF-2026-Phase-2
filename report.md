# Bio-Sniff QFF 2026 Phase 2 — PS-O-OI Results

## Executive summary

Bio-Sniff investigates a constrained sensor-placement problem: selecting
exactly three positions from nine candidates to maximize a weighted
placement objective. The Phase 2 evaluation uses QAOA at depth p = 1,
with exact enumeration and uniform-random sampling as reference baselines.

The locked objective is

\[
F(x) = 0.60U(x) + 0.25C(x) + 0.15S(x),
\]

where U represents utility, C represents pairwise complementarity,
and S represents spatial spread. The corresponding QUBO minimizes

\[
E(x) = -F(x) + P\left(\sum_i x_i - 3\right)^2,
\]

using the reference penalty P = 3.0.

Exact enumeration identifies the optimal placements as [1, 6, 8] for
Instance L, with F* = 1.452471431427, and [2, 3, 4] for Instance S,
with F* = 1.165737284241.

Processor D reduces the transpiled CX count from 121 to 102, circuit
depth from 117 to 87, and SWAP count from 17 to 10 for Instance L
relative to Processor B. These results demonstrate lower measured
circuit-resource costs for this instance, not a universal advantage
across all instances or metrics.

The solution-quality results vary by instance, processor, and noise
condition. For noisy Instance L on Processor B, the mean objective
ratio is 0.7255 compared with the uniform-random baseline of 0.8157,
while valid frequency is 0.2793 compared with 0.1641 for random
sampling. Therefore, the results do not establish that QAOA
outperforms random sampling on every metric.

## Scope and reproducibility

This report summarizes the required Phase 2 experiments using the locked
Phase 1-derived inputs, the official `qff_phase2.py` helper, and the
checkpointed experiment records. The candidate coordinates and generated
coverage profiles are synthetic, not measurements from a real field.

The required evaluation uses 4096 shots, transpiler/simulator seed 42,
optimization level 1, basis gates `rz`, `sx`, `x`, and `cx`, and the
official noise rates 0.001, 0.005, and 0.01. QAOA uses p = 1, with
COBYLA optimization and initial angles generated using
`numpy.random.default_rng(seed)` for seeds 0–4. The optimization cost
uses exact statevector probabilities.

The official helper supplies the simulator, transpilation, measurement
bit-order conversion, circuit metrics, and Bell experiments. The locked
instance data and processor definitions are preserved. Optimizer
termination statuses, failed attempts, retries, and evaluation limits
are recorded in the experiment outputs.

No real-quantum-hardware experiment, real-field validation, or
quantum-advantage claim is made. The reported results characterize
the specified synthetic benchmark and simulation conditions.



## Problem and exact reference

Instance L contains nine candidates and 84 feasible choose-three placements. Instance S is the locked five-candidate subset `[0,1,2,3,4]` and has 10 feasible placements. Exact enumeration gives:

| Instance | F* | Optimal candidate IDs | Random valid frequency | Random P_opt | Random objective ratio |
| --- | ---: | --- | ---: | ---: | ---: |
| L | 1.452471431427 | [[1, 6, 8]] | 0.164062 | 0.001953 | 0.815711 |
| S | 1.165737284241 | [[2, 3, 4]] | 0.312500 | 0.031250 | 0.882939 |

The random baseline is enumerated over all $2^n$ bitstrings. The objective ratio baseline is the mean reward over valid placements divided by $F^*$, as required by the Bio-Sniff deliverables.

## Bell-state verification

Processor D was tested on a directly connected pair and the lexicographically first farthest pair found from its graph distances. Each pair was evaluated under ideal and official noisy simulation using XX, YY, and ZZ measurements with 4096 shots per basis. Fidelity and its standard error use the helper's $F=(1+XX-YY+ZZ)/4$ convention.

| pair_label | physical_pair | pair_distance | condition | XX | XX_se | YY | YY_se | ZZ | ZZ_se | fidelity | fidelity_se |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adjacent | [0, 1] | 1 | ideal | 1.0000 | 0.0000 | -1.0000 | 0.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| adjacent | [0, 1] | 1 | noisy | 0.9458 | 0.0051 | -0.9521 | 0.0048 | 0.9551 | 0.0046 | 0.9633 | 0.0021 |
| farthest | [0, 3] | 2 | ideal | 1.0000 | 0.0000 | -1.0000 | 0.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| farthest | [0, 3] | 2 | noisy | 0.9448 | 0.0051 | -0.9360 | 0.0055 | 0.9385 | 0.0054 | 0.9548 | 0.0023 |

The noisy channel applies depolarizing error after one- and two-qubit gates and symmetric measurement bit flips, reducing measured correlations and fidelity. A distant pair requires routing to bring the qubits together, adding entangling operations and exposure to the same synthetic gate noise. The model is uniform and does not model device-specific crosstalk.

## Processor D design and routing

Processor D is the frozen, connected nine-qubit, 18-edge, degree-four circulant graph, with a diameter of 2. Its topology is shown in `results/figures/processor_D_topology.png`; the design rationale and routing probe are documented in `docs/processor_D_design.md`. The topology passes `validate_processor_d(D, 9)`.

The QUBO objective contains interactions between candidate variables, including the pairwise terms introduced by the exactly-three selection constraint. Because Processor D has degree four rather than all-to-all connectivity, some required interactions must be implemented through routing. Its value must therefore be assessed using the measured transpiled-circuit metrics, rather than topology alone.

The official resource metrics are generated for each executable instance/processor combination using `circuit_metrics()`. The earlier fixed-angle routing diagnostic is not an optimized-QAOA or noisy-quality benchmark. The table below reports the official circuit-resource measurements.

| Instance | Processor | Logical CX | CX | Depth | Two-qubit depth | SWAPs | CX overhead |
|---|---|---:|---:|---:|---:|---:|---:|
| L | Processor B | 72 | 121 | 117 | 79 | 17 | 49 |
| L | Processor D | 72 | 102 | 87 | 59 | 10 | 30 |
| S | Processor A | 20 | 32 | 59 | 28 | 4 | 12 |
| S | Processor B | 20 | 26 | 40 | 22 | 2 | 6 |
| S | Processor D | 20 | 26 | 51 | 24 | 2 | 6 |

For **Instance L**, Processor D reduces the transpiled CX count from 121 to 102 compared with Processor B, a reduction of 15.7%. Circuit depth decreases from 117 to 87 (25.6%), two-qubit depth from 79 to 59 (25.3%), and SWAP count from 17 to 10 (41.2%). CX overhead also falls from 49 to 30. These measurements show that Processor D reduces routing-related circuit costs for this instance under the evaluated configuration.

The result is not universal across instances or metrics. For **Instance S**, Processors B and D both require 26 CX gates, 2 SWAPs, and 6 CX overhead gates. However, Processor D has a circuit depth of 51 compared with 40 on Processor B, and a two-qubit depth of 24 compared with 22. Thus, Processor D does not improve every resource metric for every instance.

These results support a measured, instance-dependent conclusion: Processor D is beneficial for several circuit-resource metrics on Instance L, while Instance S exposes a depth trade-off. Circuit-resource reductions alone do not establish better solution quality; that question is evaluated separately using the objective-ratio and valid-frequency results in the main benchmark.

The saved Instance L circuit diagrams use the actual best available ideal angles: `results/figures/qaoa_logical_L.png`, `results/figures/qaoa_processor_b_L.png`, and `results/figures/qaoa_processor_d_L.png`. They visualize QAOA circuits and transpilation, not execution on physical quantum hardware.

## Main benchmark

The table reports means over five initialization seeds for ideal and noisy evaluation. Each seed uses the same ideal-optimized QAOA angles for both evaluations on a given processor. The objective ratio is the reward of the most frequently sampled valid placement divided by the exact optimum \(F^*\); valid frequency is the fraction of all shots producing feasible placements. The seed-level outputs preserve selected placements, best sampled reward, \(P_{\mathrm{opt}}\), and optimizer status. Processor A is non-executable for Instance L because it has five qubits, while L requires nine.

### QAOA results against uniform-random sampling

| Instance | Processor | Condition | Objective ratio | Random ratio | Difference | Valid frequency | Random valid frequency |
|---|---|---|---:|---:|---:|---:|---:|
| L | B | Ideal | 0.7776 | 0.8157 | -0.0381 | 0.3287 | 0.1641 |
| L | B | Noisy | 0.7255 | 0.8157 | -0.0902 | 0.2793 | 0.1641 |
| L | D | Ideal | 0.8667 | 0.8157 | +0.0510 | 0.3287 | 0.1641 |
| L | D | Noisy | 0.7786 | 0.8157 | -0.0371 | 0.2891 | 0.1641 |
| S | A | Ideal | 0.9094 | 0.8829 | +0.0265 | 0.5448 | 0.3125 |
| S | A | Noisy | 0.9094 | 0.8829 | +0.0265 | 0.5068 | 0.3125 |
| S | B | Ideal | 0.9865 | 0.8829 | +0.1036 | 0.5489 | 0.3125 |
| S | B | Noisy | 0.9865 | 0.8829 | +0.1036 | 0.5188 | 0.3125 |
| S | D | Ideal | 0.8702 | 0.8829 | -0.0127 | 0.5450 | 0.3125 |
| S | D | Noisy | 0.8959 | 0.8829 | +0.0130 | 0.5118 | 0.3125 |

*Instance L on Processor A is not executable and is omitted from this comparison.*

### Interpretation

QAOA's performance depends on the instance, processor, and metric. For Instance L on Processor B, the noisy objective ratio is 0.7255, below the random baseline of 0.8157 by 0.0902. However, its valid frequency is 0.2793, exceeding the random baseline of 0.1641 by 0.1152. Thus, QAOA produces feasible placements more often in this comparison, but the most frequently sampled valid placement has lower normalized reward than the random baseline.

For Instance L on Processor D, noisy objective ratio is 0.7786, still below random, while valid frequency is 0.2891 versus 0.1641. For Instance S, Processor B gives the strongest measured objective ratio: 0.9865 in both conditions, compared with 0.8829 for random sampling. Its noisy valid frequency is also higher than random (0.5188 versus 0.3125). Processor A also exceeds the random objective-ratio baseline on S, while Processor D is slightly below it in the ideal condition and slightly above it in the noisy condition.

Across these tested configurations, QAOA has higher valid-placement frequency than uniform-random sampling, but it does **not** outperform the random objective-ratio baseline in every case. These results characterize the specified synthetic benchmark and simulation settings; they do not establish quantum advantage or demonstrate real-field performance.

### Initialization-seed consistency

The following table reports the mean objective ratio and sample standard deviation across the five initialization seeds. The standard deviation indicates variation across these tested initializations; it is not a confidence interval.

| Instance | Processor | Condition | Mean objective ratio | Sample standard deviation |
|---|---|---|---:|---:|
| L | B | Ideal | 0.7776 | 0.0927 |
| L | B | Noisy | 0.7255 | 0.0897 |
| L | D | Ideal | 0.8667 | 0.0981 |
| L | D | Noisy | 0.7786 | 0.1128 |
| S | A | Ideal | 0.9094 | 0.0571 |
| S | A | Noisy | 0.9094 | 0.0571 |
| S | B | Ideal | 0.9865 | 0.0302 |
| S | B | Noisy | 0.9865 | 0.0302 |
| S | D | Ideal | 0.8702 | 0.0030 |
| S | D | Noisy | 0.8959 | 0.0582 |

### Optimizer status and reproducibility

The original Step 1A runs used a 60-evaluation limit; four of five L starts and all five S starts had limit/non-success statuses. The subsequent 150-evaluation retries and best-energy attempts are recorded separately. The best-energy attempts ended with successful final COBYLA statuses for all five L seeds and all five S seeds, and at least one attempt converged for every seed on both instances. A successful optimizer termination does not itself guarantee a globally optimal QAOA parameter set. The per-seed records retain the attempt history and termination messages for auditability.

## Penalty sensitivity

The penalty sweep evaluates Instance L on Processor D at \(P \in \{0, 0.5, 1, 2, 3, 5, 10\}\). QAOA angles were independently re-optimized for each penalty, including the reference value \(P=3\), using the five required initialization seeds. Ideal and noisy evaluations use the same optimized angles for each seed and 4096 shots. The validity of the minimum-energy QUBO bitstring is determined by exhaustive enumeration of all bitstrings, independently of the QAOA sampling results.

| Penalty \(P\) | QUBO minimum valid? | Valid frequency | \(P_{\mathrm{opt}}\) | Objective ratio | Successful optimizations | Failed optimizations |
|---:|:---:|---:|---:|---:|---:|---:|
| 0 | No | 0.0169 | 0.0002 | 0.6942 | 5 | 0 |
| 0.5 | No | 0.1165 | 0.0017 | 0.7524 | 4 | 1 |
| 1 | Yes | 0.1745 | 0.0023 | 0.7086 | 4 | 1 |
| 2 | Yes | 0.2948 | 0.0038 | 0.7284 | 5 | 0 |
| 3 | Yes | 0.2891 | 0.0026 | 0.7786 | 5 | 0 |
| 5 | Yes | 0.3791 | 0.0038 | 0.8765 | 4 | 1 |
| 10 | Yes | 0.3227 | 0.0042 | 0.7446 | 3 | 2 |

### Interpretation

At \(P=0\), the QUBO has no penalty enforcing the requirement to select exactly three candidates. Its minimum-energy bitstring is therefore invalid, and the noisy QAOA run produces only 0.0169 valid frequency with an objective ratio of 0.6942. This demonstrates why the cardinality constraint must be represented in the QUBO objective.

At \(P=0.5\), the minimum-energy bitstring is also invalid, although the sampled valid frequency rises to 0.1165. For \(P \geq 1\), the exhaustively enumerated QUBO minimum is valid for the tested sweep. However, validity of the QUBO minimum does not guarantee that QAOA will frequently sample valid placements; the observed valid frequency still depends on the optimized circuit and sampling distribution.

Among the tested values, \(P=5\) gives the highest noisy valid frequency (0.3791) and the highest objective ratio (0.8765). It also maximizes the team-defined descriptive product of valid frequency and objective ratio. This makes \(P=5\) the strongest measured balance in this sweep, rather than proof of a globally optimal penalty. The reference value \(P=3\) achieves a valid frequency of 0.2891 and an objective ratio of 0.7786, both lower than the observed values at \(P=5\).

The sweep also shows optimization variability: some runs at \(P=0.5\), \(1\), \(5\), and \(10\) did not report successful optimization termination. These statuses are retained rather than omitted from the report. Full results, including standard deviations and optimization counts, are available in `results/tables/penalty_sweep.csv`.

The product of valid frequency and objective ratio is a team-selected descriptive indicator, **not an official scoring metric**. The conclusion is limited to the tested synthetic instance, processor, seeds, shot count, and noise configuration.

## Limitations and next steps

### Limitations

The candidate grid, source locations, wind displacement, coverage values, utility, complementarity, and spacing used in this milestone are synthetic. Therefore, the results do not establish measured VOC transport, calibrated detection probability, a disease-specific sensor signal, or optimal sensor placement for a physical farm.

The QAOA experiments were performed using simulation rather than real quantum hardware. The results compare QAOA sampling with uniform-random sampling under the specified benchmark conditions; they do not establish quantum advantage over classical optimization. The measured circuit-resource reductions on Processor D are also specific to the tested instances and transpilation settings.

### Requirements for real-field validation

Before deployment on a physical farm, the system would require:

- **Sensor calibration:** Characterize sensor response, drift, repeatability, and environmental sensitivity under documented conditions.
- **Real candidate coordinates:** Record actual sensor positions and farm boundaries rather than relying on synthetic coordinates.
- **Validated dispersion assumptions:** Test wind-displacement and plume/dispersion assumptions against measured field conditions.
- **Controlled field measurements:** Collect VOC and environmental readings under documented healthy and disease-affected conditions, with appropriate ground-truth labels.
- **Placement validation:** Compare the selected sensor positions with field observations to determine whether the optimized placement improves detection and localization in practice.

These steps are necessary to evaluate whether the simulated placement results transfer to real agricultural conditions; they are proposed validation work, not completed experiments.

### Reproducibility artifacts

The experiment preserves the locked input hash, processor hashes, package versions, official settings, random seeds, optimizer attempts, shot counts, and raw sampled count maps in `results/optimization/phase2_experiment_cache.json`. Together with the notebook, helper module, and result tables, these artifacts support inspection and reproduction of the reported simulation results.

No real-hardware experiment or real-field validation was completed in this milestone.