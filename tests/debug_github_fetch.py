import requests
import base64
import json
import os
from typing import List, Dict
from dotenv import load_dotenv

def main():
    print("\n[STEP] Loading environment variables...")
    load_dotenv()

    # ========== CONFIG ==========
    EXCLUDED_DIRS = {"venv", "__pycache__", "node_modules", "dist", "build", ".git"}
    INCLUDE_EXTENSIONS = {".py", ".js", ".ts", ".ipynb", ".java"}
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50000))
    OUTPUT_DIR = "data/github_repos"
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    print(f"[DEBUG] Headers set: {'✅ with token' if GITHUB_TOKEN else '❌ no token found'}")

    # ---------- CORE FUNCTIONS ----------

    def fetch_github_repos(username: str) -> List[Dict]:
        print(f"\n[STEP] Fetching repos for user '{username}'...")
        url = f"https://api.github.com/users/{username}/repos"
        try:
            resp = requests.get(url, headers=HEADERS)
        except Exception as e:
            print(f"[ERROR] Network error fetching repos: {e}")
            return []

        print(f"[DEBUG] GitHub response code: {resp.status_code}")
        if resp.status_code != 200:
            print(f"[ERROR] Failed to fetch repos: {resp.status_code}")
            return []

        data = resp.json()
        print(f"[INFO] Found {len(data)} repos for '{username}'.")
        return data

    def fetch_repo_contents(owner: str, repo: str, path: str = "", all_files: List[str] = None) -> List[Dict]:
        if all_files is None:
            all_files = []
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        print(f"[DEBUG] Fetching repo contents: {url}")

        try:
            resp = requests.get(url, headers=HEADERS)
        except Exception as e:
            print(f"[ERROR] Network error for {url}: {e}")
            return []

        if resp.status_code != 200:
            print(f"[WARN] Cannot fetch '{path}' in '{repo}' (HTTP {resp.status_code})")
            return []

        try:
            data = resp.json()
        except Exception as e:
            print(f"[ERROR] Invalid JSON in repo contents: {e}")
            return []

        filtered_files = []
        for item in data:
            if item["type"] == "dir":
                fetch_repo_contents(owner, repo, item["path"], all_files)
            elif item["type"] == "file":
                all_files.append(item["path"])
                ext = os.path.splitext(item["name"])[1].lower()
                if ext in INCLUDE_EXTENSIONS and item["size"] <= MAX_FILE_SIZE:
                    if not any(ex in item["path"].lower() for ex in EXCLUDED_DIRS):
                        filtered_files.append(item)
        print(f"[INFO] Found {len(filtered_files)} filtered files in '{repo}'.")
        return filtered_files

    def fetch_file_text(item: Dict) -> str:
        """Fetch file content using download_url or Base64 API fallback."""
        url = item.get("download_url")
        print(f"[DEBUG] Fetching file text for: {url or item.get('url')}")
        if url:
            resp = requests.get(url, headers=HEADERS)
            if resp.status_code == 200:
                return resp.text

        api_url = item.get("url")
        if api_url:
            resp = requests.get(api_url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("encoding") == "base64":
                    return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        print(f"[WARN] Could not fetch file content for {item.get('path', 'unknown')}")
        return ""

    def analyze_repository(owner: str, repo: str) -> Dict:
        print(f"\n[STEP] 🔍 Analyzing repository: {repo}")

        repo_data = {
            "repository": repo,
            "readme": "",
            "requirements": "",
            "files_name": []
        }

        # --- Fetch README ---
        for file_name in ["README.md", "readme.md"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file_name}"
            print(f"[DEBUG] Trying README URL: {url}")
            resp = requests.get(url, headers=HEADERS)
            if resp.status_code == 200:
                repo_data["readme"] = resp.text
                print("[INFO] README found.")
                break
        if not repo_data["readme"]:
            print("[WARN] README not found.")

        # --- Fetch requirements.txt or setup.py ---
        for req_file in ["requirements.txt", "setup.py"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{req_file}"
            print(f"[DEBUG] Trying requirements URL: {url}")
            resp = requests.get(url, headers=HEADERS)
            if resp.status_code == 200:
                repo_data["requirements"] = resp.text
                print("[INFO] Requirements file found.")
                break
        if not repo_data["requirements"]:
            print("[WARN] Requirements not found.")

        all_files_collector = []
        filtered_files = fetch_repo_contents(owner, repo, "", all_files_collector)
        repo_data["files_name"] = all_files_collector
        print(f"[INFO] Total files collected: {len(all_files_collector)}")

        return repo_data

    def fetch_and_analyze_github(username: str):
        print(f"\n[STEP] Starting full fetch and analyze for '{username}'...")
        repos = fetch_github_repos(username)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        results = []
        for r in repos:
            repo_name = r.get("name")
            print(f"\n[STEP] Processing repo: {repo_name}")
            save_path = os.path.join(OUTPUT_DIR, f"{repo_name}.json")

            if os.path.exists(save_path):
                print(f"[SKIP] '{repo_name}' already analyzed. Loading existing file.")
                with open(save_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                results.append(existing_data)
                continue

            try:
                analysis = analyze_repository(username, repo_name)
                results.append(analysis)
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(analysis, f, ensure_ascii=False, indent=2)
                print(f"[SAVED] Data saved to: {save_path}")
            except Exception as e:
                print(f"[ERROR] Failed to analyze '{repo_name}': {e}")

        print(f"\n[INFO] Completed analysis for {len(results)} repos.")
        return results

    # ---------- ENTRY POINT ----------
    username = "harsh16kumar"
    all_results = fetch_and_analyze_github(username)
    print(f"\n✅ DONE: Analyzed {len(all_results)} repositories for '{username}'.")

if __name__ == "__main__":
    main()
