"""
c3d_to_trc.py
─────────────
Converte arquivos .c3d do Gait Dataset para .trc (OpenSim),
renomeando os marcadores para compatibilidade com o modelo utilizado.

Uso:
    python src/c3d_to_trc.py --file caminho/arquivo.c3d --output-dir data/trc
    python src/c3d_to_trc.py --subject Young/01_LLG
    python src/c3d_to_trc.py
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import ezc3d
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATASET_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "trc"

MARKER_RENAME = {
    "RASIS": "R.ASIS",
    "LASIS": "L.ASIS",
    "RPSIS": "R.PSIS",
    "LPSIS": "L.PSIS",
    "RTHI": "R.THIGH",
    "LTHI": "L.THIGH",
    "RFIB": "R.FIB",
    "LFIB": "L.FIB",
    "RTIB": "R.TIB",
    "LTIB": "L.TIB",
    "RKNEELAT": "R.Knee",
    "LKNEELAT": "L.Knee",
    "RKNEEMED": "R.Knee.Med",
    "LKNEEMED": "L.Knee.Med",
    "RANKLELAT": "R.Ankle",
    "LANKLELAT": "L.Ankle",
    "RANKLEMED": "R.Ankle.Med",
    "LANKLEMED": "L.Ankle.Med",
    "RHEEL": "R.Heel",
    "LHEEL": "L.Heel",
    "RTOEMED": "R.MT1",
    "LTOEMED": "L.MT1",
    "RTOELAT": "R.MT5",
    "LTOELAT": "L.MT5",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("c3d_to_trc")


def convert_c3d_to_trc(c3d_path: Path, trc_path: Path) -> bool:
    c3d_path = c3d_path.expanduser().resolve()
    trc_path = trc_path.expanduser().resolve()

    if not c3d_path.exists():
        log.error("Arquivo não encontrado: %s", c3d_path)
        return False

    c3d = ezc3d.c3d(str(c3d_path))
    labels_raw = c3d["parameters"]["POINT"]["LABELS"]["value"]
    point_data = c3d["data"]["points"]
    frame_rate = float(c3d["header"]["points"]["frame_rate"])
    n_frames = point_data.shape[2]

    selected_indices: list[int] = []
    selected_names: list[str] = []

    for index, label in enumerate(labels_raw):
        clean_label = label.strip()
        if clean_label in MARKER_RENAME:
            selected_indices.append(index)
            selected_names.append(MARKER_RENAME[clean_label])

    if not selected_indices:
        log.warning("SKIP %s: nenhum marcador reconhecido.", c3d_path.name)
        return False

    xyz = point_data[:3, selected_indices, :]
    xyz = np.transpose(xyz, (2, 1, 0))

    residuals = point_data[3, selected_indices, :]
    residuals = np.transpose(residuals, (1, 0))

    units = ""
    try:
        units = c3d["parameters"]["POINT"]["UNITS"]["value"][0].strip().lower()
    except (KeyError, IndexError, AttributeError):
        pass

    converted_units = False
    if units == "mm" or np.nanmax(np.abs(xyz)) > 100:
        xyz = xyz / 1000.0
        converted_units = True

    n_markers = len(selected_names)
    trc_path.parent.mkdir(parents=True, exist_ok=True)

    with trc_path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(f"PathFileType\t4\t(X/Y/Z)\t{trc_path.name}\n")
        output.write(
            "DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\t"
            "OrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n"
        )
        output.write(
            f"{frame_rate:.1f}\t{frame_rate:.1f}\t{n_frames}\t{n_markers}\t"
            f"m\t{frame_rate:.1f}\t1\t{n_frames}\n"
        )

        marker_header = "Frame#\tTime"
        for name in selected_names:
            marker_header += f"\t{name}\t\t"
        output.write(marker_header.rstrip() + "\n")

        coordinate_header = "\t"
        for marker_number in range(1, n_markers + 1):
            coordinate_header += (
                f"\tX{marker_number}\tY{marker_number}\tZ{marker_number}"
            )
        output.write(coordinate_header + "\n")

        for frame_index in range(n_frames):
            frame_number = frame_index + 1
            time_value = frame_index / frame_rate
            line = f"{frame_number}\t{time_value:.6f}"

            for marker_index in range(n_markers):
                x_c3d, y_c3d, z_c3d = xyz[frame_index, marker_index, :]
                residual = residuals[frame_index, marker_index]

                # C3D: Z vertical e Y progressão.
                # OpenSim: Y vertical.
                x_osim = y_c3d
                y_osim = z_c3d
                z_osim = x_c3d

                invalid = (
                    np.isnan([x_osim, y_osim, z_osim]).any()
                    or np.allclose([x_osim, y_osim, z_osim], [0, 0, 0])
                    or residual < 0
                )

                if invalid:
                    line += "\t\t\t"
                else:
                    line += f"\t{x_osim:.6f}\t{y_osim:.6f}\t{z_osim:.6f}"

            output.write(line + "\n")

    unit_message = (
        "Coordenadas convertidas de mm para m."
        if converted_units
        else "Nenhuma conversão de unidade aplicada."
    )
    log.info(
        "OK %s -> %s (%d marcadores) | %s",
        c3d_path.name,
        trc_path.name,
        n_markers,
        unit_message,
    )

    report_lines = [
        f"Arquivo original: {c3d_path.name}",
        f"Número de frames: {n_frames}",
        f"Frequência: {frame_rate} Hz",
        f"Unidade original: {units or 'não informada'}",
        f"Conversão mm -> m: {'Sim' if converted_units else 'Não'}",
        f"Marcadores exportados: {n_markers}",
        "Mapeamento usado: marcadores anatômicos e de rastreamento",
        "Eixos: X=Y_c3d, Y=Z_c3d, Z=X_c3d",
        f"Status: {unit_message}",
    ]
    trc_path.with_suffix(".txt").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )
    return True


def process_subject(subject_path: Path, output_base: Path) -> int:
    subject_path = subject_path.expanduser().resolve()
    output_base = output_base.expanduser().resolve()

    c3d_files = sorted(subject_path.glob("*.c3d"))
    if not c3d_files:
        log.warning("Nenhum C3D encontrado em %s", subject_path)
        return 0

    log.info("--- %s / %s ---", subject_path.parent.name, subject_path.name)
    converted = 0

    for c3d_file in c3d_files:
        output_path = (
            output_base
            / subject_path.parent.name
            / subject_path.name
            / f"{c3d_file.stem}.trc"
        )
        if convert_c3d_to_trc(c3d_file, output_path):
            converted += 1

    return converted


def convert_single_file(file_path: Path, output_base: Path) -> bool:
    file_path = file_path.expanduser().resolve()
    output_base = output_base.expanduser().resolve()

    if file_path.suffix.lower() != ".c3d":
        log.error("O arquivo informado não possui extensão .c3d: %s", file_path)
        return False

    output_path = output_base / f"{file_path.stem}.trc"
    return convert_c3d_to_trc(file_path, output_path)


def resolve_subject(subject_argument: str) -> Path:
    supplied = Path(subject_argument).expanduser()

    if supplied.is_absolute():
        return supplied.resolve()

    return (DATASET_DIR / supplied).resolve()


def available_group_directories() -> list[Path]:
    candidates = [
        DATASET_DIR / "Young",
        DATASET_DIR / "Old",
        DATASET_DIR / "young",
        DATASET_DIR / "older",
    ]
    return [path for path in candidates if path.exists()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte arquivos C3D do dataset para TRC compatível com OpenSim."
    )
    parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help="Pasta de um participante, absoluta ou relativa a data/raw.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Caminho para um único arquivo C3D.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Pasta de saída. Padrão: data/trc.",
    )
    args = parser.parse_args()

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else DEFAULT_OUTPUT_DIR
    )

    if args.file:
        convert_single_file(Path(args.file), output_dir)
        return

    if args.subject:
        process_subject(resolve_subject(args.subject), output_dir)
        return

    group_dirs = available_group_directories()
    if not group_dirs:
        log.error(
            "Nenhuma pasta de grupo encontrada em %s. "
            "Use --file ou --subject para informar uma entrada.",
            DATASET_DIR,
        )
        return

    for group_dir in group_dirs:
        for subject_dir in sorted(path for path in group_dir.iterdir() if path.is_dir()):
            process_subject(subject_dir, output_dir)


if __name__ == "__main__":
    main()
