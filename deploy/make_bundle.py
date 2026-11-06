"""Builds the upload bundle for the server: the Sakala WhatsApp POC (app/) + Mitra (mitra/) + deploy/, nothing else.
Never included: any .env file, the KPCL / RDPR folders, launchers, tests, logs, caches, the 'vpn key' file.
Databases come from a consistent snapshot folder (sqlite backup), so a running laptop server cannot tear them.
Usage: python deploy/make_bundle.py <snapshot_dir> <out.tar.gz>"""
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP, OUT = Path(sys.argv[1]), Path(sys.argv[2])
STAGE = OUT.parent / "bundle_stage"
SKIP_DIRS = {"__pycache__", "tests", ".pytest_cache", "backups"}
SKIP_FILES = {".env", "dbg.html", "shot.html", "vercel.json", "run.bat", "start.sh"}
SKIP_SUFFIX = (".log", ".pyc", "-wal", "-shm")

if STAGE.exists():
    shutil.rmtree(STAGE)


def copy_tree(src: Path, dst: Path):
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts) or p.name in SKIP_FILES or p.name.endswith(SKIP_SUFFIX):
            continue
        if p.is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel)


for app in ("app", "mitra"):
    for sub in ("server", "web"):
        copy_tree(ROOT / app / sub, STAGE / app / sub)
shutil.copy2(ROOT / "mitra" / "knowledge.yaml", STAGE / "mitra" / "knowledge.yaml")
(STAGE / "app" / "data").mkdir(parents=True)
(STAGE / "mitra" / "data").mkdir(parents=True)
for f in ("local_models.joblib", "llm_eval.json", "sakala_pristine.db"):
    shutil.copy2(ROOT / "app" / "data" / f, STAGE / "app" / "data" / f)
shutil.copy2(SNAP / "sakala.db", STAGE / "app" / "data" / "sakala.db")
shutil.copy2(SNAP / "mitra.db", STAGE / "mitra" / "data" / "mitra.db")
copy_tree(ROOT / "deploy", STAGE / "deploy")

bad = [p for p in STAGE.rglob("*") if p.name == ".env" or "vpn" in p.name.lower() or "KPCL" in str(p) or "RDPR POC" in str(p)]
assert not bad, f"refusing to bundle: {bad}"
with tarfile.open(OUT, "w:gz") as t:
    for p in sorted(STAGE.iterdir()):
        t.add(p, arcname=p.name)
size = sum(p.stat().st_size for p in STAGE.rglob("*") if p.is_file())
print(f"bundle {OUT} · {OUT.stat().st_size / 1e6:.1f} MB compressed · {size / 1e6:.1f} MB unpacked · {sum(1 for _ in STAGE.rglob('*') if _.is_file())} files")
