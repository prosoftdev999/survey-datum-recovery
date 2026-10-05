import csv
import itertools
import json
import math
from pathlib import Path

DATA_DIR = Path("/app/data")
OUTPUT_PATH = Path("/app/output.json")

def read_csv(name):
    with (DATA_DIR / name).open(newline="") as handle:
        return list(csv.DictReader(handle))

def load_handoff():
    with (DATA_DIR / "control_handoff.json").open() as handle:
        raw = json.load(handle)
    site = {
        point: (values["east_m"], values["north_m"])
        for point, values in raw["site_coordinates"].items()
    }
    trend = {"final_epoch_displacements": raw["prior_epoch_displacements"]}
    return site, trend

def solve_linear(matrix, vector):
    n = len(vector)
    aug = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        if abs(scale) < 1e-14:
            raise RuntimeError("singular system")
        aug[col] = [v / scale for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [aug[i][-1] for i in range(n)]


def least_squares(rows, values, sigmas=None):
    p = len(rows[0])
    normal = [[0.0] * p for _ in range(p)]
    rhs = [0.0] * p
    if sigmas is None:
        sigmas = [1.0] * len(rows)
    for row, value, sigma in zip(rows, values, sigmas):
        w = 1.0 / (sigma * sigma)
        for i in range(p):
            rhs[i] += w * row[i] * value
            for j in range(p):
                normal[i][j] += w * row[i] * row[j]
    return solve_linear(normal, rhs)




def matrix_vec(matrix, vector):
    return (
        matrix[0][0] * vector[0] + matrix[0][1] * vector[1],
        matrix[1][0] * vector[0] + matrix[1][1] * vector[1],
    )




def carrier_target_candidates(site):
    arc_rows = read_csv("carrier_arcs.csv")
    tokens = sorted(
        {row["target_token"] for row in arc_rows}, key=lambda value: int(value[1:])
    )
    points = sorted(site)
    checks = read_csv("carrier_target_checks.csv")
    candidates = []
    for point_order in itertools.permutations(points):
        mapping = dict(zip(tokens, point_order))
        acceptable = True
        check_ss = 0.0
        for row in checks:
            a = mapping[row["token_a"]]
            b = mapping[row["token_b"]]
            distance = math.hypot(site[b][0] - site[a][0], site[b][1] - site[a][1])
            sigma = float(row["sigma_m"])
            residual = (distance - float(row["distance_m"])) / sigma
            if abs(residual) > 3.0:
                acceptable = False
                break
            check_ss += residual * residual
        if acceptable:
            candidates.append((check_ss, mapping))
    if not candidates:
        raise RuntimeError("no carrier target assignment passes the commissioning checks")
    candidates.sort(
        key=lambda item: (
            item[0],
            tuple(item[1][token] for token in tokens),
        )
    )
    return candidates

def build_carrier_system(site, target_mapping):
    epochs = {
        row["epoch_id"]: (float(row["elapsed_day"]), float(row["load_index"]))
        for row in read_csv("carrier_epochs.csv")
    }
    arcs = {
        row["arc_id"]: (row["target_token"], float(row["wavelength_m"]))
        for row in read_csv("carrier_arcs.csv")
    }
    arc_ids = sorted(arcs, key=lambda value: int(value[1:]))
    arc_index = {arc_id: i for i, arc_id in enumerate(arc_ids)}
    geometry = {
        (row["epoch_id"], row["arc_id"]):
        (float(row["east_los"]), float(row["north_los"]))
        for row in read_csv("carrier_geometry.csv")
    }

    points = sorted(site)
    mean_e = sum(site[p][0] for p in points) / len(points)
    mean_n = sum(site[p][1] for p in points) / len(points)
    centered = {p: (site[p][0] - mean_e, site[p][1] - mean_n) for p in points}

    datum_weights = {
        row["point_id"]: float(row["weight"]) for row in read_csv("datum_weights.csv")
    }
    total_weight = sum(datum_weights.values())
    weighted_q = (
        sum(datum_weights[p] * centered[p][0] for p in points) / total_weight,
        sum(datum_weights[p] * centered[p][1] for p in points) / total_weight,
    )

    continuous_rows = []
    ambiguity_rows = []
    values = []
    sigmas = []

    def continuous_row(point, load, los):
        f1 = load
        f2 = load * (load - 0.55)
        x, y = centered[point]
        ux, uy = los
        return [
            f1 * ux,
            f1 * uy,
            f2 * ux,
            f2 * uy,
            f1 * ux * x,
            f1 * ux * y,
            f1 * uy * x,
            f1 * uy * y,
            f2 * ux * x,
            f2 * ux * y,
            f2 * uy * x,
            f2 * uy * y,
        ]

    for row in read_csv("carrier_phase.csv"):
        epoch_id = row["epoch_id"]
        arc_id = row["arc_id"]
        target_token, wavelength = arcs[arc_id]
        point = target_mapping[target_token]
        load = epochs[epoch_id][1]
        los = geometry[(epoch_id, arc_id)]
        continuous_rows.append(continuous_row(point, load, los))
        ambiguity = [0.0] * len(arc_ids)
        ambiguity[arc_index[arc_id]] = wavelength
        ambiguity_rows.append(ambiguity)
        values.append(wavelength * float(row["phase_cycles"]))
        sigmas.append(wavelength * float(row["sigma_cycles"]))

    for row in read_csv("carrier_datum.csv"):
        load = epochs[row["epoch_id"]][1]
        f1 = load
        f2 = load * (load - 0.55)
        for component, key in ((0, "mean_east_m"), (1, "mean_north_m")):
            design = [0.0] * 12
            if component == 0:
                design[0] = f1
                design[2] = f2
                design[4] = f1 * weighted_q[0]
                design[5] = f1 * weighted_q[1]
                design[8] = f2 * weighted_q[0]
                design[9] = f2 * weighted_q[1]
            else:
                design[1] = f1
                design[3] = f2
                design[6] = f1 * weighted_q[0]
                design[7] = f1 * weighted_q[1]
                design[10] = f2 * weighted_q[0]
                design[11] = f2 * weighted_q[1]
            continuous_rows.append(design)
            ambiguity_rows.append([0.0] * len(arc_ids))
            values.append(float(row[key]))
            sigmas.append(float(row["sigma_m"]))

    return {
        "epochs": epochs,
        "arc_ids": arc_ids,
        "target_mapping": dict(target_mapping),
        "centered": centered,
        "continuous": continuous_rows,
        "ambiguity": ambiguity_rows,
        "values": values,
        "sigmas": sigmas,
    }


def weighted_normal(matrix, values, sigmas):
    width = len(matrix[0])
    normal = [[0.0] * width for _ in range(width)]
    rhs = [0.0] * width
    for row, value, sigma in zip(matrix, values, sigmas):
        weight = 1.0 / (sigma * sigma)
        for i in range(width):
            rhs[i] += weight * row[i] * value
            for j in range(width):
                normal[i][j] += weight * row[i] * row[j]
    return normal, rhs


def cholesky_upper(matrix):
    n = len(matrix)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            value = matrix[i][j]
            for k in range(j):
                value -= lower[i][k] * lower[j][k]
            if i == j:
                if value <= 1e-10:
                    raise RuntimeError("carrier ambiguity precision is not positive definite")
                lower[i][j] = math.sqrt(value)
            else:
                lower[i][j] = value / lower[j][j]
    return [[lower[j][i] if j >= i else 0.0 for j in range(n)] for i in range(n)]


def quadratic_cost(vector, center, precision):
    delta = [vector[i] - center[i] for i in range(len(vector))]
    return sum(
        delta[i] * precision[i][j] * delta[j]
        for i in range(len(vector))
        for j in range(len(vector))
    )


def two_best_integer_vectors(center, precision):
    upper = cholesky_upper(precision)
    n = len(center)
    rounded = [int(round(value)) for value in center]
    best = []

    def add_candidate(candidate):
        key = tuple(candidate)
        if any(tuple(item[1]) == key for item in best):
            return
        best.append((quadratic_cost(candidate, center, precision), list(candidate)))
        best.sort(key=lambda item: item[0])
        del best[2:]

    add_candidate(rounded)
    for i in range(n):
        for step in (-1, 1):
            trial = list(rounded)
            trial[i] += step
            add_candidate(trial)

    current = [0] * n

    def visit(k, partial_cost):
        radius = best[-1][0]
        if partial_cost >= radius:
            return
        if k < 0:
            add_candidate(current)
            return

        tail = sum(
            upper[k][j] * (current[j] - center[j]) for j in range(k + 1, n)
        )
        conditional_center = center[k] - tail / upper[k][k]
        remaining = radius - partial_cost
        if remaining <= 0.0:
            return
        delta = math.sqrt(remaining) / abs(upper[k][k])
        low = math.ceil(conditional_center - delta)
        high = math.floor(conditional_center + delta)
        candidates = list(range(low, high + 1))
        candidates.sort(key=lambda value: abs(value - conditional_center))
        for value in candidates:
            current[k] = value
            term = (upper[k][k] * (value - center[k]) + tail) ** 2
            visit(k - 1, partial_cost + term)

    visit(n - 1, 0.0)
    if len(best) != 2:
        raise RuntimeError("could not isolate two carrier ambiguity candidates")
    return best[0][1], best[1][1]


def carrier_float_problem(system):
    continuous = system["continuous"]
    ambiguity = system["ambiguity"]
    values = system["values"]
    sigmas = system["sigmas"]
    combined = [a + b for a, b in zip(continuous, ambiguity)]
    normal, rhs = weighted_normal(combined, values, sigmas)
    solution = solve_linear(normal, rhs)
    continuous_count = len(continuous[0])
    ambiguity_center = solution[continuous_count:]

    c_block = [row[:continuous_count] for row in normal[:continuous_count]]
    d_block = [row[continuous_count:] for row in normal[:continuous_count]]
    e_block = [row[continuous_count:] for row in normal[continuous_count:]]
    ambiguity_count = len(ambiguity_center)

    c_inv_d = [[0.0] * ambiguity_count for _ in range(continuous_count)]
    for column in range(ambiguity_count):
        solved = solve_linear(c_block, [d_block[row][column] for row in range(continuous_count)])
        for row, value in enumerate(solved):
            c_inv_d[row][column] = value

    precision = [[0.0] * ambiguity_count for _ in range(ambiguity_count)]
    for i in range(ambiguity_count):
        for j in range(ambiguity_count):
            correction = sum(
                d_block[row][i] * c_inv_d[row][j] for row in range(continuous_count)
            )
            precision[i][j] = e_block[i][j] - correction
    for i in range(ambiguity_count):
        for j in range(i):
            average = 0.5 * (precision[i][j] + precision[j][i])
            precision[i][j] = average
            precision[j][i] = average
    return ambiguity_center, precision


def refit_carrier(system, integers):
    adjusted_values = []
    for value, row in zip(system["values"], system["ambiguity"]):
        integer_term = sum(coefficient * integer for coefficient, integer in zip(row, integers))
        adjusted_values.append(value - integer_term)
    coefficients = least_squares(
        system["continuous"], adjusted_values, system["sigmas"]
    )
    weighted_ss = 0.0
    for row, value, sigma in zip(system["continuous"], adjusted_values, system["sigmas"]):
        predicted = sum(a * b for a, b in zip(row, coefficients))
        residual = (value - predicted) / sigma
        weighted_ss += residual * residual
    return coefficients, weighted_ss



def recover_carrier(site, trend):
    joint_candidates = []
    for _, target_mapping in carrier_target_candidates(site):
        system = build_carrier_system(site, target_mapping)
        center, precision = carrier_float_problem(system)
        best_integers, second_integers = two_best_integer_vectors(center, precision)
        for integers in (best_integers, second_integers):
            coefficients, weighted_ss = refit_carrier(system, integers)
            joint_candidates.append(
                (
                    weighted_ss,
                    tuple(target_mapping[token] for token in sorted(target_mapping, key=lambda value: int(value[1:]))),
                    tuple(integers),
                    dict(target_mapping),
                    list(integers),
                    coefficients,
                    system,
                )
            )

    joint_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    if len(joint_candidates) < 2:
        raise RuntimeError("carrier archive did not produce two distinct joint candidates")
    fixed_record = joint_candidates[0]
    runner_record = next(
        record
        for record in joint_candidates[1:]
        if (record[1], record[2]) != (fixed_record[1], fixed_record[2])
    )
    fixed_ss, _, _, fixed_mapping, fixed, coefficients, system = fixed_record
    runner_ss, _, _, runner_mapping, runner_up, _, _ = runner_record

    final_epoch_id = max(system["epochs"], key=lambda key: system["epochs"][key][0])
    load = system["epochs"][final_epoch_id][1]
    f1 = load
    f2 = load * (load - 0.55)
    c1 = (coefficients[0], coefficients[1])
    c2 = (coefficients[2], coefficients[3])
    h1 = [[coefficients[4], coefficients[5]], [coefficients[6], coefficients[7]]]
    h2 = [[coefficients[8], coefficients[9]], [coefficients[10], coefficients[11]]]
    gradient = [
        [f1 * h1[i][j] + f2 * h2[i][j] for j in range(2)] for i in range(2)
    ]

    increment = {}
    total = {}
    for point in sorted(site):
        x, y = system["centered"][point]
        deformation = matrix_vec(gradient, (x, y))
        value = (
            f1 * c1[0] + f2 * c2[0] + deformation[0],
            f1 * c1[1] + f2 * c2[1] + deformation[1],
        )
        increment[point] = value
        previous = trend["final_epoch_displacements"][point]
        total[point] = (
            previous["d_east_m"] + value[0],
            previous["d_north_m"] + value[1],
        )

    s00 = gradient[0][0]
    s11 = gradient[1][1]
    s01 = 0.5 * (gradient[0][1] + gradient[1][0])
    trace_half = 0.5 * (s00 + s11)
    radius = math.hypot(0.5 * (s00 - s11), s01)
    principal = [trace_half - radius, trace_half + radius]
    rotation = 0.5 * (gradient[1][0] - gradient[0][1])

    arc_ids = system["arc_ids"]
    return {
        "final_epoch_id": final_epoch_id,
        "target_mapping": fixed_mapping,
        "runner_up_target_mapping": runner_mapping,
        "ambiguities": {arc_id: fixed[i] for i, arc_id in enumerate(arc_ids)},
        "runner_up_ambiguities": {arc_id: runner_up[i] for i, arc_id in enumerate(arc_ids)},
        "fixed_weighted_ss": fixed_ss,
        "runner_up_weighted_ss": runner_ss,
        "ambiguity_gap": runner_ss - fixed_ss,
        "final_increment_displacements": {
            point: {"d_east_m": increment[point][0], "d_north_m": increment[point][1]}
            for point in sorted(increment)
        },
        "final_total_displacements": {
            point: {"d_east_m": total[point][0], "d_north_m": total[point][1]}
            for point in sorted(total)
        },
        "final_gradient": gradient,
        "final_principal_strains": principal,
        "final_rotation_rad": rotation,
    }


def _seed_rows():
    seeds = {}
    for row in read_csv("circle_state_seeds.csv"):
        seeds[row["sequence_id"]] = (
            float(row["seed_raw_unwrapped_rad"]),
            int(row["seed_direction"]),
            float(row["seed_travel_rad"]),
        )
    return seeds


def _unwrap_motion(rows, sequence_key, sequence_value, wrapped_key="raw_circle_rad"):
    seeds = _seed_rows()
    if sequence_value not in seeds:
        raise RuntimeError(f"missing circle state seed for {sequence_value}")
    prev, prev_direction, prev_travel = seeds[sequence_value]
    out = []
    selected = [r for r in rows if r[sequence_key] == sequence_value]
    selected.sort(key=lambda r: int(r["seq"]))
    for row in selected:
        wrapped = float(row[wrapped_key])
        k = round((prev - wrapped) / (2.0 * math.pi))
        unwrapped = wrapped + k * 2.0 * math.pi
        delta = unwrapped - prev
        direction = 1 if delta > 0 else -1 if delta < 0 else prev_direction
        travel = abs(delta) if direction != prev_direction else prev_travel + abs(delta)
        out.append((row, unwrapped, direction, travel))
        prev, prev_direction, prev_travel = unwrapped, direction, travel
    return out


def recover_temperature_calibration():
    groups = {}
    for row in read_csv("thermometer_checks.csv"):
        groups.setdefault(row["logger_id"], []).append(row)
    result = {}
    for logger, rows in groups.items():
        design = [[1.0, float(r["raw_temp_C"])] for r in rows]
        values = [float(r["reference_temp_C"]) for r in rows]
        sigmas = [float(r["sigma_C"]) for r in rows]
        result[logger] = least_squares(design, values, sigmas)
    return result


def _correct_temperature(calibration, logger, raw):
    a, b = calibration[logger]
    return a + b * raw


def _angle_design_row(kind, raw, temp, direction, travel, tau=None):
    row = [1.0, temp - 20.0, math.sin(raw), math.cos(raw)]
    if kind == "none":
        return row
    if kind == "direction":
        return row + [float(direction)]
    if kind == "linear_travel":
        return row + [float(direction), float(direction) * travel]
    if kind == "exponential":
        return row + [float(direction), float(direction) * math.exp(-travel / tau)]
    if kind == "rational":
        return row + [float(direction), float(direction) / (1.0 + travel / tau)]
    raise RuntimeError(f"unknown circle model {kind}")


def _weighted_fit_score(design, values, sigmas):
    coeff = least_squares(design, values, sigmas)
    score = 0.0
    for row, value, sigma in zip(design, values, sigmas):
        pred = sum(a * b for a, b in zip(row, coeff))
        z = (value - pred) / sigma
        score += z * z
    return coeff, score


def recover_angle_model(temp_cal):
    rows = read_csv("angle_reference.csv")
    by_run = sorted(set(r["run_id"] for r in rows))
    records = []
    for run_id in by_run:
        for row, raw, direction, travel in _unwrap_motion(rows, "run_id", run_id):
            temp = _correct_temperature(temp_cal, row["logger_id"], float(row["temp_raw_C"]))
            records.append((raw, temp, direction, travel, float(row["reference_direction_rad"]) - raw, float(row["sigma_rad"])))

    models = read_csv("circle_models.csv")
    candidates = []
    for model in models:
        code, kind = model["model_code"], model["memory_form"]
        values = [r[4] for r in records]
        sigmas = [r[5] for r in records]
        if kind not in ("exponential", "rational"):
            design = [_angle_design_row(kind, r[0], r[1], r[2], r[3]) for r in records]
            coeff, score = _weighted_fit_score(design, values, sigmas)
            candidates.append((score, code, kind, coeff, None))
            continue

        def evaluate(tau):
            design = [_angle_design_row(kind, r[0], r[1], r[2], r[3], tau) for r in records]
            coeff, score = _weighted_fit_score(design, values, sigmas)
            return score, coeff

        # Coarse scan followed by golden-section refinement. The interval is part of the handoff record.
        coarse = []
        for i in range(256):
            tau = 0.040001 + (0.549999 - 0.040001) * i / 255.0
            score, coeff = evaluate(tau)
            coarse.append((score, tau, coeff))
        coarse.sort(key=lambda x: x[0])
        center = coarse[0][1]
        lo = max(0.040001, center - 0.006)
        hi = min(0.549999, center + 0.006)
        phi = (math.sqrt(5.0) - 1.0) / 2.0
        c = hi - phi * (hi - lo)
        d = lo + phi * (hi - lo)
        fc, cc = evaluate(c)
        fd, cd = evaluate(d)
        for _ in range(55):
            if fc < fd:
                hi, d, fd, cd = d, c, fc, cc
                c = hi - phi * (hi - lo)
                fc, cc = evaluate(c)
            else:
                lo, c, fc, cc = c, d, fd, cd
                d = lo + phi * (hi - lo)
                fd, cd = evaluate(d)
        if fc < fd:
            score, tau, coeff = fc, c, cc
        else:
            score, tau, coeff = fd, d, cd
        candidates.append((score, code, kind, coeff, tau))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0], candidates


def _range_design_row(kind, raw_range, temp):
    dt = temp - 20.0
    if kind == "constant":
        return [1.0]
    if kind == "temperature":
        return [1.0, dt]
    if kind == "ppm_temperature":
        return [1.0, dt, raw_range * 1e-6]
    if kind == "quadratic_temperature":
        return [1.0, dt, dt * dt]
    raise RuntimeError(f"unknown range model {kind}")


def recover_range_model(temp_cal):
    refs = read_csv("range_reference.csv")
    candidates = []
    for model in read_csv("range_models.csv"):
        code, kind = model["model_code"], model["form"]
        design, values, sigmas = [], [], []
        for row in refs:
            raw = float(row["raw_range_m"])
            temp = _correct_temperature(temp_cal, row["logger_id"], float(row["temp_raw_C"]))
            design.append(_range_design_row(kind, raw, temp))
            values.append(float(row["reference_range_m"]) - raw)
            sigmas.append(float(row["sigma_m"]))
        coeff, score = _weighted_fit_score(design, values, sigmas)
        candidates.append((score, code, kind, coeff))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0], candidates


def _apply_angle_model(model, raw, temp, direction, travel):
    _, _, kind, coeff, tau = model
    row = _angle_design_row(kind, raw, temp, direction, travel, tau)
    return raw + sum(a * b for a, b in zip(row, coeff))


def _apply_range_model(model, raw, temp):
    _, _, kind, coeff = model
    row = _range_design_row(kind, raw, temp)
    return raw + sum(a * b for a, b in zip(row, coeff))


def _fit_rigid(local_points, global_points):
    n = len(local_points)
    lx = sum(p[0] for p in local_points) / n
    ly = sum(p[1] for p in local_points) / n
    gx = sum(p[0] for p in global_points) / n
    gy = sum(p[1] for p in global_points) / n
    a = 0.0
    b = 0.0
    for (x, y), (X, Y) in zip(local_points, global_points):
        x -= lx; y -= ly; X -= gx; Y -= gy
        a += x * X + y * Y
        b += x * Y - y * X
    alpha = math.atan2(b, a)
    c = math.cos(alpha); s = math.sin(alpha)
    tx = gx - (c * lx - s * ly)
    ty = gy - (s * lx + c * ly)
    rss = 0.0
    for (x, y), (X, Y) in zip(local_points, global_points):
        px = tx + c * x - s * y
        py = ty + s * x + c * y
        rss += (px - X) ** 2 + (py - Y) ** 2
    return tx, ty, alpha, rss


def _wrap_pi(value):
    while value <= -math.pi:
        value += 2.0 * math.pi
    while value > math.pi:
        value -= 2.0 * math.pi
    return value


def recover_closing_resection(site, carrier):
    temp_cal = recover_temperature_calibration()
    angle_best, angle_candidates = recover_angle_model(temp_cal)
    range_best, range_candidates = recover_range_model(temp_cal)

    # Carrier-final target coordinates form the control for the closing resection.
    target_coords = {}
    for point in sorted(site):
        total = carrier["final_total_displacements"][point]
        target_coords[point] = (
            site[point][0] + total["d_east_m"],
            site[point][1] + total["d_north_m"],
        )

    field_rows = read_csv("closing_resection.csv")
    setup_rows = {r["setup_id"]: r for r in read_csv("setup_register.csv")}
    reduced = {}
    tags = sorted(set(r["target_tag"] for r in field_rows), key=lambda x: int(x[1:]))
    setup_ids = sorted(set(r["setup_id"] for r in field_rows))
    for setup_id in setup_ids:
        setup = setup_rows[setup_id]
        items = []
        for row, raw, direction, travel in _unwrap_motion(field_rows, "setup_id", setup_id):
            temp = _correct_temperature(temp_cal, setup["logger_id"], float(row["temp_raw_C"]))
            circle = _apply_angle_model(angle_best, raw, temp, direction, travel)
            distance = _apply_range_model(range_best, float(row["raw_range_m"]), temp)
            items.append((row["target_tag"], circle, distance))
        reduced[setup_id] = items

    point_ids = sorted(target_coords)
    sense_codes = sorted(set(r["circle_sense_code"] for r in setup_rows.values()))
    if len(sense_codes) != 2:
        raise RuntimeError("closing resection expects two opposite sense codes")
    candidates = []
    for first_sign in (1, -1):
        sense_map = {sense_codes[0]: first_sign, sense_codes[1]: -first_sign}
        for perm in itertools.permutations(point_ids):
            mapping = dict(zip(tags, perm))
            setup_fits = {}
            total_rss = 0.0
            for setup_id in setup_ids:
                sense = sense_map[setup_rows[setup_id]["circle_sense_code"]]
                local = []
                global_pts = []
                for tag, circle, distance in reduced[setup_id]:
                    bearing = sense * circle
                    local.append((distance * math.sin(bearing), distance * math.cos(bearing)))
                    global_pts.append(target_coords[mapping[tag]])
                tx, ty, alpha, rss = _fit_rigid(local, global_pts)
                setup_fits[setup_id] = (tx, ty, alpha, rss, len(local))
                total_rss += rss
            candidates.append((total_rss, tuple(perm), first_sign, mapping, sense_map, setup_fits))
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    best = candidates[0]
    second = next(x for x in candidates[1:] if (x[1], x[2]) != (best[1], best[2]))
    total_rss, _, _, mapping, sense_map, setup_fits = best
    n_obs = sum(fit[4] for fit in setup_fits.values())
    setups = {}
    for setup_id, (tx, ty, alpha, rss, n) in setup_fits.items():
        setups[setup_id] = {
            "east_m": tx,
            "north_m": ty,
            "orientation_rad": _wrap_pi(-alpha),
            "rms_m": math.sqrt(rss / n),
        }
    s0, s1 = setup_ids
    de = setups[s1]["east_m"] - setups[s0]["east_m"]
    dn = setups[s1]["north_m"] - setups[s0]["north_m"]
    return {
        "angle_model_code": angle_best[1],
        "angle_weighted_ss": angle_best[0],
        "range_model_code": range_best[1],
        "range_weighted_ss": range_best[0],
        "circle_sense": sense_map,
        "target_mapping": mapping,
        "setups": setups,
        "interstation_baseline_m": math.hypot(de, dn),
        "interstation_azimuth_rad": math.atan2(de, dn),
        "closure_rms_m": math.sqrt(total_rss / n_obs),
        "runner_up_closure_rms_m": math.sqrt(second[0] / n_obs),
    }


def main():
    site, trend = load_handoff()
    carrier_full = recover_carrier(site, trend)
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
    result = {
        "carrier_reconstruction": carrier,
        "closing_resection": recover_closing_resection(site, carrier_full),
    }
    with OUTPUT_PATH.open("w") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)

if __name__ == "__main__":
    main()
