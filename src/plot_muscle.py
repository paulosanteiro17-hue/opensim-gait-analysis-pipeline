from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import find_peaks


MUSCLE_ALIASES = {
    "rect_fem_r": ["rect_fem_r", "rec_fem_r"],
    "semimem_r": ["semimem_r", "semi_mem_r"],
    "bifemlh_r": ["bifemlh_r", "bi_fem_lh_r"],
    "gasmed_r": ["gasmed_r", "med_gas_r"],
    "soleus_r": ["soleus_r", "sol_r"],
    "tib_ant_r": ["tib_ant_r"],
}

DISPLAY_NAMES = {
    "rect_fem_r": "Reto femoral",
    "semimem_r": "Semimembranoso",
    "bifemlh_r": "Bíceps femoral — cabeça longa",
    "gasmed_r": "Gastrocnêmio medial",
    "soleus_r": "Sóleo",
    "tib_ant_r": "Tibial anterior",
}


def load_opensim_file(filepath: Path) -> pd.DataFrame:
    filepath = filepath.expanduser().resolve()
    skip_lines = 0

    with filepath.open("r", encoding="utf-8", errors="ignore") as file:
        for index, line in enumerate(file):
            if line.startswith("endheader"):
                skip_lines = index + 1
                break
            if line.startswith("time"):
                skip_lines = index
                break

    return pd.read_csv(filepath, sep="\t", skiprows=skip_lines)


def find_muscle_column(dataframe: pd.DataFrame, standard_name: str) -> str | None:
    for alias in MUSCLE_ALIASES[standard_name]:
        if alias in dataframe.columns:
            return alias
    return None


def cycle_bounds_from_peak_times(
    signal_time: np.ndarray,
    peak_times: np.ndarray,
) -> list[tuple[int, int]]:
    bounds: list[tuple[int, int]] = []

    for start_time, end_time in zip(peak_times[:-1], peak_times[1:]):
        start_index = int(np.argmin(np.abs(signal_time - start_time)))
        end_index = int(np.argmin(np.abs(signal_time - end_time)))

        if end_index > start_index + 5:
            bounds.append((start_index, end_index))

    return bounds


def process_cycles(
    signal: np.ndarray,
    bounds: list[tuple[int, int]],
) -> np.ndarray:
    normalized_cycles: list[np.ndarray] = []
    normalized_axis = np.linspace(0, 100, 101)

    for start_index, end_index in bounds:
        cycle = np.asarray(signal[start_index:end_index], dtype=float)

        if cycle.size < 4 or not np.isfinite(cycle).all():
            continue

        original_axis = np.linspace(0, 100, cycle.size)
        interpolator = interp1d(
            original_axis,
            cycle,
            kind="cubic",
            bounds_error=False,
            fill_value="extrapolate",
        )
        normalized_cycles.append(interpolator(normalized_axis))

    return np.asarray(normalized_cycles)


def select_file(title: str, pattern: str) -> Path | None:
    root = tk.Tk()
    root.withdraw()
    selected = filedialog.askopenfilename(
        title=title,
        filetypes=[("OpenSim files", pattern), ("Todos os arquivos", "*.*")],
    )
    root.destroy()
    return Path(selected) if selected else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera gráficos de variação musculotendínea."
    )
    parser.add_argument("--ik_file", type=str, default=None)
    parser.add_argument("--muscle_file", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    ik_path = Path(args.ik_file) if args.ik_file else select_file(
        "Selecione o arquivo MOT da cinemática inversa",
        "*.mot",
    )
    muscle_path = Path(args.muscle_file) if args.muscle_file else select_file(
        "Selecione o arquivo STO de comprimentos musculotendíneos",
        "*.sto",
    )

    if ik_path is None or muscle_path is None:
        print("Processamento cancelado: arquivos não selecionados.")
        return

    if not ik_path.exists() or not muscle_path.exists():
        raise FileNotFoundError("Arquivo MOT ou STO não encontrado.")

    df_ik = load_opensim_file(ik_path)
    df_muscle = load_opensim_file(muscle_path)

    if not {"time", "hip_flexion_r"}.issubset(df_ik.columns):
        raise ValueError("O MOT não contém time e hip_flexion_r.")
    if "time" not in df_muscle.columns:
        raise ValueError("O STO muscular não contém a coluna time.")

    peaks, _ = find_peaks(
        df_ik["hip_flexion_r"].to_numpy(),
        distance=50,
        prominence=10,
    )
    if len(peaks) < 2:
        raise ValueError("Foram encontrados menos de dois picos de flexão do quadril.")

    peak_times = df_ik["time"].iloc[peaks].to_numpy()
    muscle_time = df_muscle["time"].to_numpy()
    bounds = cycle_bounds_from_peak_times(muscle_time, peak_times)

    available: list[tuple[str, str]] = []
    for standard_name in MUSCLE_ALIASES:
        column = find_muscle_column(df_muscle, standard_name)
        if column is not None:
            available.append((standard_name, column))

    if not available:
        raise ValueError("Nenhum dos músculos esperados foi encontrado no STO.")

    rows = (len(available) + 1) // 2
    fig, axes = plt.subplots(rows, 2, figsize=(12, 3.5 * rows), sharex=True)
    axes_array = np.atleast_1d(axes).flatten()
    normalized_axis = np.linspace(0, 100, 101)

    fig.suptitle(
        "Variação dos Comprimentos Musculotendíneos",
        fontsize=16,
        fontweight="bold",
        y=0.98,
    )

    plotted = 0
    for axis, (standard_name, column) in zip(axes_array, available):
        # Metros -> centímetros e centralização individual.
        signal = df_muscle[column].to_numpy(dtype=float) * 100.0
        signal = signal - np.mean(signal)

        cycles = process_cycles(signal, bounds)
        if len(cycles) == 0:
            axis.set_visible(False)
            continue

        mean = np.mean(cycles, axis=0)
        std = np.std(cycles, axis=0, ddof=1) if len(cycles) > 1 else np.zeros(101)

        axis.plot(normalized_axis, mean, linewidth=2.5, label="Média")
        axis.fill_between(
            normalized_axis,
            mean - std,
            mean + std,
            alpha=0.2,
            label="± 1 DP",
        )
        axis.axhline(0, linewidth=0.8, alpha=0.6)
        axis.set_title(DISPLAY_NAMES[standard_name])
        axis.set_ylabel("Variação de comprimento (cm)")
        axis.set_xlim(0, 100)
        axis.grid(True, linestyle="--", alpha=0.6)

        if plotted == 0:
            axis.legend(loc="best", fontsize=9)
        plotted += 1

    for axis in axes_array[len(available):]:
        axis.set_visible(False)

    fig.supxlabel("Ciclo da Marcha (%)", y=0.055)
    fig.text(
        0.5,
        0.015,
        "Curvas centralizadas pela média temporal individual; ciclos estimados pelos picos de flexão do quadril direito.",
        ha="center",
        fontsize=9,
        style="italic",
    )
    plt.tight_layout(rect=[0, 0.07, 1, 0.95])

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"Gráfico salvo em: {output_path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
