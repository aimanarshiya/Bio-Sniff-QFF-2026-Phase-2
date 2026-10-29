# Bio-Sniff QFF 2026 Phase 2 — PS-O-OI Results

## Scope and reproducibility

This report is generated from `results/tables/results.csv`, `bell.csv`, `penalty_sweep.csv`, and the checkpointed experiment records. The locked Phase 1-derived inputs are synthetic: nine candidate coordinates and generated coverage profiles, not measurements from a field. No real-field validation or quantum-advantage claim is made.

The objective is to select exactly three candidates and maximize $F(x)=0.60U(x)+0.25C(x)+0.15S(x)$. The minimized QUBO is $-F(x)+P(\sum_i x_i-3)^2$ with reference $P=3.0$. QAOA depth was $p=1$. Initial angles used `numpy.random.default_rng(seed)` for seeds 0–4 and were optimized using COBYLA against exact statevector probabilities. The official evaluation settings were 4096 shots, transpiler/simulator seed 42, optimization level 1, basis `rz,sx,x,cx`, and official noise rates 0.001/0.005/0.01.

The official `qff_phase2.py` helper supplied the simulator, transpilation, measurement bit-order conversion, circuit metrics, and Bell experiments. The required instance data and processor files were not changed. Optimizer termination status is recorded per seed in `results/tables/seed_runs.csv`; unsuccessful COBYLA termination is not described as convergence.

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

Processor D is the frozen connected nine-qubit, 18-edge, degree-four circulant graph. Its diameter is 2. The topology diagram is `results/figures/processor_D_topology.png`; rationale and the measured routing probe are in `docs/processor_D_design.md`. It passes `validate_processor_d(D, 9)`.

The official resource metrics are emitted for each executable instance/processor from `circuit_metrics()`. The earlier fixed-angle routing diagnostic was not an optimized QAOA or noisy-quality benchmark. The current comparisons do not attribute any solution-quality benefit to D unless the measured result rows support it.

| instance | processor | logical_cx | cx | depth | two_q_depth | swaps | cx_overhead |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L | Processor B | 72 | 121 | 117 | 79 | 17 | 49 |
| L | Processor D | 72 | 102 | 87 | 59 | 10 | 30 |
| S | Processor A | 20 | 32 | 59 | 28 | 4 | 12 |
| S | Processor B | 20 | 26 | 40 | 22 | 2 | 6 |
| S | Processor D | 20 | 26 | 51 | 24 | 2 | 6 |

The saved L circuit diagrams use the actual best available ideal angles: `results/figures/qaoa_logical_L.png`, `qaoa_processor_b_L.png`, and `qaoa_processor_d_L.png`. They visualize QAOA circuits and transpilation, not hardware execution.

## Main benchmark

The table below reports means over the five initialization seeds for both ideal and noisy conditions. Each seed used the same ideal-optimized angles for ideal and noisy evaluation on the processor. `objective_ratio` is the reward of the most frequently sampled valid placement divided by $F^*$; `valid_frequency` is the fraction of all shots that are feasible. The per-seed table records selected placements, best sampled reward, P_opt, and optimizer status. Processor A is explicitly non-executable for L because it has five qubits and L requires nine.

| problem_id | processor | condition | executable | quality_metric | quality_value | p_opt | classical_optimum | random_baseline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PS-O-OI-L | A | ideal | false | objective_ratio |  |  |  |  |
| PS-O-OI-L | A | ideal | false | valid_frequency |  |  |  |  |
| PS-O-OI-L | A | noisy | false | objective_ratio |  |  |  |  |
| PS-O-OI-L | A | noisy | false | valid_frequency |  |  |  |  |
| PS-O-OI-L | B | ideal | true | objective_ratio | 0.7776 | 0.0044 | 1.4525 | 0.8157 |
| PS-O-OI-L | B | ideal | true | valid_frequency | 0.3287 | 0.0044 | 1.4525 | 0.1641 |
| PS-O-OI-L | B | noisy | true | objective_ratio | 0.7255 | 0.0034 | 1.4525 | 0.8157 |
| PS-O-OI-L | B | noisy | true | valid_frequency | 0.2793 | 0.0034 | 1.4525 | 0.1641 |
| PS-O-OI-L | D | ideal | true | objective_ratio | 0.8667 | 0.0044 | 1.4525 | 0.8157 |
| PS-O-OI-L | D | ideal | true | valid_frequency | 0.3287 | 0.0044 | 1.4525 | 0.1641 |
| PS-O-OI-L | D | noisy | true | objective_ratio | 0.7786 | 0.0026 | 1.4525 | 0.8157 |
| PS-O-OI-L | D | noisy | true | valid_frequency | 0.2891 | 0.0026 | 1.4525 | 0.1641 |
| PS-O-OI-S | A | ideal | true | objective_ratio | 0.9094 | 0.0573 | 1.1657 | 0.8829 |
| PS-O-OI-S | A | ideal | true | valid_frequency | 0.5448 | 0.0573 | 1.1657 | 0.3125 |
| PS-O-OI-S | A | noisy | true | objective_ratio | 0.9094 | 0.0524 | 1.1657 | 0.8829 |
| PS-O-OI-S | A | noisy | true | valid_frequency | 0.5068 | 0.0524 | 1.1657 | 0.3125 |
| PS-O-OI-S | B | ideal | true | objective_ratio | 0.9865 | 0.0642 | 1.1657 | 0.8829 |
| PS-O-OI-S | B | ideal | true | valid_frequency | 0.5489 | 0.0642 | 1.1657 | 0.3125 |
| PS-O-OI-S | B | noisy | true | objective_ratio | 0.9865 | 0.0600 | 1.1657 | 0.8829 |
| PS-O-OI-S | B | noisy | true | valid_frequency | 0.5188 | 0.0600 | 1.1657 | 0.3125 |
| PS-O-OI-S | D | ideal | true | objective_ratio | 0.8702 | 0.0601 | 1.1657 | 0.8829 |
| PS-O-OI-S | D | ideal | true | valid_frequency | 0.5450 | 0.0601 | 1.1657 | 0.3125 |
| PS-O-OI-S | D | noisy | true | objective_ratio | 0.8959 | 0.0565 | 1.1657 | 0.8829 |
| PS-O-OI-S | D | noisy | true | valid_frequency | 0.5118 | 0.0565 | 1.1657 | 0.3125 |

Per-initialization objective-ratio consistency (mean and sample standard deviation):

| problem_id | processor | condition | objective_ratio_mean | objective_ratio_std |
| --- | --- | --- | --- | --- |
| PS-O-OI-L | B | ideal | 0.7776 | 0.0927 |
| PS-O-OI-L | B | noisy | 0.7255 | 0.0897 |
| PS-O-OI-L | D | ideal | 0.8667 | 0.0981 |
| PS-O-OI-L | D | noisy | 0.7786 | 0.1128 |
| PS-O-OI-S | A | ideal | 0.9094 | 0.0571 |
| PS-O-OI-S | A | noisy | 0.9094 | 0.0571 |
| PS-O-OI-S | B | ideal | 0.9865 | 0.0302 |
| PS-O-OI-S | B | noisy | 0.9865 | 0.0302 |
| PS-O-OI-S | D | ideal | 0.8702 | 0.0030 |
| PS-O-OI-S | D | noisy | 0.8959 | 0.0582 |

For noisy L on B, the mean objective ratio is 0.725534 versus the uniform-random ratio 0.815711 (difference -0.090177); mean valid frequency is 0.279297 versus random 0.164062 (difference +0.115234). This is a comparison on the synthetic benchmark, not evidence of quantum advantage. The preserved Step 1A 60-evaluation starts had 4/5 L and 0/5 S limit/non-success statuses. The subsequent 150-evaluation retries and best-energy attempts are recorded separately; the best-energy attempts had 5/5 successful final COBYLA statuses for L and 5/5 for S, and at least one attempt converged for 5/5 L seeds and 5/5 S seeds. See the seed table for the per-attempt history and termination messages.

## Penalty sensitivity

The sweep uses Instance L on Processor D. Angles were independently re-optimized for every P, including P=3, from the five required seeds. Both ideal and noisy conditions use the same per-seed optimized angles and 4096 shots. The QUBO minimum validity is determined by exhaustive enumeration of all bitstrings, not inferred from QAOA samples.

| penalty | qubo_minimum_valid | valid_frequency | p_opt | objective_ratio | successful_optimizations | failed_optimizations |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | false | 0.0169 | 0.0002 | 0.6942 | 5 | 0 |
| 0.5000 | false | 0.1165 | 0.0017 | 0.7524 | 4 | 1 |
| 1 | true | 0.1745 | 0.0023 | 0.7086 | 4 | 1 |
| 2 | true | 0.2948 | 0.0038 | 0.7284 | 5 | 0 |
| 3 | true | 0.2891 | 0.0026 | 0.7786 | 5 | 0 |
| 5 | true | 0.3791 | 0.0038 | 0.8765 | 4 | 1 |
| 10 | true | 0.3227 | 0.0042 | 0.7446 | 3 | 2 |

At P=0, the noisy QUBO minimum is valid: **false**; sampled valid frequency is 0.016943359375 and objective ratio is 0.694154651643673. Across the noisy sweep, the maximum of valid-frequency × objective-ratio occurs at P=5; this product is a descriptive team-selected balance indicator, not an official scoring metric. The full values and standard deviations are in `penalty_sweep.csv`.

## Limitations and next steps

The candidate grid, source locations, wind displacement, coverage values, utility, complementarity, and spacing are synthetic. They do not establish measured VOC transport, calibrated detection probability, a disease-specific signal, or the best placement for a physical farm. Field use would require calibrated sensors, documented candidate coordinates, validated plume/dispersion assumptions, and controlled field measurements. The QAOA results are simulated and do not establish a quantum advantage over classical optimization.

This milestone did not run a real hardware experiment. Reproducibility artifacts include the locked input hash, processor hashes, package versions, official settings, seeds, optimizer attempts, shot counts, and raw sampled count maps in `results/optimization/phase2_experiment_cache.json`.
