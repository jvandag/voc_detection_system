from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, MaxNLocator
try:
    from scipy.signal import butter, filtfilt
except ImportError:  # pragma: no cover - optional dependency in some envs
    butter = None
    filtfilt = None


EPOCH_COLUMN = "epoch"
CHAMBER_COLUMN = "chamber"
ELAPSED_HOURS_COLUMN = "elapsed_hours"

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "light_med_dark_exp1_data"
OUTPUT_DIR = BASE_DIR / "plots" / "visualizer2_raw"
EPOCH_WINDOW_MIN = 1773786659
EPOCH_WINDOW_MAX = 1774164141

SPECTRAL_OUTPUT_BASES = ["spectral_raw_comparison"]
STACKED_FIGURE_WIDTH = 12
STACKED_FIGURE_HEIGHT_PER_CHAMBER = 3.8
METRIC_GROUP_TITLE_FONT_SIZE = 20
STACKED_SUBPLOT_HSPACE_MULTIPLIER = 2.0
MIN_PEAK_POINTS = 3
FIT_IGNORE_FIRST_N_PEAKS = 0
OFFSET_SCAN_SPAN_FACTOR = 0.8
OFFSET_SCAN_POINTS = 120
APPLY_BUTTERWORTH_TO_TEMP_HUMIDITY = True
BUTTERWORTH_ORDER = 4
BUTTERWORTH_NORMALIZED_CUTOFF = 0.08

BME688_COLUMNS = [f"bme688_gas_res_{i}" for i in range(8)] + ["bme688_pressure"]
SCD30_COLUMNS = ["scd30_co2_ppm", "scd30_temp_c", "scd30_rel_humidity_pct"]
SCD41X_COLUMNS = ["scd41x_co2_ppm", "scd41x_temp_c", "scd41x_rel_humidity_pct"]
AVG_FREQ_COLUMNS = [f"avg_frequency_{i}" for i in range(10)]

SENSOR_COLUMNS = BME688_COLUMNS + SCD30_COLUMNS + SCD41X_COLUMNS + AVG_FREQ_COLUMNS
ALL_COLUMNS = [EPOCH_COLUMN, CHAMBER_COLUMN] + SENSOR_COLUMNS

ROAST_BY_CHAMBER = {
    1: "Light Roast",
    2: "Medium Roast",
    3: "Dark Roast",
}

METRIC_SPECS = [
    ("co2", "CO2 (ppm)", 0),
    ("temp", "Temperature (C)", 1),
    ("humidity", "Relative Humidity (%)", 2),
]

METRIC_GROUP_TITLES = {
    "co2": "CO2 ppm Over Time",
    "temp": "Temperature Over Time",
    "humidity": "Relative Humidity Over Time",
}


def _extract_chamber_number(chamber_name: str) -> int:
    digits = "".join(ch for ch in chamber_name if ch.isdigit())
    return int(digits) if digits else 999


def _display_chamber_label(chamber_name: str) -> str:
    chamber_num = _extract_chamber_number(chamber_name)
    roast = ROAST_BY_CHAMBER.get(chamber_num)
    if roast:
        # return f"{roast} ({chamber_name})"
        return f"{roast}"
    return chamber_name


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

    # Apply optional digital filtering before trimming to the selected epoch window.
    if APPLY_BUTTERWORTH_TO_TEMP_HUMIDITY:
        filter_columns = [
            (SCD30_COLUMNS[1], "temp"),
            (SCD30_COLUMNS[2], "humidity"),
            (SCD41X_COLUMNS[1], "temp"),
            (SCD41X_COLUMNS[2], "humidity"),
        ]
        for column_name, metric_slug in filter_columns:
            column_values = pd.to_numeric(df[column_name], errors="coerce").to_numpy(dtype=float)
            df[column_name] = _apply_optional_butterworth(column_values, metric_slug)

    epoch_mask = df[EPOCH_COLUMN].between(EPOCH_WINDOW_MIN, EPOCH_WINDOW_MAX, inclusive="both")
    df = df.loc[epoch_mask].copy()

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


def _apply_optional_butterworth(values: np.ndarray, metric_slug: str) -> np.ndarray:
    if metric_slug not in {"temp", "humidity"}:
        return values
    if not APPLY_BUTTERWORTH_TO_TEMP_HUMIDITY:
        return values
    if butter is None or filtfilt is None:
        raise ImportError(
            "Butterworth filtering requested, but scipy is not available. "
            "Install scipy or set APPLY_BUTTERWORTH_TO_TEMP_HUMIDITY = False."
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


def _plot_group_raw(
    title: str,
    columns: Iterable[str],
    chamber_data: Dict[str, pd.DataFrame],
    output_bases: Sequence[Path],
) -> None:
    plot_columns = list(columns)
    ncols = 3 if len(plot_columns) > 3 else len(plot_columns)
    nrows = math.ceil(len(plot_columns) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 3.8 * nrows), squeeze=False)
    axes_flat = axes.flatten()

    chamber_items = sorted(chamber_data.items(), key=lambda item: _extract_chamber_number(item[0]))

    for idx, column in enumerate(plot_columns):
        ax = axes_flat[idx]
        for chamber_name, chamber_df in chamber_items:
            ax.plot(
                chamber_df[ELAPSED_HOURS_COLUMN],
                chamber_df[column],
                linewidth=1.4,
                label=_display_chamber_label(chamber_name),
            )
        ax.set_title(column)
        ax.set_ylabel("Raw sensor value")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=8))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _pos: f"{x:.1f}"))
        ax.tick_params(axis="x", labelrotation=35)
        ax.grid(alpha=0.3)

    for idx in range(len(plot_columns), len(axes_flat)):
        fig.delaxes(axes_flat[idx])

    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=max(1, len(labels)), frameon=False)
    fig.suptitle(title, fontsize=14)
    fig.supxlabel("Hours from first sample")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    _save_figure(fig, output_bases)
    plt.close(fig)


def _detect_local_peak_points(x_values: np.ndarray, y_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if len(x_values) < 4 or len(y_values) < 4:
        return np.array([], dtype=float), np.array([], dtype=float)

    # Peak rule:
    # Let:
    #   i-2 = (y[i-1] - y[i-2])
    #   i-1 = (y[i]   - y[i-1])
    #   i+1 = (y[i+1] - y[i])
    # Rule:
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


def _select_fit_peak_points(peak_x: np.ndarray, peak_y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    # Peak filtering happens in _detect_local_peak_points. Keep this passthrough
    # so plotting and fitting always use the exact same peak set.
    return peak_x, peak_y


def _fit_single_exp_with_offset(
    fit_t: np.ndarray,
    fit_y: np.ndarray,
    full_t: np.ndarray,
) -> Tuple[np.ndarray, float, float, float] | None:
    if len(fit_y) < 3:
        return None

    y_min = float(np.min(fit_y))
    y_max = float(np.max(fit_y))
    y_span = y_max - y_min
    epsilon = max(1e-9, y_span * 1e-6)
    offset_low = y_min - max(epsilon, OFFSET_SCAN_SPAN_FACTOR * max(y_span, epsilon))
    offset_high = y_min - epsilon
    if offset_low >= offset_high:
        return None

    best_score = -np.inf
    best_fit: Tuple[float, float, float] | None = None
    for offset in np.linspace(offset_low, offset_high, OFFSET_SCAN_POINTS):
        shifted = fit_y - offset
        if np.any(shifted <= 0):
            continue

        with np.errstate(divide="ignore", invalid="ignore"):
            log_shifted = np.log(shifted)
        if not np.all(np.isfinite(log_shifted)):
            continue

        slope, intercept = np.polyfit(fit_t, log_shifted, 1)
        pred_log = intercept + slope * fit_t
        residual = log_shifted - pred_log
        ss_res = float(np.sum(residual * residual))
        ss_tot = float(np.sum((log_shifted - np.mean(log_shifted)) ** 2))
        score = -ss_res if ss_tot <= 0 else 1.0 - (ss_res / ss_tot)

        if score > best_score:
            best_score = score
            best_fit = (offset, intercept, slope)

    if best_fit is None:
        return None

    best_offset, best_intercept, best_slope = best_fit
    trend = best_offset + np.exp(best_intercept + best_slope * full_t)
    return trend, best_offset, best_intercept, best_slope


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

    fit_result = _fit_single_exp_with_offset(fit_t, fit_y, full_t)
    if fit_result is not None:
        trend, c_val, a_val, b_val = fit_result
        formula = (
            f"Fit: $y={c_val:.3g}+e^{{{a_val:.3g}+{b_val:.3g}(x-{x_ref:.3g})}}$"
            f"{skip_note}"
        )
        return trend, formula

    return None, None


def _plot_stacked_metric_chambers(
    sensor_name: str,
    sensor_aliases: Sequence[str],
    metric_column: str,
    metric_label: str,
    metric_slug: str,
    chamber_data: Dict[str, pd.DataFrame],
    output_dir: Path,
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
        y_series = pd.to_numeric(chamber_df[metric_column], errors="coerce")
        valid = x_series.notna() & y_series.notna()

        x = x_series[valid].to_numpy(dtype=float)
        y = y_series[valid].to_numpy(dtype=float)
        if len(x) == 0:
            ax.set_title(f"{_display_chamber_label(chamber_name)} (no valid data)")
            ax.grid(alpha=0.3)
            continue

        raw_label = f"Raw {metric_label}"
        if metric_slug == "co2":
            raw_label = f"CO2 ppm ({sensor_name})"
        elif APPLY_BUTTERWORTH_TO_TEMP_HUMIDITY and metric_slug in {"temp", "humidity"}:
            raw_label = f"Filtered {metric_label} ({sensor_name})"

        raw_line = ax.plot(
            x,
            y,
            color="#1f77b4",
            linewidth=1.2,
            label=raw_label,
        )

        peak_x, peak_y = _detect_local_peak_points(x, y)
        fit_peak_x, fit_peak_y = _select_fit_peak_points(peak_x, peak_y)
        peak_points = ax.scatter(
            fit_peak_x,
            fit_peak_y,
            s=18,
            color="#2ca02c",
            alpha=0.8,
            label="Peaks used for fit",
        )
        trend_y, trend_label = _fit_peak_trendline(fit_peak_x, fit_peak_y, x)
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
        ax.set_ylabel(metric_label)
        ax.grid(alpha=0.3)

    for ax in axes_flat:
        ax.set_xlabel("Hours from first sample")
        ax.tick_params(axis="x", labelbottom=True)
    axes_flat[-1].xaxis.set_major_locator(MaxNLocator(nbins=10))
    axes_flat[-1].xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:.1f}"))
    group_title = METRIC_GROUP_TITLES.get(metric_slug, f"{metric_label} Over Time")
    fig.suptitle(group_title, fontsize=METRIC_GROUP_TITLE_FONT_SIZE)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    default_hspace = float(plt.rcParams.get("figure.subplot.hspace", 0.2))
    fig.subplots_adjust(hspace=default_hspace * STACKED_SUBPLOT_HSPACE_MULTIPLIER)
    output_bases = [output_dir / f"{alias}_{metric_slug}_raw_stacked_chambers" for alias in sensor_aliases]
    _save_figure(fig, output_bases)
    plt.close(fig)


def _plot_stacked_overlap_groups(
    sensor_name: str,
    sensor_aliases: Sequence[str],
    chamber_data: Dict[str, pd.DataFrame],
    co2_column: str,
    secondary_column: str,
    secondary_slug: str,
    secondary_label: str,
    group_title: str,
    output_dir: Path,
    include_co2_fit: bool = False,
    output_suffix: str = "",
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
        ax_left = axes_flat[idx]
        ax_right = ax_left.twinx()

        x_series = pd.to_numeric(chamber_df[ELAPSED_HOURS_COLUMN], errors="coerce")
        co2_series = pd.to_numeric(chamber_df[co2_column], errors="coerce")
        second_series = pd.to_numeric(chamber_df[secondary_column], errors="coerce")

        valid = x_series.notna() & co2_series.notna() & second_series.notna()
        x = x_series[valid].to_numpy(dtype=float)
        y_co2 = co2_series[valid].to_numpy(dtype=float)
        y_second = second_series[valid].to_numpy(dtype=float)

        if len(x) == 0:
            ax_left.set_title(f"{_display_chamber_label(chamber_name)} (no valid data)")
            ax_left.grid(alpha=0.3)
            continue

        line_co2 = ax_left.plot(
            x,
            y_co2,
            color="#1f77b4",
            linewidth=1.4,
            label=f"CO2 ppm ({sensor_name})",
        )
        second_prefix = "Filtered " if APPLY_BUTTERWORTH_TO_TEMP_HUMIDITY else ""
        line_second = ax_right.plot(
            x,
            y_second,
            color="#ff7f0e",
            linewidth=1.3,
            label=f"{second_prefix}{secondary_label} ({sensor_name})",
        )

        fit_line = None
        if include_co2_fit:
            peak_x, peak_y = _detect_local_peak_points(x, y_co2)
            fit_peak_x, fit_peak_y = _select_fit_peak_points(peak_x, peak_y)
            trend_y, trend_label = _fit_peak_trendline(fit_peak_x, fit_peak_y, x)
            if trend_y is not None and trend_label is not None:
                fit_line = ax_left.plot(
                    x,
                    trend_y,
                    color="#d62728",
                    linewidth=2.0,
                    linestyle="--",
                    label=trend_label,
                )

        handles = [line_co2[0], line_second[0]]
        if fit_line:
            handles.append(fit_line[0])
        labels = [h.get_label() for h in handles]
        ax_left.legend(handles, labels, loc="upper right", frameon=False)

        ax_left.set_title(_display_chamber_label(chamber_name))
        ax_left.set_ylabel("CO2 (ppm)")
        ax_left.grid(alpha=0.3)

        ax_right.set_ylabel(secondary_label)
        ax_right.yaxis.set_label_position("right")
        ax_right.yaxis.tick_right()
        ax_right.tick_params(axis="y", labelright=True, labelleft=False)

    for ax in axes_flat:
        ax.set_xlabel("Hours from first sample")
        ax.tick_params(axis="x", labelbottom=True)
    axes_flat[-1].xaxis.set_major_locator(MaxNLocator(nbins=10))
    axes_flat[-1].xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:.1f}"))
    fig.suptitle(group_title, fontsize=METRIC_GROUP_TITLE_FONT_SIZE)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    default_hspace = float(plt.rcParams.get("figure.subplot.hspace", 0.2))
    fig.subplots_adjust(hspace=default_hspace * STACKED_SUBPLOT_HSPACE_MULTIPLIER)
    suffix = f"_{output_suffix}" if output_suffix else ""
    output_bases = [
        output_dir / f"{alias}_co2_{secondary_slug}_overlapped_stacked_chambers{suffix}"
        for alias in sensor_aliases
    ]
    _save_figure(fig, output_bases)
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

    _plot_group_raw(
        title="Spectral Sensor Raw Readings",
        columns=AVG_FREQ_COLUMNS,
        chamber_data=chamber_data,
        output_bases=[OUTPUT_DIR / name for name in SPECTRAL_OUTPUT_BASES],
    )

    for metric_slug, metric_label, metric_idx in METRIC_SPECS:
        _plot_stacked_metric_chambers(
            sensor_name="SCD30",
            sensor_aliases=["scd30"],
            metric_column=SCD30_COLUMNS[metric_idx],
            metric_label=metric_label,
            metric_slug=metric_slug,
            chamber_data=chamber_data,
            output_dir=OUTPUT_DIR,
        )
        _plot_stacked_metric_chambers(
            sensor_name="SCD40",
            sensor_aliases=["scd40", "scd41"],
            metric_column=SCD41X_COLUMNS[metric_idx],
            metric_label=metric_label,
            metric_slug=metric_slug,
            chamber_data=chamber_data,
            output_dir=OUTPUT_DIR,
        )

    _plot_stacked_overlap_groups(
        sensor_name="SCD30",
        sensor_aliases=["scd30"],
        chamber_data=chamber_data,
        co2_column=SCD30_COLUMNS[0],
        secondary_column=SCD30_COLUMNS[2],
        secondary_slug="humidity",
        secondary_label="Relative Humidity (%)",
        group_title="CO2 and Relative Humidity Over Time (SCD30)",
        output_dir=OUTPUT_DIR,
    )
    _plot_stacked_overlap_groups(
        sensor_name="SCD30",
        sensor_aliases=["scd30"],
        chamber_data=chamber_data,
        co2_column=SCD30_COLUMNS[0],
        secondary_column=SCD30_COLUMNS[2],
        secondary_slug="humidity",
        secondary_label="Relative Humidity (%)",
        group_title="CO2 and Relative Humidity Over Time (SCD30, with CO2 Fit)",
        output_dir=OUTPUT_DIR,
        include_co2_fit=True,
        output_suffix="with_co2_fit",
    )
    _plot_stacked_overlap_groups(
        sensor_name="SCD30",
        sensor_aliases=["scd30"],
        chamber_data=chamber_data,
        co2_column=SCD30_COLUMNS[0],
        secondary_column=SCD30_COLUMNS[1],
        secondary_slug="temp",
        secondary_label="Temperature (C)",
        group_title="CO2 and Temperature Over Time (SCD30)",
        output_dir=OUTPUT_DIR,
    )
    _plot_stacked_overlap_groups(
        sensor_name="SCD30",
        sensor_aliases=["scd30"],
        chamber_data=chamber_data,
        co2_column=SCD30_COLUMNS[0],
        secondary_column=SCD30_COLUMNS[1],
        secondary_slug="temp",
        secondary_label="Temperature (C)",
        group_title="CO2 and Temperature Over Time (SCD30, with CO2 Fit)",
        output_dir=OUTPUT_DIR,
        include_co2_fit=True,
        output_suffix="with_co2_fit",
    )

    _plot_stacked_overlap_groups(
        sensor_name="SCD40",
        sensor_aliases=["scd40", "scd41"],
        chamber_data=chamber_data,
        co2_column=SCD41X_COLUMNS[0],
        secondary_column=SCD41X_COLUMNS[2],
        secondary_slug="humidity",
        secondary_label="Relative Humidity (%)",
        group_title="CO2 and Relative Humidity Over Time (SCD40)",
        output_dir=OUTPUT_DIR,
    )
    _plot_stacked_overlap_groups(
        sensor_name="SCD40",
        sensor_aliases=["scd40", "scd41"],
        chamber_data=chamber_data,
        co2_column=SCD41X_COLUMNS[0],
        secondary_column=SCD41X_COLUMNS[2],
        secondary_slug="humidity",
        secondary_label="Relative Humidity (%)",
        group_title="CO2 and Relative Humidity Over Time (SCD40, with CO2 Fit)",
        output_dir=OUTPUT_DIR,
        include_co2_fit=True,
        output_suffix="with_co2_fit",
    )
    _plot_stacked_overlap_groups(
        sensor_name="SCD40",
        sensor_aliases=["scd40", "scd41"],
        chamber_data=chamber_data,
        co2_column=SCD41X_COLUMNS[0],
        secondary_column=SCD41X_COLUMNS[1],
        secondary_slug="temp",
        secondary_label="Temperature (C)",
        group_title="CO2 and Temperature Over Time (SCD40)",
        output_dir=OUTPUT_DIR,
    )
    _plot_stacked_overlap_groups(
        sensor_name="SCD40",
        sensor_aliases=["scd40", "scd41"],
        chamber_data=chamber_data,
        co2_column=SCD41X_COLUMNS[0],
        secondary_column=SCD41X_COLUMNS[1],
        secondary_slug="temp",
        secondary_label="Temperature (C)",
        group_title="CO2 and Temperature Over Time (SCD40, with CO2 Fit)",
        output_dir=OUTPUT_DIR,
        include_co2_fit=True,
        output_suffix="with_co2_fit",
    )


if __name__ == "__main__":
    main()
