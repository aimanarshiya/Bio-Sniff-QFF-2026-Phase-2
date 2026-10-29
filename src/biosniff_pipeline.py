"""Resumable Bio-Sniff PS-O-OI Phase 2 experiments using organizer helpers."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata as package_metadata
import itertools
import json
import math
import os
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from scipy.optimize import minimize

import qff_phase2 as qff


SEEDS = (0, 1, 2, 3, 4)
SHOTS = qff.SHOTS
K = 3
REFERENCE_PENALTY = 3.0
WEIGHTS = {"U": 0.60, "C": 0.25, "S": 0.15}
OPTIMIZER = "COBYLA"
INITIAL_MAXITER = 60
RETRY_MAXITER = 150
PENALTY_VALUES = (0, 0.5, 1, 2, 3, 5, 10)
RESULT_COLUMNS = [
    "problem_id", "processor", "condition", "executable", "logical_qubits",
    "physical_qubits", "logical_cx", "cx", "depth", "two_q_depth", "swaps",
    "cx_overhead", "shots", "quality_metric", "quality_value", "p_opt",
    "classical_optimum", "random_baseline", "penalty",
]
SEED_COLUMNS = [
    "problem_id", "processor", "condition", "seed", "optimizer_success",
    "optimizer_any_attempt_converged", "optimizer_nfev", "optimizer_maxiter",
    "optimizer_message", "optimizer_exception", "expected_qubo_energy",
    "initial_step1a_attempt_success", "optimizer_attempts_json",
    "selected_candidate_ids", "selected_reward", "best_sampled_reward",
    "objective_ratio", "valid_frequency", "p_opt", "shots",
]
PENALTY_COLUMNS = [
    "problem_id", "processor", "penalty", "condition", "shots",
    "qubo_minimum_energy", "qubo_minimum_bitstring", "qubo_minimum_valid",
    "valid_frequency", "valid_frequency_std", "p_opt", "p_opt_std",
    "objective_ratio", "objective_ratio_std", "classical_optimum",
    "random_valid_frequency", "random_p_opt", "random_objective_ratio",
    "optimizer", "iteration_limit", "seed_count", "successful_optimizations",
    "failed_optimizations",
]
BELL_COLUMNS = [
    "pair_label", "physical_pair", "pair_distance", "condition", "shots", "cx",
    "XX", "XX_se", "YY", "YY_se", "ZZ", "ZZ_se", "fidelity", "fidelity_se",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_text(serialized, encoding="utf-8")
    try:
        os.replace(temporary, path)
    except PermissionError:
        try:
            path.write_text(serialized, encoding="utf-8")
        finally:
            temporary.unlink(missing_ok=True)


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _configuration(root: Path) -> dict:
    instance_path = root / "data" / "instance.json"
    processor_paths = {
        label: root / "processors" / f"processor_{label}.json"
        for label in ("A", "B", "D")
    }
    return {
        "schema_version": 2,
        "problem_id": "PS-O-OI",
        "instance_sha256": _sha256(instance_path),
        "official_helper_sha256": _sha256(Path(qff.__file__).resolve()),
        "pipeline_sha256": _sha256(Path(__file__).resolve()),
        "python_version": sys.version.split()[0],
        "package_versions": {
            name: package_metadata.version(name)
            for name in ("qiskit", "qiskit-aer", "numpy", "scipy", "matplotlib")
        },
        "processor_sha256": {
            label: _sha256(path) for label, path in processor_paths.items()
        },
        "weights": WEIGHTS,
        "k": K,
        "reference_penalty": REFERENCE_PENALTY,
        "qaoa_p": 1,
        "seeds": list(SEEDS),
        "shots": SHOTS,
        "optimizer": OPTIMIZER,
        "main_maxiter": INITIAL_MAXITER,
        "retry_maxiter": RETRY_MAXITER,
        "penalty_values": list(PENALTY_VALUES),
        "cost_evaluation": "exact Qiskit Statevector probabilities",
        "official": {
            "basis_gates": list(qff.BASIS_GATES),
            "optimization_level": qff.OPT_LEVEL,
            "seed_transpiler": qff.SEED,
            "seed_simulator": qff.SEED,
            "p1_depolarizing": qff.P1_DEPOL,
            "p2_depolarizing_cx": qff.P2_DEPOL,
            "readout_bitflip": qff.P_READOUT,
        },
    }


def _objective(selected: tuple[int, ...], instance: dict) -> float:
    value = WEIGHTS["U"] * sum(instance["U"][index] for index in selected)
    for position, left in enumerate(selected):
        for right in selected[position + 1:]:
            value += WEIGHTS["C"] * instance["C"][left][right]
            value += WEIGHTS["S"] * instance["S"][left][right]
    return float(value)


def _enumerate_instance(instance: dict) -> dict:
    ids = instance["candidate_ids"]
    combinations = list(itertools.combinations(range(len(ids)), K))
    scored = [(selection, _objective(selection, instance)) for selection in combinations]
    optimum = max(score for _, score in scored)
    optimal = [selection for selection, score in scored if math.isclose(score, optimum, abs_tol=1e-14)]
    stored = instance["classical_optimum"]
    if not math.isclose(optimum, stored["objective_value"], rel_tol=0.0, abs_tol=1e-14):
        raise ValueError(f"{instance['name']} exact optimum does not match data/instance.json")
    optimal_ids = [[ids[index] for index in selected] for selected in optimal]
    if stored["candidate_ids"] not in optimal_ids:
        raise ValueError(f"{instance['name']} optimum candidates do not match data/instance.json")
    count = len(ids)
    baseline = {
        "valid_frequency": len(combinations) / (2**count),
        "p_opt": len(optimal) / (2**count),
        "objective_ratio": float(np.mean([score for _, score in scored]) / optimum),
    }
    return {
        "f_star": float(optimum),
        "optimal_local": [list(value) for value in optimal],
        "optimal_ids": optimal_ids,
        "placements": scored,
        "baseline": baseline,
    }


def _qubo(instance: dict, penalty: float) -> np.ndarray:
    utility = np.asarray(instance["U"], dtype=float)
    complementarity = np.asarray(instance["C"], dtype=float)
    spacing = np.asarray(instance["S"], dtype=float)
    n = len(utility)
    matrix = np.zeros((n, n), dtype=float)
    for i in range(n):
        matrix[i, i] = -WEIGHTS["U"] * utility[i] + penalty * (1 - 2 * K)
        for j in range(i + 1, n):
            matrix[i, j] = (
                -WEIGHTS["C"] * complementarity[i, j]
                - WEIGHTS["S"] * spacing[i, j]
                + 2 * penalty
            )
    return matrix


def _qubo_energy(bits: tuple[int, ...], matrix: np.ndarray) -> float:
    return float(sum(
        matrix[i, j] * bits[i] * bits[j]
        for i in range(len(bits))
        for j in range(i, len(bits))
    ))


def _qaoa_circuit(matrix: np.ndarray, angles: list[float] | tuple[float, float], measure=False) -> QuantumCircuit:
    gamma, beta = angles
    n = matrix.shape[0]
    circuit = QuantumCircuit(n, name="biosniff_qaoa_p1")
    circuit.h(range(n))
    z_terms = np.zeros(n, dtype=float)
    zz_terms = {}
    for i in range(n):
        z_terms[i] -= matrix[i, i] / 2.0
    for i in range(n):
        for j in range(i + 1, n):
            coefficient = matrix[i, j]
            if abs(coefficient) > 1e-12:
                z_terms[i] -= coefficient / 4.0
                z_terms[j] -= coefficient / 4.0
                zz_terms[(i, j)] = coefficient / 4.0
    for i, coefficient in enumerate(z_terms):
        if abs(coefficient) > 1e-12:
            circuit.rz(2 * gamma * coefficient, i)
    for (i, j), coefficient in zz_terms.items():
        circuit.rzz(2 * gamma * coefficient, i, j)
    for i in range(n):
        circuit.rx(2 * beta, i)
    if measure:
        circuit.measure_all()
    return circuit


def _expected_energy(angles, matrix: np.ndarray) -> float:
    circuit = _qaoa_circuit(matrix, angles)
    probabilities = Statevector.from_instruction(circuit).probabilities_dict()
    return float(sum(
        probability * _qubo_energy(qff.counts_to_x(bitstring), matrix)
        for bitstring, probability in probabilities.items()
    ))


def _initial_angles(seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(0.0, np.pi, size=2)


def _optimize(matrix: np.ndarray, seed: int, maxiter: int, initial: np.ndarray | None = None) -> dict:
    initial_angles = _initial_angles(seed) if initial is None else np.asarray(initial, dtype=float)
    started = time.perf_counter()
    try:
        result = minimize(
            _expected_energy,
            initial_angles,
            args=(matrix,),
            method=OPTIMIZER,
            options={"maxiter": maxiter, "rhobeg": 0.3},
        )
        return {
            "seed": int(seed),
            "initial_angles": initial_angles.tolist(),
            "optimized_angles": np.asarray(result.x, dtype=float).tolist(),
            "expected_qubo_energy": float(result.fun),
            "optimizer_success": bool(result.success),
            "optimizer_nfev": int(result.nfev),
            "optimizer_message": str(result.message),
            "maxiter": int(maxiter),
            "runtime_seconds": time.perf_counter() - started,
            "exception": None,
        }
    except Exception as error:
        return {
            "seed": int(seed),
            "initial_angles": initial_angles.tolist(),
            "optimized_angles": None,
            "expected_qubo_energy": None,
            "optimizer_success": False,
            "optimizer_nfev": 0,
            "optimizer_message": "optimizer exception",
            "maxiter": int(maxiter),
            "runtime_seconds": time.perf_counter() - started,
            "exception": f"{type(error).__name__}: {error}",
        }


def _save_optimization(root: Path, configuration: dict, runs: dict, prior: dict | None) -> None:
    path = root / "results" / "optimization" / "ideal_qaoa_optimization.json"
    payload = {
        "configuration": configuration,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cost_evaluation": "exact Qiskit Statevector probabilities",
        "source_cache_reused": prior is not None,
        "runs_by_instance": runs,
    }
    _atomic_json(path, payload)


def _load_prior_optimization(root: Path, configuration: dict) -> dict | None:
    path = root / "results" / "optimization" / "ideal_qaoa_optimization.json"
    if not path.exists():
        return None
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        old_config = previous.get("configuration", {})
        old_processors = {
            key: value for key, value in old_config.get("processor_sha256", {}).items()
            if key in ("B", "D")
        }
        old_settings = old_config.get("official_settings", old_config.get("official", {}))
        old_seeds = old_config.get("initialization_seeds", old_config.get("seeds"))
        old_maxiter = old_config.get("optimizer_maxiter", old_config.get("main_maxiter"))
        old_transpiler_seed = old_settings.get(
            "seed_transpiler_and_simulator", old_settings.get("seed_transpiler")
        )
        old_angle_formula = old_config.get("angle_initialization")
        if old_angle_formula is None and old_config.get("schema_version", 0) >= 2:
            old_angle_formula = "default_rng(seed).uniform(0, pi, size=2)"
        checks = (
            old_config.get("problem_id") == configuration["problem_id"],
            old_config.get("instance_sha256") == configuration["instance_sha256"],
            old_processors == {
                key: value for key, value in configuration["processor_sha256"].items()
                if key in ("B", "D")
            },
            old_config.get("qaoa_p") == 1,
            old_config.get("selection_count", old_config.get("k")) == K,
            old_config.get("reference_penalty") == REFERENCE_PENALTY,
            old_config.get("weights") == WEIGHTS,
            old_config.get("optimizer") == OPTIMIZER,
            old_maxiter == INITIAL_MAXITER,
            old_seeds == list(SEEDS),
            old_angle_formula == "default_rng(seed).uniform(0, pi, size=2)",
            old_settings.get("basis_gates") == list(qff.BASIS_GATES),
            old_settings.get("optimization_level") == qff.OPT_LEVEL,
            old_transpiler_seed == qff.SEED,
            old_config.get("package_versions", {}).get("qiskit") == configuration["package_versions"]["qiskit"],
            old_config.get("package_versions", {}).get("qiskit-aer") == configuration["package_versions"]["qiskit-aer"],
            old_config.get("package_versions", {}).get("numpy") == configuration["package_versions"]["numpy"],
            old_config.get("package_versions", {}).get("scipy") == configuration["package_versions"]["scipy"],
        )
        if not all(checks):
            print("Prior ideal optimization cache is incompatible; required seeds will be recomputed.")
            return None
        cached_runs = previous.get("runs_by_instance", {})
        if set(cached_runs) - {"L", "S"}:
            print("Prior optimization cache contains unknown instances; recomputing.")
            return None
        for label, rows in cached_runs.items():
            seeds = [run.get("seed") for run in rows]
            if len(seeds) != len(set(seeds)) or any(seed not in SEEDS for seed in seeds):
                print(f"Prior optimization cache has duplicate or invalid seeds for {label}; recomputing.")
                return None
            for run in rows:
                if run.get("optimized_angles") is None:
                    continue
                expected_angles = _initial_angles(int(run["seed"]))
                if not np.allclose(run.get("initial_angles", []), expected_angles, rtol=0.0, atol=1e-14):
                    print(f"Prior optimization cache has incompatible initial angles for {label} seed {run['seed']}; recomputing.")
                    return None
        print("Prior ideal optimization cache matches the locked instance and processor hashes.")
        return previous
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Prior ideal optimization cache could not be validated ({error}); recomputing.")
        return None


def _load_step1a_attempts(root: Path, configuration: dict) -> dict:
    archive_paths = sorted(
        (root / "results" / "optimization").glob(
            "ideal_qaoa_optimization.pre-end2end-*.bak.json"
        )
    )
    for archive_path in archive_paths:
        try:
            archive = json.loads(archive_path.read_text(encoding="utf-8"))
            archived_config = archive.get("configuration", {})
            if (
                archived_config.get("problem_id") != configuration["problem_id"]
                or archived_config.get("instance_sha256") != configuration["instance_sha256"]
                or archived_config.get("processor_sha256") != {
                    key: value for key, value in configuration["processor_sha256"].items()
                    if key in ("B", "D")
                }
                or archived_config.get("initialization_seeds") != list(SEEDS)
                or archived_config.get("optimizer") != OPTIMIZER
                or archived_config.get("optimizer_maxiter") != INITIAL_MAXITER
                or archived_config.get("angle_initialization") != "default_rng(seed).uniform(0, pi, size=2)"
            ):
                continue
            attempts = {}
            for label, rows in archive["runs_by_instance"].items():
                for row in rows:
                    attempts[(label, row["seed"])] = {
                        "seed": row["seed"],
                        "initial_angles": row["initial_angles"],
                        "optimized_angles": row.get("optimized_angles"),
                        "expected_qubo_energy": row.get("expected_qubo_energy"),
                        "optimizer_success": bool(row.get("optimizer_success")),
                        "optimizer_nfev": int(row.get("optimizer_nfev", 0)),
                        "optimizer_message": row.get("termination_message", row.get("optimizer_message", "")),
                        "maxiter": int(archived_config["optimizer_maxiter"]),
                        "runtime_seconds": row.get("runtime_seconds", 0.0),
                        "exception": None,
                        "source": "preserved Step 1A cache",
                    }
            print(f"Loaded {len(attempts)} archived Step 1A seed attempts from {archive_path.name}.")
            return attempts
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"Could not use Step 1A archive {archive_path.name}: {error}")
    return {}


def _main_optimizations(root: Path, configuration: dict, instances: dict) -> tuple[dict, dict]:
    previous = _load_prior_optimization(root, configuration)
    old_runs = previous.get("runs_by_instance", {}) if previous else {}
    archived_attempts = _load_step1a_attempts(root, configuration)
    all_runs = {
        label: list(old_runs.get(label, []))
        for label in instances
    }
    for label, instance in instances.items():
        matrix = _qubo(instance, REFERENCE_PENALTY)
        for seed in SEEDS:
            old = next((row for row in old_runs.get(label, []) if row.get("seed") == seed), None)
            attempts = []
            historical = archived_attempts.get((label, seed))
            if historical:
                attempts.append(historical)
            old_selected = None
            if old:
                attempts.extend(old.get("attempts") or [{
                    **old,
                    "maxiter": old.get("optimizer_maxiter", old_config_maxiter(previous)),
                    "source": "current ideal optimization cache",
                }])
                if old.get("optimized_angles") is not None:
                    old_selected = {
                        "seed": seed,
                        "initial_angles": old.get("initial_angles", _initial_angles(seed).tolist()),
                        "optimized_angles": old["optimized_angles"],
                        "expected_qubo_energy": old.get("expected_qubo_energy"),
                        "optimizer_success": bool(old.get("optimizer_success")),
                        "optimizer_nfev": int(old.get("optimizer_nfev", 0)),
                        "optimizer_message": old.get("optimizer_message", "reused current compatible optimization"),
                        "maxiter": int(old.get("optimizer_maxiter", INITIAL_MAXITER)),
                        "runtime_seconds": old.get("runtime_seconds", 0.0),
                        "exception": old.get("optimizer_exception"),
                        "source": "selected angles already used by completed benchmark rows",
                    }
            deduplicated_attempts = []
            seen_attempts = set()
            for attempt in attempts:
                signature = (
                    attempt.get("seed"),
                    attempt.get("maxiter", attempt.get("optimizer_maxiter")),
                    tuple(attempt.get("initial_angles") or ()),
                    tuple(attempt.get("optimized_angles") or ()),
                    attempt.get("expected_qubo_energy"),
                    attempt.get("optimizer_success"),
                )
                if signature not in seen_attempts:
                    seen_attempts.add(signature)
                    deduplicated_attempts.append(attempt)
            attempts = deduplicated_attempts

            usable_before_retry = [
                attempt for attempt in attempts
                if attempt.get("optimized_angles") is not None
                and attempt.get("expected_qubo_energy") is not None
            ]
            best_before_retry = min(
                usable_before_retry,
                key=lambda attempt: attempt["expected_qubo_energy"],
                default=None,
            )
            highest_budget = max(
                (int(attempt.get("maxiter", attempt.get("optimizer_maxiter", 0))) for attempt in attempts),
                default=0,
            )
            any_converged = any(attempt.get("optimizer_success") for attempt in attempts)
            if not any_converged and highest_budget < RETRY_MAXITER:
                print(f"{label} seed {seed}: retrying with maxiter={RETRY_MAXITER}.")
                retry = _optimize(matrix, seed, RETRY_MAXITER)
                retry["source"] = "Phase 2 retry"
                attempts.append(retry)

            usable = [row for row in attempts if row.get("expected_qubo_energy") is not None]
            best = old_selected or (
                min(usable, key=lambda row: row["expected_qubo_energy"]) if usable else None
            )
            record = {
                "seed": seed,
                "initial_angles": _initial_angles(seed).tolist(),
                "optimized_angles": best["optimized_angles"] if best else None,
                "expected_qubo_energy": best["expected_qubo_energy"] if best else None,
                "optimizer_success": bool(best and best.get("optimizer_success")),
                "any_attempt_converged": any(row.get("optimizer_success", False) for row in attempts),
                "optimizer_nfev": best.get("optimizer_nfev", 0) if best else 0,
                "optimizer_message": best.get("optimizer_message", "all attempts failed") if best else "all attempts failed",
                "optimizer_maxiter": best.get("maxiter") if best else RETRY_MAXITER,
                "optimizer_exception": best.get("exception") if best else "all attempts failed",
                "initial_step1a_attempt_success": historical.get("optimizer_success") if historical else None,
                "attempts": attempts,
            }
            all_runs[label] = [
                row for row in all_runs[label] if row.get("seed") != seed
            ] + [record]
            all_runs[label].sort(key=lambda row: row["seed"])
            print(
                f"{label} seed {seed}: best energy={record['expected_qubo_energy']}; "
                f"converged={record['optimizer_success']}; attempts={len(attempts)}"
            )
            _save_optimization(root, configuration, all_runs, previous)
        _save_optimization(root, configuration, all_runs, previous)
    return all_runs, previous


def old_config_maxiter(previous: dict | None) -> int:
    if previous:
        return int(previous.get("configuration", {}).get("optimizer_maxiter", INITIAL_MAXITER))
    return INITIAL_MAXITER


def _load_experiment_cache(path: Path, configuration: dict) -> dict:
    if not path.exists():
        return {
            "configuration": configuration,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "bell_runs": {},
            "benchmark_runs": {},
            "penalty_optimizations": {},
            "penalty_runs": {},
        }
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        cached_configuration = previous.get("configuration", {})
        current_contract = {
            key: value for key, value in configuration.items()
            if key != "pipeline_sha256"
        }
        cached_contract = {
            key: value for key, value in cached_configuration.items()
            if key != "pipeline_sha256"
        }
        if cached_contract == current_contract:
            if cached_configuration.get("pipeline_sha256") != configuration.get("pipeline_sha256"):
                print("Pipeline implementation hash changed; cached outputs will be reused only after record validation.")
            for key in ("bell_runs", "benchmark_runs", "penalty_optimizations", "penalty_runs"):
                previous.setdefault(key, {})
            orphan_path = path.with_suffix(path.suffix + ".tmp")
            if orphan_path.exists():
                try:
                    orphan = json.loads(orphan_path.read_text(encoding="utf-8"))
                    orphan_configuration = orphan.get("configuration", {})
                    orphan_contract = {
                        key: value for key, value in orphan_configuration.items()
                        if key != "pipeline_sha256"
                    }
                    if orphan_contract == current_contract:
                        recovered = 0
                        for section in ("bell_runs", "benchmark_runs", "penalty_optimizations", "penalty_runs"):
                            for record_key, record in orphan.get(section, {}).items():
                                previous[section][record_key] = record
                                recovered += 1
                        print(f"Recovered {recovered} checkpoint records from the interrupted OneDrive temp file.")
                        _atomic_json(path, previous)
                        orphan_path.unlink(missing_ok=True)
                    else:
                        print("Orphaned temp checkpoint is incompatible; leaving it untouched.")
                except (OSError, ValueError, TypeError) as error:
                    print(f"Orphaned temp checkpoint could not be recovered ({error}); leaving it untouched.")
            print("Loaded compatible Phase 2 experiment checkpoint cache.")
            return previous
        stale = path.with_name(path.stem + ".incompatible-" + datetime.now().strftime("%Y%m%d-%H%M%S") + path.suffix)
        shutil.copy2(path, stale)
        print(f"Cache configuration changed; preserved the old cache at {stale.name} and recomputing.")
    except (OSError, ValueError, TypeError) as error:
        stale = path.with_name(path.stem + ".invalid-" + datetime.now().strftime("%Y%m%d-%H%M%S") + path.suffix)
        shutil.copy2(path, stale)
        print(f"Cache could not be read ({error}); preserved it at {stale.name} and recomputing.")
    return {
        "configuration": configuration,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "bell_runs": {},
        "benchmark_runs": {},
        "penalty_optimizations": {},
        "penalty_runs": {},
    }


def _save_experiment_cache(path: Path, cache: dict) -> None:
    cache["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _atomic_json(path, cache)


def _sample_statistics(counts: dict, instance: dict, exact: dict) -> dict:
    total_shots = int(sum(counts.values()))
    selection_counts = Counter()
    invalid_bitstrings = 0
    invalid_shots = 0
    for key, count in counts.items():
        bits = qff.counts_to_x(key)
        if len(bits) != instance["candidate_count"] or any(bit not in (0, 1) for bit in bits):
            invalid_bitstrings += 1
            invalid_shots += count
            continue
        selected_local = tuple(index for index, bit in enumerate(bits) if bit == 1)
        if len(selected_local) == K:
            selection_counts[selected_local] += count
        else:
            invalid_shots += count
    valid_shots = sum(selection_counts.values())
    valid_frequency = valid_shots / total_shots if total_shots else 0.0
    if selection_counts:
        selected_local = min(
            selection_counts,
            key=lambda selection: (-selection_counts[selection], tuple(instance["candidate_ids"][i] for i in selection)),
        )
        selected_ids = [instance["candidate_ids"][index] for index in selected_local]
        selected_reward = _objective(selected_local, instance)
        best_reward = max(_objective(selection, instance) for selection in selection_counts)
        objective_ratio = selected_reward / exact["f_star"]
    else:
        selected_ids = None
        selected_reward = None
        best_reward = None
        objective_ratio = None
    optimal_set = {tuple(ids) for ids in exact["optimal_ids"]}
    p_opt = sum(
        count for selection, count in selection_counts.items()
        if tuple(instance["candidate_ids"][i] for i in selection) in optimal_set
    ) / total_shots if total_shots else 0.0
    return {
        "shots": total_shots,
        "valid_frequency": valid_frequency,
        "p_opt": p_opt,
        "selected_candidate_ids": selected_ids,
        "selected_reward": selected_reward,
        "best_sampled_reward": best_reward,
        "objective_ratio": objective_ratio,
        "invalid_bitstring_keys": invalid_bitstrings,
        "invalid_shots": int(invalid_shots),
        "unique_valid_placements": len(selection_counts),
        "selection_counts": {
            ",".join(str(instance["candidate_ids"][i]) for i in selection): int(count)
            for selection, count in selection_counts.items()
        },
    }


def _sample_cache_is_valid(record: dict, instance: dict, exact: dict,
                           condition: str, processor_label: str,
                           penalty: float | None = None) -> bool:
    counts = record.get("counts")
    if not isinstance(counts, dict) or sum(counts.values()) != SHOTS:
        return False
    if record.get("shots") != SHOTS or record.get("condition") != condition:
        return False
    if record.get("processor") != processor_label:
        return False
    if penalty is not None and record.get("penalty") != penalty:
        return False
    calculated = _sample_statistics(counts, instance, exact)
    for metric in ("valid_frequency", "p_opt", "objective_ratio"):
        cached_value = record.get(metric)
        calculated_value = calculated[metric]
        if cached_value is None or calculated_value is None:
            if cached_value != calculated_value:
                return False
        elif not math.isclose(cached_value, calculated_value, rel_tol=0.0, abs_tol=1e-12):
            return False
    return True


def _run_bell(root: Path, processors: dict, cache: dict, cache_path: Path) -> list[dict]:
    processor = processors["D"]
    coupling = qff.coupling_map_from_edges(processor["edges"], processor["num_qubits"])
    edges = [tuple(edge) for edge in processor["edges"]]
    adjacent = min(edges)
    all_pairs = [(i, j) for i in range(processor["num_qubits"]) for j in range(i + 1, processor["num_qubits"])]
    max_distance = max(coupling.distance(*pair) for pair in all_pairs)
    farthest = min(pair for pair in all_pairs if coupling.distance(*pair) == max_distance)
    pair_specs = (("adjacent", adjacent), ("farthest", farthest))
    rows = []
    for pair_label, pair in pair_specs:
        for condition, noisy in (("ideal", False), ("noisy", True)):
            key = f"{pair_label}|{pair[0]}-{pair[1]}|{condition}"
            cached = cache["bell_runs"].get(key)
            bell_valid = bool(
                isinstance(cached, dict)
                and cached.get("shots") == SHOTS
                and cached.get("pair_distance") == coupling.distance(*pair)
                and cached.get("noisy") is noisy
                and all(field in cached for field in ("XX", "XX_se", "YY", "YY_se", "ZZ", "ZZ_se", "fidelity", "fidelity_se", "cx"))
            )
            if not bell_valid:
                if key in cache["bell_runs"]:
                    print(f"Bell cache row {key} is incomplete or incompatible; rerunning it.")
                print(f"Bell: {pair_label} pair {pair}, {condition}, {SHOTS} shots per basis.")
                result = qff.bell_experiment(
                    processor, physical_pair=pair, noisy=noisy, shots=SHOTS
                )
                result["pair"] = list(result["pair"])
                cache["bell_runs"][key] = result
                _save_experiment_cache(cache_path, cache)
            result = cache["bell_runs"][key]
            rows.append({
                "pair_label": pair_label,
                "physical_pair": json.dumps(result["pair"]),
                "pair_distance": result["pair_distance"],
                "condition": condition,
                "shots": result["shots"],
                "cx": result["cx"],
                "XX": result["XX"], "XX_se": result["XX_se"],
                "YY": result["YY"], "YY_se": result["YY_se"],
                "ZZ": result["ZZ"], "ZZ_se": result["ZZ_se"],
                "fidelity": result["fidelity"], "fidelity_se": result["fidelity_se"],
            })
    _write_csv(root / "results" / "tables" / "bell.csv", BELL_COLUMNS, rows)
    return rows


def _optimizer_for_instance(label: str, seed: int, penalty: float, instance: dict,
                            main_runs: dict, cache: dict, cache_path: Path) -> dict:
    key = f"{label}|P={penalty:g}|seed={seed}"
    cached = cache["penalty_optimizations"].get(key)
    if cached and not cached.get("reused_main_reference_penalty_optimization", False):
        return cached

    matrix = _qubo(instance, penalty)
    first = _optimize(matrix, seed, INITIAL_MAXITER)
    attempts = [first]
    if not first["optimizer_success"]:
        retry = _optimize(matrix, seed, RETRY_MAXITER)
        retry["retry_of_maxiter"] = INITIAL_MAXITER
        attempts.append(retry)
    usable = [trial for trial in attempts if trial["expected_qubo_energy"] is not None]
    best = min(usable, key=lambda trial: trial["expected_qubo_energy"]) if usable else None
    record = {
        "seed": seed,
        "initial_angles": _initial_angles(seed).tolist(),
        "optimized_angles": best["optimized_angles"] if best else None,
        "expected_qubo_energy": best["expected_qubo_energy"] if best else None,
        "optimizer_success": bool(best and best["optimizer_success"]),
        "optimizer_nfev": best["optimizer_nfev"] if best else 0,
        "optimizer_message": best["optimizer_message"] if best else "all attempts failed",
        "maxiter": best["maxiter"] if best else RETRY_MAXITER,
        "attempts": attempts,
        "reused_main_reference_penalty_optimization": False,
    }
    cache["penalty_optimizations"][key] = record
    _save_experiment_cache(cache_path, cache)
    return record


def _penalty_minimum(instance: dict, penalty: float) -> dict:
    matrix = _qubo(instance, penalty)
    n = len(instance["U"])
    states = []
    for integer in range(2**n):
        bitstring = format(integer, f"0{n}b")
        bits = qff.counts_to_x(bitstring)
        states.append((_qubo_energy(bits, matrix) + penalty * (K**2), bitstring, bits))
    minimum_energy = min(state[0] for state in states)
    minima = [state for state in states if math.isclose(state[0], minimum_energy, rel_tol=0.0, abs_tol=1e-12)]
    selected = min(minima, key=lambda state: state[1])
    return {
        "energy": float(minimum_energy),
        "bitstring": selected[1],
        "valid": int(sum(selected[2])) == K,
        "tied_minimum_count": len(minima),
    }


def _run_penalty_sweep(root: Path, instance: dict, exact: dict, main_runs: dict,
                       processors: dict, cache: dict, cache_path: Path) -> list[dict]:
    label = "L"
    processor = processors["D"]
    rows = []
    for penalty in PENALTY_VALUES:
        minimum = _penalty_minimum(instance, penalty)
        print(
            f"Penalty P={penalty:g}: QUBO minimum valid={minimum['valid']}; "
            f"energy={minimum['energy']:.9g}; tied minima={minimum['tied_minimum_count']}"
        )
        seed_results = {"ideal": [], "noisy": []}
        for seed in SEEDS:
            optimization = _optimizer_for_instance(
                label, seed, penalty, instance, main_runs, cache, cache_path
            )
            if optimization["optimized_angles"] is None:
                for condition in ("ideal", "noisy"):
                    seed_results[condition].append({
                        "seed": seed, "optimizer_success": False,
                        "error": "no usable optimized angle result",
                    })
                continue
            matrix = _qubo(instance, penalty)
            logical = _qaoa_circuit(matrix, optimization["optimized_angles"], measure=True)
            transpiled = qff.transpile_for(logical, processor)
            for condition, noisy in (("ideal", False), ("noisy", True)):
                key = f"L|D|P={penalty:g}|{condition}|seed={seed}"
                cached = cache["penalty_runs"].get(key)
                optimizer_key = f"{label}|P={penalty:g}|seed={seed}"
                cached_optimizer = cache["penalty_optimizations"].get(optimizer_key)
                if (
                    cached
                    and cached.get("optimized_angles") is None
                    and cached_optimizer
                    and cached_optimizer.get("optimized_angles") is not None
                    and cached.get("expected_qubo_energy") == cached_optimizer.get("expected_qubo_energy")
                    and cached.get("optimizer_nfev") == cached_optimizer.get("optimizer_nfev")
                    and cached.get("optimizer_success") == cached_optimizer.get("optimizer_success")
                ):
                    cached["optimized_angles"] = cached_optimizer["optimized_angles"]
                if not cached or not _sample_cache_is_valid(
                    cached, instance, exact, condition, "D", penalty
                ) or cached.get("optimized_angles") != optimization["optimized_angles"]:
                    if cached:
                        print(f"Penalty cache row {key} failed validation; rerunning it.")
                    backend = qff.simulator(noisy=noisy, processor=processor)
                    counts = backend.run(transpiled, shots=SHOTS).result().get_counts()
                    measured = _sample_statistics(counts, instance, exact)
                    cache["penalty_runs"][key] = {
                        "problem_id": "PS-O-OI-L", "processor": "D",
                        "penalty": penalty, "condition": condition,
                        "seed": seed, "optimizer_success": optimization["optimizer_success"],
                        "optimizer_nfev": optimization["optimizer_nfev"],
                        "optimizer_maxiter": optimization["maxiter"],
                        "expected_qubo_energy": optimization["expected_qubo_energy"],
                        "optimized_angles": optimization["optimized_angles"],
                        "counts": {str(bitstring): int(count) for bitstring, count in counts.items()},
                        **measured,
                    }
                    _save_experiment_cache(cache_path, cache)
                seed_results[condition].append(cache["penalty_runs"][key])

        for condition in ("ideal", "noisy"):
            measured_rows = seed_results[condition]
            for metric in ("valid_frequency", "p_opt", "objective_ratio"):
                values = [row[metric] for row in measured_rows if row.get(metric) is not None]
                mean = float(np.mean(values)) if values else None
                std = float(np.std(values, ddof=1)) if len(values) > 1 else (0.0 if values else None)
                if metric == "valid_frequency":
                    valid_mean, valid_std = mean, std
                elif metric == "p_opt":
                    p_opt_mean, p_opt_std = mean, std
                else:
                    ratio_mean, ratio_std = mean, std
            successes = sum(bool(row.get("optimizer_success")) for row in measured_rows)
            rows.append({
                "problem_id": "PS-O-OI-L", "processor": "D", "penalty": penalty,
                "condition": condition, "shots": SHOTS,
                "qubo_minimum_energy": minimum["energy"],
                "qubo_minimum_bitstring": minimum["bitstring"],
                "qubo_minimum_valid": str(minimum["valid"]).lower(),
                "valid_frequency": valid_mean, "valid_frequency_std": valid_std,
                "p_opt": p_opt_mean, "p_opt_std": p_opt_std,
                "objective_ratio": ratio_mean, "objective_ratio_std": ratio_std,
                "classical_optimum": exact["f_star"],
                "random_valid_frequency": exact["baseline"]["valid_frequency"],
                "random_p_opt": exact["baseline"]["p_opt"],
                "random_objective_ratio": exact["baseline"]["objective_ratio"],
                "optimizer": OPTIMIZER, "iteration_limit": RETRY_MAXITER,
                "seed_count": len(measured_rows), "successful_optimizations": successes,
                "failed_optimizations": len(measured_rows) - successes,
            })
    _write_csv(root / "results" / "tables" / "penalty_sweep.csv", PENALTY_COLUMNS, rows)
    return rows


def _run_benchmarks(root: Path, instances: dict, exact: dict, main_runs: dict,
                    processors: dict, cache: dict, cache_path: Path) -> tuple[list[dict], list[dict], dict]:
    seed_rows = []
    resource_metrics = {}
    for label, instance in instances.items():
        matrix = _qubo(instance, REFERENCE_PENALTY)
        processor_labels = ("B", "D") if label == "L" else ("A", "B", "D")
        for processor_label in processor_labels:
            processor = processors[processor_label]
            resources_key = f"{label}|{processor_label}"
            best_run = min(
                (run for run in main_runs[label] if run.get("optimized_angles") is not None),
                key=lambda run: run["expected_qubo_energy"],
            )
            logical_for_metrics = _qaoa_circuit(matrix, best_run["optimized_angles"], measure=True)
            resource_metrics[resources_key] = qff.circuit_metrics(logical_for_metrics, processor)
            for condition, noisy in (("ideal", False), ("noisy", True)):
                backend = qff.simulator(noisy=noisy, processor=processor)
                for optimization in main_runs[label]:
                    seed = optimization["seed"]
                    key = f"{label}|{processor_label}|{condition}|seed={seed}"
                    cached = cache["benchmark_runs"].get(key)
                    sample_valid = bool(
                        cached
                        and not cached.get("error")
                        and cached.get("optimized_angles") == optimization.get("optimized_angles")
                        and _sample_cache_is_valid(
                            cached, instance, exact[label], condition, processor_label
                        )
                    )
                    if not sample_valid:
                        if cached:
                            print(f"Benchmark cache row {key} failed validation; rerunning it.")
                        if optimization.get("optimized_angles") is None:
                            cache["benchmark_runs"][key] = {
                                "seed": seed, "error": "no optimized angles available",
                                "optimizer_success": False,
                            }
                        else:
                            logical = _qaoa_circuit(matrix, optimization["optimized_angles"], measure=True)
                            transpiled = qff.transpile_for(logical, processor)
                            counts = backend.run(transpiled, shots=SHOTS).result().get_counts()
                            measured = _sample_statistics(counts, instance, exact[label])
                            cache["benchmark_runs"][key] = {
                                "problem_id": f"PS-O-OI-{label}",
                                "processor": processor_label,
                                "condition": condition,
                                "seed": seed,
                                "optimizer_success": optimization["optimizer_success"],
                                "optimizer_any_attempt_converged": optimization["any_attempt_converged"],
                                "optimizer_nfev": optimization["optimizer_nfev"],
                                "optimizer_maxiter": optimization["optimizer_maxiter"],
                                "optimizer_message": optimization["optimizer_message"],
                                "optimizer_exception": optimization.get("optimizer_exception"),
                                "expected_qubo_energy": optimization["expected_qubo_energy"],
                                "optimized_angles": optimization["optimized_angles"],
                                "counts": {str(bitstring): int(count) for bitstring, count in counts.items()},
                                **measured,
                            }
                        _save_experiment_cache(cache_path, cache)
                    record = cache["benchmark_runs"][key]
                    if record.get("error"):
                        continue
                    seed_rows.append({
                        "problem_id": f"PS-O-OI-{label}",
                        "processor": processor_label,
                        "condition": condition,
                        "seed": seed,
                        "optimizer_success": str(optimization["optimizer_success"]).lower(),
                        "optimizer_any_attempt_converged": str(optimization["any_attempt_converged"]).lower(),
                        "optimizer_nfev": optimization["optimizer_nfev"],
                        "optimizer_maxiter": optimization["optimizer_maxiter"],
                        "optimizer_message": optimization["optimizer_message"],
                        "optimizer_exception": optimization.get("optimizer_exception"),
                        "expected_qubo_energy": record["expected_qubo_energy"],
                        "initial_step1a_attempt_success": optimization.get("initial_step1a_attempt_success"),
                        "optimizer_attempts_json": json.dumps(optimization.get("attempts", []), allow_nan=False),
                        "selected_candidate_ids": json.dumps(record["selected_candidate_ids"]),
                        "selected_reward": record["selected_reward"],
                        "best_sampled_reward": record["best_sampled_reward"],
                        "objective_ratio": record["objective_ratio"],
                        "valid_frequency": record["valid_frequency"],
                        "p_opt": record["p_opt"],
                        "shots": record["shots"],
                    })

    result_rows = []
    for label, instance in instances.items():
        processor_labels = ("A", "B", "D")
        for processor_label in processor_labels:
            executable = not (label == "L" and processor_label == "A")
            for condition in ("ideal", "noisy"):
                if not executable:
                    common = {
                        "problem_id": f"PS-O-OI-{label}", "processor": processor_label,
                        "condition": condition, "executable": "false",
                        "logical_qubits": instance["qubit_count"],
                        "physical_qubits": processors[processor_label]["num_qubits"],
                        "logical_cx": "", "cx": "", "depth": "", "two_q_depth": "",
                        "swaps": "", "cx_overhead": "", "shots": "",
                        "p_opt": "", "classical_optimum": "", "penalty": REFERENCE_PENALTY,
                    }
                    for metric in ("objective_ratio", "valid_frequency"):
                        result_rows.append({
                            **common, "quality_metric": metric,
                            "quality_value": "", "random_baseline": "",
                        })
                    continue

                per_seed = [
                    row for row in seed_rows
                    if row["problem_id"] == f"PS-O-OI-{label}"
                    and row["processor"] == processor_label
                    and row["condition"] == condition
                ]
                metrics = resource_metrics[f"{label}|{processor_label}"]
                aggregate_ratio = [row["objective_ratio"] for row in per_seed if row["objective_ratio"] is not None]
                aggregate_valid = [row["valid_frequency"] for row in per_seed]
                aggregate_p_opt = [row["p_opt"] for row in per_seed]
                values = {
                    "executable": "true",
                    "logical_qubits": metrics["logical_qubits"],
                    "physical_qubits": metrics["physical_qubits"],
                    "logical_cx": metrics["logical_cx"],
                    "cx": metrics["cx"],
                    "depth": metrics["depth"],
                    "two_q_depth": metrics["two_q_depth"],
                    "swaps": metrics["swaps"],
                    "cx_overhead": metrics["cx_overhead"],
                    "shots": SHOTS,
                    "p_opt": float(np.mean(aggregate_p_opt)) if aggregate_p_opt else 0.0,
                    "classical_optimum": exact[label]["f_star"],
                    "penalty": REFERENCE_PENALTY,
                }
                for metric, series, baseline in (
                    ("objective_ratio", aggregate_ratio, exact[label]["baseline"]["objective_ratio"]),
                    ("valid_frequency", aggregate_valid, exact[label]["baseline"]["valid_frequency"]),
                ):
                    result_rows.append({
                        "problem_id": f"PS-O-OI-{label}",
                        "processor": processor_label,
                        "condition": condition,
                        **values,
                        "quality_metric": metric,
                        "quality_value": float(np.mean(series)) if series else "",
                        "random_baseline": baseline,
                    })

    _write_csv(root / "results" / "tables" / "results.csv", RESULT_COLUMNS, result_rows)
    _write_csv(root / "results" / "tables" / "seed_runs.csv", SEED_COLUMNS, seed_rows)
    consistency_rows = []
    group_keys = sorted({
        (row["problem_id"], row["processor"], row["condition"])
        for row in seed_rows
    })
    for problem_id, processor_label, condition in group_keys:
        group = [
            row for row in seed_rows
            if row["problem_id"] == problem_id
            and row["processor"] == processor_label
            and row["condition"] == condition
        ]
        ratios = [row["objective_ratio"] for row in group if row["objective_ratio"] is not None]
        consistency_rows.append({
            "problem_id": problem_id,
            "processor": processor_label,
            "condition": condition,
            "seed_count": len(group),
            "objective_ratio_mean": float(np.mean(ratios)) if ratios else None,
            "objective_ratio_std": float(np.std(ratios, ddof=1)) if len(ratios) > 1 else (0.0 if ratios else None),
            "optimizer_success_count": sum(row["optimizer_success"] == "true" for row in group),
            "optimizer_any_attempt_converged_count": sum(row["optimizer_any_attempt_converged"] == "true" for row in group),
        })
    _write_csv(
        root / "results" / "tables" / "seed_consistency.csv",
        ["problem_id", "processor", "condition", "seed_count", "objective_ratio_mean", "objective_ratio_std", "optimizer_success_count", "optimizer_any_attempt_converged_count"],
        consistency_rows,
    )
    _atomic_json(root / "results" / "optimization" / "benchmark_resources.json", resource_metrics)
    return result_rows, seed_rows, resource_metrics


def _save_figures(root: Path, result_rows: list[dict], penalty_rows: list[dict]) -> None:
    figures = root / "results" / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    colors = {"A": "#2a9d8f", "B": "#e9c46a", "D": "#e76f51"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for axis, metric, title in (
        (axes[0], "objective_ratio", "Mean objective ratio"),
        (axes[1], "valid_frequency", "Mean valid-placement frequency"),
    ):
        relevant = [row for row in result_rows if row["condition"] == "noisy" and row["quality_metric"] == metric and row["executable"] == "true"]
        labels = [f"{row['problem_id'].split('-')[-1]} / {row['processor']}" for row in relevant]
        values = [float(row["quality_value"]) for row in relevant]
        bars = axis.bar(labels, values, color=[colors[row["processor"]] for row in relevant])
        axis.set_title(title)
        axis.set_ylabel("Ratio" if metric == "objective_ratio" else "Fraction of shots")
        axis.tick_params(axis="x", labelrotation=35)
        axis.bar_label(bars, fmt="%.3f", padding=2, fontsize=8)
        axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(figures / "benchmark_noisy_quality.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for condition, style in (("ideal", "o-"), ("noisy", "s--")):
        rows = sorted(
            [row for row in penalty_rows if row["condition"] == condition],
            key=lambda row: float(row["penalty"]),
        )
        penalties = [float(row["penalty"]) for row in rows]
        axes[0].plot(penalties, [float(row["valid_frequency"]) for row in rows], style, label=condition)
        axes[1].plot(penalties, [float(row["objective_ratio"]) if row["objective_ratio"] is not None else np.nan for row in rows], style, label=condition)
    axes[0].set_title("Penalty vs valid frequency")
    axes[0].set_ylabel("Fraction of shots")
    axes[1].set_title("Penalty vs objective ratio")
    axes[1].set_ylabel("Selected placement F / F*")
    for axis in axes:
        axis.set_xlabel("Reference penalty P")
        axis.set_xticks(PENALTY_VALUES)
        axis.grid(alpha=0.2)
        axis.legend()
    fig.tight_layout()
    fig.savefig(figures / "penalty_sweep.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def _save_circuit_figures(root: Path, circuits: dict) -> None:
    output_dir = root / "results" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    for label in ("logical", "B", "D"):
        circuit = circuits[label]
        drawing = circuit.draw(output="text", fold=100)
        text = str(drawing)
        stem = f"qaoa_{'logical' if label == 'logical' else f'processor_{label.lower()}'}_L"
        (output_dir / f"{stem}.txt").write_text(text + "\n", encoding="utf-8")
        lines = text.splitlines()
        height = min(28.0, max(5.0, len(lines) * 0.19))
        figure, axis = plt.subplots(figsize=(22, height), facecolor="white")
        axis.set_axis_off()
        axis.text(
            0.01, 0.99, text, va="top", ha="left",
            family="monospace", fontsize=5.5,
        )
        figure.tight_layout(pad=0.4)
        figure.savefig(output_dir / f"{stem}.png", dpi=160, bbox_inches="tight")
        plt.close(figure)


def _table_markdown(rows: list[dict], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                value = f"{value:.4f}"
            values.append(str(value))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, sep, *body])


def _generate_report(root: Path, result_rows: list[dict], seed_rows: list[dict],
                     bell_rows: list[dict], penalty_rows: list[dict], exact: dict,
                     optimization_runs: dict, resource_metrics: dict) -> None:
    noisy_l_b = [row for row in result_rows if row["problem_id"] == "PS-O-OI-L" and row["processor"] == "B" and row["condition"] == "noisy"]
    l_ratio = next(float(row["quality_value"]) for row in noisy_l_b if row["quality_metric"] == "objective_ratio")
    l_valid = next(float(row["quality_value"]) for row in noisy_l_b if row["quality_metric"] == "valid_frequency")
    random_ratio = exact["L"]["baseline"]["objective_ratio"]
    random_valid = exact["L"]["baseline"]["valid_frequency"]
    l_success = sum(bool(run["optimizer_success"]) for run in optimization_runs["L"])
    s_success = sum(bool(run["optimizer_success"]) for run in optimization_runs["S"])
    l_any_converged = sum(bool(run["any_attempt_converged"]) for run in optimization_runs["L"])
    s_any_converged = sum(bool(run["any_attempt_converged"]) for run in optimization_runs["S"])
    l_initial_failures = sum(run.get("initial_step1a_attempt_success") is False for run in optimization_runs["L"])
    s_initial_failures = sum(run.get("initial_step1a_attempt_success") is False for run in optimization_runs["S"])
    noisy_sweep = [row for row in penalty_rows if row["condition"] == "noisy"]
    valid_candidates = [row for row in noisy_sweep if row["valid_frequency"] is not None and row["objective_ratio"] is not None]
    best_penalty = max(valid_candidates, key=lambda row: row["valid_frequency"] * row["objective_ratio"]) if valid_candidates else None
    p0 = next(row for row in noisy_sweep if float(row["penalty"]) == 0.0)
    bell_summary = _table_markdown(bell_rows, ["pair_label", "physical_pair", "pair_distance", "condition", "XX", "XX_se", "YY", "YY_se", "ZZ", "ZZ_se", "fidelity", "fidelity_se"])
    result_summary = [row for row in result_rows if row["quality_metric"] in ("objective_ratio", "valid_frequency")]
    result_table = _table_markdown(result_summary, ["problem_id", "processor", "condition", "executable", "quality_metric", "quality_value", "p_opt", "classical_optimum", "random_baseline"])
    sweep_table = _table_markdown(noisy_sweep, ["penalty", "qubo_minimum_valid", "valid_frequency", "p_opt", "objective_ratio", "successful_optimizations", "failed_optimizations"])
    consistency_rows = []
    for problem_id, processor_label, condition in sorted({
        (row["problem_id"], row["processor"], row["condition"])
        for row in seed_rows
    }):
        group = [
            row for row in seed_rows
            if row["problem_id"] == problem_id
            and row["processor"] == processor_label
            and row["condition"] == condition
        ]
        ratios = [row["objective_ratio"] for row in group if row["objective_ratio"] is not None]
        consistency_rows.append({
            "problem_id": problem_id,
            "processor": processor_label,
            "condition": condition,
            "objective_ratio_mean": float(np.mean(ratios)) if ratios else None,
            "objective_ratio_std": float(np.std(ratios, ddof=1)) if len(ratios) > 1 else (0.0 if ratios else None),
        })
    consistency_table = _table_markdown(
        consistency_rows,
        ["problem_id", "processor", "condition", "objective_ratio_mean", "objective_ratio_std"],
    )
    resource_rows = [
        {"instance": key.split("|")[0], "processor": key.split("|")[1], **metrics}
        for key, metrics in resource_metrics.items()
    ]
    resource_table = _table_markdown(resource_rows, ["instance", "processor", "logical_cx", "cx", "depth", "two_q_depth", "swaps", "cx_overhead"])
    report = fr"""# Bio-Sniff QFF 2026 Phase 2 — PS-O-OI Results

## Scope and reproducibility

This report is generated from `results/tables/results.csv`, `bell.csv`, `penalty_sweep.csv`, and the checkpointed experiment records. The locked Phase 1-derived inputs are synthetic: nine candidate coordinates and generated coverage profiles, not measurements from a field. No real-field validation or quantum-advantage claim is made.

The objective is to select exactly three candidates and maximize $F(x)=0.60U(x)+0.25C(x)+0.15S(x)$. The minimized QUBO is $-F(x)+P(\sum_i x_i-3)^2$ with reference $P=3.0$. QAOA depth was $p=1$. Initial angles used `numpy.random.default_rng(seed)` for seeds 0–4 and were optimized using COBYLA against exact statevector probabilities. The official evaluation settings were {SHOTS} shots, transpiler/simulator seed {qff.SEED}, optimization level {qff.OPT_LEVEL}, basis `{','.join(qff.BASIS_GATES)}`, and official noise rates {qff.P1_DEPOL}/{qff.P2_DEPOL}/{qff.P_READOUT}.

The official `qff_phase2.py` helper supplied the simulator, transpilation, measurement bit-order conversion, circuit metrics, and Bell experiments. The required instance data and processor files were not changed. Optimizer termination status is recorded per seed in `results/tables/seed_runs.csv`; unsuccessful COBYLA termination is not described as convergence.

## Problem and exact reference

Instance L contains nine candidates and 84 feasible choose-three placements. Instance S is the locked five-candidate subset `[0,1,2,3,4]` and has 10 feasible placements. Exact enumeration gives:

| Instance | F* | Optimal candidate IDs | Random valid frequency | Random P_opt | Random objective ratio |
| --- | ---: | --- | ---: | ---: | ---: |
| L | {exact['L']['f_star']:.12f} | {exact['L']['optimal_ids']} | {exact['L']['baseline']['valid_frequency']:.6f} | {exact['L']['baseline']['p_opt']:.6f} | {exact['L']['baseline']['objective_ratio']:.6f} |
| S | {exact['S']['f_star']:.12f} | {exact['S']['optimal_ids']} | {exact['S']['baseline']['valid_frequency']:.6f} | {exact['S']['baseline']['p_opt']:.6f} | {exact['S']['baseline']['objective_ratio']:.6f} |

The random baseline is enumerated over all $2^n$ bitstrings. The objective ratio baseline is the mean reward over valid placements divided by $F^*$, as required by the Bio-Sniff deliverables.

## Bell-state verification

Processor D was tested on a directly connected pair and the lexicographically first farthest pair found from its graph distances. Each pair was evaluated under ideal and official noisy simulation using XX, YY, and ZZ measurements with 4096 shots per basis. Fidelity and its standard error use the helper's $F=(1+XX-YY+ZZ)/4$ convention.

{bell_summary}

The noisy channel applies depolarizing error after one- and two-qubit gates and symmetric measurement bit flips, reducing measured correlations and fidelity. A distant pair requires routing to bring the qubits together, adding entangling operations and exposure to the same synthetic gate noise. The model is uniform and does not model device-specific crosstalk.

## Processor D design and routing

Processor D is the frozen connected nine-qubit, 18-edge, degree-four circulant graph. Its diameter is 2. The topology diagram is `results/figures/processor_D_topology.png`; rationale and the measured routing probe are in `docs/processor_D_design.md`. It passes `validate_processor_d(D, 9)`.

The official resource metrics are emitted for each executable instance/processor from `circuit_metrics()`. The earlier fixed-angle routing diagnostic was not an optimized QAOA or noisy-quality benchmark. The current comparisons do not attribute any solution-quality benefit to D unless the measured result rows support it.

{resource_table}

The saved L circuit diagrams use the actual best available ideal angles: `results/figures/qaoa_logical_L.png`, `qaoa_processor_b_L.png`, and `qaoa_processor_d_L.png`. They visualize QAOA circuits and transpilation, not hardware execution.

## Main benchmark

The table below reports means over the five initialization seeds for both ideal and noisy conditions. Each seed used the same ideal-optimized angles for ideal and noisy evaluation on the processor. `objective_ratio` is the reward of the most frequently sampled valid placement divided by $F^*$; `valid_frequency` is the fraction of all shots that are feasible. The per-seed table records selected placements, best sampled reward, P_opt, and optimizer status. Processor A is explicitly non-executable for L because it has five qubits and L requires nine.

{result_table}

Per-initialization objective-ratio consistency (mean and sample standard deviation):

{consistency_table}

For noisy L on B, the mean objective ratio is {l_ratio:.6f} versus the uniform-random ratio {random_ratio:.6f} (difference {l_ratio-random_ratio:+.6f}); mean valid frequency is {l_valid:.6f} versus random {random_valid:.6f} (difference {l_valid-random_valid:+.6f}). This is a comparison on the synthetic benchmark, not evidence of quantum advantage. The preserved Step 1A 60-evaluation starts had {l_initial_failures}/5 L and {s_initial_failures}/5 S limit/non-success statuses. The subsequent 150-evaluation retries and best-energy attempts are recorded separately; the best-energy attempts had {l_success}/5 successful final COBYLA statuses for L and {s_success}/5 for S, and at least one attempt converged for {l_any_converged}/5 L seeds and {s_any_converged}/5 S seeds. See the seed table for the per-attempt history and termination messages.

## Penalty sensitivity

The sweep uses Instance L on Processor D. Angles were independently re-optimized for every P, including P=3, from the five required seeds. Both ideal and noisy conditions use the same per-seed optimized angles and 4096 shots. The QUBO minimum validity is determined by exhaustive enumeration of all bitstrings, not inferred from QAOA samples.

{sweep_table}

At P=0, the noisy QUBO minimum is valid: **{p0['qubo_minimum_valid']}**; sampled valid frequency is {p0['valid_frequency'] if p0['valid_frequency'] is not None else 'unavailable'} and objective ratio is {p0['objective_ratio'] if p0['objective_ratio'] is not None else 'unavailable'}. Across the noisy sweep, the maximum of valid-frequency × objective-ratio occurs at P={best_penalty['penalty'] if best_penalty else 'undetermined'}; this product is a descriptive team-selected balance indicator, not an official scoring metric. The full values and standard deviations are in `penalty_sweep.csv`.

## Limitations and next steps

The candidate grid, source locations, wind displacement, coverage values, utility, complementarity, and spacing are synthetic. They do not establish measured VOC transport, calibrated detection probability, a disease-specific signal, or the best placement for a physical farm. Field use would require calibrated sensors, documented candidate coordinates, validated plume/dispersion assumptions, and controlled field measurements. The QAOA results are simulated and do not establish a quantum advantage over classical optimization.

This milestone did not run a real hardware experiment. Reproducibility artifacts include the locked input hash, processor hashes, package versions, official settings, seeds, optimizer attempts, shot counts, and raw sampled count maps in `results/optimization/phase2_experiment_cache.json`.
"""
    (root / "report.md").write_text(report, encoding="utf-8")


def run_pipeline(root: Path) -> dict:
    root = Path(root).resolve()
    instance_path = root / "data" / "instance.json"
    processor_paths = {
        label: root / "processors" / f"processor_{label}.json"
        for label in ("A", "B", "D")
    }
    required = [root / "qff_phase2.py", instance_path, *processor_paths.values()]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required project files: " + ", ".join(map(str, missing)))
    for folder in (
        root / "results" / "tables", root / "results" / "figures",
        root / "results" / "optimization",
    ):
        folder.mkdir(parents=True, exist_ok=True)

    instance_document = json.loads(instance_path.read_text(encoding="utf-8"))
    objective = instance_document["objective"]
    if objective["weights"] != WEIGHTS or objective["selection_count"] != K or objective["reference_penalty_P"] != REFERENCE_PENALTY:
        raise ValueError("Locked objective configuration differs from the official Bio-Sniff specification.")
    instances = instance_document["instances"]
    exact = {label: _enumerate_instance(instance) for label, instance in instances.items()}
    processors = {label: qff.load_processor(str(path)) for label, path in processor_paths.items()}
    violations = qff.validate_processor_d(processors["D"], required_qubits=9)
    if violations:
        raise ValueError(f"Frozen Processor D validation failed: {violations}")

    config = _configuration(root)
    optimization_runs, prior = _main_optimizations(root, config, instances)
    circuits = _main_circuit_objects(instances, optimization_runs, processors)
    _save_circuit_figures(root, circuits)
    cache_path = root / "results" / "optimization" / "phase2_experiment_cache.json"
    cache = _load_experiment_cache(cache_path, config)
    bell_rows = _run_bell(root, processors, cache, cache_path)
    result_rows, seed_rows, resource_metrics = _run_benchmarks(
        root, instances, exact, optimization_runs, processors, cache, cache_path
    )
    penalty_rows = _run_penalty_sweep(
        root, instances["L"], exact["L"], optimization_runs,
        processors, cache, cache_path,
    )
    _save_figures(root, result_rows, penalty_rows)
    _generate_report(
        root, result_rows, seed_rows, bell_rows, penalty_rows, exact,
        optimization_runs, resource_metrics,
    )

    cache["optimization_status"] = optimization_runs
    cache["results_generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _save_experiment_cache(cache_path, cache)
    print("Final artifacts written: results/tables/{bell,results,seed_runs,penalty_sweep}.csv; results/figures; report.md")
    return {
        "root": root,
        "exact": exact,
        "optimization_runs": optimization_runs,
        "bell_rows": bell_rows,
        "result_rows": result_rows,
        "seed_rows": seed_rows,
        "penalty_rows": penalty_rows,
        "resource_metrics": resource_metrics,
        "cache_path": cache_path,
        "main_circuits": circuits,
    }


def _main_circuit_objects(instances: dict, optimization_runs: dict, processors: dict) -> dict:
    instance = instances["L"]
    matrix = _qubo(instance, REFERENCE_PENALTY)
    completed = [run for run in optimization_runs["L"] if run.get("optimized_angles") is not None]
    best = min(completed, key=lambda row: row["expected_qubo_energy"])
    logical = _qaoa_circuit(matrix, best["optimized_angles"], measure=True)
    return {
        "logical": logical,
        "B": qff.transpile_for(logical, processors["B"]),
        "D": qff.transpile_for(logical, processors["D"]),
        "best_seed": best["seed"],
        "best_seed_converged": best["optimizer_success"],
    }