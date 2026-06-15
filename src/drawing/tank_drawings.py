"""
tank_drawings.py – Schematic cross-section drawings for elevated RCC water tanks.
Produces publication-quality matplotlib figures with dimension lines, callouts,
and reinforcement annotations.
"""
from __future__ import annotations
import io, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, Arc, FancyBboxPatch
from matplotlib.lines import Line2D

IS_BLUE  = "#004B7F"
IS_GOLD  = "#CC9900"
CONC_COL = "#D6CBB5"
STEEL_COL= "#C0392B"
WATER_COL= "#AED6F1"
BG_COL   = "#FAFAFA"

# ─────────────────────────────────────────────────────────────────────────────
def _dim_line(ax, x1, y1, x2, y2, text, offset=0.3, color=IS_BLUE, fs=7):
    """Draw a dimension line with arrows and label."""
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="<->", color=color, lw=0.8))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ax.text(mx + offset, my, text, ha="left", va="center",
            fontsize=fs, color=color, fontfamily="DejaVu Sans")


def _callout(ax, x, y, text, color=IS_BLUE, fs=7, dx=0.5, dy=0.3):
    ax.annotate(text, xy=(x, y), xytext=(x + dx, y + dy),
                fontsize=fs, color=color,
                arrowprops=dict(arrowstyle="-|>", color=color,
                                connectionstyle="arc3,rad=0.2", lw=0.7),
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=0.5))


def _hatch_concrete(ax, path, **kw):
    patch = mpatches.PathPatch(path, facecolor=CONC_COL, edgecolor="#888",
                                hatch="//", linewidth=0.4, **kw)
    ax.add_patch(patch)


# ─────────────────────────────────────────────────────────────────────────────
# CIRCULAR TANK
# ─────────────────────────────────────────────────────────────────────────────
def draw_circular_tank(geometry: dict, reinforcement: dict) -> bytes:
    D    = geometry.get("D_int_m", 6.0)
    R    = D / 2
    Hw   = geometry.get("H_water_m", 3.0)
    Ht   = geometry.get("H_total_m", 3.3)
    Hs   = geometry.get("staging_height_m", 12.0)
    tw   = reinforcement.get("wall", {}).get("thickness_mm", 200) / 1000
    tf   = reinforcement.get("floor_slab", {}).get("thickness_mm", 250) / 1000
    t_dome = reinforcement.get("top_dome", {}).get("t_dome_mm", 120) / 1000
    rd   = geometry.get("R_int_m", R) + 0.5  # dome radius (approx for sketch)
    rise_d = D / 5

    fig, axes = plt.subplots(1, 2, figsize=(14, 10), facecolor=BG_COL)
    fig.suptitle(f"Circular Elevated RCC Water Tank\nCapacity = {geometry.get('actual_vol_m3',0):.0f} m³  |  Ø{D:.1f}m × {Hw:.1f}m",
                 fontsize=11, fontweight="bold", color=IS_BLUE, y=0.97)

    # ── Left: Full elevation ────────────────────────────────────────────────
    ax = axes[0]
    ax.set_facecolor(BG_COL)
    ax.set_aspect("equal")
    ax.set_title("Sectional Elevation", fontsize=9, color=IS_BLUE, pad=6)

    # Ground line
    ax.axhline(0, color="#555", lw=1.0, ls="--", zorder=1)
    ax.text(-R - 0.5, -0.3, "GL", fontsize=7, color="#555")

    # Staging columns (simplified 2D)
    col_d = geometry.get("staging", {}) or 0.5
    for x_col in [-R * 0.7, R * 0.7]:
        col = mpatches.FancyBboxPatch((x_col - 0.20, 0), 0.40, Hs,
                                       boxstyle="square", fc=CONC_COL,
                                       ec="#555", lw=0.6, zorder=2)
        ax.add_patch(col)
    # Bracing at mid-height
    brace_y = Hs / 2
    ax.plot([-R * 0.7, R * 0.7], [brace_y, brace_y], color=CONC_COL,
            lw=8, solid_capstyle="butt", zorder=2)
    ax.plot([-R * 0.7, R * 0.7], [brace_y, brace_y], color="#555",
            lw=0.5, zorder=3)

    # Tank shell (wall)
    wall_outer_R = R + tw
    base_y = Hs
    # Outer wall rectangle (left & right)
    for x_sign in [-1, 1]:
        x0 = x_sign * R if x_sign < 0 else R
        x1 = x_sign * (R + tw)
        wall_rect = mpatches.FancyBboxPatch(
            (min(x0, x1), base_y - tf), abs(x1 - x0), Ht + tf,
            boxstyle="square", fc=CONC_COL, ec="#555", lw=0.6,
            hatch="//", zorder=4)
        ax.add_patch(wall_rect)

    # Floor slab
    floor = mpatches.FancyBboxPatch((-wall_outer_R, base_y - tf),
                                     2 * wall_outer_R, tf,
                                     boxstyle="square", fc=CONC_COL,
                                     ec="#555", lw=0.6, hatch="//", zorder=4)
    ax.add_patch(floor)

    # Water fill
    water = mpatches.FancyBboxPatch((-R, base_y), 2 * R, Hw,
                                     boxstyle="square", fc=WATER_COL,
                                     alpha=0.55, ec=WATER_COL, lw=0.3, zorder=3)
    ax.add_patch(water)
    ax.text(0, base_y + Hw / 2, f"Water\n{geometry.get('actual_vol_m3',0):.0f} m³",
            ha="center", va="center", fontsize=8, color=IS_BLUE,
            fontweight="bold", zorder=5)

    # Dome (arc)
    dome_theta1 = math.degrees(math.asin(R / (rd + 0.1)))
    dome_theta2 = 180 - dome_theta1
    dome_arc = Arc((0, base_y + Ht), 2 * (rd + 0.1), 2 * (rd + 0.1),
                   angle=0, theta1=dome_theta1, theta2=dome_theta2,
                   color="#555", lw=1.2, zorder=6)
    ax.add_patch(dome_arc)

    # Water surface line
    ax.plot([-R, R], [base_y + Hw, base_y + Hw],
            color=IS_BLUE, lw=0.8, ls="--", zorder=6)
    ax.text(R + 0.1, base_y + Hw, "FSL", fontsize=7, color=IS_BLUE, va="center")

    # Dimension lines
    _dim_line(ax, wall_outer_R + 0.4, base_y, wall_outer_R + 0.4, base_y + Ht,
              f"H={Ht:.2f}m", offset=0.15)
    _dim_line(ax, wall_outer_R + 0.4, 0, wall_outer_R + 0.4, base_y,
              f"Hs={Hs:.1f}m", offset=0.15)
    _dim_line(ax, -wall_outer_R, base_y - 0.8, wall_outer_R, base_y - 0.8,
              f"D+2t={2*wall_outer_R:.2f}m", offset=-0.5)

    # Callouts
    _callout(ax, -wall_outer_R, base_y + Ht / 2,
             f"Wall t={int(tw*1000)}mm\n"
             f"Hoop: {reinforcement.get('wall',{}).get('hoop_bar_dia','—')}ø"
             f"@{reinforcement.get('wall',{}).get('hoop_spacing_mm','—')}",
             dx=-1.5, dy=0.5)
    _callout(ax, 0, base_y - tf / 2,
             f"Floor t={int(tf*1000)}mm\n"
             f"R/F: {reinforcement.get('floor_slab',{}).get('bar_dia','—')}ø"
             f"@{reinforcement.get('floor_slab',{}).get('bar_spacing_mm','—')}",
             dx=1.2, dy=-0.8)

    ax.set_xlim(-R - 2.5, R + 2.5)
    ax.set_ylim(-1.0, Hs + Ht + rise_d + 1.5)
    ax.set_xlabel("Width (m)", fontsize=8, color="#333")
    ax.set_ylabel("Elevation (m)", fontsize=8, color="#333")
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.2, lw=0.4)

    # ── Right: Plan and detail ───────────────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor(BG_COL)
    ax2.set_aspect("equal")
    ax2.set_title("Plan View & Reinforcement Detail", fontsize=9, color=IS_BLUE, pad=6)

    # Outer circle (plan)
    circ_out = plt.Circle((0, 0), wall_outer_R, fill=False, ec="#555",
                           lw=1.2, ls="-", zorder=3)
    circ_in  = plt.Circle((0, 0), R, fill=True, fc=WATER_COL,
                           ec=IS_BLUE, lw=0.6, alpha=0.4, zorder=2)
    ax2.add_patch(circ_out)
    ax2.add_patch(circ_in)

    # Wall hatch (annulus)
    theta = np.linspace(0, 2 * math.pi, 200)
    x_out = wall_outer_R * np.cos(theta)
    y_out = wall_outer_R * np.sin(theta)
    x_in  = R * np.cos(theta)
    y_in  = R * np.sin(theta)
    ax2.fill_between(x_out, y_out, color=CONC_COL, alpha=0.8, zorder=2)
    ax2.fill_between(x_in,  y_in,  color=WATER_COL, alpha=0.4, zorder=3)

    # Staging columns in plan
    n_col = geometry.get("n_columns", 6)
    R_stg = R * 0.75
    for i in range(n_col):
        angle = 2 * math.pi * i / n_col
        cx = R_stg * math.cos(angle)
        cy = R_stg * math.sin(angle)
        circ_col = plt.Circle((cx, cy), 0.22, fc=CONC_COL, ec="#555", lw=0.5, zorder=5)
        ax2.add_patch(circ_col)
        ax2.text(cx, cy, f"C{i+1}", ha="center", va="center",
                 fontsize=5, color=IS_BLUE, fontweight="bold")

    # Hoop bar layer (schematic)
    for r_layer in [R - 0.06, R + tw - 0.06]:
        for angle in np.linspace(0, 2 * math.pi, 36):
            ax2.plot(r_layer * math.cos(angle), r_layer * math.sin(angle),
                     "o", color=STEEL_COL, ms=2, zorder=6)

    # Centrelines
    ax2.axhline(0, color="#aaa", lw=0.5, ls="--", zorder=1)
    ax2.axvline(0, color="#aaa", lw=0.5, ls="--", zorder=1)

    # Dim
    _dim_line(ax2, 0, -wall_outer_R - 0.4, wall_outer_R, -wall_outer_R - 0.4,
              f"R+tw={wall_outer_R:.2f}m", offset=-0.3)
    ax2.text(0, R * 0.4, f"D={D:.1f}m", ha="center", va="center",
             fontsize=9, color=IS_BLUE, fontweight="bold", zorder=7)

    _callout(ax2, R + tw, 0.0,
             f"Wall t={int(tw*1000)}mm\n"
             f"Hoop Ø{reinforcement.get('wall',{}).get('hoop_bar_dia','—')}"
             f"@{reinforcement.get('wall',{}).get('hoop_spacing_mm','—')}mm",
             dx=0.8, dy=0.5)

    ax2.set_xlim(-R - 2.2, R + 2.5)
    ax2.set_ylim(-R - 1.8, R + 1.8)
    ax2.set_xlabel("Width (m)", fontsize=8, color="#333")
    ax2.set_ylabel("Width (m)", fontsize=8, color="#333")
    ax2.tick_params(labelsize=7)
    ax2.grid(True, alpha=0.2, lw=0.4)

    _add_north_legend(ax2)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    return _fig_to_bytes(fig)


# ─────────────────────────────────────────────────────────────────────────────
# INTZE TANK
# ─────────────────────────────────────────────────────────────────────────────
def draw_intze_tank(geometry: dict, reinforcement: dict) -> bytes:
    D      = geometry.get("D_int_m", 8.0)
    R      = D / 2
    Hc     = geometry.get("H_cylinder_m", 4.0)
    Hcone  = geometry.get("H_cone_m", 2.0)
    r1     = geometry.get("d1_m", D / 2) / 2
    R_bot  = geometry.get("R_bot_dome_m", 4.0)
    h_s    = geometry.get("h_s_m", 0.5)
    Hs     = geometry.get("staging_height_m", 12.0)
    rise_td = D / 5

    tw   = reinforcement.get("wall", {}).get("thickness_mm", 220) / 1000
    t_td = reinforcement.get("top_dome", {}).get("t_mm", 120) / 1000
    t_c  = reinforcement.get("conical_dome", {}).get("t_cone_mm", 160) / 1000
    t_bd = reinforcement.get("bottom_dome", {}).get("t_mm", 150) / 1000

    fig, ax = plt.subplots(1, 1, figsize=(10, 13), facecolor=BG_COL)
    fig.suptitle(f"Intze Elevated RCC Water Tank\n"
                 f"Capacity = {geometry.get('actual_vol_m3',0):.0f} m³  |  Ø{D:.1f}m",
                 fontsize=11, fontweight="bold", color=IS_BLUE, y=0.98)
    ax.set_facecolor(BG_COL)
    ax.set_aspect("equal")
    ax.set_title("Sectional Elevation (Half Section)", fontsize=9, color=IS_BLUE, pad=6)

    base_y = Hs   # base of cylindrical shell

    # ── Staging columns ─────────────────────────────────────────────────────
    ax.axhline(0, color="#666", lw=0.8, ls="--")
    ax.text(-0.2, -0.4, "GL", fontsize=7, color="#555")
    for x_c in [-R * 0.75, R * 0.75]:
        ax.add_patch(mpatches.FancyBboxPatch((x_c - 0.22, 0), 0.44, Hs,
                      boxstyle="square", fc=CONC_COL, ec="#555",
                      lw=0.6, hatch="//", zorder=2))
    # Ring girder
    brg_d = reinforcement.get("ring_girder", {}).get("d_mm", 800) / 1000
    brg_b = reinforcement.get("ring_girder", {}).get("b_mm", 500) / 1000
    ax.add_patch(mpatches.FancyBboxPatch((-R - tw - brg_b * 0.5, base_y - brg_d),
                  2 * (R + tw + brg_b * 0.5), brg_d,
                  boxstyle="square", fc=CONC_COL, ec="#555",
                  lw=0.7, hatch="//", zorder=3))
    _callout(ax, R + tw, base_y - brg_d / 2,
             f"Ring Girder\n{int(brg_b*1000)}×{int(brg_d*1000)}mm",
             dx=1.0, dy=-0.3)

    # ── Bottom spherical dome ────────────────────────────────────────────────
    theta_bd = math.degrees(math.asin(r1 / R_bot))
    y_bd_centre = base_y - math.sqrt(R_bot ** 2 - r1 ** 2)
    arc_bd = Arc((0, y_bd_centre), 2 * R_bot, 2 * R_bot,
                 angle=0, theta1=90 - theta_bd, theta2=90 + theta_bd,
                 color="#555", lw=1.2, zorder=4)
    ax.add_patch(arc_bd)
    ax.fill_between(
        np.linspace(-r1, r1, 100),
        y_bd_centre + np.sqrt(np.maximum(0, R_bot ** 2 - np.linspace(-r1, r1, 100) ** 2)),
        base_y,
        color=CONC_COL, alpha=0.6, zorder=3
    )
    _callout(ax, r1, y_bd_centre + math.sqrt(R_bot ** 2 - r1 ** 2) - h_s / 2,
             f"Bot Dome t={int(t_bd*1000)}mm\nR={R_bot:.2f}m",
             dx=-1.8, dy=-0.5)

    # ── Conical dome ──────────────────────────────────────────────────────────
    cone_top_y = base_y
    cone_bot_y = base_y - Hcone
    for sign in [-1, 1]:
        ax.plot([sign * r1, sign * R], [cone_bot_y, cone_top_y],
                color="#555", lw=1.5, zorder=4)
        # thickness offset (inner face)
        offset_x = sign * t_c / math.cos(math.atan2(Hcone, R - r1))
        ax.plot([sign * (r1 + sign * t_c), sign * (R + sign * t_c)],
                [cone_bot_y, cone_top_y],
                color="#888", lw=0.7, ls="--", zorder=4)
    ax.fill([-R, -r1, r1, R], [cone_top_y, cone_bot_y, cone_bot_y, cone_top_y],
            color=CONC_COL, alpha=0.5, zorder=3)
    _callout(ax, R / 2 + r1 / 2, (cone_top_y + cone_bot_y) / 2,
             f"Conical Dome t={int(t_c*1000)}mm\nα={geometry.get('cone_angle_deg',45):.0f}°",
             dx=1.2, dy=0.0)

    # Middle ring beam label
    mrb_d = reinforcement.get("middle_ring_beam", {}).get("d_mm", 500) / 1000
    _callout(ax, R + tw, cone_top_y,
             f"Middle Ring Beam\nT_net={reinforcement.get('intze_check',{}).get('T_net_brb_kN',0):.1f}kN",
             dx=1.0, dy=0.3)

    # ── Cylindrical wall ──────────────────────────────────────────────────────
    wall_top_y = base_y + Hc
    water_top  = base_y
    for sign in [-1, 1]:
        x0 = sign * R
        x1 = sign * (R + tw)
        ax.add_patch(mpatches.FancyBboxPatch(
            (min(x0, x1), base_y), abs(tw), Hc,
            boxstyle="square", fc=CONC_COL, ec="#555", lw=0.6, hatch="//", zorder=4
        ))
    _callout(ax, -(R + tw), base_y + Hc / 2,
             f"Wall t={int(tw*1000)}mm\nHoop: {reinforcement.get('wall',{}).get('hoop_bar_dia','—')}ø"
             f"@{reinforcement.get('wall',{}).get('hoop_spacing_mm','—')}",
             dx=-2.0, dy=0.0)

    # Water fill
    ax.add_patch(mpatches.FancyBboxPatch((-R, base_y), 2 * R, Hc * 0.95,
                  boxstyle="square", fc=WATER_COL, alpha=0.45, ec=None, zorder=3))
    ax.text(0, base_y + Hc * 0.5,
            f"Water\n{geometry.get('actual_vol_m3',0):.0f}m³",
            ha="center", va="center", fontsize=9, color=IS_BLUE,
            fontweight="bold", zorder=6)

    # FSL
    ax.plot([-R, R], [base_y + Hc, base_y + Hc],
            color=IS_BLUE, lw=0.8, ls="--", zorder=6)
    ax.text(R + 0.15, base_y + Hc, "FSL", fontsize=7, color=IS_BLUE, va="center")

    # ── Top dome ──────────────────────────────────────────────────────────────
    Rd_top = (R ** 2 + rise_td ** 2) / (2 * rise_td)
    y_td_ctr = wall_top_y + Rd_top - rise_td
    theta_td = math.degrees(math.asin(R / Rd_top))
    arc_td = Arc((0, y_td_ctr), 2 * Rd_top, 2 * Rd_top,
                 angle=0, theta1=90 - theta_td, theta2=90 + theta_td,
                 color="#555", lw=1.2, zorder=4)
    ax.add_patch(arc_td)
    _callout(ax, R * 0.6, y_td_ctr + Rd_top - rise_td + rise_td * 0.6,
             f"Top Dome t={int(t_td*1000)}mm\nR={Rd_top:.2f}m",
             dx=1.2, dy=0.2)

    # Top ring beam
    _callout(ax, R + tw, wall_top_y,
             f"Top Ring Beam\nT={reinforcement.get('top_dome',{}).get('T_top_ring_kN',0):.1f}kN",
             dx=0.8, dy=-0.3)

    # ── Dimension lines ───────────────────────────────────────────────────────
    _dim_line(ax, R + tw + 0.5, base_y, R + tw + 0.5, wall_top_y, f"Hc={Hc:.2f}m", 0.15)
    _dim_line(ax, R + tw + 0.5, cone_bot_y, R + tw + 0.5, base_y, f"Hcone={Hcone:.2f}m", 0.15)
    _dim_line(ax, R + tw + 0.5, 0, R + tw + 0.5, base_y, f"Hs={Hs:.1f}m", 0.15)
    _dim_line(ax, -R, base_y - 1.5, R, base_y - 1.5, f"D={D:.2f}m", -0.5)
    _dim_line(ax, -r1, cone_bot_y - 1.0, r1, cone_bot_y - 1.0, f"d1={geometry.get('d1_m',D/2):.2f}m", -0.5)

    ax.set_xlim(-R - 3.5, R + 3.5)
    ax.set_ylim(-1.5, Hs + Hc + rise_td + 2.0)
    ax.set_xlabel("Width (m)", fontsize=8, color="#333")
    ax.set_ylabel("Elevation (m)", fontsize=8, color="#333")
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.2, lw=0.4)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    return _fig_to_bytes(fig)


# ─────────────────────────────────────────────────────────────────────────────
# RECTANGULAR TANK
# ─────────────────────────────────────────────────────────────────────────────
def draw_rectangular_tank(geometry: dict, reinforcement: dict) -> bytes:
    L    = geometry.get("L_m", 5.0)
    B    = geometry.get("B_m", 3.5)
    Hw   = geometry.get("H_water_m", 3.0)
    Ht   = geometry.get("H_total_m", 3.3)
    Hs   = geometry.get("staging_height_m", 10.0)
    tw   = reinforcement.get("long_wall", {}).get("thickness_mm", 200) / 1000
    tf   = reinforcement.get("floor_slab", {}).get("thickness_mm", 250) / 1000
    t_rf = reinforcement.get("roof_slab", {}).get("thickness_mm", 150) / 1000

    fig, axes = plt.subplots(1, 2, figsize=(14, 10), facecolor=BG_COL)
    fig.suptitle(f"Rectangular Elevated RCC Water Tank\n"
                 f"Capacity = {geometry.get('actual_vol_m3',0):.0f} m³  |  "
                 f"{L:.1f}m × {B:.1f}m × {Hw:.1f}m",
                 fontsize=11, fontweight="bold", color=IS_BLUE, y=0.97)

    # ── Elevation (long section) ──────────────────────────────────────────────
    ax = axes[0]
    ax.set_facecolor(BG_COL)
    ax.set_aspect("equal")
    ax.set_title(f"Long Section (L = {L:.1f}m)", fontsize=9, color=IS_BLUE, pad=6)
    ax.axhline(0, color="#666", lw=0.8, ls="--")
    ax.text(-0.3, -0.4, "GL", fontsize=7, color="#555")

    base_y = Hs
    # Columns (4 corner)
    for xc in [-L / 2 * 0.8, L / 2 * 0.8]:
        ax.add_patch(mpatches.FancyBboxPatch((xc - 0.2, 0), 0.4, Hs,
                      boxstyle="square", fc=CONC_COL, ec="#555",
                      lw=0.6, hatch="//", zorder=2))
    # Long walls
    for sign in [-1, 1]:
        x0 = sign * L / 2
        ax.add_patch(mpatches.FancyBboxPatch(
            (x0 if sign > 0 else x0 - tw, base_y - tf), tw, Ht + tf,
            boxstyle="square", fc=CONC_COL, ec="#555", lw=0.6, hatch="//", zorder=4))
    # Floor
    ax.add_patch(mpatches.FancyBboxPatch((-L / 2 - tw, base_y - tf),
                  L + 2 * tw, tf, boxstyle="square",
                  fc=CONC_COL, ec="#555", lw=0.6, hatch="//", zorder=4))
    # Roof
    ax.add_patch(mpatches.FancyBboxPatch((-L / 2 - tw, base_y + Ht),
                  L + 2 * tw, t_rf, boxstyle="square",
                  fc=CONC_COL, ec="#555", lw=0.6, hatch="//", zorder=4))
    # Water
    ax.add_patch(mpatches.FancyBboxPatch((-L / 2, base_y), L, Hw,
                  boxstyle="square", fc=WATER_COL, alpha=0.5, ec=None, zorder=3))
    ax.text(0, base_y + Hw / 2, f"Water\n{geometry.get('actual_vol_m3',0):.0f}m³",
            ha="center", va="center", fontsize=9, color=IS_BLUE, fontweight="bold")

    ax.plot([-L / 2, L / 2], [base_y + Hw, base_y + Hw],
            color=IS_BLUE, lw=0.8, ls="--")
    ax.text(L / 2 + 0.1, base_y + Hw, "FSL", fontsize=7, color=IS_BLUE, va="center")

    _dim_line(ax, L / 2 + tw + 0.4, base_y, L / 2 + tw + 0.4, base_y + Ht,
              f"H={Ht:.2f}m", 0.15)
    _dim_line(ax, L / 2 + tw + 0.4, 0, L / 2 + tw + 0.4, base_y,
              f"Hs={Hs:.1f}m", 0.15)
    _dim_line(ax, -L / 2 - tw, base_y - 1.0, L / 2 + tw, base_y - 1.0,
              f"L={L:.2f}m", -0.4)

    _callout(ax, -(L / 2 + tw), base_y + Ht / 2,
             f"Long Wall\nt={int(tw*1000)}mm\n"
             f"Hoop {reinforcement.get('long_wall',{}).get('horiz_bar_dia','—')}ø"
             f"@{reinforcement.get('long_wall',{}).get('horiz_spacing_mm','—')}",
             dx=-1.8, dy=0.0)

    ax.set_xlim(-L / 2 - 3, L / 2 + 3)
    ax.set_ylim(-1.0, Hs + Ht + 1.5)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.2, lw=0.4)
    ax.set_xlabel("Width (m)", fontsize=8, color="#333")
    ax.set_ylabel("Elevation (m)", fontsize=8, color="#333")

    # ── Plan ────────────────────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor(BG_COL)
    ax2.set_aspect("equal")
    ax2.set_title("Plan View", fontsize=9, color=IS_BLUE, pad=6)
    # Outer rectangle
    ax2.add_patch(mpatches.FancyBboxPatch((-L/2-tw, -B/2-tw), L+2*tw, B+2*tw,
                   boxstyle="square", fc=CONC_COL, ec="#555", lw=0.8, hatch="//"))
    # Inner
    ax2.add_patch(mpatches.FancyBboxPatch((-L/2, -B/2), L, B,
                   boxstyle="square", fc=WATER_COL, ec=IS_BLUE, lw=0.6, alpha=0.5))
    # Columns
    for xc, yc in [(-L/2*0.8, -B/2*0.8), (L/2*0.8, -B/2*0.8),
                   (-L/2*0.8, B/2*0.8), (L/2*0.8, B/2*0.8)]:
        ax2.add_patch(mpatches.FancyBboxPatch((xc-0.2, yc-0.2), 0.4, 0.4,
                       boxstyle="square", fc=CONC_COL, ec="#555", lw=0.5))

    ax2.axhline(0, color="#aaa", lw=0.5, ls="--")
    ax2.axvline(0, color="#aaa", lw=0.5, ls="--")
    _dim_line(ax2, -L/2-tw, -B/2-tw-0.4, L/2+tw, -B/2-tw-0.4, f"L+2t={L+2*tw:.2f}m", -0.35)
    _dim_line(ax2, L/2+tw+0.4, -B/2-tw, L/2+tw+0.4, B/2+tw, f"B+2t={B+2*tw:.2f}m", 0.15)
    ax2.text(0, 0, f"{L:.1f}m×{B:.1f}m", ha="center", va="center",
             fontsize=9, color=IS_BLUE, fontweight="bold", zorder=5)

    ax2.set_xlim(-L/2 - 3, L/2 + 3)
    ax2.set_ylim(-B/2 - 2, B/2 + 2)
    ax2.tick_params(labelsize=7)
    ax2.grid(True, alpha=0.2, lw=0.4)
    ax2.set_xlabel("Length (m)", fontsize=8, color="#333")
    ax2.set_ylabel("Breadth (m)", fontsize=8, color="#333")

    _add_north_legend(ax2)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    return _fig_to_bytes(fig)


# ─────────────────────────────────────────────────────────────────────────────
# BBS BAR CHART
# ─────────────────────────────────────────────────────────────────────────────
def draw_bbs_chart(bbs: list) -> bytes:
    if not bbs:
        return b""
    from collections import defaultdict
    by_loc = defaultdict(float)
    for row in bbs:
        by_loc[row.get("location", "Unknown")[:30]] += float(row.get("weight_kg", 0))

    locs = list(by_loc.keys())
    wts  = [by_loc[l] for l in locs]
    total = sum(wts)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 5), facecolor=BG_COL)
    fig.suptitle("Bar Bending Schedule – Weight Distribution", fontsize=10,
                 fontweight="bold", color=IS_BLUE)

    # Bar chart
    colors_list = [IS_BLUE, IS_GOLD, STEEL_COL, "#27AE60",
                   "#8E44AD", "#16A085", "#E67E22"] * 5
    bars = ax.barh(locs, wts, color=colors_list[:len(locs)], edgecolor="white", height=0.7)
    for bar, wt in zip(bars, wts):
        ax.text(bar.get_width() + total * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{wt:.1f} kg", va="center", ha="left", fontsize=7, color="#333")
    ax.set_xlabel("Weight (kg)", fontsize=8, color="#333")
    ax.set_title("Weight by Location", fontsize=9, color=IS_BLUE)
    ax.tick_params(labelsize=7)
    ax.set_facecolor(BG_COL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0.98, 0.02, f"Total: {total:.0f} kg", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color=IS_BLUE, fontweight="bold")

    # Pie chart by dia
    by_dia = defaultdict(float)
    for row in bbs:
        by_dia[f"Ø{row.get('dia_mm','?')}mm"] += float(row.get("weight_kg", 0))
    labels = list(by_dia.keys())
    sizes  = [by_dia[l] for l in labels]
    wedge_colors = [IS_BLUE, IS_GOLD, STEEL_COL, "#27AE60", "#8E44AD", "#16A085"]
    ax2.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140,
            colors=wedge_colors[:len(labels)], textprops={"fontsize": 8},
            wedgeprops={"edgecolor": "white", "linewidth": 1.5})
    ax2.set_title("Proportion by Bar Diameter", fontsize=9, color=IS_BLUE)
    ax2.set_facecolor(BG_COL)

    plt.tight_layout()
    return _fig_to_bytes(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def _add_north_legend(ax):
    ax.annotate("N ↑", xy=(0.92, 0.92), xycoords="axes fraction",
                fontsize=9, color=IS_BLUE, fontweight="bold",
                ha="center",
                bbox=dict(boxstyle="circle,pad=0.3", fc="white",
                          ec=IS_BLUE, lw=1.0))


def dispatch_drawing(tank_type: str, geometry: dict, reinforcement: dict) -> bytes:
    """Dispatch to the correct drawing function based on tank type."""
    tt = tank_type.lower()
    if "intze" in tt:
        return draw_intze_tank(geometry, reinforcement)
    elif "rect" in tt:
        return draw_rectangular_tank(geometry, reinforcement)
    else:
        return draw_circular_tank(geometry, reinforcement)
