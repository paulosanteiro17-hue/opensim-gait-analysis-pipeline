# Dataset

The biomechanical data used in this project are not redistributed in this repository.

## Source

Le Goff, Ludovic (2026).  
*A public dataset of treadmill walking kinematics and kinetics at steady speeds in healthy individuals*.  
Mendeley Data, Version 1.

DOI: https://doi.org/10.17632/3dmymnb65h.1

Dataset page: https://data.mendeley.com/datasets/3dmymnb65h/1

## Description

The dataset contains treadmill walking data from healthy younger and older adults acquired at different steady walking speeds. The available files include three-dimensional marker trajectories, joint kinematics, and ground reaction force data.

The present pipeline uses the motion-capture files required for kinematic and musculoskeletal processing. Ground reaction forces are not used in the analyses included in this repository.

## Data organization

After downloading the original dataset, the input files should be organized locally. A suggested structure is:

```text
data/
├── raw/
│   ├── young/
│   └── older/
├── trc/
└── processed/
