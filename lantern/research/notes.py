"""Research notes: assembled from a stored model run, prose checked so every number traces back to the run JSON."""

import json
import re

AUTHOR = "Lantern model, reviewed by Abhay"
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _floats(o):
    if isinstance(o, bool):
        return
    if isinstance(o, (int, float)):
        yield float(o)
    elif isinstance(o, dict):
        for v in o.values():
            yield from _floats(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _floats(v)


def run_numbers(run: dict) -> set[str]:
    """Every number token a faithful sentence about this run may use: the raw JSON tokens plus the
    rounded and percent renderings of every float (|v| <= 1 is also admitted as a percentage)."""
    toks = set(_NUM.findall(json.dumps(run)))
    for v in _floats(run):
        a = abs(v)
        for x in ((a, a * 100) if a <= 1 else (a,)):
            toks |= {f"{x:.0f}", f"{x:.1f}", f"{x:.2f}", f"{x:g}"}
    return toks


def verify_numbers(prose: str, run: dict) -> list[str]:
    """The number tokens in the prose that do not appear in the run; empty means the prose passes."""
    allowed = run_numbers(run)
    return [t for t in _NUM.findall(prose) if t not in allowed]


def scenario_sentence(run: dict) -> str:
    s = run["chart"]["scenarios"]
    return (
        f"The model puts {s['base']['prob']:.0%} on the base path, "
        f"{s['derating']['prob']:.0%} on a derating ({s['derating']['end_return']:+.0%} at the horizon) "
        f"and {s['meltup']['prob']:.0%} on a melt-up ({s['meltup']['end_return']:+.0%})."
    )


def note_payload(note: dict, run: dict) -> dict:
    """Everything the note view renders, assembled from the stored note and the run it came from."""
    return {
        "id": note.get("id"),
        "title": note["title"],
        "summary": note.get("summary", ""),
        "author": AUTHOR,
        "as_of": run["as_of"],
        "created_at": note["created_at"],
        "status": note["status"],
        "source": note.get("source", "api"),
        "run_id": note["run_id"],
        "lead": note["lead"],
        "commentary": note.get("commentary", []),
        "scenario_sentence": scenario_sentence(run),
        "drivers": run["drivers"],
        "triggers": run["triggers"],
        "tiles": run["tiles"],
        "chart": run["chart"],
        "sources": note.get("sources", []),
    }
