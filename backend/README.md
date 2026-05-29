# backend — platform side (RAG / audit / eval)

Platform services for Tanomude (design §10), separate from the Mock AS-400.

## Manual RAG

- Ingestion: structure-aware chunking (markdown headings = procedure sections) → `passage:` embeddings (multilingual-e5-large, 1024d) → `knowledge_chunks`.
- Retrieval: hybrid Vector (pgvector cosine) + FTS (`simple`) fused with RRF (k=60).

### Retrieval is exact-scan by design

Migration `0001` creates no GIN (fts) or ivfflat/hnsw (embedding) index. For the
current single-manual corpus, exact KNN is both fast enough and strictly more accurate
than an approximate index. Adding a GIN index for FTS and an ANN index for the embedding
column is the scale-up path when the corpus grows; it is intentionally omitted now, not an
oversight.

### Japanese FTS

The `fts` column uses the `simple` configuration, which does not tokenize Japanese
(no whitespace). Retrieval-eval shows vector search carries Japanese queries while `simple`
FTS only matches latin tokens (field/project codes). A Japanese-aware FTS backend
(pgroonga / pg_bigm) is the upgrade path (design §13 stretch) when lexical Japanese matching
is required.
