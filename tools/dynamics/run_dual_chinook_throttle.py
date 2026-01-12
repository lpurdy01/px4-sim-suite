#!/usr/bin/env python3
"""Run the dual Chinook analytic throttle scenario and emit Plotly HTML."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dual_chinook_sim import load_descriptor, load_scenario, run_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", required=True, help="Path to vehicle YAML descriptor")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML definition")
    parser.add_argument(
        "--output",
        required=True,
        help="Destination Plotly HTML report (will be overwritten)",
    )
    parser.add_argument(
        "--csv",
        help="Optional CSV log path (defaults to alongside the HTML report)",
    )
    parser.add_argument(
        "--gazebo-csv",
        help="Optional Gazebo CSV to overlay on the Plotly report",
    )
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, samples: List[dict]) -> None:
    ensure_parent(path)
    fieldnames = list(samples[0].keys()) if samples else []
    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)


def parse_float(value: str | float | int) -> float:
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_csv_rows(path: Path) -> List[dict]:
    with path.open() as csv_file:
        reader = csv.DictReader(csv_file)
        rows: List[dict] = []
        for row in reader:
            rows.append({key: parse_float(value) for key, value in row.items()})
    return rows


def build_figure(
    samples: List[dict],
    descriptor_name: str,
    scenario_name: str,
    vehicle_mass: float,
    gazebo_rows: List[dict] | None = None,
) -> go.Figure:
    times = [row["time"] for row in samples]
    throttle = [row["throttle_cmd"] for row in samples]
    altitude = [row["altitude"] for row in samples]
    velocity = [row["vertical_velocity"] for row in samples]
    thrust = [row["net_thrust"] for row in samples]
    rotor0 = [row.get("rotor_0_speed", 0.0) for row in samples]
    rotor1 = [row.get("rotor_1_speed", 0.0) for row in samples]

    gazebo_times: List[float] = []
    gazebo_altitude: List[float] = []
    gazebo_throttle: List[float] = []
    gazebo_rotor0: List[float] = []
    gazebo_rotor1: List[float] = []

    if gazebo_rows:
        if gazebo_rows and "sim_time" in gazebo_rows[0]:
            t0 = gazebo_rows[0]["sim_time"]
        else:
            t0 = gazebo_rows[0]["time"] if gazebo_rows else 0.0
        for row in gazebo_rows:
            gazebo_times.append(row.get("sim_time", row.get("time", 0.0)) - t0)
            gazebo_throttle.append(row.get("throttle_cmd", 0.0))
            gazebo_altitude.append(row.get("measured_altitude", 0.0))
            gazebo_rotor0.append(row.get("rotor_0_velocity", 0.0))
            gazebo_rotor1.append(row.get("rotor_1_velocity", 0.0))

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Throttle Command & Rotor Speed", "Altitude vs Time", "Net Thrust"),
    )
    fig.add_trace(go.Scatter(x=times, y=throttle, name="Throttle Cmd", line=dict(color="#636EFA")), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=times, y=rotor0, name="Rotor 0 Speed", line=dict(color="#EF553B")), row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=times, y=rotor1, name="Rotor 1 Speed", line=dict(color="#00CC96", dash="dot")),
        row=1,
        col=1,
    )

    if gazebo_rows:
        fig.add_trace(
            go.Scatter(
                x=gazebo_times,
                y=gazebo_throttle,
                name="Throttle Cmd (Gazebo)",
                line=dict(color="#636EFA", dash="dash"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=gazebo_times,
                y=gazebo_rotor0,
                name="Rotor 0 Velocity (Gazebo)",
                line=dict(color="#EF553B", dash="dash"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=gazebo_times,
                y=gazebo_rotor1,
                name="Rotor 1 Velocity (Gazebo)",
                line=dict(color="#00CC96", dash="dot"),
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Scatter(x=times, y=altitude, name="Altitude", line=dict(color="#AB63FA")), row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=times, y=velocity, name="Vertical Velocity", line=dict(color="#FFA15A", dash="dash")),
        row=2,
        col=1,
    )

    if gazebo_rows:
        fig.add_trace(
            go.Scatter(
                x=gazebo_times,
                y=gazebo_altitude,
                name="Altitude (Gazebo)",
                line=dict(color="#19D3F3"),
            ),
            row=2,
            col=1,
        )

    fig.add_trace(
        go.Scatter(x=times, y=thrust, name="Net Thrust", line=dict(color="#19D3F3")), row=3, col=1
    )
    fig.add_hline(
        y=vehicle_mass * 9.80665,
        row=3,
        col=1,
        line=dict(color="#B6E880", dash="dash"),
        annotation_text="Weight",
    )

    title_suffix = "Analytic Scenario"
    if gazebo_rows:
        title_suffix = "Analytic vs Gazebo"

    fig.update_layout(
        title=f"Dual Chinook {title_suffix} — {descriptor_name} · {scenario_name}",
        xaxis3=dict(title="Time (s)"),
        height=900,
        template="plotly_white",
    )
    return fig


def main() -> None:
    args = parse_args()
    descriptor = load_descriptor(args.descriptor)
    scenario = load_scenario(args.scenario)
    samples = run_simulation(descriptor, scenario)

    output_path = Path(args.output)
    ensure_parent(output_path)

    csv_path = Path(args.csv) if args.csv else output_path.with_suffix(".csv")
    write_csv(csv_path, samples)

    gazebo_rows = load_csv_rows(Path(args.gazebo_csv)) if args.gazebo_csv else None
    fig = build_figure(samples, descriptor.name, scenario.name, descriptor.mass, gazebo_rows)
    fig.write_html(output_path, include_plotlyjs="cdn")
    print(f"Saved Plotly report to {output_path}")
    print(f"Saved CSV log to {csv_path}")


if __name__ == "__main__":
    main()
