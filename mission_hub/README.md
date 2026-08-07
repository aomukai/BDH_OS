# Ninereeds Mission Hub

Mission Hub is the sole authoritative control plane for Ninereeds. It replaces the legacy dual JSON ledgers, supervisor policy loop, trainbox worker ledger, and filesystem-derived status with one transactional job/run/event/artifact model.

The initial configuration is intentionally inert:

- training and external model calls are disabled;
- the trainbox is in maintenance mode;
- all schedules are disabled;
- automatic campaign rollover and Git mutation are disabled;
- protected-registry cleanup is enabled only at globally quiet run boundaries and only inside declared build roots;
- `system.healthcheck` is the only enabled job;
- the legacy Play campaign is preserved as non-resumable evidence.

Use `python3 -m mission_hub config-validate` to validate all configuration. See `docs/mission_hub_operator_runbook.md` before running any state-changing command.

The package is split by release manifest. The trainbox archive receives the stateless agent, safe handler code, schemas, model code, and exact training/evaluation entry points. It does not receive the Mission Hub database, API, scheduler, migration/evidence tools, Lab, historical scripts, legacy autonomous policies, corpora, or archives.
