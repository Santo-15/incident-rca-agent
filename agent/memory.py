import os
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from agent.schemas import Finding

ROOT = Path(__file__).resolve().parents[1]                              # repo root, so the path works from any folder
CHROMA_PATH = os.getenv("CHROMA_PATH", str(ROOT / "data" / "chroma"))   # KEY: on-disk store; gitignored, always rebuilt from the seed
COLLECTION = "incidents"                                                # one collection = all past incidents
MAX_DISTANCE = 0.2   


@lru_cache(maxsize=1)   # open the client once per process, reuse after that
def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False))  # no usage pings to Chroma
    return client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=DefaultEmbeddingFunction(),   # KEY: local all-MiniLM-L6-v2 (384 numbers); no API key, no LLM call
        configuration={"hnsw": {"space": "cosine"}},      # KEY: distance = 1 - cosine similarity (0 = same meaning)
    )


def incident_text(alerts: list[str], silent: list[str], findings: list[Finding]) -> str:
    # KEY: ONE text format for seed records AND live queries; if they differ, distances become meaningless
    firing = ", ".join(a.split(" since ")[0] for a in alerts) or "none"   # KEY: drop timestamps; they change every incident and add noise
    quiet = ", ".join(silent) or "none"
    ordered = sorted(findings, key=lambda f: (f.source, f.signal))        # KEY: parallel agents finish in any order; sort so same evidence = same text
    lines = [f"- {f.source}: {f.signal}: {f.detail}" for f in ordered]
    return f"Firing: {firing}\nSilent: {quiet}\nFindings:\n" + "\n".join(lines)


def add_incident(incident_id: str, text: str, cause: str, scenario: str, fix: str, source_doc: str = "") -> None:
    get_collection().upsert(   # KEY: upsert = insert, or replace if the id exists; re-running the seed never duplicates
        ids=[incident_id],
        documents=[text],                                                # KEY: symptoms only; this is what gets embedded
        metadatas=[{"cause": cause, "scenario": scenario, "fix": fix, "source_doc": source_doc}],  # KEY: the answer rides along, not embedded
    )


def search_similar(text: str, k: int = 2, max_distance: float = MAX_DISTANCE,
                   exclude_scenario: str | None = None) -> list[dict]:
    col = get_collection()
    if col.count() == 0:   # empty memory (e.g. during eval) -> nothing to suggest
        return []
    res = col.query(
        query_texts=[text],                    # Chroma embeds the query with the same model
        n_results=min(k, col.count()),         # can't ask for more records than exist
        where={"scenario": {"$ne": exclude_scenario}} if exclude_scenario else None,  # KEY: eval leakage guard (skip the scenario under test)
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for id_, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):  # [0] = our single query
        if dist <= max_distance:   # KEY: Chroma always returns k results; keep only the ones that are actually close
            hits.append({"id": id_, "distance": round(dist, 3), "text": doc, **meta})
    return hits