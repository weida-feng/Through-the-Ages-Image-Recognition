# Code organization and project history

The author dates the original personal project to 2022. This 2026 version organizes the existing implementation and adds documented validation and pandas automation. Earlier dates inside saved artifacts are retained as artifact history rather than used to overwrite the author's project date.

## Reusable Python modules

| Responsibility | Modules |
| --- | --- |
| Card metadata and text inputs | `_labels.py`, `catalog.py`, `records.py` |
| Image processing and original model method | `cropping.py`, `recognition.py`, `training.py` |
| Data quality and screenshot orchestration | `validation.py`, `audit.py`, `pipeline.py`, `sample_verification.py` |
| Historical game collection | `capture.py` |
| New pandas preparation and historical reconciliation | `sources.py`, `preparation.py`, `reconciliation.py` |
| New statistical automation and reports | `statistics.py`, `statistics_reference.py`, `reporting.py` |
| Package and commands | `cli.py`, `__init__.py`, `__main__.py` |

There are 20 package `.py` files. Importing them does not start screenshot collection, train models, or write batch outputs. Model dependencies are imported only by vision operations, and analysis can run independently in a modern pandas environment.

The refactor replaces literal Windows paths with `pathlib`, joins records by game identity, detects UTF-8/UTF-16 encoding, checks duplicate and missing keys, loads model pairs once per run, guards output directories against accidental mixing, and uses signed pixel arithmetic for difference calculations.

## The original training method

The author confirmed that one PCA/KNN notebook was manually switched to train leaders and later switched back to wonders. That original method is organized in `training.py`; it is not a newly inferred leader model. Both saved pairs use PCA retaining 95% variance with whitening and K=3. A separate older notebook retains a K=5 experiment, which is not the saved final configuration.

## Historical and current analysis

In 2022, the Python workflow produced recognition text and anomaly checks. TXT import, player organization and statistical formulas were handled manually in Excel.

The current pandas workflows automate those Excel steps and independently reconcile historical results. Public sample selection, pseudonym replacement, demonstration scripts and test organization are also 2026 work. Old notebooks, logs and unchanged source workbooks remain in the local evidence archive, while the public package presents the organized implementation.

## Full-archive operations

The package retains `audit`, `prepare`, `analyze`, `recognize`, `verify-examples`, and `train` commands for working with the full archive. Commands requiring historical TXT files, workbooks, complete screenshots or training images need those inputs; they are not runnable against the public sample as substitutes. The two scripts under `examples/` are the public runnable entry points.

Live collection retains the original Windows interface and coordinates. It has not been retested against the game in 2026. The screenshot-to-card flow was checked offline in the matching model environment.
