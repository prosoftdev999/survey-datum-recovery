"""Reviewer-side near misses for the two-stage carrier/resection task."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "environment" / "data"
SPEC = importlib.util.spec_from_file_location("reference", ROOT / "solution" / "solve.py")
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
reference.DATA_DIR = DATA


def correct_result():
    site, trend = reference.load_handoff()
    carrier_full = reference.recover_carrier(site, trend)
    carrier = {
        key: carrier_full[key]
        for key in (
            "final_epoch_id",
            "target_mapping",
            "runner_up_target_mapping",
            "ambiguities",
            "runner_up_ambiguities",
            "fixed_weighted_ss",
            "runner_up_weighted_ss",
            "ambiguity_gap",
            "final_total_displacements",
        )
    }
    return site, trend, carrier_full, {
        "carrier_reconstruction": carrier,
        "closing_resection": reference.recover_closing_resection(site, carrier_full),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "variant",
        choices=["carrier-rounding", "carrier-first-map", "closing-wrong-sense", "closing-wrong-model"],
    )
    parser.add_argument("output")
    args = parser.parse_args()

    site, trend, carrier_full, result = correct_result()
    carrier = result["carrier_reconstruction"]
    closing = result["closing_resection"]

    if args.variant == "carrier-rounding":
        system = reference.build_carrier_system(site, carrier_full["target_mapping"])
        center, _ = reference.carrier_float_problem(system)
        rounded = [int(round(value)) for value in center]
        _, rounded_ss = reference.refit_carrier(system, rounded)
        carrier["ambiguities"] = {
            arc_id: rounded[i] for i, arc_id in enumerate(system["arc_ids"])
        }
        carrier["fixed_weighted_ss"] = rounded_ss
        carrier["ambiguity_gap"] = carrier["runner_up_weighted_ss"] - rounded_ss

    elif args.variant == "carrier-first-map":
        wrong_mapping = reference.carrier_target_candidates(site)[0][1]
        system = reference.build_carrier_system(site, wrong_mapping)
        center, precision = reference.carrier_float_problem(system)
        integers, _ = reference.two_best_integer_vectors(center, precision)
        _, wrong_ss = reference.refit_carrier(system, integers)
        carrier["target_mapping"] = wrong_mapping
        carrier["ambiguities"] = {
            arc_id: integers[i] for i, arc_id in enumerate(system["arc_ids"])
        }
        carrier["fixed_weighted_ss"] = wrong_ss
        carrier["ambiguity_gap"] = carrier["runner_up_weighted_ss"] - wrong_ss

    elif args.variant == "closing-wrong-sense":
        closing["circle_sense"] = {
            key: -value for key, value in closing["circle_sense"].items()
        }

    else:
        closing["angle_model_code"] = "C17"

    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
