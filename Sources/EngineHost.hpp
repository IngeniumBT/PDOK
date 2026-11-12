#pragma once

// Pakt de in het .apx ingebouwde motor (Python + onze Python-code) uit naar de map van de gebruiker, start hem als
// apart programma en wacht tot hij luistert. Alleen Win32 en de standaardbibliotheek: alle paden en teksten zijn
// UTF-8 in een std::string (de DevKit compileert met een afwijkende wchar_t, dus geen std::wstring).

#include <string>

namespace EngineHost
{

struct StartResult
{
    bool        ok = false;
    int         port = 0;
    std::string error;      // een melding voor de gebruiker (UTF-8), leeg als alles goed ging
    std::string folder;     // de map waarin de motor staat
    std::string logPath;    // het logboek van de motor
};

struct Status
{
    bool        running = false;
    int         port = 0;
    std::string folder;
    std::string logPath;
};

// Pakt de motor zo nodig uit (eenmalig per versie), start hem als hij nog niet draait, en wacht op zijn poort.
// `buildId` bepaalt de map (%LOCALAPPDATA%\PDOKImport\<buildId>), zodat een nieuwe versie een verse motor krijgt.
// `archicadPort` is de poort van Archicads JSON-interface; de motor gebruikt die om onze opdrachten aan te roepen.
StartResult EnsureRunning (const std::string& buildId, int archicadPort);

// Stopt de motor (ook als Archicad sluit of crasht, dan doet Windows dat zelf via een 'job').
void Stop ();

Status GetStatus ();

}
