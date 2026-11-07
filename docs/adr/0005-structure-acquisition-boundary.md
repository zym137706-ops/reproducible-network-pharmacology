# ADR 0005 — Structure acquisition boundary

- Status: accepted design; implementation pending
- Date: 2026-11-07
- Relates to: [ADR-0004](0004-staged-upstream-and-docking.md) (items 4, 5 and 7), [docking design](../docking.md) §3, [upstream design](../upstream.md) §3

## Context

ADR-0004 puts receptor selection (review gate G10) in front of docking, and the docking design requires every
receptor record to carry its source ID, version, download time and hash, the target-sequence and chain mapping,
mutations and missing regions, the assembly state and the retained or removed components. Those facts have to be
reproducible. Two kinds of tool can touch the public structure and sequence services:

1. an explicit acquisition step inside this repository that freezes what it retrieved;
2. optional external discovery tools (for example a read-only MCP server) that list candidate structures,
   chain-to-UniProt mappings, co-crystal ligands and UniProt site annotations for a person to look at.

Checks against the public services on 2026-11-06 showed why the two must not be mixed up:

- the RCSB GraphQL endpoint silently drops unknown IDs instead of reporting them;
- UniProt returns a deleted or demerged accession as HTTP 200 with an `Inactive` entry type;
- GraphQL errors arrive as HTTP 200 with an `errors` field, and two identical GraphQL requests can return
  different bytes, so a hash identifies one retrieval, not one query;
- the declared mutation count and sequence alignment can disagree with the actual sequence: PDB entry 7XJO, an
  engineered MMP-2 catalytic-domain construct, differs from UniProt P08253 at three positions including the
  catalytic glutamate, yet its declared mutation count is 0; its alignment record is one contiguous segment
  although the construct is a two-segment deletion construct;
- UniProt feature positions and PDB residue numbers differ by an entry-specific offset (14 for human PTGS2 in
  PDB 5F19, 0 for the FAK kinase domain in PDB 6YOJ).

None of this is a reason to distrust a discovery tool for browsing. It is a reason to keep every fact that a
receptor record, a candidate pair or a docking run relies on out of anything that is not frozen, hashed and
re-checkable.

## Decision

1. **Receptor and sequence facts come from frozen records only.** Everything a receptor record, a candidate pair
   or a docking run relies on (structure file, entry metadata, UniProt record, sequence, release or version,
   retrieval time, hash) is produced by one explicit acquisition step and read back from the frozen files
   afterwards. Analysis and docking never query a service.
2. **The acquisition step is a core command.** It will be `rnp acquire`, implemented in Python under
   `src/rnp/acquire/` with the HTTP fetcher injectable so that tests run offline, using the standard library only
   (no new runtime dependency). It talks only to documented public endpoints (initially `files.rcsb.org`,
   `data.rcsb.org` and `rest.uniprot.org`); adding a host requires amending this ADR. This is data retrieval, not
   online prediction, scraping or form replay, so the non-goals in [architecture.md](../architecture.md) §2 still
   hold.
3. **It is the only command that uses the network.** No module other than `rnp.acquire` may import a networking
   library, and `rnp dock *` never goes online. A guard test enforces this by inspecting imports.
4. **Failure is explicit.** An unknown ID, an inactive or secondary accession, a non-2xx response, an empty body,
   an error reported inside an HTTP 200 response, or a hash mismatch on offline verification is an error that
   names the URL and the reason. A run with both successes and failures is partial (exit code 3) and records both.
   Nothing is dropped silently, and a search hit is never substituted for a requested ID.
5. **Every retrieval is recorded.** The acquisition record lists, per request, the URL and method, a hash of the
   request body where there is one, the HTTP status, the retrieval time, the byte count, the hash of the decoded
   response body, a whitelist of response headers that carry version information, and the frozen file path. The
   record's JSON Schema is written before any fetching code (a later slice).
6. **Frozen files stay local.** Structure and sequence files go to `data/local/structures/` (git-ignored). The
   repository commits acquisition records and hashes, and small trimmed test fixtures with provenance, only where
   the source's terms allow it (see [data licenses](../data-licenses.md)).
7. **Discovery tools are optional, external and ID-only.** A read-only discovery tool may help a person list
   candidate PDB entries, chains, co-crystal ligands and UniProt site annotations at G10. It is never a dependency
   of the core, no command or test requires it, and nothing it returns is an input to a record. Only identifiers
   (PDB ID, UniProt accession, component ID) cross into `rnp`; the facts are re-obtained by `rnp acquire`. A
   decision record may cite the hash of the candidate list the reviewer was shown, as a record of what was shown
   and never as evidence.
8. **Declared facts are cross-checked, not trusted.** Mutations, deletions, tags and the UniProt-to-PDB residue
   numbering are derived from the frozen sequences and compared with what the services declare; a disagreement is
   reported for review and never resolved silently. (The construct check is a later slice.)

Out of scope here: predicted structures (ADR-0004 item 7), automatic receptor selection, preparation, docking and
scoring.

## Alternatives considered

1. **A download script only, as for the HGNC snapshot and the PubChem structures.** Simple and keeps the core
   offline, but scripts are not packaged, are not part of the command and exit-code contract, and are not covered
   by the run manifest; receptor facts would sit outside the audited surface.
2. **Let an agent or MCP tool write staging files and manifests.** Rejected: the provenance of a docking input
   would begin with an agent session, and a second implementation would carry its own provenance semantics.
3. **Resolve everything at docking time.** Rejected: runs would not repeat offline, and a change at a service
   would silently change results.

## Consequences

- The core gains one networked command, bounded by the import guard and the endpoint list; CI and the offline
  demo stay network-free.
- Receptor facts carry a hash and a retrieval time; a later change at a service shows up as drift when the frozen
  files are re-verified, with no network needed.
- The acquisition-record schema, the `rnp acquire` command, the construct check and the candidate-pair tables are
  separate later slices. This ADR adds no command, schema or runtime behaviour.
- `docs/data-licenses.md` and `data/SOURCES.yaml` gain RCSB PDB and UniProt rows now; `docs/citations.md` gains
  their entries when `rnp acquire` ships.
- A discovery tool can be replaced or removed without touching any result.
