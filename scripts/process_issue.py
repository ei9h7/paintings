#!/usr/bin/env python3
"""
Parse a "Add painting photos" issue form and hand it off to add_painting.py.

Used by .github/workflows/add-painting.yml -- not meant to be run by hand,
though you can point it at a saved issue body for testing:

  python3 scripts/process_issue.py path/to/issue_body.md

Reads the issue body (GitHub issue-form markdown: "### Label" headers
followed by the answer), downloads any attached photos, and calls
add_painting.py with the right mode (new painting / new collection /
append to an existing one).
"""
import os
import re
import subprocess
import sys
import tempfile
import mimetypes

try:
    import requests
except ImportError:
    sys.exit("requests is required: pip install requests")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADD_PAINTING = os.path.join(REPO_ROOT, "scripts", "add_painting.py")

ATTACHMENT_RE = re.compile(
    r'(https://(?:github\.com/user-attachments/assets|user-images\.githubusercontent\.com)/\S+?)'
    r'(?=["\'\)\s]|$)'
)
FIELD_RE = re.compile(r"^### (.+?)\s*$\n+(.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL)


def parse_fields(body):
    fields = {}
    for m in FIELD_RE.finditer(body):
        label = m.group(1).strip()
        value = m.group(2).strip()
        if value == "_No response_":
            value = ""
        fields[label] = value
    return fields


def find_attachment_urls(body):
    seen = []
    for m in ATTACHMENT_RE.finditer(body):
        url = m.group(1)
        if url not in seen:
            seen.append(url)
    return seen


def download(url, dest_dir, index, token):
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    ctype = resp.headers.get("Content-Type", "")
    ext = mimetypes.guess_extension(ctype.split(";")[0].strip()) or ".jpg"
    if ext == ".jpe":
        ext = ".jpg"
    path = os.path.join(dest_dir, f"photo-{index}{ext}")
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


def set_output(name, value):
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"{name}<<__EOF__\n{value}\n__EOF__\n")
    else:
        print(f"[output] {name}={value}")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: process_issue.py <issue-body-file>")
    with open(sys.argv[1], encoding="utf-8") as f:
        body = f.read()

    fields = parse_fields(body)
    painting = fields.get("Which painting is this?", "")
    new_title = fields.get("New painting title", "")
    kind = fields.get("If new — is this a collection?", "")
    artist = fields.get("Artist", "").strip() or "ei9h7"
    notes = fields.get("Notes / commentary (optional)", "")

    urls = find_attachment_urls(fields.get("Photos", "") or body)
    if not urls:
        sys.exit("No photo attachments found in the issue -- did the upload finish before submitting?")

    token = os.environ.get("GITHUB_TOKEN", "")
    tmp_dir = tempfile.mkdtemp(prefix="issue-photos-")
    photo_paths = []
    print(f"Downloading {len(urls)} photo(s)...")
    for i, url in enumerate(urls, 1):
        path = download(url, tmp_dir, i, token)
        print(f"  [{i}] {url} -> {path} ({os.path.getsize(path)/1024:.0f}KB)")
        photo_paths.append(path)

    is_new = painting.strip().startswith("🆕") or painting.strip().lower().startswith("new painting")

    if is_new:
        if not new_title.strip():
            sys.exit("'New painting' was selected but no title was given in 'New painting title'")
        title = new_title.strip()
        cmd = [sys.executable, ADD_PAINTING, title, *photo_paths, "--artist", artist]
        if "collection" in kind.lower():
            cmd.append("--collection")
        if notes.strip():
            cmd += ["--notes", notes.strip()]
    else:
        title = re.sub(r"\s*\(collection\)\s*$", "", painting.strip())
        cmd = [sys.executable, ADD_PAINTING, "--append-to", title, *photo_paths, "--artist", artist]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)

    set_output("title", title)
    set_output("is_new", "true" if is_new else "false")


if __name__ == "__main__":
    main()
