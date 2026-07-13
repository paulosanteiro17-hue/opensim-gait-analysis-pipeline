from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import detrend, find_peaks


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    normalized_cycles: list[np.ndarray] = []
    normalized_axis = np.linspace(0, 100, 101)

    for start_index, end_index in bounds:
        cycle = np.asarray(signal[start_index:end_index], dtype=float)

        if cycle.size < 4 or not np.isfinite(cycle).all():
            continue

        original_axis = np.linspace(0, 100, cycle.size)
        interpolation_kind = "cubic" if cycle.size >= 4 else "linear"
        interpolator = interp1d(
            original_axis,
            cycle,
            kind=interpolation_kind,
            bounds_error=False,
            fill_value="extrapolate",
        )
        normalized_cycles.append(interpolator(normalized_axis))

    if not normalized_cycles:
        raise ValueError("Nenhum ciclo válido foi encontrado.")

    cycles = np.asarray(normalized_cycles)
    mean = np.mean(cycles, axis=0)
    std = np.std(cycles, axis=0, ddof=1) if len(cycles) > 1 else np.zeros(101)
    return cycles, mean, std, normalized_axis


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
    parser = argparse.ArgumentParser(description="Gera gráfico do centro de massa.")
    parser.add_argument("--ik_file", type=str, default=None)
    parser.add_argument("--com_file", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    mot_path = Path(args.ik_file) if args.ik_file else select_file(
        "Selecione o arquivo MOT da cinemática inversa",
        "*.mot",
    )
    com_path = Path(args.com_file) if args.com_file else select_file(
        "Selecione o arquivo STO do centro de massa",
        "*.sto",
    )

    if mot_path is None or com_path is None:
        print("Processamento cancelado: arquivos não selecionados.")
        return

    if not mot_path.exists() or not com_path.exists():
        raise FileNotFoundError("Arquivo MOT ou STO não encontrado.")

    df_mot = load_opensim_file(mot_path)
    df_com = load_opensim_file(com_path)

    required_mot = {"time", "hip_flexion_r"}
    required_com = {
        "time",
        "center_of_mass_X",
        "center_of_mass_Y",
        "center_of_mass_Z",
    }

    if not required_mot.issubset(df_mot.columns):
        raise ValueError("O MOT não contém time e hip_flexion_r.")
    if not required_com.issubset(df_com.columns):
        raise ValueError("O STO não contém as colunas esperadas do centro de massa.")

    peaks, _ = find_peaks(
        df_mot["hip_flexion_r"].to_numpy(),
        distance=30,
        prominence=10,
    )
    if len(peaks) < 2:
        raise ValueError("Foram encontrados menos de dois picos de flexão do quadril.")

    peak_times = df_mot["time"].iloc[peaks].to_numpy()
    com_time = df_com["time"].to_numpy()
    bounds = cycle_bounds_from_peak_times(com_time, peak_times)

    # Conversão de metros para centímetros.
    com_x = detrend(df_com["center_of_mass_X"].to_numpy(dtype=float)) * 100.0
    com_y = (
        df_com["center_of_mass_Y"].to_numpy(dtype=float)
        - df_com["center_of_mass_Y"].mean()
    ) * 100.0
    com_z = (
        df_com["center_of_mass_Z"].to_numpy(dtype=float)
        - df_com["center_of_mass_Z"].mean()
    ) * 100.0

    results = [
        (*process_cycles(com_x, bounds), "Anteroposterior — detrendido"),
        (*process_cycles(com_y, bounds), "Vertical — centrado"),
        (*process_cycles(com_z, bounds), "Mediolateral — centrado"),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    fig.suptitle(
        "Deslocamento do Centro de Massa ao longo do Ciclo da Marcha",
        fontsize=16,
        fontweight="bold",
        y=0.97,
    )

    for axis, result in zip(axes, results):
        cycles, mean, std, normalized_axis, title = result

        for cycle in cycles:
            axis.plot(normalized_axis, cycle, alpha=0.25, linewidth=1)

        axis.plot(
            normalized_axis,
            mean,
            linewidth=2.5,
            label=f"Média ({len(cycles)} ciclos)",
        )
        axis.fill_between(
            normalized_axis,
            mean - std,
            mean + std,
            alpha=0.2,
            label="± 1 DP",
        )
        axis.set_title(title, loc="left")
        axis.set_ylabel("Deslocamento (cm)")
        axis.set_xlim(0, 100)
        axis.grid(True, linestyle="--", alpha=0.6)
        axis.legend(loc="upper right", fontsize=9)

    axes[-1].set_xlabel("Ciclo da Marcha (%)")
    fig.text(
        0.5,
        0.015,
        "Eventos de ciclo estimados cinematicamente pelos picos de flexão do quadril direito.",
        ha="center",
        fontsize=9,
        style="italic",
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])

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
