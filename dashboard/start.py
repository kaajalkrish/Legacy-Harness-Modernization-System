"""
One-command launcher for the COBOL RE Dashboard.

Usage (from repo root, with .venv active):
    python dashboard/start.py
    python dashboard/start.py --output outputs/carddemo
    python dashboard/start.py --output outputs/sample --port 8787
"""
import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Launch the COBOL RE Dashboard")
    ap.add_argument("--output", default="outputs/carddemo",
                    help="Path to the harness output folder (default: outputs/carddemo)")
    ap.add_argument("--port", type=int, default=8787,
                    help="Port to serve on (default: 8787)")
    ap.add_argument("--no-browser", action="store_true",
                    help="Don't open the browser automatically")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir   = (repo_root / args.output).resolve()
    frontend  = Path(__file__).resolve().parent / "frontend"
    dist      = frontend / "dist"

    # ── Validate output dir ─────────────────────────────────────────────────
    if not out_dir.exists():
        print(f"[ERROR] Output directory not found: {out_dir}")
        print(f"  Run the pipeline first: python run_pipeline.py --output {args.output}")
        sys.exit(1)

    # ── Build frontend if dist is missing or stale ──────────────────────────
    if not dist.exists():
        print("[INFO] Building React frontend (first run — this takes ~30s)…")
        if not (frontend / "node_modules").exists():
            print("[INFO] Installing npm dependencies…")
            subprocess.run(["npm", "install"], cwd=str(frontend), check=True, shell=True)
        subprocess.run(["npm", "run", "build"], cwd=str(frontend), check=True, shell=True)
        print("[OK] Frontend built.")
    else:
        print(f"[OK] Using existing frontend build at {dist}")

    # ── Launch uvicorn ───────────────────────────────────────────────────────
    url = f"http://localhost:{args.port}?outputDir={out_dir}"
    print(f"\n{'='*60}")
    print(f"  Dashboard: {url}")
    print(f"  Output:    {out_dir}")
    print(f"  Stop:      Ctrl+C")
    print(f"{'='*60}\n")

    if not args.no_browser:
        import threading, time
        def _open():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    subprocess.run(
        [sys.executable, "-m", "uvicorn", "dashboard.server:app",
         "--port", str(args.port), "--reload"],
        cwd=str(repo_root),
    )


if __name__ == "__main__":
    main()
