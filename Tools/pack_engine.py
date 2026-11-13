"""Zet de motor klaar om in het .apx te worden ingebouwd.

Maakt twee bestanden in de map Sources, die AddOnMain.rc2 als bronnen (RCDATA) in het .apx opneemt:
  python-embed.zip   de officiele 'embeddable' Python van python.org (wordt gedownload)
  engine-app.zip     onze eigen Python-code uit de map Engine
Wordt door CMake aangeroepen bij het instellen van het project, en kan ook los worden gedraaid.
Alleen de standaardbibliotheek.
"""
import os
import subprocess
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


def vendor_requests(lib: Path) -> None:
    """Zet requests en wat daarbij hoort (urllib3, idna, certifi, charset_normalizer) in Engine/lib, voor de Python die in
    het .apx zit (3.12, Windows 64 bit). pip downloadt daarvoor de juiste pakketten, ook op een andere computer."""
    if (lib / "requests").is_dir():
        return
    if os.environ.get("PDOK_PACK_ZONDER_PIP"):
        print("PDOK_PACK_ZONDER_PIP is gezet: requests wordt niet meegeleverd (alleen voor tests).")
        return
    print("requests meeleveren via pip...", flush=True)
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-compile",
        "--target", str(lib), "--platform", "win_amd64", "--python-version", PY_VERSION.rsplit(".", 1)[0],
        "--implementation", "cp", "--only-binary=:all:", "requests"])


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
    vendor_requests(ENGINE / "lib")
    versie = "onbekend"
    try:                                           # het versienummer staat in AddOnVersion.hpp; de motor toont het in het palet en in het logboek
        import re
        m = re.search(r'ADDON_VERSION\s+"([^"]+)"', (SOURCES / "AddOnVersion.hpp").read_text(encoding="utf-8"))
        versie = m.group(1) if m else versie
    except OSError:
        pass
    app = SOURCES / "engine-app.zip"
    with zipfile.ZipFile(app, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ENGINE.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                z.write(p, p.relative_to(ENGINE).as_posix())
        z.writestr("versie.txt", versie)
    print(f"versie:           {versie}")
    print(f"python-embed.zip: {embed.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"engine-app.zip:   {app.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
