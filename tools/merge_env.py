"""Merge the KPCL gateway env (read-only source) with the Gemini env in the project root into app/.env.
Backs up the current app/.env first. Prints key names only, never values."""
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KPCL_ENV = Path(r"D:\KPCL POC\KPCL POC\webapp\.env")
GEM_ENV = ROOT / ".env"
OUT = ROOT / "app" / ".env"

kp = KPCL_ENV.read_text(encoding="utf-8")
gem_lines = [l for l in GEM_ENV.read_text(encoding="utf-8").splitlines() if re.match(r"^[A-Z_][A-Z0-9_]*=", l)]
kp_keys = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", kp, flags=re.M))

backup = ROOT / "tools" / "backups" / f"app.env.before_merge_{datetime.now():%Y%m%d_%H%M}"
backup.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    shutil.copy2(OUT, backup)

added = [l for l in gem_lines if l.split("=", 1)[0] not in kp_keys]
merged = kp.rstrip("\n") + "\n\n# ── Merged 15 Oct 2026 from the project-root .env (Gemini) ─────────────────\n" + "\n".join(added) + "\n"
OUT.write_text(merged, encoding="utf-8")
print("backup:", backup.name)
print("kpcl keys:", len(kp_keys), "| added from root .env:", [l.split("=", 1)[0] for l in added])
