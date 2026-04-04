from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, MaxNLocator


EPOCH_COLUMN = "epoch"
CHAMBER_COLUMN = "chamber"
ELAPSED_HOURS_COLUMN = "elapsed_hours"
DEFAULT_NORMALIZE = False
DEFAULT_SAVE_BOTH = True
DEFAULT_BME_ROW_NORMALIZE = False

MODE_RAW = "raw"
MODE_NORMALIZED = "normalized"
MODE_BME_ROW_NORMALIZED = "bme_row_normalized"

BME688_COLUMNS = [f"bme688_gas_res_{i}" for i in range(8)] + ["bme688_pressure"]
SCD30_COLUMNS = ["scd30_co2_ppm", "scd30_temp_c", "scd30_rel_humidity_pct"]
SCD41X_COLUMNS = ["scd41x_co2_ppm", "scd41x_temp_c", "scd41x_rel_humidity_pct"]
AVG_FREQ_COLUMNS = [f"avg_frequency_{i}" for i in range(10)]

SENSOR_COLUMNS = BME688_COLUMNS + SCD30_COLUMNS + SCD41X_COLUMNS + AVG_FREQ_COLUMNS
ALL_COLUMNS = [EPOCH_COLUMN, CHAMBER_COLUMN] + SENSOR_COLUMNS

PLOT_GROUPS: List[Tuple[str, List[str], str]] = [
    ("BME688 Readings", BME688_COLUMNS, "bme688_comparison.png"),
    ("SCD30 Readings", SCD30_COLUMNS, "scd30_comparison.png"),
    ("SCD41x Readings", SCD41X_COLUMNS, "scd41x_comparison.png"),
    (
        "Average Frequency Readings",
        AVG_FREQ_COLUMNS,
        "avg_frequency_comparison.png",
    ),
]


def _baseline_from_column(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().sort_values()
    if values.empty:
        return float("nan")

    if len(values) >= 10:
        window = values.iloc[4:10]
    elif len(values) >= 5:
        window = values.iloc[4:]
    else:
        window = values

    baseline = float(window.mean())
    if np.isnan(baseline) or baseline == 0:
        return float("nan")
    return baseline


def _load_chamber_csv(csv_path: Path, mode: str) -> Tuple[str, pd.DataFrame]:
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
    chamber_raw = str(chamber_values.iloc[0]).strip() if not chamber_values.empty else csv_path.stem
    if chamber_raw.isdigit():
        chamber_name = f"Chamber {chamber_raw}"
    else:
        chamber_name = chamber_raw

    processed_df = df.copy()
    if mode == MODE_NORMALIZED:
        for column in SENSOR_COLUMNS:
            baseline = _baseline_from_column(df[column])
            if np.isnan(baseline):
                processed_df[column] = np.nan
            else:
                processed_df[column] = df[column] / baseline
    elif mode == MODE_BME_ROW_NORMALIZED:
        row_divider = pd.to_numeric(df[BME688_COLUMNS[0]], errors="coerce")
        row_divider = row_divider.replace(0, np.nan)
        for column in BME688_COLUMNS:
            processed_df[column] = df[column] / row_divider

    return chamber_name, processed_df


def _build_chamber_data(csv_paths: List[Path], mode: str) -> Dict[str, pd.DataFrame]:
    chamber_data: Dict[str, pd.DataFrame] = {}
    for csv_path in csv_paths:
        chamber_name, processed_df = _load_chamber_csv(csv_path, mode=mode)
        chamber_data[chamber_name] = processed_df

    all_start_times = [
        chamber_df[EPOCH_COLUMN].dropna().min()
        for chamber_df in chamber_data.values()
        if not chamber_df[EPOCH_COLUMN].dropna().empty
    ]
    if not all_start_times:
        raise ValueError("No valid epoch values were found in chamber data.")
    first_sample_epoch = min(all_start_times)

    for chamber_df in chamber_data.values():
        chamber_df[ELAPSED_HOURS_COLUMN] = (chamber_df[EPOCH_COLUMN] - first_sample_epoch) / 3600.0

    return chamber_data


def _plot_group(
    title: str,
    columns: Iterable[str],
    chamber_data: Dict[str, pd.DataFrame],
    output_path: Path,
    mode: str,
) -> None:
    plot_columns = list(columns)
    ncols = 3 if len(plot_columns) > 3 else len(plot_columns)
    nrows = math.ceil(len(plot_columns) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 3.8 * nrows), squeeze=False)
    axes_flat = axes.flatten()

    for idx, column in enumerate(plot_columns):
        ax = axes_flat[idx]
        for chamber_name, chamber_df in chamber_data.items():
            ax.plot(
                chamber_df[ELAPSED_HOURS_COLUMN],
                chamber_df[column],
                linewidth=1.4,
                label=chamber_name,
            )
        ax.set_title(column)
        if mode == MODE_NORMALIZED:
            ax.set_ylabel("Normalized value")
        elif mode == MODE_BME_ROW_NORMALIZED:
            ax.set_ylabel("Value (BME row-normalized mode)")
        else:
            ax.set_ylabel("Sensor value")
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
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare chamber sensor readings over time. "
            "Optionally normalize each sensor column by the average of its 5th-10th lowest readings."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing chamber CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "plots",
        help="Directory where generated plot PNGs are saved.",
    )
    parser.add_argument(
        "--normalize",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_NORMALIZE,
        help=(
            "Enable per-column normalization (5th-10th lowest average baseline). "
            "Use --no-normalize to plot raw values."
        ),
    )
    parser.add_argument(
        "--save-both",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_SAVE_BOTH,
        help=(
            "Generate normalized, raw, and BME row-normalized plots in separate subfolders. "
            "Use --no-save-both to generate only the selected normalize mode."
        ),
    )
    parser.add_argument(
        "--bme-row-normalize",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_BME_ROW_NORMALIZE,
        help=(
            "Apply row-wise normalization to BME columns only (divide all BME values in a row "
            f"by `{BME688_COLUMNS[0]}` from that same row)."
        ),
    )
    args = parser.parse_args()

    csv_paths = sorted(args.input_dir.glob("chamber_*_test_readings.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No chamber CSV files found in: {args.input_dir}")

    mode_settings: List[str]
    if args.save_both:
        mode_settings = [MODE_NORMALIZED, MODE_RAW, MODE_BME_ROW_NORMALIZED]
    elif args.bme_row_normalize:
        mode_settings = [MODE_BME_ROW_NORMALIZED]
    else:
        mode_settings = [MODE_NORMALIZED if args.normalize else MODE_RAW]

    mode_title = {
        MODE_NORMALIZED: "Normalized",
        MODE_RAW: "Raw",
        MODE_BME_ROW_NORMALIZED: "BME Row Normalized",
    }

    for mode_name in mode_settings:
        chamber_data = _build_chamber_data(csv_paths, mode=mode_name)
        mode_output_dir = args.output_dir / mode_name
        mode_output_dir.mkdir(parents=True, exist_ok=True)

        for base_title, columns, file_name in PLOT_GROUPS:
            output_path = mode_output_dir / f"{Path(file_name).stem}_{mode_name}.png"
            _plot_group(
                title=f"{base_title} ({mode_title[mode_name]})",
                columns=columns,
                chamber_data=chamber_data,
                output_path=output_path,
                mode=mode_name,
            )
            print(f"Wrote: {output_path}")


if __name__ == "__main__":
    main()
