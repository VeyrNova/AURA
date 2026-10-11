# ADF source comparison

All historical reads were read-only on 2026-10-02.

| Capability | Workspace Native | Legacy local | GitHub commit | Canonical |
|---|---|---|---|---|
| ADF-A foundation | safety scaffold | manifest/architecture | identical | GitHub contract, native reimplementation |
| ADF-B gateway | absent | manifest/docs/runtime | identical | recover contract; no Chromium copy |
| ADF-C provider/quota | generic router | registry/policy | identical | metadata contract, no secrets |
| ADF-D agents/bridges | absent | 10-agent catalog/IDE bridges | identical | catalog contract; adapters later |
| ADF-E resilience | absent | manifest/docs | identical | staged native design |
| ADF-F transactions | bounded primitive | runtime/policy | identical policy | native safety contract |
| ADF-G self-development | default-off mode | policy/audit contract | identical | preserve gates |
| ADF-H live binding | no ADF bridge | Chromium patchers/live state | identical | separate Qt/QML bridge |

Old `.aura_audit`, `.aura_transactions`, credentials, state and build outputs are evidence/generated data and are not migration inputs.
