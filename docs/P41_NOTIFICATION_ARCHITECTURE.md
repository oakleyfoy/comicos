# P41 Notifications / Alerting / Operational Messaging Architecture

## Notification philosophy

P41-06 adds a deterministic notification and alert ledger for automation, scan intelligence, replay diagnostics, recovery, and workflow orchestration events. The layer records immutable notification payloads, template resolution, delivery attempts, alert escalation, append-only history, and diagnostic issues without external email/SMS providers, push infrastructure, or websocket delivery.

## Alert escalation model

Operational failures can be elevated into alerts with deterministic severity and escalation levels (`LEVEL_1`, `LEVEL_2`, `LEVEL_3`). Escalation metadata is preserved in alert checksum lineage and append-only history. Acknowledgements transition alerts through explicit states without hidden suppression.

## Deterministic routing model

Notification types map to alert types through stable routing rules (for example workflow failure → workflow failure alert, dead-letter transfer → dead-letter alert, replay warnings → replay drift alert). Routing is replay-safe and duplicate alerts are rejected through checksum deduplication.

## Delivery lineage model

Deliveries are queued with stable channel ordering (`delivery_rank`) and recorded as append-only delivery rows with checksums. In-app and ops-console channels are delivered deterministically in P41-06; future channels are recorded as skipped rather than silently dropped.

## Replay-safe messaging guarantees

Identical notification inputs produce identical notification keys and stable manifest checksums after template resolution, delivery lineage, alert lineage, and artifact exports are applied. Artifacts are stored under deterministic filesystem paths rooted at `automation-notifications/{notification_type}/{notification_id}/`.

## Non-goals

- External email providers
- SMS integrations
- Push notifications
- Realtime websockets
- Distributed alert routing
- ML-driven alert prioritization
- External notification brokers
