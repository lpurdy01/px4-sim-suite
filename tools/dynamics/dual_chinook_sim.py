"""Lightweight dual-rotor analytic model + scenario loader.

The intent is to iterate on tandem-rotor configurations before touching Gazebo
submodules. All inputs come from YAML descriptors/scenarios so the data can be
reused by other tooling (e.g. template generators, PX4 mixers).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import yaml

GRAVITY = 9.80665  # m/s^2


@dataclass
class RotorSpec:
    name: str
    position: Sequence[float]
    axis: Sequence[float]
    spin: str
    diameter: float
    max_rot_speed: float
    thrust_coefficient: float
    moment_coefficient: float
    time_constant: float


@dataclass
class VehicleDescriptor:
    name: str
    mass: float
    inertia: Dict[str, float]
    cg: Sequence[float]
    rotors: List[RotorSpec]
    hover_throttle: float
    initial_position: Sequence[float]
    initial_velocity: Sequence[float]
    drag_coefficient: float
    reference_area: float
    air_density: float


@dataclass
class ScenarioPhase:
    type: str  # "ramp" or "hold"
    start_time: float
    end_time: float
    start_throttle: float | None = None
    end_throttle: float | None = None
    throttle: float | None = None

    def value_at(self, t: float) -> float:
        if self.type == "hold":
            return float(self.throttle or 0.0)
        if self.type == "ramp":
            assert self.start_throttle is not None and self.end_throttle is not None
            span = self.end_time - self.start_time
            if span <= 0:
                return float(self.end_throttle)
            ratio = min(max((t - self.start_time) / span, 0.0), 1.0)
            return float(
                self.start_throttle + ratio * (self.end_throttle - self.start_throttle)
            )
        raise ValueError(f"Unsupported phase type: {self.type}")


@dataclass
class Scenario:
    name: str
    sample_rate_hz: float
    phases: List[ScenarioPhase]

    @property
    def duration(self) -> float:
        return max((phase.end_time for phase in self.phases), default=0.0)

    def throttle_at(self, t: float) -> float:
        for phase in self.phases:
            if phase.start_time <= t <= phase.end_time:
                return phase.value_at(t)
        # default to last value if time exceeds final phase
        return self.phases[-1].value_at(self.phases[-1].end_time)


@dataclass
class SimulationSample:
    time: float
    throttle_cmd: float
    altitude: float
    vertical_velocity: float
    acceleration: float
    net_thrust: float
    rotor_speeds: List[float]

    def as_dict(self) -> Dict[str, float]:
        data = {
            "time": self.time,
            "throttle_cmd": self.throttle_cmd,
            "altitude": self.altitude,
            "vertical_velocity": self.vertical_velocity,
            "acceleration": self.acceleration,
            "net_thrust": self.net_thrust,
        }
        for idx, speed in enumerate(self.rotor_speeds):
            data[f"rotor_{idx}_speed"] = speed
        return data


class DualRotorSimulator:
    def __init__(self, descriptor: VehicleDescriptor):
        self.descriptor = descriptor
        self.altitude = float(descriptor.initial_position[2])
        self.velocity = float(descriptor.initial_velocity[2])
        self.rotor_speeds: List[float] = [0.0 for _ in descriptor.rotors]

    def step(self, throttle_cmd: float, dt: float) -> SimulationSample:
        total_thrust = 0.0
        new_speeds: List[float] = []
        for speed, rotor in zip(self.rotor_speeds, self.descriptor.rotors):
            target_speed = throttle_cmd * rotor.max_rot_speed
            accel = (target_speed - speed) * dt / max(rotor.time_constant, 1e-4)
            updated_speed = max(speed + accel, 0.0)
            thrust = rotor.thrust_coefficient * updated_speed**2
            total_thrust += thrust
            new_speeds.append(updated_speed)
        self.rotor_speeds = new_speeds

        drag = self._drag_force(self.velocity)
        acceleration = (total_thrust - drag - self.descriptor.mass * GRAVITY) / self.descriptor.mass
        self.velocity += acceleration * dt
        self.altitude = max(self.altitude + self.velocity * dt, 0.0)

        return SimulationSample(
            time=0.0,  # placeholder, caller fills in
            throttle_cmd=throttle_cmd,
            altitude=self.altitude,
            vertical_velocity=self.velocity,
            acceleration=acceleration,
            net_thrust=total_thrust,
            rotor_speeds=list(self.rotor_speeds),
        )

    def _drag_force(self, velocity: float) -> float:
        rho = self.descriptor.air_density
        area = self.descriptor.reference_area
        cd = self.descriptor.drag_coefficient
        return 0.5 * rho * area * cd * velocity * abs(velocity)


def load_descriptor(path: str | Path) -> VehicleDescriptor:
    data = yaml.safe_load(Path(path).read_text())
    rotors = [RotorSpec(**rotor) for rotor in data["rotors"]]
    mass_props = data["mass_properties"]
    aero = data.get("aerodynamics", {})
    trim = data.get("trim", {})
    initial_pos = trim.get("initial_position", [0.0, 0.0, 0.0])
    initial_vel = trim.get("initial_velocity", [0.0, 0.0, 0.0])
    return VehicleDescriptor(
        name=data["name"],
        mass=float(mass_props["mass"]),
        inertia=mass_props.get("inertia", {}),
        cg=mass_props.get("cg", [0.0, 0.0, 0.0]),
        rotors=rotors,
        hover_throttle=float(trim.get("hover_throttle", 0.5)),
        initial_position=initial_pos,
        initial_velocity=initial_vel,
        drag_coefficient=float(aero.get("axial_drag_coefficient", 1.0)),
        reference_area=float(aero.get("reference_area", 1.0)),
        air_density=float(aero.get("air_density", 1.204)),
    )


def load_scenario(path: str | Path) -> Scenario:
    data = yaml.safe_load(Path(path).read_text())
    phases = [ScenarioPhase(**phase) for phase in data["phases"]]
    return Scenario(
        name=data["name"],
        sample_rate_hz=float(data["sample_rate_hz"]),
        phases=phases,
    )


def run_simulation(descriptor: VehicleDescriptor, scenario: Scenario) -> List[Dict[str, float]]:
    sim = DualRotorSimulator(descriptor)
    dt = 1.0 / scenario.sample_rate_hz
    total_steps = int(scenario.duration / dt)
    samples: List[Dict[str, float]] = []
    time = 0.0
    for _ in range(total_steps + 1):
        throttle_cmd = scenario.throttle_at(time)
        sample = sim.step(throttle_cmd=throttle_cmd, dt=dt)
        sample.time = time
        samples.append(sample.as_dict())
        time += dt
    return samples


__all__ = [
    "load_descriptor",
    "load_scenario",
    "run_simulation",
    "VehicleDescriptor",
    "Scenario",
]
