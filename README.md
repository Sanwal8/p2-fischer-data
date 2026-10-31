# Fischer 2023 IMC data mirror

A copy of public data, made so that it can be downloaded from networks where the original hosts are unreachable. Nothing here is new data.

**Sources (both CC BY 4.0):**
- EBI spora release `fischer2023multiplex`: https://livingobjects.ebi.ac.uk/bioimaging-01-pub/spora-submissions/fischer2023multiplex/
- Zenodo record 7494509 (SingleCellExperiment_IMC.rds, Patient_metadata.csv, Panel.csv): https://zenodo.org/records/7494509

**Please cite the original study:** Fischer JR, Jackson HW, de Souza N, Varga Z, Schraml P, Moch H, Bodenmiller B. Multiplex imaging of breast cancer lymph node metastases identifies prognostic single-cell populations independent of clinical classifiers. *Cell Reports Medicine* 4(3), 100977 (2023).

The files are in the release `fischer-data-v1`: tar archives of the spora files and the Zenodo files as published. `manifest.json` lists every file with its original size and every release file with its SHA-256 (and Zenodo's MD5 for the Zenodo files). `tools/mirror.py` is the script that built the release.
