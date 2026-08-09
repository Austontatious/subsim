# Hydrophone Classifier Baseline Report

Generated: 2026-05-07T16:12:34+00:00

## Status

Ran RandomForestClassifier baseline using fixed split manifests.

## Fixed Split Evaluation

### Train

- Rows: 47
- Classes: ambient_ocean=25, biologic_fish=10, biologic_mammal=6, surface_vessel=6
- Groups: 28

### Validation

- Rows: 16
- Classes: ambient_ocean=9, biologic_fish=3, biologic_mammal=2, surface_vessel=2
- Groups: 9

```text
                 precision    recall  f1-score   support

  ambient_ocean       1.00      0.67      0.80         9
  biologic_fish       0.50      1.00      0.67         3
biologic_mammal       1.00      1.00      1.00         2
 surface_vessel       1.00      1.00      1.00         2

       accuracy                           0.81        16
      macro avg       0.88      0.92      0.87        16
   weighted avg       0.91      0.81      0.82        16
```

### Heldout Source Eval

This is the main smoke signal because source groups were held out from training.

- Rows: 15
- Classes: ambient_ocean=6, biologic_fish=5, biologic_mammal=2, surface_vessel=2
- Groups: 9

```text
                 precision    recall  f1-score   support

  ambient_ocean       1.00      0.83      0.91         6
  biologic_fish       1.00      1.00      1.00         5
biologic_mammal       1.00      1.00      1.00         2
 surface_vessel       0.67      1.00      0.80         2

       accuracy                           0.93        15
      macro avg       0.92      0.96      0.93        15
   weighted avg       0.96      0.93      0.94        15
```

### Reliability Warning

- Total real clips used: 78
- Split strategy: fixed_split_manifest
- Synthetic included: no
- Classes below 10 clips: none
- Known leakage risks: corpus is still small
- Should metrics be trusted? limited

## Confusion Matrices

- Validation CSV: `reports/hydrophone/classifier_confusion_matrix_validation.csv`
- Heldout CSV: `reports/hydrophone/classifier_confusion_matrix_heldout_source_eval.csv`

## Split Metadata

- JSON: `reports/hydrophone/classifier_split_metadata.json`
