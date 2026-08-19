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

Mission Hub also contains the Ninereeds research memory:

- `mission_hub/research/` defines immutable source registration, Luna's librarian
  contract, and Sol's evidence-bound campaign-planning checklist.
- `mission_hub/wiki/` is the persistent, LLM-maintained research synthesis. Read
  `mission_hub/wiki/index.md` first.

Operational state remains authoritative in Mission Hub's transactional ledger.
Registered source bytes remain evidentiary truth. Wiki pages are the current research
synthesis over those sources; they may never serve as their own evidence.

Validate the research memory with:

```bash
python3 -m mission_hub.research_wiki lint
```

The package is split by release manifest. The trainbox archive receives the stateless agent, safe handler code, schemas, model code, and exact training/evaluation entry points. It does not receive the Mission Hub database, API, scheduler, migration/evidence tools, Lab, historical scripts, legacy autonomous policies, corpora, or archives.
