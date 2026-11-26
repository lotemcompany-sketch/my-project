"""העלאת קבצים גדולים לדרייב דרך המעלה האישי (Apps Script) — כל גודל."""
import json
import os
import subprocess
import sys

FOLDERS = {"מוכנים": "15qWegtYKxNShKb8x8oR6rzahky-WYzZk", "ריקוד": "1bCkT_yiJ2bEae52hvMsi0TZ5QQNt7og0",
           "ספורט": "1XrIhp7DRw9bNqqzH3p8rGjO2lyl-v5uy", "BeatCut": "1d_zhnaaYaWMQPbKqQCXqpDL3BmN1gbhZ"}


def upload(script_url, key, path, name=None, folder="מוכנים", mime="video/mp4"):
    size = os.path.getsize(path)
    body = json.dumps({"key": key, "name": name or os.path.basename(path), "size": size,
                       "mimeType": mime, "folder": FOLDERS.get(folder, folder)})
    r = subprocess.run(["curl", "-sSL", "-X", "POST", "-H", "Content-Type: application/json",
                        "--data-binary", body, script_url], capture_output=True, text=True, check=True)
    resp = json.loads(r.stdout)
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error"))
    r = subprocess.run(["curl", "-sS", "-X", "PUT", "-H", f"Content-Type: {mime}", "--data-binary", f"@{path}",
                        resp["uploadUrl"]], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


if __name__ == "__main__":
    url, key = os.environ["BEATCUT_UPLOADER_URL"], os.environ["BEATCUT_UPLOADER_KEY"]
    for p in sys.argv[1:]:
        print(upload(url, key, p))
