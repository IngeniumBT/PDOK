# Bestanden van derden

Dit project gebruikt bestanden uit twee open-sourceprojecten, beide onder de MIT-licentie.

## Tapir (ENZYME-APD)

De map `Tools/` (`CMakeCommon.cmake`, `CompileResources.py`, `download_and_unzip.py` en
`WriteAddOnBuildCommit.cmake`) en `Sources/APIEnvir.h` en `Sources/RFIX.win/AddOnMain.rc2` komen uit het
Tapir-project, <https://github.com/ENZYME-APD/tapir-archicad-automation> (MIT-licentie, zie het bestand
`LICENSE` in die repository). Gewijzigd zijn alleen: de waarschuwingen laten de bouw niet meer mislukken
(`/WX` is weggehaald) en de versie-informatie van het `.apx` is die van dit project.

## Graphisoft Archicad Add-On CMake Template

Het pictogram `Sources/RFIX/Images/AddOnIcon_18x18.svg` komt uit
<https://github.com/GRAPHISOFT/archicad-addon-cmake>, en de opzet van de add-on volgt dat sjabloon.

```
MIT License

Copyright (c) 2020 GRAPHISOFT

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

De Archicad API DevKit zelf wordt bij het bouwen gedownload van Graphisoft en zit niet in dit project.
