"""Zet de motor klaar om in het .apx te worden ingebouwd.

Maakt twee bestanden in de map Sources, die AddOnMain.rc2 als bronnen (RCDATA) in het .apx opneemt:
  python-embed.zip   de officiele 'embeddable' Python van python.org (wordt gedownload)
  engine-app.zip     onze eigen Python-code uit de map Engine
Wordt door CMake aangeroepen bij het instellen van het project, en kan ook los worden gedraaid.
Alleen de standaardbibliotheek.
"""
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

PY_VERSION = "3.12.8"
URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "Sources"
ENGINE = ROOT / "Engine"


def download(url: str, dest: Path, attempts: int = 5) -> None:
    for n in range(1, attempts + 1):
        try:
            print(f"Downloaden: {url}", flush=True)
            with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
                f.write(r.read())
            if not zipfile.is_zipfile(dest):
                raise OSError("het gedownloade bestand is geen zip")
            return
        except Exception as fout:  # noqa: BLE001
            dest.unlink(missing_ok=True)
            if n == attempts:
                raise
            wacht = 5 * n
            print(f"Mislukt ({fout}); opnieuw over {wacht} s ({n} van {attempts})", flush=True)
            time.sleep(wacht)


def main() -> int:
    embed = SOURCES / "python-embed.zip"
    if not embed.exists():
        download(URL, embed)
    with zipfile.ZipFile(embed) as z:
        namen = {n.lower() for n in z.namelist()}
    if "python.exe" not in namen:
        print("FOUT: python.exe zit niet in de gedownloade Python.", file=sys.stderr)
        return 1

    if not ENGINE.is_dir() or not (ENGINE / "engine.py").is_file():
        print(f"FOUT: {ENGINE / 'engine.py'} ontbreekt.", file=sys.stderr)
        return 1
    app = SOURCES / "engine-app.zip"
    with zipfile.ZipFile(app, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ENGINE.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                z.write(p, p.relative_to(ENGINE).as_posix())
    print(f"python-embed.zip: {embed.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"engine-app.zip:   {app.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
