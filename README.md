# Bio-Sniff Quantum Optimisation

**An AI and Quantum Computing-based approach to intelligent sensor placement for early agricultural disease detection.**

Bio-Sniff explores the use of electronic-nose sensor networks and quantum optimization to support intelligent sensor placement for detecting potential crop disease signals through volatile organic compounds (VOCs).

This repository preserves the research, implementation, experiments, and development of Bio-Sniff across two phases.

## Project Overview

The project investigates how intelligent sensor placement and quantum optimization can contribute to early agricultural disease detection.

### Project Phases

| Phase | Description |
|---|---|
| **Phase One** | Original Bio-Sniff research, synthetic dataset development, initial sensor-placement formulation, and foundational quantum optimization experiments. |
| **Phase Two** | QFF 2026 Open Innovation evaluation, QAOA benchmarking, processor topology design, circuit-resource analysis, Bell-state experiments, and reproducibility studies. |

### Repository Organization

```text
Bio-Sniff-Quantum-Optimization/
|
|-- Phase One/
|   |-- data/
|   |-- docs/
|   |-- notebooks/
|   |-- results/
|   |-- README.md
|   `-- requirements.txt
|
|-- data/
|-- docs/
|-- processors/
|-- results/
|-- src/
|-- main.ipynb
|-- qff_phase2.py
|-- report.md
|-- requirements.txt
`-- README.md
```

**Development convention:** Phase One is preserved as a historical milestone inside `Phase One/`. Phase Two and all future development continue directly in the repository root. No separate `Phase Two/` directory is used.

---

# Phase Two - QFF 2026 Open Innovation

Bio-Sniff continues its Phase One Open Innovation sensor-placement problem. The locked inputs describe synthetic placements and must not be interpreted as measured field performance. The Phase Two Bio-Sniff deliverables document controls the evaluation requirements for the generic PS-O1/O2/O3 instances in `data/instances.json`. The Bio-Sniff-specific locked input is `data/instance.json`.

## Environment and Installation

### Requirements

- Python 3.10–3.12
- Python 3.12.10 was used for the reported verification.
- Dependencies specified in `requirements.txt`.

### Create the environment

Run the following commands in PowerShell from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Run the experiment

1. Open `main.ipynb`.
2. Select the installed Python 3.12 virtual environment as the notebook kernel.
3. Start with a clean kernel.
4. Run all notebook cells from beginning to end.

The notebook performs the following operations:

- **Cell 1:** Checks the Python environment, dependencies, and official helper functions.
- **Cell 2:** Executes the Phase Two experiment pipeline using checkpointed optimization and measurement caches.

Compatible completed experiment records are reused. Missing or invalid cache records are recomputed. Optimizer termination statuses, failed attempts, retries, and iteration limits are preserved in the per-seed experiment outputs.

The official organizer helper `qff_phase2.py` is preserved unchanged.

## Experimental Results

The following values are taken from the generated result tables. They describe the specified synthetic simulation benchmark only.

### QAOA versus uniform-random sampling

| Instance | Processor | Noisy objective ratio | Noisy valid frequency | Random objective ratio | Random valid frequency |
|---|---|---:|---:|---:|---:|
| L | B | 0.7255 | 0.2793 | 0.8157 | 0.1641 |
| L | D | 0.7786 | 0.2891 | 0.8157 | 0.1641 |
| S | A | 0.9094 | 0.5068 | 0.8829 | 0.3125 |
| S | B | 0.9865 | 0.5188 | 0.8829 | 0.3125 |
| S | D | 0.8959 | 0.5118 | 0.8829 | 0.3125 |

The results show that QAOA performance depends on the instance, processor, and evaluation metric. Although valid-placement frequency exceeds the uniform-random baseline in all five reported configurations, objective ratio does not exceed the random baseline in every case.

These measurements do not establish quantum advantage over classical optimization.

### Optimizer convergence and reproducibility

For Instance L, four of the five original Step 1A starts had unsuccessful or iteration-limit statuses under the 60-evaluation limit.

The subsequent 150-evaluation retries reached successful final COBYLA termination for all five L seeds. The original attempts, retries, and optimizer statuses are retained in the experiment records.

### Bell-state verification

The required two-pair Bell experiment produced:

| Measurement | Ideal fidelity | Noisy fidelity |
|---|---:|---:|
| Adjacent pair `[0,1]` | 1.0000 | 0.9633 |
| Farthest pair `[0,3]` | 1.0000 | 0.9548 |

The farthest pair has graph distance 2.

### Penalty sensitivity

For the noisy Instance L penalty sweep on Processor D:

- At `P = 0`, the minimum-energy QUBO bitstring is invalid.
- Among the tested penalty values, `P = 5` produced the highest measured valid-frequency × objective-ratio product.
- This product is a team-defined descriptive comparison, not an official competition scoring metric.

Detailed results and standard deviations are available in `results/tables/penalty_sweep.csv`.

## Processor Evaluation

The Phase Two experiments evaluate the specified processor configurations:

- Processor A
- Processor B
- Processor D

Processor A is correctly marked non-executable for Instance L because L requires nine logical qubits while Processor A provides five physical qubits.

Processor D introduces a connected nine-qubit, 18-edge, degree-four topology. Its circuit-resource performance is evaluated through the transpiled circuit metrics.

The experiments use the official processor definitions, noise rates, 4096-shot evaluation, transpilation optimization level 1, transpiler seed 42, and the specified basis gates.

See `report.md` and `docs/processor_D_design.md` for the detailed analysis.

## Generated Outputs

The repository preserves the experiment outputs and reproducibility artifacts.

| Path | Description |
|---|---|
| `results/tables/results.csv` | Per-instance, processor, condition, quality, and circuit-resource results. |
| `results/tables/bell.csv` | Ideal/noisy Bell correlations, standard errors, fidelity, and CX count. |
| `results/tables/penalty_sweep.csv` | Instance L on Processor D penalty-sensitivity results. |
| `results/tables/seed_runs.csv` | Per-seed optimization attempts and sampled results. |
| `results/tables/seed_consistency.csv` | Per-seed objective-ratio statistics and optimizer consistency. |
| `results/optimization/` | Optimization angles, resource metrics, smoke tests, and experiment checkpoint cache. |
| `results/figures/` | Processor D topology, QAOA circuits, benchmark comparisons, and penalty-sweep figures. |
| `report.md` | Detailed Phase Two experimental analysis and findings. |

Additional implementation and validation files include:

- `qff_phase2.py`
- `validate_instance.py`
- `processor_D_template.json`
- `example_usage.py`
- `src/`
- `processors/`

## Limitations and Future Validation

The candidate grid, source locations, wind displacement, coverage values, utility, complementarity, and spacing used in the experiments are synthetic.

Consequently, the reported results do not establish:

- Measured VOC transport or plume behavior.
- Calibrated disease-detection probability.
- A disease-specific signal validated under field conditions.
- Optimal sensor placement for a physical agricultural field.

Real-world validation would require calibrated sensors, documented candidate coordinates, validated plume and dispersion assumptions, and controlled field measurements.

The QAOA experiments are simulation-based. No real quantum-hardware experiment or real-field validation was completed in this milestone. No quantum-advantage claim is made.

## AI Assistance Disclosure

GitHub Copilot was used to assist with inspection of the official specifications, implementation of the notebook and experiment pipeline, validation code, and summarization of executed results.

All reported measurements were generated by the repository's experiment pipeline using the official helper and are traceable to the saved CSV files and checkpoint outputs.

---

## Project Status

Bio-Sniff is maintained as a continuing research and development project.

- **Phase One:** Preserved as the original project milestone.
- **Phase Two:** Completed experimental implementation and documented benchmarking deliverables.
- **Future development:** Continues in the repository root, building on the existing work.

For detailed Phase Two methodology, experimental configurations, and analysis, refer to `report.md` and the supporting documentation in `docs/`.