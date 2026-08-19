# Domain Overlay: ML / VLA / Data Pipelines

Apply to training, evaluation, inference, dataset, preprocessing, model-serving, and VLA/robot-learning changes.

Check:

- train/validation/test leakage;
- data provenance and schema versioning;
- split stability;
- preprocessing parity between training and inference;
- shape, dtype, device, masking, padding;
- numerical stability and NaN/Inf handling;
- reproducibility and seed claims;
- checkpoint/config compatibility;
- metric definition and aggregation;
- distribution assumptions and evaluation coverage;
- dataset filtering that changes target semantics;
- resource usage and batch-size-dependent behavior;
- caching that changes sample semantics;
- hidden nondeterminism;
- mismatch between offline metrics and production behavior.

Do not accept “metric improved” without checking whether the evaluation protocol itself stayed valid.
