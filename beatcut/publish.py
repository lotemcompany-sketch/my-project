"""מכין חבילת דשבורד לפרסום כעמוד ב-claude.ai: פרוקסי קלים לצפייה בטלפון, תמונות, ו-project.json יחסי."""
import json
import shutil
import subprocess
from pathlib import Path


def export(proj_dir, out_dir, title="", kind="dance"):
    proj = json.loads(Path(proj_dir, "project.json").read_text(encoding="utf-8"))
    out = Path(out_dir); (out / "media").mkdir(parents=True, exist_ok=True); (out / "thumbs").mkdir(exist_ok=True)
    names = {}
    for c in proj["clips"]:
        rel = f"media/{Path(c['path']).stem}.mp4"
        names[c["path"]] = rel
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", c["path"], "-an", "-vf",
                        "scale=360:640:force_original_aspect_ratio=increase,crop=360:640,fps=30",
                        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "450k", "-g", "15",
                        "-movflags", "+faststart", str(out / rel)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", proj["song"]["path"], "-vn",
                    "-c:a", "libmp3lame", "-b:a", "128k", str(out / "song.mp3")], check=True)
    for m in proj["moments"]:
        src = Path(proj_dir, m["thumb"])
        if src.exists():
            shutil.copy(src, out / m["thumb"])
    rel = lambda p: names.get(p, p)
    pub = {
        "id": Path(proj_dir).name, "title": title, "kind": kind,
        "hasFinal": Path(proj_dir, "final.mp4").exists(),
        "song": {k: proj["song"][k] for k in ("duration", "tempo", "beats", "downbeats", "sections", "waveform")} | {"src": "song.mp3"},
        "clips": [{"id": names[c["path"]], "name": c["name"], "duration": c["duration"]} for c in proj["clips"]],
        "moments": [dict(m, clip=rel(m["clip"])) for m in proj["moments"]],
        "timeline": [dict(s, clip=rel(s["clip"])) for s in proj["timeline"]],
    }
    (out / "project.json").write_text(json.dumps(pub, ensure_ascii=False), encoding="utf-8")
    if Path(proj_dir, "final.mp4").exists():
        # גרסת צפייה קלה לעמוד (המקור באיכות מלאה עולה לדרייב)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(Path(proj_dir, "final.mp4")),
                        "-vf", "scale=720:1280", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out / "final.mp4")], check=True)
    return out


def import_edits(proj_dir, timeline):
    """מחיל עריכות שנשמרו בדשבורד (מזהי media/...) על הפרויקט המקומי."""
    proj = json.loads(Path(proj_dir, "project.json").read_text(encoding="utf-8"))
    back = {f"media/{Path(c['path']).stem}.mp4": c["path"] for c in proj["clips"]}
    proj["timeline"] = [dict(s, clip=back.get(s["clip"], s["clip"])) for s in timeline]
    Path(proj_dir, "project.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    return proj
