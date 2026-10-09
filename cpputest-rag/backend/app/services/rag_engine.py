"""RAG engine — FAISS indexing, embedding, and similarity retrieval"""

import aiohttp
import os
import numpy as np
import faiss
import pickle
from typing import List, Dict, Optional
from datetime import datetime
import logging

from app.models import FunctionInfo
from app.config import config

logger = logging.getLogger(__name__)

# Module-level state
index = None
test_examples_metadata: Dict = {"texts": [], "meta": [], "examples": {}}

# Max characters sent to the embedding model (see embed_text).
EMBED_MAX_CHARS = int(os.getenv("EMBED_MAX_CHARS", "1600"))


async def embed_text(text: str, session: aiohttp.ClientSession) -> Optional[np.ndarray]:
    """Generate embedding for text via Ollama"""
    if not text or not text.strip():
        return None

    url = f"{config.OLLAMA_URL}/embeddings"
    # Small embedding models (all-minilm: ~256 tokens) reject longer input
    # with HTTP 500 "input length exceeds the context length". The start of a
    # test file identifies it, so embed a prefix and halve it until it fits.
    limit = EMBED_MAX_CHARS
    while limit >= 100:
        payload = {"model": config.EMBED_MODEL, "prompt": text[:limit]}
        try:
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
                    return None
                body = await response.text()
                if "context length" not in body or len(text) <= limit // 2:
                    logger.error(f"Embedding HTTP {response.status}: {body[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None
        limit //= 2

    return None


async def build_examples_index():
    """Build FAISS index from test example files"""
    global index, test_examples_metadata

    logger.info("Building index from test examples...")

    example_files = list(config.TEST_EXAMPLES_DIR.rglob("*.cpp")) + \
                    list(config.TEST_EXAMPLES_DIR.rglob("*.c"))

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

    # Generate embeddings
    logger.info(f"Generating embeddings for {len(texts)} examples...")
    vectors = []
    kept_texts = []
    kept_meta = []

    # Keep texts/metadata in lock-step with the vectors: FAISS row i must
    # describe texts[i], so a failed embedding drops its text too.
    async with aiohttp.ClientSession() as session:
        for i, text in enumerate(texts):
            vec = await embed_text(text, session)
            if vec is not None:
                vectors.append(vec)
                kept_texts.append(text)
                kept_meta.append(metadata[i])
            else:
                logger.warning(f"Failed to embed example {i}")
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

    # Save index to disk
    faiss.write_index(index, config.INDEX_FILE)

    test_examples_metadata = {
        "texts": texts,
        "meta": metadata,
        "created_at": datetime.now().isoformat()
    }

    with open(config.META_FILE, "wb") as f:
        pickle.dump(test_examples_metadata, f)

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
        if idx < len(test_examples_metadata["texts"]):
            results.append({
                "text": test_examples_metadata["texts"][idx],
                "metadata": test_examples_metadata["meta"][idx],
                "score": float(dist)
            })

    return results
