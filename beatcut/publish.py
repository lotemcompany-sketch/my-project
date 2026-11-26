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
        if not m.get("thumb"):
            continue
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


def export_options(options, out_dir):
    """options: [(proj_dir, option_id, label)] -> site with shared media/ and options/<id>.json + index.json"""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    index = []
    for proj_dir, oid, label in options:
        tmp = out / "_tmp" / oid
        export(proj_dir, tmp, title=label)
        for sub in ("media", "thumbs"):
            (out / sub).mkdir(exist_ok=True)
            for f in (tmp / sub).iterdir():
                shutil.copy(f, out / sub / f.name)
        pj = json.loads((tmp / "project.json").read_text(encoding="utf-8"))
        song_name = f"songs/{oid}.mp3"; (out / "songs").mkdir(exist_ok=True)
        shutil.copy(tmp / "song.mp3", out / song_name); pj["song"]["src"] = song_name
        if (tmp / "final.mp4").exists():
            (out / "finals").mkdir(exist_ok=True); shutil.copy(tmp / "final.mp4", out / f"finals/{oid}.mp4")
            pj["final"] = f"finals/{oid}.mp4"
        pj["id"] = oid
        # בדשבורד: רק רגעים עם תמונה, הכי חזקים + הרמות (שומר על העמוד קל)
        ms = sorted((m for m in pj["moments"] if m.get("thumb")), key=lambda m: -m["score"])
        pick, seen = [], set()
        for m in ms[:40] + [m for m in ms if m["lift"] > 0.6][:20]:
            if m["id"] not in seen:
                seen.add(m["id"]); pick.append(m)
        pj["moments"] = pick
        (out / "options").mkdir(exist_ok=True)
        (out / f"options/{oid}.json").write_text(json.dumps(pj, ensure_ascii=False), encoding="utf-8")
        index.append({"id": oid, "label": label})
    shutil.rmtree(out / "_tmp", ignore_errors=True)
    keep = set()
    for x in index:
        keep |= {m["thumb"] for m in json.loads((out / f"options/{x['id']}.json").read_text(encoding="utf-8"))["moments"]}
    for f in (out / "thumbs").iterdir():
        if f"thumbs/{f.name}" not in keep:
            f.unlink()
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return out
