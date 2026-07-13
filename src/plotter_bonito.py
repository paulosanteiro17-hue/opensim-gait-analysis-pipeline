from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import butter, filtfilt, find_peaks


def load_mot_file(filepath: Path) -> pd.DataFrame:
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


def process_cycles(
    signal: np.ndarray,
    peaks: np.ndarray,
) -> np.ndarray:
    normalized_cycles: list[np.ndarray] = []
    normalized_axis = np.linspace(0, 100, 101)

    for start_index, end_index in zip(peaks[:-1], peaks[1:]):
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


def lowpass_filter(
    signal: np.ndarray,
    time: np.ndarray,
    cutoff_hz: float = 6.0,
) -> np.ndarray:
    if len(signal) < 20 or len(time) < 2:
        return signal

    dt = float(np.median(np.diff(time)))
    if dt <= 0:
        return signal

    sampling_rate = 1.0 / dt
    normalized_cutoff = cutoff_hz / (sampling_rate / 2.0)

    if not 0 < normalized_cutoff < 1:
        return signal

    b, a = butter(4, normalized_cutoff, btype="low")
    minimum_length = 3 * max(len(a), len(b))

    if len(signal) <= minimum_length:
        return signal

    return filtfilt(b, a, signal)


def select_file() -> Path | None:
    root = tk.Tk()
    root.withdraw()
    selected = filedialog.askopenfilename(
        title="Selecione o arquivo MOT da cinemática inversa",
        filetypes=[("OpenSim Motion Files", "*.mot"), ("Todos os arquivos", "*.*")],
    )
    root.destroy()
    return Path(selected) if selected else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera gráfico da cinemática articular.")
    parser.add_argument("--ik_file", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    input_path = Path(args.ik_file) if args.ik_file else select_file()
    if input_path is None:
        print("Processamento cancelado: arquivo não selecionado.")
        return
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    dataframe = load_mot_file(input_path)

    required_columns = {
        "time",
        "hip_flexion_r",
        "knee_angle_r",
        "ankle_angle_r",
    }
    missing = required_columns.difference(dataframe.columns)
    if missing:
        raise ValueError(
            "O MOT não contém todas as colunas necessárias: "
            + ", ".join(sorted(missing))
        )

    peaks, _ = find_peaks(
        dataframe["hip_flexion_r"].to_numpy(),
        distance=50,
        prominence=10,
    )
    if len(peaks) < 2:
        raise ValueError("Foram encontrados menos de dois picos de flexão do quadril.")

    time = dataframe["time"].to_numpy(dtype=float)
    variables = [
        (
            dataframe["hip_flexion_r"].to_numpy(dtype=float),
            "Quadril direito — flexão/extensão",
        ),
        (
            -dataframe["knee_angle_r"].to_numpy(dtype=float),
            "Joelho direito — flexão/extensão",
        ),
        (
            lowpass_filter(
                dataframe["ankle_angle_r"].to_numpy(dtype=float),
                time,
                cutoff_hz=6.0,
            ),
            "Tornozelo direito — dorsiflexão/flexão plantar",
        ),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    normalized_axis = np.linspace(0, 100, 101)

    fig.suptitle(
        "Cinemática Articular ao longo do Ciclo da Marcha",
        fontsize=16,
        fontweight="bold",
        y=0.97,
    )

    for axis, (signal, title) in zip(axes, variables):
        cycles = process_cycles(signal, peaks)
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
        axis.set_title(title, loc="left")
        axis.set_ylabel("Ângulo (graus)")
        axis.set_xlim(0, 100)
        axis.grid(True, linestyle="--", alpha=0.6)
        axis.legend(loc="best", fontsize=9)

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
