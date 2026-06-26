# Pipeline

HCF's `/hcf:plan-orchestrate` Phase 6 reads this file to determine which agents run after all tasks complete and before the final commit.

## post-implementation

- standards-enforcer
- security-quorum

`standards-enforcer` verifies code conforms to the conventions in `.claude/CLAUDE.md` and `.claude/testing.md` — ruff format/lint clean, pyright clean in basic mode, line length 100, single-quoted strings.

`security-quorum` runs the 3-specialist 2-of-3 consensus audit on the diff. The chat service is a network listener, so security review is non-optional — input validation on the REST endpoints, authn/authz on subagent write paths, SQLite injection risk on parameterised queries, secret handling for any future API key surfaces. Verdict surfaces in the orchestration summary.

`gitnexus-reviewer` is intentionally NOT listed — this is a Python project, not Magento; gitnexus code-graph index doesn't cover Python ASTs in this fleet.

## post-plan

(no agents — devils-advocate is HCF's built-in plan reviewer and runs before this phase)
