# Open Knowledge Format (OKF v0.2) - Core System Rules

This document distills the **Open Knowledge Format (OKF v0.2)** specification ([`SPEC.md`](SPEC.md)) into concise rules for AI agents, memory engines, and tools generating or consuming persistent knowledge records.

---

## 1. Document Structure & Conformance

Every OKF concept document is a UTF-8 Markdown file (`.md`) consisting of two parts:
1. **YAML Frontmatter**: Delimited by `---` on line 1 and `---` closing line.
2. **Markdown Body**: Structured prose, headings, lists, tables, and fenced code blocks.

### Conformance Criteria (§11)
- Every non-reserved `.md` file **MUST** contain parseable YAML frontmatter.
- Every frontmatter block **MUST** contain a non-empty `type` field.
- Reserved filenames (`index.md`, `log.md`) **MUST NOT** be used as concept filenames.

---

## 2. Frontmatter Fields & Schemas (§4 & §5)

### Required Field
- `type`: String identifying the concept type (e.g. `Agent Memory`, `Metric`, `Playbook`, `Attested Computation`, `BigQuery Table`, `API Endpoint`).

### Recommended Core Fields
- `title`: Human-readable display name.
- `description`: Single-sentence summary of the concept.
- `resource`: Canonical URI of the underlying asset (if applicable).
- `tags`: YAML array of short strings for categorization (e.g. `[preferences, python]`).

### Trust Family (§5.2 & §7)
- `generated`: Object detailing document creation/update metadata:
  - `by`: Actor string following actor convention (§7):
    - Agent/Tool: `<producer>/<version>` (e.g. `mcp-memory/0.2.0`, `reference_agent/gemini-2.5-pro`)
    - Human: `human:<id>` (e.g. `human:ahormati`)
    - Process: `process:<id>` (e.g. `process:finance-nightly`)
  - `at`: ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`).
- `verified`: List of verification events `[{ by: "<actor>", at: "<ISO 8601 timestamp>" }]` (or a single `{ by, at }` mapping).

#### Derived Trust Tiers (§5.3)
- **Unverified**: No `verified` field.
- **Machine-Confirmed**: Verified by non-`human:` actors only.
- **Human-Reviewed**: Verified by at least one `human:<id>` actor.

### Provenance Family (§5.1)
- `sources`: Array of source objects that the concept derives from:
  - `resource`: REQUIRED within entry (absolute URL, bundle path, or scope description).
  - `id`: Stable key used for per-claim body attribution footnotes (`[^id]`).
  - `title`: Human-readable label.
  - `author`: Actor string (`<producer>/<version>`, `human:<id>`, `process:<id>`).
  - `usage_count`: Liveness/exercise count integer.
  - `last_modified`: ISO date (`YYYY-MM-DD`).
- `usage_window`: Shared framing object `{ from: "YYYY-MM-DD", to: "YYYY-MM-DD" }`.

#### Per-Claim Attribution (§5.1)
In the Markdown body, attribute specific claims using footnotes matching `sources[].id`:
```markdown
The user prefers tab indentation.[^style-guide]

[^style-guide]: Engineering Style Guide
```

### Lifecycle Family (§5.4 & §5.5)
- `status`: Lifecycle state string (`draft` | `stable` | `deprecated`). Defaults to `stable`.
- `stale_after`: ISO date string (`YYYY-MM-DD`). Concept is stale when `today >= stale_after`.

---

## 3. Attested Computations (§10)

For concepts executing sanctioned logic (`type: Attested Computation`):
- `runtime`: REQUIRED (`bigquery`, `postgres`, `dbt`, `python`, etc.).
- `parameters`: Array of parameter descriptors `[{ name: "<name>", type: "<type>", required: true|false }]`.
- `executor`: `{ resource: "<path>", receipt: [<field_names>] }`.
- `attester`: `{ resource: "<path>" }`.
- `computation`: Optional relative/absolute path to file containing computation. If absent, logic lives inline under body heading `# Computation`.

---

## 4. Bundle Structure & Reserved Files (§3, §8, §9)

Knowledge bundles are organized as hierarchical directory trees:

```
memory/
  index.md          # Bundle Root Index (Contains okf_version: "0.2")
  log.md            # Bundle Update Log
  <concept>.md
  <subdirectory>/
    index.md        # Directory Index (No frontmatter)
    <concept>.md
```

### Index Files (`index.md`) (§8 & §12)
- **Bundle Root `index.md`**: MUST contain frontmatter with `okf_version: "0.2"`.
- **Subdirectory `index.md`**: MUST NOT contain frontmatter.
- Body lists subdirectories and concept files grouped by sections for progressive disclosure.

### Log Files (`log.md`) (§9)
- Records chronological update history for the bundle or subdirectory.
- Date headings use ISO 8601 `## YYYY-MM-DD` format, ordered newest first.
- Log entries use bold prefix conventions: `**Creation**`, `**Update**`, `**Deletion**`, `**Deprecation**`.

```markdown
# Directory Update Log

## 2026-08-12
* **Creation**: Stored concept [Coding Style](/user/preferences/coding_style.md).
* **Update**: Modified [Database Architecture](/project/architecture.md).
```

---

## 5. Cross-Linking & Paths (§6)

- Prefer bundle-relative links starting with `/` (e.g. `[Coding Style](/user/preferences/coding_style.md)`).
- Path-valued fields (`resource`, `sources[].resource`, `computation`) accept absolute URLs, bundle-relative paths (`/path`), or relative paths (`./path`).

---

## 6. Last Memory Continuity Protocol

To enable seamless context resumption across sessions and long-running multi-day tasks:

- **Canonical Key**: `system/last_memory`
- **Concept Type**: `Checkpoint`
- **Agent Initialization Directive**: Upon starting a session or opening a project, the AI agent **MUST** call `memory_get_last` (or retrieve `system/last_memory`) as its first action to inspect where work was last left off.
- **Milestone & Progress Directive**: Whenever completing a milestone, making key structural changes, or pausing work, the AI agent **MUST** call `memory_update_last` (or update `system/last_memory`) to record a brief summary of progress and link active concepts.

