# Verification and provenance

## Full local evidence archive

The original project files are retained locally, with 289 copied source files checked byte-for-byte using SHA-256. The subsequently supplied environment export is tracked separately. The public package is a curated derivative; it does not contain all original files.

| Scope | Completed check |
| --- | --- |
| Historical counts | 5,239 + 6,724 + 2,594 = 14,557 distinct canonical games; component subsets excluded from double counting |
| Training records and artifacts | 900 labeled games; 6,958 leader and 4,980 wonder samples represented by the model pairs; 48 leader and 32 wonder classes |
| Pandas preparation | 14,557 games, 29,114 players, 116,456 leader-era slots and 77,053 wonder uses |
| Early workbook reconciliation | 141,453 winner/loser and card fields matched across 5,239 games |
| Saved statistical values | 252 values across 84 workbook rows independently reproduced, with zero mismatches |
| Offline screenshot flow | 20 complete screenshots processed, generating 234 candidate crops |
| Preserved crop/reference agreement | 199/199 aligned crop predictions matched historical references |
| Recropping comparison | 185/185 count-aligned saved crops had identical decoded pixels after regeneration |
| Raw full-list comparison | 70/80 card lists matched; all four lists matched for 15/20 games |
| Empty-wonder diagnostic | 10 empty candidates among 102 wonder crops; diagnostic comparison matched 80/80 lists without overwriting raw predictions |
| Full-archive test suite | 49 tests successfully covered across analysis and model environments |

The complete screenshots, individual reference comparisons, source workbooks and discrepancy records remain in the local archive. The public [machine-readable verification summary](../reports/verification-summary.json) records these results and hashes of the local reports. Public aggregate tables and original model artifacts are copied unchanged; [public_manifest.json](../public_manifest.json) records the public files and their hashes.

Historical agreement is not independent accuracy. Five screenshots come from the training subset; other references include previous recognition output and manual cleanup. No held-out accuracy figure is reported, and no raw result is replaced with a historical reference during prediction.

## Public demonstration checks

The public analysis script validates the 20-game pseudonymized sample and computes three sample populations using the same reusable statistical functions. It produced 240 metric rows and 12 coverage rows. Selection is curated, so these results demonstrate processing rather than estimate the full population.

The crop script predicts three historical card references and one empty region with the original models. Template difference is 550 for the empty region and 128,913 for the genuine Silk Road. Both raw labels are `丝绸之路`; this is why deletion by class name would remove valid data.

The public suite has **37 tests**, consisting of 33 retained archive-independent unit checks and four public asset/data/model checks. The modern analysis run passes 35 and skips two model checks; the legacy model run passes 21 and skips 16 analysis checks. Every public test is exercised in at least one environment. The full local archive's 49 checks are a different suite; their historical reconciliation inputs are not distributed here.

Checked demonstration outputs are in [analysis metadata](../reports/public-demo/analysis/sample_analysis.json) and [crop predictions](../reports/public-demo/vision/crop_predictions.json). The examples import the public package, and their inputs do not depend on the local private archive.

## Release-candidate installation check

On **2026-10-10**, the public ZIP was extracted into a separate directory and installed in two new virtual environments with system packages disabled. Dependencies were installed from the respective pinned requirements files, and the package was installed from that extracted public copy.

- Python 3.12.14 analysis: 35 tests passed and two model tests skipped. All three generated analysis files matched the included checked outputs byte-for-byte.
- Python 3.8.8 x86_64 model runtime: 21 tests passed and 16 analysis tests skipped. The crop-prediction JSON matched the included output byte-for-byte. Python isolation mode excluded this host's unrelated search-path configuration.
- Both environments passed dependency consistency checks. Loaded model sample counts, class counts, PCA settings and KNN settings matched the recorded metadata.

The release review also checked all 560 aggregate metric rows for count, denominator and interval consistency; all 252 recorded historical comparisons remain matches. Public text files were checked against the 14,557 original game IDs, personal path strings and common credential patterns. Public player fields contain the declared sample-local pseudonyms. This is a targeted release check, rather than a guarantee that external information cannot identify a curated game.

The final documentation update adds the [project-claim evidence guide](project_evidence.md); package code and demonstration inputs are unchanged from the extracted copy used for these runs. These checks were local macOS runs. The public analysis workflow subsequently ran successfully on GitHub on **2026-10-14**. See [GitHub Actions](https://github.com/weida-feng/Through-the-Ages-Image-Recognition/actions) for the latest checks. The dated release-candidate records retain their original workflow status.

## Remaining limits

Full retraining has not been run because the complete training crops are absent. The Windows game-collection macro has been organized as code but not retested live. The recorded cleanup notebook was not executed; the current empty-template comparison automates its documented metric while retaining the raw error. The GitHub-hosted workflow covers the public analysis suite, sample analysis and manifest integrity; it does not run the legacy model environment or full private-archive checks.
