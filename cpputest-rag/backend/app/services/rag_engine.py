"""RAG engine — FAISS indexing, embedding, and similarity retrieval"""

import aiohttp
import numpy as np
import faiss
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

from app.models import FunctionInfo
from app.config import config

logger = logging.getLogger(__name__)

# Module-level state
index = None
test_examples_metadata: Dict = {"texts": [], "meta": [], "examples": {}}


def _index_paths() -> tuple:
    """Index + metadata live next to the database (the persisted data volume)."""
    data_dir = Path(config.DATABASE_PATH).parent
    return data_dir / config.INDEX_FILE, data_dir / config.META_FILE


def _example_files() -> List[Path]:
    return sorted(
        list(config.TEST_EXAMPLES_DIR.rglob("*.cpp")) + list(config.TEST_EXAMPLES_DIR.rglob("*.c"))
    )


def _examples_signature(files: List[Path]) -> str:
    """Changes whenever the embedding model or any example file changes."""
    h = hashlib.sha256(config.EMBED_MODEL.encode())
    for f in files:
        h.update(str(f).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def _load_saved_index() -> bool:
    """Load a saved index if it matches the current examples + embed model.

    Returns True when a valid saved index was loaded (no re-embedding needed).
    """
    global index, test_examples_metadata
    index_file, meta_file = _index_paths()
    if not (index_file.exists() and meta_file.exists()):
        return False
    try:
        with open(meta_file, "rb") as f:
            meta = pickle.load(f)
        if meta.get("signature") != _examples_signature(_example_files()):
            logger.info("Examples or embed model changed — index will be rebuilt")
            return False
        loaded = faiss.read_index(str(index_file))
        if loaded.ntotal != len(meta.get("texts", [])):
            return False
        index, test_examples_metadata = loaded, meta
        logger.info(f"Loaded saved examples index ({loaded.ntotal} examples)")
        return True
    except Exception as e:
        logger.warning(f"Could not load saved index ({e}) — rebuilding")
        return False


async def load_or_build_examples_index():
    """Startup path: reuse the saved index when possible, else embed everything."""
    if not _load_saved_index():
        await build_examples_index()


async def embed_text(text: str, session: aiohttp.ClientSession) -> Optional[np.ndarray]:
    """Generate embedding for text via Ollama"""
    if not text or not text.strip():
        return None

    try:
        url = f"{config.OLLAMA_URL}/embeddings"
        payload = {
            "model": config.EMBED_MODEL,
            "prompt": text
        }

        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        ) as response:
            if response.status == 200:
                result = await response.json()
                embedding = result.get("embedding")
                if embedding:
                    return np.array(embedding, dtype="float32")
    except Exception as e:
        logger.error(f"Embedding error: {e}")

    return None


async def build_examples_index():
    """Build FAISS index from test example files"""
    global index, test_examples_metadata

    logger.info("Building index from test examples...")

    example_files = _example_files()

    if not example_files:
        logger.warning(f"No example files found in {config.TEST_EXAMPLES_DIR}")
        return

    texts = []
    metadata = []

    for example_file in example_files:
        try:
            with open(example_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            texts.append(content)
            metadata.append({
                'file': example_file.name,
                'path': str(example_file)
            })

            logger.info(f"Added example: {example_file.name}")
        except Exception as e:
            logger.error(f"Error reading {example_file}: {e}")

    if not texts:
        logger.warning("No text extracted from examples")
        return

    # Generate embeddings. texts/metadata are rebuilt in lock-step with the
    # vectors so FAISS row i always refers to texts[i] — skipping a failed
    # embedding without dropping its text would shift every later result.
    logger.info(f"Generating embeddings for {len(texts)} examples...")
    vectors = []
    kept_texts = []
    kept_meta = []

    async with aiohttp.ClientSession() as session:
        for text, meta in zip(texts, metadata):
            vec = await embed_text(text, session)
            if vec is not None:
                vectors.append(vec)
                kept_texts.append(text)
                kept_meta.append(meta)
            else:
                logger.warning(f"Failed to embed example {meta['file']} — left out of the index")
    texts, metadata = kept_texts, kept_meta

    if not vectors:
        logger.error("Failed to generate any embeddings")
        return

    # Create FAISS index
    dim = vectors[0].shape[0]
    vectors_array = np.vstack(vectors)
    faiss.normalize_L2(vectors_array)

    index = faiss.IndexFlatIP(dim)
    index.add(vectors_array)

    test_examples_metadata = {
        "texts": texts,
        "meta": metadata,
        "created_at": datetime.now().isoformat(),
        "signature": _examples_signature(example_files),
    }

    # Save index to disk (best effort — a read-only data dir must not break startup)
    index_file, meta_file = _index_paths()
    try:
        index_file.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(index_file))
        with open(meta_file, "wb") as f:
            pickle.dump(test_examples_metadata, f)
    except Exception as e:
        logger.warning(f"Could not save examples index: {e}")

    logger.info(f"Index built: {len(vectors)} examples indexed")


async def retrieve_similar_examples(function_info: FunctionInfo, k: int = 3) -> List[Dict]:
    """Retrieve similar test examples for a given function"""
    if index is None:
        return []

    # Create query from function info
    query = f"""
    Function: {function_info.name}
    Return type: {function_info.return_type}
    Parameters: {', '.join([f"{p['type']} {p['name']}" for p in function_info.parameters])}
    Source:
    {function_info.source_code[:500]}
    """

    async with aiohttp.ClientSession() as session:
        qvec = await embed_text(query, session)

    if qvec is None:
        return []

    qvec = qvec.reshape(1, -1)
    faiss.normalize_L2(qvec)

    k = min(k, len(test_examples_metadata["texts"]))
    distances, indices_result = index.search(qvec, k)

    results = []
    for dist, idx in zip(distances[0], indices_result[0]):
        if 0 <= idx < len(test_examples_metadata["texts"]):
            results.append({
                "text": test_examples_metadata["texts"][idx],
                "metadata": test_examples_metadata["meta"][idx],
                "score": float(dist)
            })

    return results
