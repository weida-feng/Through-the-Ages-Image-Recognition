# Data and analytical methods

## Historical populations

The canonical batches are 5,239 early games, 6,724 later completed games, and 2,594 resigned games, with no overlapping game identities. The 900-game training subset and 4,339-game batch together form the early 5,239. The total is 14,557, without counting subsets twice.

The primary `completed` population has neither resignation nor expiration flags and contains 11,963 games. Seventeen resigned games also have an expiration flag; these flags are retained even when attached to a winner. Three recorded age-order findings remain pending review. The complete aggregate report includes seven overlapping populations; their counts must not be summed.

## Metrics

| Metric | Definition |
| --- | --- |
| Uses | Number of recorded uses of a card in the population |
| Selection rate | Uses / games; each card can appear at most once per game, checked before aggregation |
| Player usage rate | Uses / (2 × games) |
| Observed win rate | Winning uses / uses |
| Wilson interval | Nominal 95% binomial interval with z=1.96; missing when uses=0 |
| Leader absence | `无` slots / player-era slots, separate from actual card categories |

Wilson intervals follow the [NIST binomial proportion method](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). They do not adjust for repeated players, dependence between cards, or multiple comparisons. Availability, player ability and game state are not controlled. These are descriptive estimates.

Sensitivity tables report comparison-minus-baseline changes in percentage points. The historical scaled score is retained only in the original Excel comparison: Wilson lower bound / historical scale × 50. Those saved scale constants are reproduced without treating them as a calibrated strength model.

## Public sample

`data/demo/` contains the same 20 games selected for local screenshot verification: five training-subset, five early completed, five later completed, and five resigned examples. It is a curated convenience sample, not a representative or held-out sample. Its 38 distinct player strings are replaced consistently with `player_###`; games become `DEMO####`. The mapping remains local. Linkability within the sample is preserved for join checks and distinct-player counts.

Original sequence numbers, workbook rows, source paths, batch identifiers and usernames are omitted. Card identities, outcomes, absent slots and ending flags are retained from the checked historical preparation, including existing historical corrections. This is not newly generated synthetic gameplay or a fresh raw recognition result.

| Public table | Rows | Key and important fields |
| --- | ---: | --- |
| `games.csv` | 20 | `game_code`; demo batch, `winner_position`, resignation/expiration flags |
| `players.csv` | 40 | `game_code`, `player_position`; pseudonym in `username`, screenshot position, outcome flags |
| `leader_slots.csv` | 160 | game, position, era; card ID/name, presence, pseudonym, win flag |
| `wonders.csv` | 92 | game, position, `card_index`; card ID/name, era, pseudonym, win flag |
| `quality_findings.csv` | 0 | No pending chronology cases among these prepared reference records |

The empty findings table does not mean that raw screenshot predictions were error-free: the empty-wonder diagnostic concerns extra raw candidates, while these tables contain historical prepared references.

`reconciliation.json` records expected row counts; `selection.json` declares scope, selection and input hashes. `load_prepared` validates joins, two players/one winner per game, ending flags, four leader-era slots, category metadata and unique card use per game before the example aggregates.

The sample script reports `demo_completed` (15 games), `demo_resigned` (5), and `demo_all` (20), using the same statistical functions as the full analysis. Its 240 metric rows are sample results. The 560 rows under `reports/statistics/` are full-archive results and cannot be regenerated from this sample alone.

## Image inputs and reference scope

Leader features use the center 48×48 of a 144×144 grayscale JPEG. Wonder features use the whole 64×120 crop. PCA retains 95% variance with whitening; KNN uses K=3 and uniform weights. The saved PCA outputs have 48 leader and 70 wonder dimensions.

Three public crops have historical card references. A fourth is an empty region regenerated from a preserved screenshot using the verified cropping pipeline. Its reference card label is null; the forced KNN label is retained as an error example. The sample-local tables and the crop demo are separate demonstrations and do not claim that the four crops represent all cards in the sample.

Recognition agreement with historical labels, especially training examples or earlier model output, is not independent classification accuracy. Full retraining and held-out evaluation require additional images that are not supplied.
