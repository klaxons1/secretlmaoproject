# All experiment calculations

The KVM and desktop AWT engines must not be combined into a phone/FPS claim.
A tile operation is one background + tiles + wall-shadows phase, not a full game frame.
A queue operation is a complete enqueue/drain batch; a path operation is one query.

- `us/op = elapsed_ms * 1000 / operations`.
- `speedup_sample = reference_us_sample / candidate_us_sample` for the same trial.
- Reported speedup is the **median of paired ratios**, not the ratio of medians.
- `time reduction (%) = 100 * (1 - 1 / median_speedup)`; negative means slower.
- Ranges are observed paired min–max, **not confidence intervals**.
- All fixed-batch checksums, trial rotations, units and missing/duplicate rows are validated.

| Engine | Family | Scenario | Comparison | Reference µs/op | Candidate µs/op | Paired median | Time reduction | Observed range | Every paired ratio |
|---|---|---|---|---:|---:|---:|---:|---|---|
| desktop-awt-reference | tiles | irongate:240x320:shadows | original → index | 382.812 | 373.698 | 1.0162× | 1.59% | 0.9133–1.0525 | 1.03058, 1.01616, 1.01906, 0.99826, 1.05254, 0.91331, 0.98211, 0.98780, 1.04926 |
| desktop-awt-reference | tiles | irongate:240x320:shadows | original → cull | 382.812 | 388.672 | 1.0000× | 0.00% | 0.9056–1.1191 | 1.02139, 0.90560, 0.98492, 1.02139, 0.97724, 0.91615, 1.00000, 1.00532, 1.11909 |
| desktop-awt-reference | tiles | irongate:240x320:shadows | index → cull | 373.698 | 388.672 | 1.0031× | 0.31% | 0.8912–1.0665 | 0.99109, 0.89120, 0.96650, 1.02317, 0.92846, 1.00311, 1.01821, 1.01773, 1.06655 |
| desktop-awt-reference | tiles | jungle:240x320:shadows | original → index | 352.865 | 348.958 | 0.9963× | -0.37% | 0.9315–1.1625 | 0.95704, 1.00383, 0.99627, 1.16252, 1.06716, 0.93448, 0.97757, 0.93146, 1.04404 |
| desktop-awt-reference | tiles | jungle:240x320:shadows | original → cull | 352.865 | 337.891 | 1.0324× | 3.14% | 0.9611–1.0761 | 1.07322, 1.00963, 1.03488, 1.07611, 1.07116, 1.03238, 1.01161, 1.02515, 0.96115 |
| desktop-awt-reference | tiles | jungle:240x320:shadows | index → cull | 348.958 | 337.891 | 1.0348× | 3.36% | 0.9206–1.1214 | 1.12139, 1.00578, 1.03876, 0.92566, 1.00375, 1.10476, 1.03482, 1.10058, 0.92061 |
| desktop-awt-reference | tiles | perks:240x320:shadows | original → index | 314.453 | 316.732 | 1.0097× | 0.96% | 0.9109–1.1353 | 1.07511, 0.91087, 0.95992, 1.00967, 1.06324, 0.92617, 1.13534, 1.01486, 0.97984 |
| desktop-awt-reference | tiles | perks:240x320:shadows | original → cull | 314.453 | 300.781 | 1.0341× | 3.30% | 1.0081–1.3159 | 1.09868, 1.00813, 1.01082, 1.03410, 1.06839, 1.02711, 1.31590, 1.02301, 1.04685 |
| desktop-awt-reference | tiles | perks:240x320:shadows | index → cull | 316.732 | 300.781 | 1.0530× | 5.04% | 1.0048–1.1590 | 1.02193, 1.10678, 1.05303, 1.02420, 1.00485, 1.10898, 1.15904, 1.00803, 1.06839 |
| desktop-awt-reference | tiles | sanpancho:240x320:shadows | original → index | 333.008 | 319.336 | 1.0428× | 4.11% | 0.9383–1.2152 | 1.01636, 1.00857, 1.04281, 0.93831, 1.02173, 1.05157, 1.07932, 1.06357, 1.21522 |
| desktop-awt-reference | tiles | sanpancho:240x320:shadows | original → cull | 333.008 | 316.895 | 1.0272× | 2.65% | 0.8543–1.2606 | 1.16319, 1.02722, 0.90691, 0.99318, 0.96642, 1.06861, 1.08607, 0.85430, 1.26064 |
| desktop-awt-reference | tiles | sanpancho:240x320:shadows | index → cull | 319.336 | 316.895 | 1.0162× | 1.59% | 0.8032–1.1445 | 1.14446, 1.01849, 0.86968, 1.05848, 0.94586, 1.01621, 1.00626, 0.80324, 1.03738 |
| desktop-awt-reference | tiles | shanktonstatepen:240x320:shadows | original → index | 404.297 | 402.344 | 0.9935× | -0.65% | 0.9601–1.1186 | 1.01305, 1.11862, 0.97444, 1.07436, 0.96729, 1.01498, 0.97872, 0.99353, 0.96006 |
| desktop-awt-reference | tiles | shanktonstatepen:240x320:shadows | original → cull | 404.297 | 388.672 | 1.0478× | 4.56% | 0.9884–1.1504 | 1.04545, 1.13735, 1.07285, 1.12203, 1.00648, 1.04096, 0.98843, 1.04778, 1.15043 |
| desktop-awt-reference | tiles | shanktonstatepen:240x320:shadows | index → cull | 402.344 | 388.672 | 1.0405× | 3.89% | 1.0099–1.1983 | 1.03199, 1.01675, 1.10099, 1.04437, 1.04052, 1.02560, 1.00992, 1.05461, 1.19829 |
| desktop-awt-reference | tiles | stalagflucht:240x320:shadows | original → index | 340.495 | 328.776 | 1.0159× | 1.57% | 0.9776–1.0721 | 1.06433, 0.97757, 1.04752, 0.99598, 0.99799, 1.07214, 1.01594, 1.04669, 0.97852 |
| desktop-awt-reference | tiles | stalagflucht:240x320:shadows | original → cull | 340.495 | 328.776 | 1.0061× | 0.60% | 0.8659–1.0986 | 1.09859, 1.03564, 1.04752, 1.00609, 0.86585, 1.09184, 0.97514, 0.97641, 0.99405 |
| desktop-awt-reference | tiles | stalagflucht:240x320:shadows | index → cull | 328.776 | 328.776 | 1.0101× | 1.00% | 0.8676–1.0594 | 1.03219, 1.05941, 1.00000, 1.01014, 0.86760, 1.01837, 0.95985, 0.93285, 1.01587 |
