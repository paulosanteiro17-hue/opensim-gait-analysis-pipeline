# OpenSim Gait Analysis Pipeline

Automated computational pipeline for lower-limb gait biomechanical analysis using OpenSim.

The pipeline organizes motion-capture data, converts C3D files to TRC, performs musculoskeletal processing in OpenSim, estimates gait cycles, normalizes biomechanical curves, generates individual and group-level figures, and produces quality-control reports.

## Main features

- C3D to TRC conversion;
- OpenSim model scaling;
- inverse kinematics;
- Body Kinematics and Muscle Analysis;
- kinematic estimation of gait cycles;
- temporal normalization from 0 to 100%;
- joint kinematics analysis;
- center of mass trajectory analysis;
- musculotendon length analysis;
- participant-level and group-level processing;
- quality-control and audit reports.

## Repository structure

```text
opensim-gait-analysis-pipeline/
├── src/
│   ├── automacao_opensim.py
│   ├── gerar_resultados_grupo.py
│   ├── c3d_to_trc.py
│   ├── plot_com.py
│   ├── plot_muscle.py
│   ├── plotter_bonito.py
│   └── README.md
│
├── templates/
│   ├── Setup_Scale_Template.xml
│   ├── Setup_IK_Template.xml
│   ├── Setup_Analyze_Template.xml
│   └── README.md
│
├── data/
│   └── README.md
│
├── requirements.txt
├── .gitignore
└── README.md
```

The original biomechanical data, participant-specific models, OpenSim outputs, and generated results are not included in the repository.

## Dataset

The pipeline was developed and applied using the following public dataset:

Le Goff, Ludovic (2026).  
*A public dataset of treadmill walking kinematics and kinetics at steady speeds in healthy individuals*.  
Mendeley Data, Version 1.

DOI: https://doi.org/10.17632/3dmymnb65h.1

Dataset page:

https://data.mendeley.com/datasets/3dmymnb65h/1

After downloading the dataset, organize the participant folders locally as:

```text
data/
└── raw/
    ├── Young/
    │   ├── participant_01/
    │   │   ├── static.c3d
    │   │   └── 1_00.c3d
    │   └── ...
    │
    └── Old/
        ├── participant_01/
        │   ├── static.c3d
        │   └── 1_00.c3d
        └── ...
```

The scripts also recognize the lowercase folder names `young` and `older`.

## Requirements

- Python 3.10 or later;
- OpenSim 4.x;
- `opensim-cmd` available in the system PATH or provided through the command line;
- a generic OpenSim musculoskeletal model compatible with the marker set;
- the Python packages listed in `requirements.txt`.

The OpenSim software and the generic musculoskeletal model are not distributed with this repository.

## Python installation

Create and activate a virtual environment.

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## C3D to TRC conversion

To convert a single C3D file:

```bash
python src/c3d_to_trc.py \
    --file "path/to/file.c3d" \
    --output-dir "data/trc"
```

To convert all C3D files belonging to one participant:

```bash
python src/c3d_to_trc.py \
    --subject "Young/participant_folder"
```

To process every participant located in `data/raw/Young` and `data/raw/Old`:

```bash
python src/c3d_to_trc.py
```

During conversion, the script:

- selects markers compatible with the model;
- renames the markers;
- converts millimeters to meters when necessary;
- transforms the coordinate system;
- removes invalid marker samples;
- generates a conversion report.

## Running the complete OpenSim pipeline

The complete pipeline requires:

- `static.c3d`;
- a dynamic C3D trial;
- the XML templates located in `templates/`;
- a generic OpenSim model;
- the `opensim-cmd` executable.

Example:

```bash
python src/automacao_opensim.py \
    --opensim "path/to/opensim-cmd.exe" \
    --generic-model "path/to/generic_model.osim" \
    --trial "1_00.c3d"
```

When `opensim-cmd` is already available in the system PATH, the `--opensim` argument can be omitted:

```bash
python src/automacao_opensim.py \
    --generic-model "path/to/generic_model.osim" \
    --trial "1_00.c3d"
```

To process only one participant:

```bash
python src/automacao_opensim.py \
    --generic-model "path/to/generic_model.osim" \
    --teste-paciente "participant_folder" \
    --trial "1_00.c3d"
```

## Pipeline outputs

Participant-specific files are generated under:

```text
data/processed/
└── participant_folder/
    ├── static.trc
    ├── dynamic_trial.trc
    ├── participant_scaled_markerplaced.osim
    └── Resultados/
        ├── participant_ik.mot
        ├── Analyze/
        ├── Graficos/
        └── Logs/
```

The logs include:

- C3D conversion output;
- Scale output;
- inverse kinematics output;
- Analyze output;
- marker error metrics;
- quality-control status.

## Group analysis

After participant processing, run:

```bash
python src/gerar_resultados_grupo.py
```

The group-level outputs are stored in:

```text
results/group/
```

The script generates:

- joint kinematic curves;
- center of mass curves;
- musculotendon length variation curves;
- summary tables;
- an audit report showing the number of participants included in each variable.

Multiple gait cycles are first averaged within each participant. Group means and standard deviations are then calculated across participants.

## Gait-cycle estimation

Gait cycles are estimated from consecutive peaks of the right hip flexion curve.

Each accepted cycle is interpolated to 101 points, representing 0 to 100% of the estimated gait cycle.

This procedure represents a kinematic estimation and does not correspond to force-platform measurement of heel-strike events.

## Biomechanical variables

The current implementation includes:

- right hip flexion/extension;
- right knee flexion/extension;
- right ankle dorsiflexion/plantarflexion;
- anteroposterior, vertical, and mediolateral center of mass trajectories;
- estimated musculotendon lengths of selected lower-limb muscles.

The center of mass coordinates are expressed in centimeters. The anteroposterior component is detrended, while the vertical and mediolateral components are centered.

Musculotendon lengths are centered using each participant's temporal mean and are expressed as relative length variation in centimeters.

## Methodological scope

The current pipeline focuses on variables supported by kinematics and musculoskeletal model geometry.

Ground reaction forces are not used. Therefore, inverse dynamics, static optimization, joint moments, joint power, muscle forces, and joint reaction analyses are not included as primary outputs.

The pipeline is intended for research and methodological development. It is not a clinical diagnostic system.

## Reproducibility

The XML files stored in `templates/` contain `Unassigned` fields. Before each OpenSim execution, the Python pipeline creates participant-specific XML files and inserts:

- model paths;
- marker-file paths;
- output paths;
- time intervals;
- result directories.

This prevents computer-specific absolute paths from being stored in the public templates.

## Citation

Citation information for this software will be added after publication of the first stable release.

## License

A software license will be added before the repository is made public.

## Author

Paulo Augusto de Faria  
Graduate Program in Electrical Engineering  
Federal University of São Carlos — UFSCar  
São Carlos, São Paulo, Brazil
