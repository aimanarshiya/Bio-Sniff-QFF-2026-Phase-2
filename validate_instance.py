"""Build once or validate the locked Bio-Sniff Phase 2 instance data."""

from __future__ import annotations

import argparse
import ast
import csv
import itertools
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
INSTANCE_PATH = ROOT / "data" / "instance.json"
PHASE1_RESULTS_PATH = (
    ROOT.parent
    / "BIO-SNIFF-QFF-2026-PHASE-1"
    / "results"
    / "biosniff_processor_A_B_results.csv"
)
SEED = 42
N_SCENARIOS = 24
K_SELECTED = 3
PENALTY = 3.0
WEIGHTS = {"U": 0.60, "C": 0.25, "S": 0.15}


def build_synthetic_problem(seed=SEED, n_scenarios=N_SCENARIOS):
    rng = np.random.default_rng(seed)

    coords = np.array([
        [0, 0], [1, 0], [2, 0],
        [0, 1], [1, 1], [2, 1],
        [0, 2], [1, 2], [2, 2]
    ], dtype=float)

    sources = rng.uniform(0, 2, size=(n_scenarios, 2))
    wind_angles = rng.uniform(0, 2 * np.pi, size=n_scenarios)
    wind_shift = 0.30 * np.column_stack([
        np.cos(wind_angles), np.sin(wind_angles)
    ])
    shifted_sources = sources + wind_shift

    sigma = 0.70
    coverage = np.zeros((len(coords), n_scenarios))

    for i, point in enumerate(coords):
        distances_sq = np.sum(
            (shifted_sources - point) ** 2, axis=1
        )
        coverage[i] = np.exp(
            -distances_sq / (2 * sigma**2)
        )

    utility = coverage.mean(axis=1)

    complementarity = np.zeros((9, 9))
    for i in range(9):
        for j in range(9):
            a, b = coverage[i], coverage[j]
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            similarity = np.dot(a, b) / denom if denom else 0.0
            complementarity[i, j] = 1.0 - np.clip(
                similarity, 0.0, 1.0
            )

    distances = np.linalg.norm(
        coords[:, None, :] - coords[None, :, :], axis=2
    )
    max_distance = distances.max()
    spacing = distances / max_distance if max_distance else distances

    return coords, coverage, utility, complementarity, spacing


def placement_reward(selected, utility, complementarity, spacing):
    reward = 0.60 * sum(utility[i] for i in selected)

    for a, i in enumerate(selected):
        for j in selected[a + 1:]:
            reward += 0.25 * complementarity[i, j]
            reward += 0.15 * spacing[i, j]

    return float(reward)


def exact_classical_solution(utility, complementarity, spacing):
    utility = np.asarray(utility, dtype=float)
    complementarity = np.asarray(complementarity, dtype=float)
    spacing = np.asarray(spacing, dtype=float)
    best_score = -np.inf
    best_selection = None

    for selection in itertools.combinations(range(len(utility)), K_SELECTED):
        score = placement_reward(
            selection, utility, complementarity, spacing
        )
        if score > best_score:
            best_score = score
            best_selection = selection

    return tuple(best_selection), float(best_score)


def make_instance(name, candidate_ids, coords, coverage, utility,
                  complementarity, spacing):
    candidate_ids = list(candidate_ids)
    local_coords = coords[candidate_ids]
    local_coverage = coverage[candidate_ids]
    local_utility = utility[candidate_ids]
    local_complementarity = complementarity[
        np.ix_(candidate_ids, candidate_ids)
    ]
    local_spacing = spacing[np.ix_(candidate_ids, candidate_ids)]
    optimum_local, optimum_value = exact_classical_solution(
        local_utility, local_complementarity, local_spacing
    )

    return {
        "name": name,
        "candidate_ids": candidate_ids,
        "candidate_count": len(candidate_ids),
        "qubit_count": len(candidate_ids),
        "selection_count": K_SELECTED,
        "valid_placement_count": len(
            list(itertools.combinations(candidate_ids, K_SELECTED))
        ),
        "candidates": [
            {
                "candidate_id": candidate_id,
                "qubit": qubit,
                "coordinates": local_coords[qubit].tolist(),
            }
            for qubit, candidate_id in enumerate(candidate_ids)
        ],
        "coverage": local_coverage.tolist(),
        "U": local_utility.tolist(),
        "C": local_complementarity.tolist(),
        "S": local_spacing.tolist(),
        "classical_optimum": {
            "objective_value": optimum_value,
            "candidate_ids": [candidate_ids[i] for i in optimum_local],
        },
    }


def build_instance_document():
    coords, coverage, utility, complementarity, spacing = (
        build_synthetic_problem(seed=SEED, n_scenarios=N_SCENARIOS)
    )
    return {
        "schema_version": 1,
        "problem_id": "PS-O-OI",
        "source": {
            "repository": "BIO-SNIFF-QFF-2026-PHASE-1",
            "notebook": "notebooks/BioSniff_QAOA_Synthetic_Benchmark.ipynb",
            "function": "build_synthetic_problem(seed=42, n_scenarios=24)",
            "seed": SEED,
            "n_scenarios": N_SCENARIOS,
            "coordinate_units": "unitless synthetic 3x3 grid",
            "coverage_model": {
                "wind_displacement": 0.30,
                "sigma": 0.70,
                "utility_definition": "mean coverage over scenarios",
                "complementarity_definition": (
                    "1 - clipped cosine similarity of candidate coverage profiles"
                ),
                "spacing_definition": (
                    "Euclidean distance divided by the maximum grid distance"
                ),
            },
        },
        "objective": {
            "expression": "F(x) = 0.60 U(x) + 0.25 C(x) + 0.15 S(x)",
            "weights": WEIGHTS,
            "selection_count": K_SELECTED,
            "reference_penalty_P": PENALTY,
            "qubo_energy": "E(x) = -F(x) + P * (sum(x) - 3)^2",
            "pairwise_convention": "sum over unique pairs i < j",
        },
        "instances": {
            "L": make_instance(
                "nine-candidate instance",
                range(9), coords, coverage, utility, complementarity, spacing,
            ),
            "S": make_instance(
                "original five-candidate subset",
                [0, 1, 2, 3, 4], coords, coverage, utility,
                complementarity, spacing,
            ),
        },
    }


def validate_instance_document(document):
    expected = build_instance_document()
    if document.get("schema_version") != expected["schema_version"]:
        raise AssertionError("Unexpected schema_version")
    if document.get("problem_id") != expected["problem_id"]:
        raise AssertionError("Unexpected problem_id")
    if document.get("source") != expected["source"]:
        raise AssertionError("Source metadata differs from Phase 1 generator")
    if document.get("objective") != expected["objective"]:
        raise AssertionError("Weights, cardinality, or penalty differ")

    for label in ("L", "S"):
        actual = document["instances"][label]
        original = expected["instances"][label]
        for key in (
            "name", "candidate_ids", "candidate_count", "qubit_count",
            "selection_count", "valid_placement_count", "candidates",
            "classical_optimum",
        ):
            if actual[key] != original[key]:
                raise AssertionError(f"Instance {label}: {key} mismatch")

        for key in ("coverage", "U", "C", "S"):
            if not np.array_equal(
                np.asarray(actual[key], dtype=float),
                np.asarray(original[key], dtype=float),
            ):
                raise AssertionError(
                    f"Instance {label}: {key} differs from regenerated Phase 1 data"
                )

        n = actual["candidate_count"]
        if np.asarray(actual["coverage"]).shape != (n, N_SCENARIOS):
            raise AssertionError(f"Instance {label}: invalid coverage dimensions")
        if np.asarray(actual["U"]).shape != (n,):
            raise AssertionError(f"Instance {label}: invalid U dimensions")
        if np.asarray(actual["C"]).shape != (n, n):
            raise AssertionError(f"Instance {label}: invalid C dimensions")
        if np.asarray(actual["S"]).shape != (n, n):
            raise AssertionError(f"Instance {label}: invalid S dimensions")

        optimum_local, optimum_value = exact_classical_solution(
            actual["U"], actual["C"], actual["S"]
        )
        optimum_ids = [actual["candidate_ids"][i] for i in optimum_local]
        if optimum_value != actual["classical_optimum"]["objective_value"]:
            raise AssertionError(f"Instance {label}: stored optimum value mismatch")
        if optimum_ids != actual["classical_optimum"]["candidate_ids"]:
            raise AssertionError(f"Instance {label}: stored optimum candidates mismatch")

    return expected


def compare_phase1_results(document):
    if not PHASE1_RESULTS_PATH.exists():
        print("Historical Phase 1 CSV comparison: skipped (CSV not found).")
        return

    with PHASE1_RESULTS_PATH.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))

    references = {
        "L": "Processor B — full 9-candidate problem",
        "S": "Processor A — 5-candidate study",
    }
    for label, processor_label in references.items():
        historical = next(
            row for row in rows if row["processor"] == processor_label
        )
        old_value = float(historical["classical_optimum_reward"])
        old_candidates = ast.literal_eval(
            historical["classical_optimum_candidates"]
        )
        current = document["instances"][label]["classical_optimum"]
        matches = (
            current["objective_value"] == old_value
            and current["candidate_ids"] == old_candidates
        )
        if not matches:
            raise AssertionError(
                f"Instance {label}: recomputed optimum differs from historical Phase 1 CSV"
            )
        print(
            f"Instance {label}: historical Phase 1 optimum matches "
            f"(reference only): {current['objective_value']!r} "
            f"at {current['candidate_ids']}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Create data/instance.json if it does not already exist.",
    )
    args = parser.parse_args()

    if args.write:
        if INSTANCE_PATH.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing file: {INSTANCE_PATH}"
            )
        INSTANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with INSTANCE_PATH.open("x", encoding="utf-8") as output:
            json.dump(build_instance_document(), output, indent=2, allow_nan=False)
            output.write("\n")

    with INSTANCE_PATH.open(encoding="utf-8") as source:
        document = json.load(source)

    validate_instance_document(document)
    print("Instance L: validated 84/84 valid placements.")
    print("Instance S: validated 10/10 valid placements.")
    compare_phase1_results(document)


if __name__ == "__main__":
    main()