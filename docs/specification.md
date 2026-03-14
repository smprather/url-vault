# Project Specification

## 1. Purpose

`mirror-repos` keeps local mirrors of configured Git repositories up to date.

## 2. Goals

List measurable goals.

- Mirror repositories on a schedule.
- Support both public and private remotes.
- Provide clear logs for sync outcomes.

## 3. Non-Goals

Call out what this project will not do.

- No full CI/CD orchestration.
- No GUI

## 4. Users & Use Cases

- Used to build a local database of repositories that will eventually be further mirrored into a secure
  compute environment. But secure environment can't see the internet, so I have to use work laptop as an
  intermediate jump point. I already have another script that will mirror directories into the secure
  environment.

## 5. Functional Requirements

Number requirements for traceability.

1. The system must read a local yaml config file of repositories.
2. The system must clone missing repositories.
3. The system must fetch updates for existing repositories.
4. The system must report per-repository success/failure.
5. The system must use git clone --mirror.
6. The system must provide a CLI flag to run one update cycle and exit.

## 6. Configuration

Define expected configuration keys and formats.

```yaml
update_period: 24h
max_parallel: 4
destination_dir: $HOME/repo_mirrors
repositories:
  - url: git@github.com:org/example.git
```

Repository paths are derived automatically and are not configured per repository.
`repositories` remains a list of per-repository mapping objects so additional keys can be added later.
Each repository entry currently requires only a `url`.
`max_parallel` controls how many repository syncs may run at the same time.
For GitHub remotes, the local mirror path is:

`<destination_dir>/<everything-after-github.com>`

Examples:

- `https://github.com/org/example.git` -> `<destination_dir>/org/example.git`
- `git@github.com:org/example.git` -> `<destination_dir>/org/example.git`

## 7. Non-Functional Requirements

Document quality attributes.

- Reliability: partial failures should not stop other repo syncs.
- Performance: complete sync of N repositories within acceptable time.
- Security: secrets must never be logged.

## 8. Error Handling & Observability

Specify expected behavior for failures and logging.

- Retry transient network failures.
- Emit structured logs with repository URL or derived path and status.

## 9. Open Questions

Track unresolved decisions.

- Should sync be pull-based, fetch-only, or configurable?
- Should concurrency be fixed or user-configurable?

## 10. Acceptance Criteria

Define what “done” means for the next milestone.

- Running `python main.py --once` with a valid config mirrors all repos once.
- Failures are summarized with actionable messages.
- Core behavior is covered by automated tests.
