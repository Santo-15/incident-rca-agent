# GitHub API: deploy tags (deploy.sh names them deploy-YYYYmmdd-HHMMSS in UTC) and the diff between two tags
import os
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
API = "https://api.github.com"


def _repo() -> str:
    return os.getenv("GITHUB_REPO", "Santo-15/incident-rca-agent")


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := os.getenv("GITHUB_TOKEN"):   # optional: needed for a private repo, raises the limit from 60 to 5000 req/h
        h["Authorization"] = f"Bearer {token}"
    return h


def tag_time(tag: str) -> float:
    return datetime.strptime(tag, "deploy-%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc).timestamp()   # KEY: deploy time comes from the tag name, no extra API call per tag


def list_deploy_tags() -> list[tuple[str, float]]:
    resp = httpx.get(f"{API}/repos/{_repo()}/git/matching-refs/tags/deploy-", headers=_headers(), timeout=10)   # KEY: one call returns every deploy-* tag
    resp.raise_for_status()
    tags = []
    for ref in resp.json():
        name = ref["ref"].removeprefix("refs/tags/")
        try:
            tags.append((name, tag_time(name)))
        except ValueError:   # a tag that doesn't follow the deploy.sh format
            continue
    return sorted(tags, key=lambda t: t[1])


def compare(base: str, head: str) -> list[dict]:
    resp = httpx.get(f"{API}/repos/{_repo()}/compare/{base}...{head}", headers=_headers(), timeout=15)   # KEY: GitHub compare API
    resp.raise_for_status()
    return resp.json().get("files", [])   # [{filename, status, additions, deletions, patch}]
