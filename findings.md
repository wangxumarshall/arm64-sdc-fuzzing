# Findings

## Summary

这轮源码审阅后的结论可以收敛为五点：

1. 当前项目已经有一条强控制平面骨架：`generation -> vault -> campaign/differential -> scheduler -> genetic`。
2. 高频内循环、低频外循环、硬件验证环必须显式拆层，不能继续混写。
3. 当前生成路径本质上偏 `SIM_SAFE`，不足以独立兑现 README 中更激进的硬件覆盖愿景。
4. 当前 Vault 单表模型不够承载多次 fault run、功耗版本和真机回灌。
5. `gem5` fault control plane 已通，但真实 injector，以及 `opendcdiag-arm` promotion/backfill 仍未落地。

## Pointers

- 全量发现见 [doc/findings.md](/Users/wangxu/1-project/sdc-fuzzing/doc/findings.md)
- 完整目标架构见 [doc/spec.md](/Users/wangxu/1-project/sdc-fuzzing/doc/spec.md)
- 分阶段执行方案见 [doc/plan.md](/Users/wangxu/1-project/sdc-fuzzing/doc/plan.md)
