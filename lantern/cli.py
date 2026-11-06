"""lantern pull | model | backtest | status | serve"""

import argparse
import os
import sys
from pathlib import Path

from lantern import backtest, config, pull
from lantern.store import Store


def _print_status(store: Store) -> None:
    rec = store.get_meta("last_pull_attempt") or {}
    print(f"{'source':<22} {'status':<7} {'series':>6}  detail")
    for item in rec.get("items", []):
        print(f"{item['source']:<22} {item['status']:<7} {item['series']:>6}  {item['detail'][:70]}")
    b = pull.badge(store)
    print(f"badge: {b['label']}")


def load_env(path: Path) -> None:
    """KEY=VALUE lines from a local .env (git-ignored) into the environment, never over a variable already set."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _filings(args, store: Store) -> int:
    import collections

    from lantern.filings import corpus, retrieve

    if args.fcmd == "build":
        chunks, manifest = corpus.build_corpus(config.FILINGS_DIR)
        try:
            embedder = retrieve.FastEmbedder()
        except Exception as exc:  # offline without the cached model: index with the hash fallback and say so
            print(f"embedding model unavailable ({type(exc).__name__}); indexing with the hash fallback")
            embedder = retrieve.HashEmbedder()
        meta = retrieve.build_index(chunks, config.FILINGS_INDEX, embedder, manifest)
        per_file = collections.Counter(c.file for c in chunks)
        for m in manifest:
            print(f"{m['ticker']:10} {m['pages']:5} pages {m['pages_without_text']:4} without text {per_file.get(m['file'], 0):6} chunks  {m['sha256'][:12] or 'missing'}")
        print(f"index: {meta['n_chunks']} chunks from {meta['n_files']} files, model {meta['embed_model']}, built {meta['built_at']}")
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    for env in (Path(__file__).resolve().parent.parent / ".env", Path(".env")):
        load_env(env)
    parser = argparse.ArgumentParser(prog="lantern", description="AI-bubble monitor data and model commands")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pull", help="pull every public series into the cache")
    sub.add_parser("model", help="compute the monitor payload from the cache")
    sub.add_parser("backtest", help="refit the calibration on the stored history")
    sub.add_parser("status", help="show the last pull and the data badge")
    serve = sub.add_parser("serve", help="serve the API and the front end")
    filings = sub.add_parser("filings", help="filings Q&A corpus and answers")
    fsub = filings.add_subparsers(dest="fcmd", required=True)
    fsub.add_parser("build", help="ingest the PDFs in the manifest, chunk and embed them")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    store = Store(config.DATA_DIR)

    if args.cmd == "filings":
        return _filings(args, store)
    if args.cmd == "pull":
        st = pull.run_pull(store)
        _print_status(store)
        return 0 if all(i["status"] == "ok" for i in st.items) else 1
    if args.cmd == "backtest":
        res = backtest.run_backtest(store)
        print(f"calibration {res.start} to {res.end}: a={res.a:.3f} b={res.b:.3f} n={res.n_months} hit rate {res.hit_rate:.2f} brier {res.brier:.3f}")
        print(f"2000 analogue: {res.analogue_2000}")
        return 0
    if args.cmd == "model":
        run = pull.run_model(store)
        t = run["tiles"]["probability"]
        gap = run["tiles"]["fv_gap"]["value"]
        gap_text = f"{gap:+.0%}" if gap is not None else "n/a"
        print(f"probability {t['value']:.0%} ({t['status']}), fair-value gap {gap_text}, run {run['model']['run_at']}")
        return 0
    if args.cmd == "status":
        _print_status(store)
        return 0
    if args.cmd == "serve":
        import uvicorn

        from lantern import api

        uvicorn.run(api.create_app(store), host=args.host, port=args.port)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
