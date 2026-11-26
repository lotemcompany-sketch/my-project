import argparse
import json
from pathlib import Path

from . import project, render, server, template


def main():
    ap = argparse.ArgumentParser(prog="beatcut", description="עריכת ריקוד אוטומטית לפי ביט")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auto", help="ניתוח + בניית טיימליין")
    a.add_argument("--song", required=True); a.add_argument("--clips", required=True)
    a.add_argument("--out", required=True); a.add_argument("--template", default="dance", help="dance / sport / נתיב לקובץ")
    a.add_argument("--length", type=float, help="אורך בשניות 15–45")
    a.add_argument("--bpm", type=float, help="קצב ידוע של השיר (מדלג על זיהוי)")
    a.add_argument("--seed", type=int, default=0, help="מספר וריאציה: כל מספר נותן עריכה אחרת")
    a.add_argument("--render", action="store_true")
    d = sub.add_parser("dashboard", help="פתיחת דשבורד עריכה"); d.add_argument("project"); d.add_argument("--port", type=int, default=8765)
    r = sub.add_parser("render", help="רנדר סופי"); r.add_argument("project")
    L = sub.add_parser("learn", help="ללמוד טמפלייט מסרטונים שערכת")
    L.add_argument("videos", nargs="+"); L.add_argument("--out", default="templates/my_style.json")
    x = ap.parse_args()
    if x.cmd == "auto":
        proj = project.create(x.song, x.clips, x.out, x.template, length=x.length, bpm=x.bpm, seed=x.seed)
        if x.render:
            print(render.render(proj, Path(x.out) / "final.mp4"))
    elif x.cmd == "dashboard":
        server.serve(x.project, x.port)
    elif x.cmd == "render":
        print(render.render(project.load(x.project), Path(x.project) / "final.mp4"))
    elif x.cmd == "learn":
        learned = []
        for v in x.videos:
            r_ = template.learn_from_reference(v); learned.append(r_)
            print(json.dumps(r_, ensure_ascii=False, indent=1))
        t = template.merge_learned(learned)
        Path(x.out).parent.mkdir(parents=True, exist_ok=True)
        Path(x.out).write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
        print("נשמר טמפלייט:", x.out)


if __name__ == "__main__":
    main()
