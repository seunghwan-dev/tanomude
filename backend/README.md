# backend — platform side (RAG / audit / eval)

Platform services for Tanomude, separate from the Mock AS-400.

## Manual RAG

- Ingestion: structure-aware chunking (markdown headings = procedure sections) → `passage:` embeddings (multilingual-e5-large, 1024d) → `knowledge_chunks`.
- Retrieval: hybrid Vector (pgvector cosine) + FTS (`simple`) fused with RRF (k=60).

### Retrieval is exact-scan by design

Migration `0001` creates no GIN (fts) or ivfflat/hnsw (embedding) index. For the
current single-manual corpus, exact KNN is both fast enough and strictly more accurate
than an approximate index. Adding a GIN index for FTS and an ANN index for the embedding
column is the scale-up path when the corpus grows; it is intentionally omitted now, not an
oversight.

## Core loop screen-transition contract

`coreloop.execute` and `slotfill.assemble` share an implicit screen-transition contract:
`execute` sends one login `nav Enter` (`LOGIN → MENU`), then runs the assembled keysequence
whose own leading `nav Enter` is `MENU → TRIP_INPUT`. The keysequence is authored to start at
`MENU`; the orchestrator owns the login step. A real AS-400 adapter (or a future change to either
side) must preserve this split — execute does login, the keysequence does menu→trip onward.

## Slot-fill engine

Code owns structure, refusal (required-field absence → first-class `Refusal`), and the
deterministic fields: dates and DAYS are parsed/normalized from `request.fields` (not the
LLM), and the project code is read from `proj_resolved`/`proj_hint`. The LLM only returns
`dest_code` (romaji), `purpose`, and the `overseas`/`reuse_prev_proj` branch flags.

Executor contract: on the reuse branch (`reuse_prev_proj`), the `PROJ` field step may carry
a `null` value when no project code is provided — the `F9` key recalls the previous value, so
the executor must treat a null-valued field step on that path as "leave blank / F9 fills it"
rather than typing a literal.

### Japanese FTS

The `fts` column uses the `simple` configuration, which does not tokenize Japanese
(no whitespace). Retrieval-eval shows vector search carries Japanese queries while `simple`
FTS only matches latin tokens (field/project codes). A Japanese-aware FTS backend
(pgroonga / pg_bigm) is the stretch upgrade path when lexical Japanese matching
is required.
