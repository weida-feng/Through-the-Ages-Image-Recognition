# Installation and runnable examples

Use separate environments for modern data analysis and the old saved models. Importing the package does not start game collection. All commands below run from the repository root; outputs require a new empty directory.

## Public analysis example

Locally verified with Python 3.12.14, NumPy 2.3.5, pandas 2.2.3 and openpyxl 3.1.5:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/analysis.txt
python -m pip install --no-deps -e .
python examples/analyze_sample.py --output results/demo-analysis
python -m unittest discover -s tests -v
```

On Windows, activate with `.venv\Scripts\activate`. An existing modern environment can instead install the package's `analysis,test` extras; the pinned file records the direct versions tested here.

Expected sample output: 20 games, 40 player rows, populations of 15 completed / 5 resigned / 20 all games, 240 card-statistic rows and 12 leader-coverage rows. The checked files are also included in [reports/public-demo/analysis](../reports/public-demo/analysis/sample_analysis.json).

The public test suite contains 37 tests: the analysis environment passes 35 and explicitly skips two real-model tests. This public suite does not run full historical workbook checks because those inputs are kept in the local archive.

## Original model example

The saved models record scikit-learn 0.24.1. A later author-supplied original environment export also records Python 3.8.8, NumPy 1.20.1, SciPy 1.6.2, OpenCV 4.5.3.56, joblib 1.0.1 and threadpoolctl 2.1.0. These scientific versions were installed in a separate environment and exercised on macOS using x86_64 Python; this is a compatible model runtime rather than a recreation of the full historical Windows installation.

If Python 3.8.8 is available:

```bash
/path/to/python3.8 -m venv .venv-vision
source .venv-vision/bin/activate
python -m pip install "pip==24.0" "setuptools==68.2.2" "wheel==0.41.3"
python -m pip install --only-binary=:all: -r requirements/legacy-vision.txt
python -m pip install --no-deps --no-build-isolation -e .
python examples/recognize_crops.py --output results/demo-vision
python -m unittest discover -s tests -v
```

Expected raw labels are 孔子, 大图书馆, 丝绸之路, and 丝绸之路. The final image is empty: its template difference is 550, compared with 128,913 for the genuine Silk Road, against threshold 5,000. The diagnostic records the candidate without replacing its raw prediction. See [checked crop output](../reports/public-demo/vision/crop_predictions.json).

The model environment passes 21 of the public tests, including the two real-model checks, and skips 16 analysis-dependent tests. Across both runs, all 37 public tests are exercised successfully.

If your shell sets a custom `PYTHONPATH`, add `-I` to example and test commands, such as `python -I examples/recognize_crops.py --output results/demo-vision`. The release check used this isolation mode for the legacy runtime to exclude unrelated host search paths.

The supplied [minimal Conda recipe](../environments/legacy-vision.yml) records the same scientific versions but was not separately instantiated. On Apple Silicon, the historical wheel versions need an appropriate Intel Python environment; [Conda platform selection](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html) describes this option. Installer versions above are bootstrap choices for the current package, rather than claims about the historical installer.

`CardPredictor.load` checks the recorded scikit-learn version before loading artifacts. Cross-version loading is unsupported according to the [scikit-learn persistence documentation](https://scikit-learn.org/stable/model_persistence.html). The broad `vision` extra describes components; use the pinned file for these saved models.

## Full-archive operations and GitHub checks

The retained CLI exposes full-archive operations, but `audit`, `prepare`, `analyze`, and `verify-examples` require inputs omitted from this public package. `train` additionally needs the complete labeled image set. The public scripts above use only files included here.

The [GitHub Actions workflow](../.github/workflows/checks.yml) installs pinned analysis dependencies, runs the public suite, and executes the sample analysis with Python 3.12. Its action references follow the [checkout](https://github.com/actions/checkout) and [setup-python](https://github.com/actions/setup-python) documentation. The public analysis workflow has run successfully on GitHub; see [GitHub Actions](https://github.com/weida-feng/Through-the-Ages-Image-Recognition/actions) for the latest checks.

The workflow also verifies the tracked public-file sizes and SHA-256 hashes. After editing public files, explicitly stage the intended additions or removals, then refresh and check the manifest:

```bash
python scripts/public_manifest.py
git add public_manifest.json
python scripts/public_manifest.py --check
```

The helper reads Git's tracked-file list and the current file contents, excludes the manifest itself, and preserves its scope and release metadata. It does not add untracked files to Git. Finish editing and staging the intended files before the final check.
