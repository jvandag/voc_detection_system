from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, MaxNLocator


EPOCH_COLUMN = "epoch"
CHAMBER_COLUMN = "chamber"
ELAPSED_HOURS_COLUMN = "elapsed_hours"

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "light_med_dark_exp1_data"
OUTPUT_DIR = BASE_DIR / "plots" / "visualizer_bme688_raw"
EPOCH_WINDOW_MIN = 1773786659
EPOCH_WINDOW_MAX = 1774164141

STACKED_FIGURE_WIDTH = 12
STACKED_FIGURE_HEIGHT_PER_CHAMBER = 3.8
GROUP_TITLE_FONT_SIZE = 20
STACKED_SUBPLOT_HSPACE_MULTIPLIER = 2.0
FIT_IGNORE_FIRST_N_PEAKS = 0
POLY_FIT_ORDER = 4

BME688_GAS_COLUMNS = [f"bme688_gas_res_{i}" for i in range(8)]
BME688_DERIVED_COLUMN = "bme688_norm_sum"

SCD30_COLUMNS = ["scd30_co2_ppm", "scd30_temp_c", "scd30_rel_humidity_pct"]
SCD41X_COLUMNS = ["scd41x_co2_ppm", "scd41x_temp_c", "scd41x_rel_humidity_pct"]
AVG_FREQ_COLUMNS = [f"avg_frequency_{i}" for i in range(10)]

SENSOR_COLUMNS = BME688_GAS_COLUMNS + ["bme688_pressure"] + SCD30_COLUMNS + SCD41X_COLUMNS + AVG_FREQ_COLUMNS
ALL_COLUMNS = [EPOCH_COLUMN, CHAMBER_COLUMN] + SENSOR_COLUMNS

ROAST_BY_CHAMBER = {
    1: "Light Roast",
    2: "Medium Roast",
    3: "Dark Roast",
}
LIGHT_ROAST_CHAMBER_NUMBER = 1


def _extract_chamber_number(chamber_name: str) -> int:
    digits = "".join(ch for ch in chamber_name if ch.isdigit())
    return int(digits) if digits else 999


def _display_chamber_label(chamber_name: str) -> str:
    chamber_num = _extract_chamber_number(chamber_name)
    return ROAST_BY_CHAMBER.get(chamber_num, chamber_name)


def _canonical_chamber_name(raw_value: object, fallback_name: str) -> str:
    raw_text = str(raw_value).strip()
    try:
        chamber_num = int(float(raw_text))
        return f"Chamber {chamber_num}"
    except (TypeError, ValueError):
        if raw_text:
            return raw_text
        return fallback_name


def _load_chamber_csv(csv_path: Path) -> Tuple[str, pd.DataFrame]:
    df = pd.read_csv(
        csv_path,
        header=None,
        names=ALL_COLUMNS,
        usecols=range(len(ALL_COLUMNS)),
        on_bad_lines="skip",
    )

    for column in [EPOCH_COLUMN] + SENSOR_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    chamber_values = df[CHAMBER_COLUMN].dropna()
    chamber_raw = chamber_values.iloc[0] if not chamber_values.empty else csv_path.stem
    chamber_name = _canonical_chamber_name(chamber_raw, fallback_name=csv_path.stem)

    epoch_mask = df[EPOCH_COLUMN].between(EPOCH_WINDOW_MIN, EPOCH_WINDOW_MAX, inclusive="both")
    df = df.loc[epoch_mask].copy()

    base = df[BME688_GAS_COLUMNS[0]].replace(0, np.nan)
    normalized = df[BME688_GAS_COLUMNS].div(base, axis=0)
    df[BME688_DERIVED_COLUMN] = normalized.sum(axis=1, min_count=len(BME688_GAS_COLUMNS))

    return chamber_name, df


def _build_chamber_data(csv_paths: Sequence[Path]) -> Dict[str, pd.DataFrame]:
    chamber_data: Dict[str, pd.DataFrame] = {}
    for csv_path in csv_paths:
        chamber_name, df = _load_chamber_csv(csv_path)
        chamber_data[chamber_name] = df

    all_start_times = [
        chamber_df[EPOCH_COLUMN].dropna().min()
        for chamber_df in chamber_data.values()
        if not chamber_df[EPOCH_COLUMN].dropna().empty
    ]
    if not all_start_times:
        raise ValueError(
            "No valid epoch values were found in chamber CSV data "
            f"within [{EPOCH_WINDOW_MIN}, {EPOCH_WINDOW_MAX}]."
        )
    first_sample_epoch = min(all_start_times)

    for chamber_df in chamber_data.values():
        chamber_df[ELAPSED_HOURS_COLUMN] = (chamber_df[EPOCH_COLUMN] - first_sample_epoch) / 3600.0

    return chamber_data


def _save_figure(fig: plt.Figure, output_bases: Sequence[Path]) -> None:
    for output_base in output_bases:
        png_dir = output_base.parent / "png"
        pdf_dir = output_base.parent / "pdf"
        png_dir.mkdir(parents=True, exist_ok=True)
        pdf_dir.mkdir(parents=True, exist_ok=True)

        png_path = png_dir / f"{output_base.stem}.png"
        pdf_path = pdf_dir / f"{output_base.stem}.pdf"
        fig.savefig(png_path, dpi=180)
        fig.savefig(pdf_path)
        print(f"Wrote: {png_path}")
        print(f"Wrote: {pdf_path}")


def _detect_local_peak_points(x_values: np.ndarray, y_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if len(x_values) < 4 or len(y_values) < 4:
        return np.array([], dtype=float), np.array([], dtype=float)

    # Peak rule:
    # Let:
    #   i-2 = (y[i-1] - y[i-2])
    #   i-1 = (y[i]   - y[i-1])
    #   i+1 = (y[i+1] - y[i])
    # Rule requested:
    #   - i-2 and i-1 can be positive or negative
    #   - i+1 must be negative
    #   - |i+1| > 3 * (|i-1| + |i-2|)
    peak_indices: list[int] = []
    for idx in range(2, len(y_values) - 1):
        delta_prev_2 = y_values[idx - 1] - y_values[idx - 2]
        delta_prev_1 = y_values[idx] - y_values[idx - 1]
        delta_next = y_values[idx + 1] - y_values[idx]

        if delta_next < 0 and abs(delta_next) > 3.0 * (abs(delta_prev_1) + abs(delta_prev_2)):
            peak_indices.append(idx)

    peak_idx = np.array(peak_indices, dtype=int)
    return x_values[peak_idx], y_values[peak_idx]


def _fit_polynomial(
    fit_t: np.ndarray,
    fit_y: np.ndarray,
    full_t: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray] | None:
    if len(fit_y) < (POLY_FIT_ORDER + 1):
        return None

    coeffs = np.polyfit(fit_t, fit_y, POLY_FIT_ORDER)
    trend = np.polyval(coeffs, full_t)
    return trend, coeffs


def _fit_peak_trendline(
    peak_x: np.ndarray,
    peak_y: np.ndarray,
    x_full: np.ndarray,
) -> Tuple[np.ndarray | None, str | None]:
    if len(peak_x) < 3:
        return None, None

    order = np.argsort(peak_x)
    fit_x = peak_x[order]
    fit_y = peak_y[order]

    if FIT_IGNORE_FIRST_N_PEAKS > 0 and len(fit_x) > FIT_IGNORE_FIRST_N_PEAKS:
        fit_x = fit_x[FIT_IGNORE_FIRST_N_PEAKS:]
        fit_y = fit_y[FIT_IGNORE_FIRST_N_PEAKS:]

    if len(fit_x) < 3:
        return None, None

    skip_note = f", skip first {FIT_IGNORE_FIRST_N_PEAKS}" if FIT_IGNORE_FIRST_N_PEAKS > 0 else ""
    x_ref = float(np.min(fit_x))
    fit_t = fit_x - x_ref
    full_t = x_full - x_ref

    fit_result = _fit_polynomial(fit_t, fit_y, full_t)
    if fit_result is None:
        return None, None

    trend, coeffs = fit_result
    c4, c3, c2, c1, c0 = coeffs

    def _term(coeff: float, term_suffix: str, leading: bool = False) -> str:
        sign = "-" if coeff < 0 else "+"
        magnitude = f"{abs(coeff):.2g}{term_suffix}"
        if leading:
            return magnitude if sign == "+" else f"-{magnitude}"
        return f"{sign}{magnitude}"

    formula = (
        f"Fit: $y={_term(c4, f'(x-{x_ref:.3g})^4', leading=True)}"
        f"{_term(c3, f'(x-{x_ref:.3g})^3')}$\n"
        f"${_term(c2, f'(x-{x_ref:.3g})^2')}"
        f"{_term(c1, f'(x-{x_ref:.3g})')}{_term(c0, '')}$"
        f"{skip_note}"
    )
    return trend, formula


def _plot_bme_stacked(chamber_data: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    chamber_items = sorted(chamber_data.items(), key=lambda item: _extract_chamber_number(item[0]))
    if not chamber_items:
        raise ValueError("No chamber data available to plot.")

    fig, axes = plt.subplots(
        nrows=len(chamber_items),
        ncols=1,
        figsize=(STACKED_FIGURE_WIDTH, STACKED_FIGURE_HEIGHT_PER_CHAMBER * len(chamber_items)),
        sharex=True,
        squeeze=False,
    )
    axes_flat = axes.flatten()

    for idx, (chamber_name, chamber_df) in enumerate(chamber_items):
        ax = axes_flat[idx]
        x_series = pd.to_numeric(chamber_df[ELAPSED_HOURS_COLUMN], errors="coerce")
        y_series = pd.to_numeric(chamber_df[BME688_DERIVED_COLUMN], errors="coerce")
        valid = x_series.notna() & y_series.notna()

        x = x_series[valid].to_numpy(dtype=float)
        y = y_series[valid].to_numpy(dtype=float)
        if len(x) == 0:
            ax.set_title(f"{_display_chamber_label(chamber_name)} (no valid data)")
            ax.grid(alpha=0.3)
            continue

        raw_line = ax.plot(
            x,
            y,
            color="#1f77b4",
            linewidth=1.2,
            label="BME688 norm sum",
        )

        peak_x, peak_y = _detect_local_peak_points(x, y)
        peak_points = ax.scatter(
            peak_x,
            peak_y,
            s=18,
            color="#2ca02c",
            alpha=0.8,
            label="Peaks used for fit",
        )
        chamber_num = _extract_chamber_number(chamber_name)
        trend_y = None
        trend_label = None
        if chamber_num != LIGHT_ROAST_CHAMBER_NUMBER:
            trend_y, trend_label = _fit_peak_trendline(peak_x, peak_y, x)
        trend_line = None
        if trend_y is not None and trend_label is not None:
            trend_line = ax.plot(
                x,
                trend_y,
                color="#d62728",
                linewidth=2.0,
                linestyle="--",
                label=trend_label,
            )

        legend_handles = [raw_line[0], peak_points]
        if trend_line:
            legend_handles.append(trend_line[0])
        ax.legend(handles=legend_handles, loc="upper right", frameon=False)

        ax.set_title(_display_chamber_label(chamber_name))
        ax.set_ylabel(r"$\sum_{i=0}^{7} \left(\mathrm{BME}_i / \mathrm{BME}_0\right)$")
        ax.grid(alpha=0.3)

    for ax in axes_flat:
        ax.set_xlabel("Hours from first sample")
        ax.tick_params(axis="x", labelbottom=True)
    axes_flat[-1].xaxis.set_major_locator(MaxNLocator(nbins=10))
    axes_flat[-1].xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:.1f}"))

    fig.suptitle("BME688 Normalized Sum Over Time", fontsize=GROUP_TITLE_FONT_SIZE)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    default_hspace = float(plt.rcParams.get("figure.subplot.hspace", 0.2))
    fig.subplots_adjust(hspace=default_hspace * STACKED_SUBPLOT_HSPACE_MULTIPLIER)

    _save_figure(fig, [output_dir / "bme688_normalized_sum_stacked_chambers"])
    plt.close(fig)


def _find_csv_paths(input_dir: Path) -> list[Path]:
    patterns = ["chamber_*_readings.csv", "chamber_*_test_readings.csv"]
    found = []
    for pattern in patterns:
        found.extend(input_dir.glob(pattern))
    return sorted(set(found))


def main() -> None:
    csv_paths = _find_csv_paths(INPUT_DIR)
    if not csv_paths:
        raise FileNotFoundError(f"No chamber CSV files found in: {INPUT_DIR}")

    chamber_data = _build_chamber_data(csv_paths)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _plot_bme_stacked(chamber_data, output_dir=OUTPUT_DIR)


if __name__ == "__main__":
    main()
