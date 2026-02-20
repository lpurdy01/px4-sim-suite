#!/usr/bin/env python3
"""Generate visuals for the /dev/reno meetup presentation.

Usage: python3 scripts/generate_devreno_visuals.py

Outputs PNGs to docs/images/devreno/
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent.parent / "images" / "devreno"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# -- Color palette --
BLUE = "#1565C0"
BLUE_LIGHT = "#E3F2FD"
TEAL = "#00838F"
TEAL_LIGHT = "#E0F7FA"
GREEN = "#2E7D32"
GREEN_LIGHT = "#E8F5E9"
ORANGE = "#E65100"
ORANGE_LIGHT = "#FFF3E0"
GRAY = "#546E7A"
GRAY_LIGHT = "#ECEFF1"
DARK = "#263238"
WHITE = "#FFFFFF"


def rounded_box(ax, x, y, w, h, label, sublabel, facecolor, edgecolor, fontsize=22):
    """Draw a rounded rectangle with centered label and sublabel."""
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.15",
        facecolor=facecolor, edgecolor=edgecolor, linewidth=3,
        zorder=3,
    )
    ax.add_patch(box)
    ax.text(x, y + 0.15, label, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=edgecolor, zorder=4)
    ax.text(x, y - 0.35, sublabel, ha="center", va="center",
            fontsize=fontsize - 6, color=GRAY, style="italic", zorder=4)


def curved_arrow(ax, start, end, color=GRAY, connectionstyle="arc3,rad=0.25"):
    """Draw a curved arrow between two points."""
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle="-|>",
        mutation_scale=28,
        linewidth=3,
        color=color,
        connectionstyle=connectionstyle,
        zorder=2,
    )
    ax.add_patch(arrow)


def arrow_label(ax, x, y, text, color=GRAY, fontsize=15):
    """Place a label near an arrow."""
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, color=color, style="italic",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=WHITE, edgecolor="none", alpha=0.85),
            zorder=5)


def generate_feedback_loop():
    """The universal feedback/control loop diagram.

    Wide diamond layout for 16:9 slides:
    SENSE (top) → DECIDE (right) → ACT (bottom) → WORLD (left)
    """
    fig, ax = plt.subplots(1, 1, figsize=(18, 10), dpi=200)
    ax.set_xlim(-7.5, 7.5)
    ax.set_ylim(-4.5, 4.5)
    ax.axis("off")
    fig.patch.set_alpha(0)

    # Node positions (wide diamond layout)
    bw, bh = 3.2, 1.4  # box width, height
    nodes = {
        "SENSE":  (0, 3.2,    BLUE,   BLUE_LIGHT,   "observe the state"),
        "DECIDE": (5.5, 0,    TEAL,   TEAL_LIGHT,   "compute response"),
        "ACT":    (0, -3.2,   GREEN,  GREEN_LIGHT,   "apply output"),
        "WORLD":  (-5.5, 0,   ORANGE, ORANGE_LIGHT,  "physics / reality"),
    }

    for label, (x, y, edge, face, sub) in nodes.items():
        rounded_box(ax, x, y, bw, bh, label, sub, face, edge)

    # Arrows (clockwise): SENSE → DECIDE → ACT → WORLD → SENSE
    # SENSE → DECIDE
    curved_arrow(ax, (1.4, 2.6), (4.2, 0.9), GRAY, "arc3,rad=0.15")
    arrow_label(ax, 3.6, 2.2, "input data")

    # DECIDE → ACT
    curved_arrow(ax, (4.2, -0.9), (1.4, -2.6), GRAY, "arc3,rad=0.15")
    arrow_label(ax, 3.6, -2.2, "command")

    # ACT → WORLD
    curved_arrow(ax, (-1.4, -2.6), (-4.2, -0.9), GRAY, "arc3,rad=0.15")
    arrow_label(ax, -3.6, -2.2, "force / signal")

    # WORLD → SENSE
    curved_arrow(ax, (-4.2, 0.9), (-1.4, 2.6), GRAY, "arc3,rad=0.15")
    arrow_label(ax, -3.6, 2.2, "measurement")

    # Center label
    ax.text(0, 0, "FEEDBACK\nLOOP", ha="center", va="center",
            fontsize=28, fontweight="bold", color=DARK, alpha=0.25, zorder=1)

    out = OUTPUT_DIR / "feedback-loop.png"
    fig.savefig(out, bbox_inches="tight", transparent=True, pad_inches=0.3)
    plt.close()
    print(f"  -> {out}")


def _pipeline_column(ax, x_center, title, steps, colors, title_color):
    """Draw a vertical pipeline of steps."""
    y_start = 4.0
    y_step = -1.6
    box_w = 4.5
    box_h = 1.0

    # Title
    ax.text(x_center, y_start + 1.2, title, ha="center", va="center",
            fontsize=24, fontweight="bold", color=title_color)

    for i, (step, (face, edge)) in enumerate(zip(steps, colors)):
        y = y_start + i * y_step
        box = FancyBboxPatch(
            (x_center - box_w / 2, y - box_h / 2), box_w, box_h,
            boxstyle="round,pad=0.12",
            facecolor=face, edgecolor=edge, linewidth=2.5,
            zorder=3,
        )
        ax.add_patch(box)
        ax.text(x_center, y, step, ha="center", va="center",
                fontsize=17, fontweight="bold", color=edge, zorder=4)

        # Arrow to next step
        if i < len(steps) - 1:
            ax.annotate(
                "", xy=(x_center, y - box_h / 2 - 0.08),
                xytext=(x_center, y + y_step + box_h / 2 + 0.08),
                arrowprops=dict(arrowstyle="<|-", color=GRAY, lw=2.5),
                zorder=2,
            )


def generate_ci_comparison():
    """Side-by-side comparison: conventional CI vs simulation CI."""
    fig, ax = plt.subplots(1, 1, figsize=(20, 12), dpi=200)
    ax.set_xlim(-11, 11)
    ax.set_ylim(-6.5, 6.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_alpha(0)

    # Conventional CI (left)
    conv_steps = ["Code Change", "Lint / Format", "Compile", "Unit Tests", "Integration Tests", "Deploy"]
    conv_colors = [(BLUE_LIGHT, BLUE)] * len(conv_steps)

    _pipeline_column(ax, -5.5, "Conventional CI", conv_steps, conv_colors, BLUE)

    # Simulation CI (right)
    sim_steps = ["Code Change", "Compile Firmware", "Launch Simulator", "Fly the Mission", "Collect Flight Data", "Generate Report"]
    sim_colors = [(GREEN_LIGHT, GREEN)] * len(sim_steps)

    _pipeline_column(ax, 5.5, "Simulation CI", sim_steps, sim_colors, GREEN)

    # Connecting dashed lines to show parallels
    y_start = 4.0
    y_step = -1.6
    for i in range(len(conv_steps)):
        y = y_start + i * y_step
        ax.plot([-3.0, 3.0], [y, y], "--", color=GRAY, alpha=0.3, lw=1.5, zorder=1)

    # Center annotation
    ax.text(0, -5.8, "Same pattern. Different domain.", ha="center", va="center",
            fontsize=22, fontweight="bold", color=DARK, style="italic")

    out = OUTPUT_DIR / "ci-comparison.png"
    fig.savefig(out, bbox_inches="tight", transparent=True, pad_inches=0.3)
    plt.close()
    print(f"  -> {out}")


def generate_domain_loops():
    """Grid showing the same feedback loop pattern across different domains."""
    domains = [
        ("Web App",      "User clicks",     "Validate input",   "Update DOM",       "Page renders",    BLUE, BLUE_LIGHT),
        ("Game Engine",  "Player input",     "Game logic",       "Physics step",     "Frame renders",   TEAL, TEAL_LIGHT),
        ("Drone",        "Read sensors",     "PID controller",   "Set motor PWM",    "Drone moves",     GREEN, GREEN_LIGHT),
        ("Autoscaler",   "Check CPU load",   "Scaling policy",   "Add instances",    "Load changes",    ORANGE, ORANGE_LIGHT),
        ("CNC Machine",  "Measure position", "Path planner",     "Move stepper",     "Material cut",    "#6A1B9A", "#F3E5F5"),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(28, 6), dpi=200)
    fig.patch.set_alpha(0)

    for ax, (domain, sense, decide, act, world, color, bg) in zip(axes, domains):
        ax.set_xlim(-2.2, 2.2)
        ax.set_ylim(-3.2, 2.8)
        ax.set_aspect("equal")
        ax.axis("off")

        # Domain title
        ax.text(0, 2.5, domain, ha="center", va="center",
                fontsize=18, fontweight="bold", color=color)

        # 4 small boxes in a diamond
        positions = [(0, 1.5), (1.5, 0), (0, -1.5), (-1.5, 0)]
        labels = [sense, decide, act, world]
        phases = ["sense", "decide", "act", "world"]

        bw, bh = 2.6, 0.75
        for (bx, by), label, phase in zip(positions, labels, phases):
            box = FancyBboxPatch(
                (bx - bw / 2, by - bh / 2), bw, bh,
                boxstyle="round,pad=0.08",
                facecolor=bg, edgecolor=color, linewidth=1.5,
                zorder=3,
            )
            ax.add_patch(box)
            ax.text(bx, by, label, ha="center", va="center",
                    fontsize=9, color=color, fontweight="bold", zorder=4)

        # Arrows clockwise
        arrow_kw = dict(arrowstyle="-|>", mutation_scale=16, linewidth=1.5, color=color, alpha=0.5)
        ax.annotate("", xy=(1.0, 0.55), xytext=(0.55, 1.1),
                    arrowprops={**arrow_kw, "connectionstyle": "arc3,rad=0.2"}, zorder=2)
        ax.annotate("", xy=(0.55, -1.1), xytext=(1.0, -0.55),
                    arrowprops={**arrow_kw, "connectionstyle": "arc3,rad=0.2"}, zorder=2)
        ax.annotate("", xy=(-1.0, -0.55), xytext=(-0.55, -1.1),
                    arrowprops={**arrow_kw, "connectionstyle": "arc3,rad=0.2"}, zorder=2)
        ax.annotate("", xy=(-0.55, 1.1), xytext=(-1.0, 0.55),
                    arrowprops={**arrow_kw, "connectionstyle": "arc3,rad=0.2"}, zorder=2)

        # Phase labels
        for (bx, by), phase in zip(positions, phases):
            ax.text(bx, by - bh / 2 - 0.18, phase, ha="center", va="top",
                    fontsize=7, color=GRAY, style="italic", zorder=5)

    fig.suptitle("Same Pattern, Every Domain", fontsize=26, fontweight="bold",
                 color=DARK, y=1.02)

    out = OUTPUT_DIR / "domain-loops.png"
    fig.savefig(out, bbox_inches="tight", transparent=True, pad_inches=0.3)
    plt.close()
    print(f"  -> {out}")


if __name__ == "__main__":
    print("Generating /dev/reno visuals...\n")
    generate_feedback_loop()
    generate_ci_comparison()
    generate_domain_loops()
    print("\nDone!")
