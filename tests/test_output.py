import json
import math

PATH = "/app/output.json"
POINTS = ["M17", "M23", "M31", "M44", "M52", "M68"]

CARRIER_AMBIGUITIES = {
    "R03": 164, "R07": 76, "R11": 103, "R14": 134, "R19": 115, "R22": 119,
    "R27": 175, "R31": 72, "R36": 78, "R42": 146, "R47": 165, "R53": 97,
    "R58": 90, "R64": 149, "R69": 83, "R73": 106, "R81": 163, "R88": 94,
}
CARRIER_RUNNER_UP = dict(CARRIER_AMBIGUITIES, R31=73)
CARRIER_TARGET_MAPPING = {
    "T2": "M31", "T5": "M17", "T8": "M68", "T11": "M44", "T14": "M23", "T17": "M52",
}
CARRIER_FIXED_SS = 37.765001660621785
CARRIER_RUNNER_SS = 41.63140753816763
CARRIER_GAP = 3.8664058775458443
CARRIER_TOTAL = {
    "M17": (0.028082659837814578, -0.023989509134618017),
    "M23": (0.04345827707291187, -0.006367562733711614),
    "M31": (0.04807297717202779, 0.015317411549665679),
    "M44": (0.007130790313103793, -0.010149930085227691),
    "M52": (-0.005324238937144416, -0.03486917940351923),
    "M68": (0.054591525745104036, 0.028045286078961115),
}

CLOSING = {
    "angle_model_code": "C52",
    "angle_weighted_ss": 183.47442679316086,
    "range_model_code": "D41",
    "range_weighted_ss": 14.680432697519597,
    "circle_sense": {"Q4": 1, "Q9": -1},
    "target_mapping": {"X2": "M44", "X5": "M17", "X8": "M68", "X11": "M23", "X14": "M52", "X17": "M31"},
    "setups": {
        "S3": {"east_m": 1042.73510213622, "north_m": 1998.412162525233, "orientation_rad": 0.7129982071614608, "rms_m": 0.0019362693495373821},
        "S8": {"east_m": 1074.1883892690014, "north_m": 2184.626952261027, "orientation_rad": -1.1320027857107284, "rms_m": 0.001533410792836276},
    },
    "interstation_baseline_m": 188.85247466687616,
    "interstation_azimuth_rad": 0.16732926194527784,
    "closure_rms_m": 0.0017464947256640505,
    "runner_up_closure_rms_m": 19.423388576577377,
}


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def angular_error_rad(got, expected):
    return abs((got - expected + math.pi) % (2.0 * math.pi) - math.pi)


def test_output():
    with open(PATH) as handle:
        result = json.load(handle)

    assert set(result) == {"carrier_reconstruction", "closing_resection"}

    carrier = result["carrier_reconstruction"]
    assert set(carrier) == {
        "final_epoch_id",
        "target_mapping",
        "runner_up_target_mapping",
        "ambiguities",
        "runner_up_ambiguities",
        "fixed_weighted_ss",
        "runner_up_weighted_ss",
        "ambiguity_gap",
        "final_total_displacements",
    }
    assert carrier["final_epoch_id"] == "K09"
    assert carrier["target_mapping"] == CARRIER_TARGET_MAPPING
    assert carrier["runner_up_target_mapping"] == CARRIER_TARGET_MAPPING

    ambiguities = carrier["ambiguities"]
    runner_up = carrier["runner_up_ambiguities"]
    assert set(ambiguities) == set(CARRIER_AMBIGUITIES)
    assert set(runner_up) == set(CARRIER_RUNNER_UP)
    for arc_id, expected in CARRIER_AMBIGUITIES.items():
        assert isinstance(ambiguities[arc_id], int) and not isinstance(ambiguities[arc_id], bool)
        assert ambiguities[arc_id] == expected
    for arc_id, expected in CARRIER_RUNNER_UP.items():
        assert isinstance(runner_up[arc_id], int) and not isinstance(runner_up[arc_id], bool)
        assert runner_up[arc_id] == expected

    for key, expected in (
        ("fixed_weighted_ss", CARRIER_FIXED_SS),
        ("runner_up_weighted_ss", CARRIER_RUNNER_SS),
        ("ambiguity_gap", CARRIER_GAP),
    ):
        assert numeric(carrier[key])
        assert abs(carrier[key] - expected) <= 0.05

    totals = carrier["final_total_displacements"]
    assert set(totals) == set(POINTS)
    for point in POINTS:
        assert set(totals[point]) == {"d_east_m", "d_north_m"}
        east = totals[point]["d_east_m"]
        north = totals[point]["d_north_m"]
        assert numeric(east) and numeric(north)
        expected_east, expected_north = CARRIER_TOTAL[point]
        assert abs(east - expected_east) <= 0.022
        assert abs(north - expected_north) <= 0.022

    closing = result["closing_resection"]
    assert set(closing) == {
        "angle_model_code",
        "angle_weighted_ss",
        "range_model_code",
        "range_weighted_ss",
        "circle_sense",
        "target_mapping",
        "setups",
        "interstation_baseline_m",
        "interstation_azimuth_rad",
        "closure_rms_m",
        "runner_up_closure_rms_m",
    }
    assert closing["angle_model_code"] == CLOSING["angle_model_code"]
    assert closing["range_model_code"] == CLOSING["range_model_code"]
    assert closing["circle_sense"] == CLOSING["circle_sense"]
    assert closing["target_mapping"] == CLOSING["target_mapping"]

    assert numeric(closing["angle_weighted_ss"])
    assert abs(closing["angle_weighted_ss"] - CLOSING["angle_weighted_ss"]) <= 0.75
    assert numeric(closing["range_weighted_ss"])
    assert abs(closing["range_weighted_ss"] - CLOSING["range_weighted_ss"]) <= 0.30

    setups = closing["setups"]
    assert set(setups) == {"S3", "S8"}
    for setup_id in ("S3", "S8"):
        got = setups[setup_id]
        expected = CLOSING["setups"][setup_id]
        assert set(got) == {"east_m", "north_m", "orientation_rad", "rms_m"}
        for key in got:
            assert numeric(got[key])
        assert abs(got["east_m"] - expected["east_m"]) <= 0.010
        assert abs(got["north_m"] - expected["north_m"]) <= 0.010
        assert angular_error_rad(got["orientation_rad"], expected["orientation_rad"]) <= 0.00012
        assert abs(got["rms_m"] - expected["rms_m"]) <= 0.0010

    assert numeric(closing["interstation_baseline_m"])
    assert abs(closing["interstation_baseline_m"] - CLOSING["interstation_baseline_m"]) <= 0.015
    assert numeric(closing["interstation_azimuth_rad"])
    assert angular_error_rad(closing["interstation_azimuth_rad"], CLOSING["interstation_azimuth_rad"]) <= 0.00012
    assert numeric(closing["closure_rms_m"])
    assert abs(closing["closure_rms_m"] - CLOSING["closure_rms_m"]) <= 0.0010
    assert numeric(closing["runner_up_closure_rms_m"])
    assert abs(closing["runner_up_closure_rms_m"] - CLOSING["runner_up_closure_rms_m"]) <= 0.050
