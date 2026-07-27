import hashlib
import json
import logging
from typing import Any, Dict

import httpx
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import settings
from services.rag import index

logger = logging.getLogger("uvicorn.error")


class IngestionService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_pat:
            self.headers["Authorization"] = f"Bearer {settings.github_pat}"

    def _extract_json_strings(self, data: Any) -> str:
        """Recursively extracts all string values from a JSON structure."""
        if isinstance(data, dict):
            return "\n".join(self._extract_json_strings(v) for v in data.values())
        elif isinstance(data, list):
            return "\n".join(self._extract_json_strings(item) for item in data)
        elif isinstance(data, str):
            return data
        else:
            return ""

    def _should_process_file(
        self,
        file_path: str,
        folders: list[str] | None,
        read_dependency: bool,
        exact_files: list[str] | None = None,
    ) -> bool:
        if exact_files:
            return file_path in exact_files

        filename = file_path.split("/")[-1]
        is_dependency = filename in [
            "package.json",
            "requirements.txt",
            "composer.json",
            "go.mod",
        ]
        if is_dependency and read_dependency:
            return True

        if not (file_path.endswith(".md") or file_path.endswith(".json")):
            return False

        if not folders:
            return True

        for folder in folders:
            if file_path.startswith(f"{folder}/") or file_path == folder:
                return True

        return False

    def _generate_link(self, repo_full_name: str, branch: str, file_path: str) -> str:
        if (
            repo_full_name == "keynesfariz/keynesfariz.github.io"
            and file_path.startswith("contents/")
            and file_path.endswith(".md")
        ):
            filename = file_path.split("/")[-1]
            slug = filename[:-3]
            return f"https://keynesfariz.github.io/writings/{slug}"

        return f"https://github.com/{repo_full_name}/blob/{branch}/{file_path}"

    async def process_webhook_payload(
        self,
        payload: Dict,
        folders: list[str] | None = None,
        read_dependency: bool = False,
        exact_files: list[str] | None = None,
    ):
        """Processes a GitHub push webhook payload to selectively ingest added/modified files."""
        if "commits" not in payload:
            return

        repo_full_name = payload["repository"]["full_name"]
        branch = payload["ref"].split("/")[-1]

        files_to_process = set()

        for commit in payload["commits"]:
            for file_path in commit.get("added", []) + commit.get("modified", []):
                if self._should_process_file(
                    file_path, folders, read_dependency, exact_files
                ):
                    files_to_process.add(file_path)

        async with httpx.AsyncClient(headers=self.headers) as client:
            for file_path in files_to_process:
                raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{file_path}"
                response = await client.get(raw_url)

                if response.status_code == 200:
                    content = response.text
                    link = self._generate_link(repo_full_name, branch, file_path)
                    await self._embed_and_upsert(
                        file_path, content, repo_full_name, link
                    )
                else:
                    logger.error(
                        f"Failed to fetch {file_path}: HTTP {response.status_code}"
                    )

    async def process_initial_ingestion(
        self,
        repo_full_name: str,
        branch: str = "main",
        folders: list[str] | None = None,
        read_dependency: bool = False,
        exact_files: list[str] | None = None,
    ):
        """Fetches all markdown, json, and dependency files from the repository's git tree for initial ingestion."""
        logger.info(
            f"Starting initial ingestion for {repo_full_name} on branch {branch}"
        )

        if not settings.github_pat:
            logger.warning(
                "GITHUB_PAT is missing. Ingestion may fail if the repository is private."
            )

        async with httpx.AsyncClient(headers=self.headers) as client:
            tree_url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}?recursive=1"
            response = await client.get(tree_url)

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch git tree for {repo_full_name}: HTTP {response.status_code}. Response: {response.text}"
                )
                return

            tree_data = response.json()
            files_to_process = [
                item["path"]
                for item in tree_data.get("tree", [])
                if item["type"] == "blob"
                and self._should_process_file(
                    item["path"], folders, read_dependency, exact_files
                )
            ]

            logger.info(f"Found {len(files_to_process)} files to process in tree.")

            for file_path in files_to_process:
                raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{file_path}"
                file_response = await client.get(raw_url)

                if file_response.status_code == 200:
                    content = file_response.text
                    link = self._generate_link(repo_full_name, branch, file_path)
                    await self._embed_and_upsert(
                        file_path, content, repo_full_name, link
                    )

    async def _embed_and_upsert(
        self, file_path: str, content: str, repo_name: str, link: str
    ):
        if not index:
            logger.error(
                "Skipping upsert: Pinecone index is not initialized. Check your API key and Index name."
            )
            return

        try:
            index.delete(
                namespace=settings.pinecone_namespace, filter={"source": file_path}
            )
            logger.info(f"Cleaned up old chunks for {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete old chunks for {file_path}: {str(e)}")

        if (
            file_path.endswith(".json")
            and "package.json" not in file_path
            and "composer.json" not in file_path
        ):
            try:
                data = json.loads(content)
                content = self._extract_json_strings(data)
            except Exception:
                pass

        chunks = self.text_splitter.split_text(content)

        records = []
        for chunk in chunks:
            if not chunk.strip():
                continue
            hash_input = f"{file_path}_{chunk}".encode("utf-8")
            chunk_id = hashlib.md5(hash_input).hexdigest()
            records.append(
                {
                    "id": chunk_id,
                    "text": chunk,
                    "source": file_path,
                    "repo": repo_name,
                    "link": link,
                }
            )

        for i in range(0, len(records), 100):
            batch = records[i : i + 100]
            try:
                index.upsert_records(
                    namespace=settings.pinecone_namespace, records=batch
                )
            except Exception as e:
                logger.error(f"Pinecone upsert failed for batch: {str(e)}")


ingestor = IngestionService()
