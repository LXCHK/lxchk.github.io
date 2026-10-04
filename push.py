#!/usr/bin/env python3
"""Push every file under ~/workspace/hkid0-site (except public/) to the
hkid0/hkid0.github.io repo via the GitHub Contents API, using the stored
custom.github credential. Idempotent-ish: skips files that already exist with
identical content (avoids needing shas for updates in this simple flow by
fetching sha when a file exists)."""
import base64
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

CRED = "custom.github"
HOSTS = ["api.github.com"]
REPO = "hkid0/hkid0.github.io"
ROOT = os.path.expanduser("~/workspace/hkid0-site")
SKIP_DIRS = {"public", ".git"}
SKIP_FILES = {".hugo_build.lock"}


def api(method, path, payload=None):
    url = "https://api.github.com" + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "muse-agent",
                 "Content-Type": "application/json"},
    )
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body


def get_sha(repo_path):
    status, body = api("GET", f"/repos/{REPO}/contents/{urllib.parse.quote(repo_path)}")
    if status == 200 and isinstance(body, dict):
        return body.get("sha")
    return None


def push_file(local, repo_path):
    with open(local, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    # check existing
    status, body = api("GET", f"/repos/{REPO}/contents/{urllib.parse.quote(repo_path)}")
    if status == 200 and isinstance(body, dict) and body.get("content"):
        existing = body["content"].replace("\n", "")
        if existing == content.replace("\n", ""):
            print(f"skip (unchanged): {repo_path}")
            return
        sha = body.get("sha")
    else:
        sha = None
    payload = {"message": f"site: {repo_path}", "content": content}
    if sha:
        payload["sha"] = sha
    status, body = api("PUT", f"/repos/{REPO}/contents/{urllib.parse.quote(repo_path)}", payload)
    if status in (200, 201):
        print(f"ok: {repo_path}")
    else:
        print(f"FAIL {status}: {repo_path} -> {json.dumps(body)[:300]}")


def main():
    count = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn in SKIP_FILES:
                continue
            local = os.path.join(dirpath, fn)
            repo_path = os.path.relpath(local, ROOT).replace(os.sep, "/")
            push_file(local, repo_path)
            count += 1
    print(f"done: {count} files")


if __name__ == "__main__":
    main()
