from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator
import matplotlib.patheffects as path_effects
try:
    from scipy.signal import butter, filtfilt
except ImportError:  # pragma: no cover - optional dependency in some envs
    butter = None
    filtfilt = None


EPOCH_COLUMN = "epoch"
CHAMBER_COLUMN = "chamber"
ELAPSED_HOURS_COLUMN = "elapsed_hours"

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIRS = [
    BASE_DIR / "light_med_dark_exp1_data",
    BASE_DIR / "open_air_samples",
    BASE_DIR / "medium_roast_control_data",
]
OUTPUT_DIR = BASE_DIR / "plots" / "visualizer_bme688_raw"
EPOCH_WINDOW_MIN = 1773786659
EPOCH_WINDOW_MAX = 1774164141
ALIGN_END_SAMPLE_DIRS = {"open_air_samples", "medium_roast_control_data"}

STACKED_FIGURE_WIDTH = 13.2
STACKED_FIGURE_HEIGHT_PER_CHAMBER = 3.8
GROUP_TITLE_FONT_SIZE = 26
STACKED_SUBPLOT_HSPACE_MULTIPLIER = 3.0
FIT_IGNORE_FIRST_N_PEAKS = 0
POLY_FIT_ORDER = 4
APPLY_BUTTERWORTH_TO_BME688 = True
BUTTERWORTH_ORDER = 4
BUTTERWORTH_NORMALIZED_CUTOFF = 0.08
BME_LINE_WIDTH_MIN = 2.4
BME_LINE_WIDTH_MAX = 4.2
SUMMARY_LINE_WIDTH = 3.0
BME_STROKE_WIDTH = 1.2
BME_STROKE_ALPHA = 0.25
SUMMARY_STROKE_WIDTH = 1.1
SUMMARY_STROKE_ALPHA = 0.25
LEGEND_TOP_Y = 0.93
TITLE_TOP_Y = 0.97
LAYOUT_TOP = 2 * LEGEND_TOP_Y - TITLE_TOP_Y+0.03

BASE_FONT_SIZE = 16
AXIS_TITLE_FONT_SIZE = 18
AXIS_LABEL_FONT_SIZE = 17
TICK_LABEL_FONT_SIZE = 14
LEGEND_FONT_SIZE = 14

plt.rcParams.update(
    {
        "font.size": BASE_FONT_SIZE,
        "axes.titlesize": AXIS_TITLE_FONT_SIZE,
        "axes.labelsize": AXIS_LABEL_FONT_SIZE,
        "xtick.labelsize": TICK_LABEL_FONT_SIZE,
        "ytick.labelsize": TICK_LABEL_FONT_SIZE,
        "legend.fontsize": LEGEND_FONT_SIZE,
        "figure.titlesize": GROUP_TITLE_FONT_SIZE,
    }
)

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


def _load_chamber_csv(
    csv_path: Path,
    epoch_window: Tuple[int, int] | None = None,
) -> Tuple[str, pd.DataFrame]:
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

    if epoch_window is not None:
        window_min, window_max = epoch_window
        epoch_mask = df[EPOCH_COLUMN].between(window_min, window_max, inclusive="both")
        df = df.loc[epoch_mask].copy()

    base = df[BME688_GAS_COLUMNS[0]].replace(0, np.nan)
    normalized = df[BME688_GAS_COLUMNS].div(base, axis=0)
    df[BME688_DERIVED_COLUMN] = normalized.sum(axis=1, min_count=len(BME688_GAS_COLUMNS))

    return chamber_name, df


def _build_chamber_data(
    csv_paths: Sequence[Path],
    align_end_samples: bool = False,
    epoch_window: Tuple[int, int] | None = None,
) -> Dict[str, pd.DataFrame]:
    chamber_data: Dict[str, pd.DataFrame] = {}
    for csv_path in csv_paths:
        chamber_name, df = _load_chamber_csv(csv_path, epoch_window=epoch_window)
        chamber_data[chamber_name] = df

    if align_end_samples:
        last_samples = [
            chamber_df[EPOCH_COLUMN].dropna().max()
            for chamber_df in chamber_data.values()
            if not chamber_df[EPOCH_COLUMN].dropna().empty
        ]
        if not last_samples:
            raise ValueError("No valid epoch values were found in chamber CSV data.")
        cutoff_epoch = min(last_samples)
        for chamber_name, chamber_df in chamber_data.items():
            chamber_data[chamber_name] = chamber_df.loc[
                chamber_df[EPOCH_COLUMN] <= cutoff_epoch
            ].copy()

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


def _apply_optional_butterworth(values: np.ndarray) -> np.ndarray:
    if not APPLY_BUTTERWORTH_TO_BME688:
        return values
    if butter is None or filtfilt is None:
        raise ImportError(
            "Butterworth filtering requested, but scipy is not available. "
            "Install scipy or set APPLY_BUTTERWORTH_TO_BME688 = False."
        )

    values = np.asarray(values, dtype=float)
    min_len = BUTTERWORTH_ORDER * 3 + 3

    b, a = butter(BUTTERWORTH_ORDER, BUTTERWORTH_NORMALIZED_CUTOFF, btype="low")

    valid = np.isfinite(values)
    if not np.any(valid):
        return values

    filtered = values.copy()
    if np.all(valid):
        if len(values) < min_len:
            return values
        try:
            return np.asarray(filtfilt(b, a, values), dtype=float)
        except ValueError:
            return values

    valid_idx = np.where(valid)[0]
    splits = np.where(np.diff(valid_idx) > 1)[0] + 1
    segments = np.split(valid_idx, splits)
    for segment in segments:
        if len(segment) < min_len:
            continue
        start = int(segment[0])
        end = int(segment[-1]) + 1
        try:
            filtered[start:end] = filtfilt(b, a, filtered[start:end])
        except ValueError:
            continue
    return np.asarray(filtered, dtype=float)


def _format_plain_comma(value: float) -> str:
    if not np.isfinite(value):
        return ""
    if abs(value - round(value)) < 1e-6:
        return f"{value:,.0f}"
    if abs(value) >= 1000:
        return f"{value:,.3f}"
    return f"{value:.3f}"


def _format_bme_sensor_label(column_name: str) -> str:
    if column_name.startswith("bme688_gas_res_"):
        try:
            sensor_idx = int(column_name.rsplit("_", 1)[-1]) + 1
            return f"BME688 Sensor {sensor_idx}"
        except ValueError:
            return column_name
    return column_name


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


def _plot_bme_raw_stacked(
    chamber_data: Dict[str, pd.DataFrame],
    output_dir: Path,
    chamber_title_override: str | None = None,
) -> None:
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

        has_any = False
        total_lines = len(BME688_GAS_COLUMNS)
        for line_idx, column in enumerate(BME688_GAS_COLUMNS):
            raw_values = pd.to_numeric(chamber_df[column], errors="coerce").to_numpy(dtype=float)
            filtered_values = _apply_optional_butterworth(raw_values)
            y_series = pd.Series(filtered_values, index=chamber_df.index)
            valid = x_series.notna() & y_series.notna()

            x = x_series[valid].to_numpy(dtype=float)
            y = y_series[valid].to_numpy(dtype=float)
            if len(x) == 0:
                continue

            has_any = True
            if total_lines > 1:
                back_weight = (total_lines - 1 - line_idx) / (total_lines - 1)
            else:
                back_weight = 0.0
            line_width = BME_LINE_WIDTH_MIN + (BME_LINE_WIDTH_MAX - BME_LINE_WIDTH_MIN) * back_weight
            if line_idx in {0, 1}:
                line_width *= 0.8
            line = ax.plot(
                x,
                y,
                linewidth=line_width,
                label=_format_bme_sensor_label(column),
            )
            line[0].set_path_effects(
                [
                    path_effects.Stroke(
                        linewidth=line_width + BME_STROKE_WIDTH,
                        foreground=(0, 0, 0, BME_STROKE_ALPHA),
                    ),
                    path_effects.Normal(),
                ]
            )

        chamber_title = chamber_title_override or _display_chamber_label(chamber_name)
        if not has_any:
            ax.set_title(f"{chamber_title} (no valid data)")
            ax.grid(alpha=0.3)
            continue

        ax.set_title(chamber_title)
        ax.set_ylabel("Filtered raw value")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_plain_comma(v)))
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(alpha=0.3)

    for ax in axes_flat:
        ax.set_xlabel("Hours from first sample")
        ax.tick_params(axis="x", labelbottom=True)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_plain_comma(v)))
    axes_flat[-1].xaxis.set_major_locator(MaxNLocator(nbins=10))
    axes_flat[-1].xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:.1f}"))

    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=4,
        frameon=True,
        edgecolor="#d0d0d0",
        facecolor="none",
        bbox_to_anchor=(0.5, LEGEND_TOP_Y),
        borderpad=0.4,
        labelspacing=0.4,
        handletextpad=0.6,
    )
    fig.suptitle("BME688 Raw Readings Over Time", fontsize=GROUP_TITLE_FONT_SIZE, y=TITLE_TOP_Y)
    fig.tight_layout(rect=(0, 0, 1, LAYOUT_TOP))
    default_hspace = float(plt.rcParams.get("figure.subplot.hspace", 0.2))
    fig.subplots_adjust(hspace=default_hspace * STACKED_SUBPLOT_HSPACE_MULTIPLIER)

    _save_figure(fig, [output_dir / "bme688_raw_stacked_chambers"])
    plt.close(fig)


def _plot_bme_stacked(
    chamber_data: Dict[str, pd.DataFrame],
    output_dir: Path,
    chamber_title_override: str | None = None,
    disable_fit: bool = False,
) -> None:
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
    fit_labels: list[str] = []
    include_peaks = False

    for idx, (chamber_name, chamber_df) in enumerate(chamber_items):
        ax = axes_flat[idx]
        x_series = pd.to_numeric(chamber_df[ELAPSED_HOURS_COLUMN], errors="coerce")
        y_series = pd.to_numeric(chamber_df[BME688_DERIVED_COLUMN], errors="coerce")
        valid = x_series.notna() & y_series.notna()

        x = x_series[valid].to_numpy(dtype=float)
        y = y_series[valid].to_numpy(dtype=float)
        chamber_title = chamber_title_override or _display_chamber_label(chamber_name)
        if len(x) == 0:
            ax.set_title(f"{chamber_title} (no valid data)")
            ax.grid(alpha=0.3)
            continue

        raw_line = ax.plot(
            x,
            y,
            color="#1f77b4",
            linewidth=SUMMARY_LINE_WIDTH,
            label="BME688 norm sum",
        )
        raw_line[0].set_path_effects(
            [
                path_effects.Stroke(
                    linewidth=SUMMARY_LINE_WIDTH + SUMMARY_STROKE_WIDTH,
                    foreground=(0, 0, 0, SUMMARY_STROKE_ALPHA),
                ),
                path_effects.Normal(),
            ]
        )

        if not disable_fit:
            peak_x, peak_y = _detect_local_peak_points(x, y)
            peak_points = ax.scatter(
                peak_x,
                peak_y,
                s=18,
                color="#2ca02c",
                alpha=0.8,
                label="Peaks used for fit",
            )
            include_peaks = True
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
                clean_label = trend_label
                if clean_label.startswith("Fit: "):
                    clean_label = clean_label.replace("Fit: ", "", 1)
                fit_labels.append(f"{chamber_title} Fit Line: {clean_label}")

        ax.set_title(chamber_title)
        ax.set_ylabel("Normalized Sum")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_plain_comma(v)))
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(alpha=0.3)

    for ax in axes_flat:
        ax.set_xlabel("Hours from first sample")
        ax.tick_params(axis="x", labelbottom=True)
    axes_flat[-1].xaxis.set_major_locator(MaxNLocator(nbins=10))
    axes_flat[-1].xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:.1f}"))

    legend_handles = [
        Line2D([0], [0], color="#1f77b4", linewidth=SUMMARY_LINE_WIDTH, label="BME688 norm sum"),
    ]
    if include_peaks:
        legend_handles.append(
            Line2D(
                [0],
                [0],
                linestyle="",
                marker="o",
                markersize=6,
                markerfacecolor="#2ca02c",
                markeredgecolor="none",
                label="Peaks used for fit",
            )
        )
    for fit_label in fit_labels:
        legend_handles.append(
            Line2D(
                [0],
                [0],
                color="#d62728",
                linewidth=2.0,
                linestyle="--",
                label=fit_label,
            )
        )
    fig.legend(
        legend_handles,
        [h.get_label() for h in legend_handles],
        loc="upper center",
        ncol=2,
        frameon=True,
        edgecolor="#d0d0d0",
        facecolor="none",
        bbox_to_anchor=(0.5, LEGEND_TOP_Y),
        borderpad=0.4,
        labelspacing=0.4,
        handletextpad=0.6,
    )
    fig.suptitle("BME688 Normalized Sum Over Time", fontsize=GROUP_TITLE_FONT_SIZE, y=TITLE_TOP_Y)
    fig.tight_layout(rect=(0, 0, 1, LAYOUT_TOP))
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for input_dir in INPUT_DIRS:
        csv_paths = _find_csv_paths(input_dir)
        if not csv_paths:
            print(f"No chamber CSV files found in: {input_dir}")
            continue

        align_end_samples = input_dir.name in ALIGN_END_SAMPLE_DIRS
        chamber_title_override = None
        disable_fit = False
        epoch_window = None
        if input_dir.name == "medium_roast_control_data":
            chamber_title_override = "Medium Roast"
            disable_fit = True
        elif input_dir.name == "open_air_samples":
            chamber_title_override = "Open Air"
        elif input_dir.name == "light_med_dark_exp1_data":
            epoch_window = (EPOCH_WINDOW_MIN, EPOCH_WINDOW_MAX)
        chamber_data = _build_chamber_data(
            csv_paths,
            align_end_samples=align_end_samples,
            epoch_window=epoch_window,
        )
        output_dir = OUTPUT_DIR / input_dir.name
        output_dir.mkdir(parents=True, exist_ok=True)
        _plot_bme_raw_stacked(
            chamber_data,
            output_dir=output_dir,
            chamber_title_override=chamber_title_override,
        )
        _plot_bme_stacked(
            chamber_data,
            output_dir=output_dir,
            chamber_title_override=chamber_title_override,
            disable_fit=disable_fit,
        )


if __name__ == "__main__":
    main()
