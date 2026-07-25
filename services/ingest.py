import httpx
import uuid
import json
from typing import Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from services.rag import index
from core.config import settings

class IngestionService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_pat:
            self.headers["Authorization"] = f"token {settings.github_pat}"

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

    async def process_webhook_payload(self, payload: Dict):
        """Processes a GitHub push webhook payload to selectively ingest added/modified md and json files."""
        if "commits" not in payload:
            return

        repo_full_name = payload["repository"]["full_name"]
        branch = payload["ref"].split("/")[-1]

        files_to_process = set()
        
        for commit in payload["commits"]:
            for file_path in commit.get("added", []) + commit.get("modified", []):
                if file_path.endswith(".md") or file_path.endswith(".json"):
                    files_to_process.add(file_path)

        async with httpx.AsyncClient(headers=self.headers) as client:
            for file_path in files_to_process:
                raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{file_path}"
                response = await client.get(raw_url)
                
                if response.status_code == 200:
                    content = response.text
                    await self._embed_and_upsert(file_path, content, repo_full_name)

    async def process_initial_ingestion(self, repo_full_name: str, branch: str = "main"):
        """Fetches all markdown and json files from the repository's git tree for initial ingestion."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            tree_url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}?recursive=1"
            response = await client.get(tree_url)
            
            if response.status_code != 200:
                print(f"Failed to fetch git tree for {repo_full_name}: {response.status_code}")
                return
                
            tree_data = response.json()
            files_to_process = [
                item["path"] for item in tree_data.get("tree", [])
                if item["type"] == "blob" and (item["path"].endswith(".md") or item["path"].endswith(".json"))
            ]
            
            for file_path in files_to_process:
                raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{file_path}"
                file_response = await client.get(raw_url)
                
                if file_response.status_code == 200:
                    content = file_response.text
                    await self._embed_and_upsert(file_path, content, repo_full_name)

    async def _embed_and_upsert(self, file_path: str, content: str, repo_name: str):
        if not index:
            return
            
        if file_path.endswith(".json"):
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
            chunk_id = str(uuid.uuid4())
            records.append({
                "id": chunk_id,
                "text": chunk,
                "source": file_path,
                "repo": repo_name
            })

        print(records)
            
        for i in range(0, len(records), 100):
            batch = records[i:i+100]
            index.upsert_records(namespace=settings.pinecone_namespace, records=batch)

ingestor = IngestionService()
