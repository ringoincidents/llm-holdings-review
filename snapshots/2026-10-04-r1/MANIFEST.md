# Snapshot Manifest

- review_round: `2026-10-04-r1`
- created_at: `2026-10-04`
- private_upstream_commit: `6153ca1366b7cc8ef672ef316cdc1741bb5e99fc`
- policy: selected sanitized snapshot; not a full repository mirror
- old_snapshot_mutation: prohibited except factual correction clearly marked as such

## Included architecture

- Frozen Runtime core
- Module boundaries
- Lab layer
- Mission orchestration
- Federated authority
- Living Organizational Knowledge
- Knowledge Context Pack
- Governed Record Writer

## Included decisions

- federated authority
- living organizational knowledge
- no cold-start work
- governed record writer

## Included source

Selected modules are copied under `source/` using their original relative paths.

They are included because they expose reviewable boundaries without publishing the entire private runtime.

## Included verification

Selected tests are copied under `tests/`.

## Included UI

The QuanTrade Private Investment Office surface is copied under `ui/`.

## Deliberate exclusions

This snapshot does not include:

- credentials or secrets;
- private client data;
- raw organizational memory;
- deployment configuration not required for review;
- complete task backlog;
- full production repository;
- every runtime module;
- every UI surface.

A reviewer may request additional sanitized files through an Issue if a conclusion cannot be verified from the current snapshot.
