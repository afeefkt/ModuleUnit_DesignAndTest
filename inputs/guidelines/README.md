# Design Guidelines Folder

Drop your standards documents here. The AI will read and reference them when generating diagrams.

## Supported Formats

| Format | Notes |
|--------|-------|
| `.html` | AUTOSAR standards, web-exported guidelines |
| `.pdf`  | ISO 26262, A-SPICE checklists, PDFs |
| `.docx` | Word documents |
| `.txt` / `.md` | Plain text or Markdown guidelines |

## How It Works

1. On each generation run, documents are parsed and split into ~800-character chunks
2. Chunks are embedded via Ollama (`nomic-embed-text`) for semantic search, or fall back to keyword matching if Ollama is not running
3. The top 3 most relevant chunks per diagram type are injected into the AI prompt as a **DESIGN GUIDELINES** block
4. Chunk embeddings are cached (in `data/guidelines_cache/`) — re-parsing only happens when a file changes

## Clearing the Cache

Click **Clear Cache** in the Design Guidelines sidebar panel, or call:

```
POST /api/v1/guidelines/clear-cache
```

After clearing, the next generation run will re-parse and re-embed all documents.

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MUD_GUIDELINES_ENABLED` | `true` | Set to `false` to disable entirely |
| `MUD_GUIDELINES_DIR` | `data/guidelines` | Path to this folder |
| `MUD_GUIDELINES_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `MUD_GUIDELINES_MAX_CHUNKS` | `3` | Max chunks injected per diagram type |
| `MUD_GUIDELINES_CHUNK_SIZE` | `800` | Target characters per chunk |

## Vector Embeddings (recommended)

Pull the embedding model once:

```
ollama pull nomic-embed-text
```

When Ollama is reachable, chunks are embedded as vectors and semantic similarity is used for retrieval (shown as `· vector` in the sidebar). If Ollama is not running, keyword-based TF-IDF matching is used as fallback (shown as `· keyword`).
