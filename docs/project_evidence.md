# Project experience and supporting evidence

This repository supports the author's **Image Recognition & Data Pipeline (Through the Ages, Digital Board Game)** project experience. The original personal project is dated **2022**. Code organization, pandas automation and additional verification were completed in **2026**, as described in the [project history](code_organization.md).

## Screenshot extraction and recognition

**Experience:** Built a Python pipeline to extract and recognize game elements from screenshots.

The implementation separates [cropping](../src/tta_pipeline/cropping.py), [PCA/KNN prediction](../src/tta_pipeline/recognition.py), [screenshot orchestration](../src/tta_pipeline/pipeline.py), and [validation rules](../src/tta_pipeline/validation.py). The historical [collection module](../src/tta_pipeline/capture.py) retains the original Windows interface assumptions.

The full local archive was checked on 20 complete screenshots, producing 234 candidate crops. Of 80 historical card lists, 70 matched the raw predictions; five resigned games contained ten extra empty wonder regions. The empty-template diagnostic explains these candidates without changing raw predictions. The public [crop example](../examples/recognize_crops.py) demonstrates successful recognition and this failure case using included images and original models.

This supports the implemented image pipeline and its offline operation. Live Windows collection has not been retested, and the public example begins with selected crops. Historical-reference agreement is not independent test accuracy.

## Manual labeling, PCA and nearest neighbors

**Experience:** Manually labeled training data from approximately 900 games and implemented PCA with a scikit-learn nearest-neighbor classifier.

The 900-game labeling records remain in the local archive. The author confirmed that the same training notebook was manually switched between leaders and wonders. The [training module](../src/tta_pipeline/training.py) organizes that original method, and the [saved model metadata](../assets/models/metadata.json) records:

| Model | Training crops represented | Classes | Input features | PCA dimensions |
| --- | ---: | ---: | ---: | ---: |
| Leaders | 6,958 | 48 | 2,304 | 48 |
| Wonders | 4,980 | 32 | 7,680 | 70 |

The saved model pairs use PCA retaining 95% variance, whitening, and K=3 with uniform weights. These settings and dimensions were checked on the loaded artifacts. Both model pairs are included for the public demonstration.

**Wording matters:** approximately 900 refers to games used for labeling, rather than 900 individual training images. Full retraining needs the complete labeled crop set, which is not available here. The manual labeling history is supported by the local records and the author's account; the public package does not distribute those complete records.

## 14,000+ records and recognition quality control

**Experience:** Automated extraction and processing of 14,000+ game records, using anomaly checks and manual verification to identify and correct recognition errors.

The canonical historical archive contains **5,239 + 6,724 + 2,594 = 14,557 distinct games**. The 900-game training subset and 4,339-game batch are components of the first 5,239 and are not counted again. The [audit code](../src/tta_pipeline/audit.py) counts canonical batches and reports rule findings. Historical text outputs, error logs and correction comparisons remain in the local archive.

The [worked example](case_study.md) shows why a predicted class alone cannot identify an empty region: the genuine Silk Road and an empty wonder crop both receive `丝绸之路`. Shared-card, duplicate-card and age-order checks provide review signals; the template diagnostic records an additional finding. It preserves raw outputs and does not delete every occurrence of a class name.

The new pandas preparation separately reconciles outcomes against source workbooks. It matched 141,453 early winner/loser and card fields and explicitly records 2,075 conflicting historical text outcome records. These are **2026 reconciliation checks**, rather than a claim that the historical recognition had no errors. Three chronology cases remain pending review. The [verification summary](../reports/verification-summary.json) distinguishes full local evidence from public sample checks.

## 48 leaders, 32 wonders and comparative analysis

**Experience:** Analyzed 48 leaders and 32 wonders, producing comparative statistics and reports to support data-driven evaluation.

The [card catalog](../src/tta_pipeline/catalog.py) and model class counts agree on all 80 categories. The [aggregate report](../reports/statistics/report.md) includes use counts, selection rates, observed win rates, nominal Wilson intervals, leader absence and population sensitivity. Its [560 metric rows](../reports/statistics/card_statistics.csv) cover 80 cards across seven population views.

The original analysis was done manually in Excel. The 2026 [statistics implementation](../src/tta_pipeline/statistics.py) and [reference comparison](../src/tta_pipeline/statistics_reference.py) automate those calculations. They independently reproduced 252 saved Excel values across 84 rows, with zero mismatches. The public [20-game analysis script](../examples/analyze_sample.py) uses the same statistical functions on included pseudonymized records.

The complete aggregate estimates cannot be regenerated from the 20 curated games. Rates describe observed associations; they do not control player ability, game state or card availability and do not establish causal card strength. This scope is stated in the [methods](methods.md).

## What a visitor can verify

Visitors can inspect the method, original model artifacts, aggregate results and recorded hashes, and run both public examples in their documented environments. The [verification notes](verification.md) identify which additional checks use the full local archive. Public samples do not constitute an independent audit of every historical game or the complete manual labeling history.

The repository provides concrete code, runnable demonstrations and qualified result evidence for the four project claims. It preserves the distinction between the original work and the later portfolio release.
