#include "EngineHost.hpp"

#include <windows.h>

#include <cstdlib>

#include <string>
#include <vector>

// Resource-ID's van de ingebouwde bestanden (zie RFIX.win/AddOnMain.rc2).
#define PDOK_RES_PYTHON_EMBED 2000
#define PDOK_RES_ENGINE_APP   2001

namespace EngineHost
{

namespace
{

// ------------------------------------------------------------------ toestand
HANDLE      g_process = nullptr;
HANDLE      g_job = nullptr;
int         g_port = 0;
std::string g_folder;
std::string g_logPath;

constexpr DWORD kStartTimeoutMs = 25000;
constexpr DWORD kExtractTimeoutMs = 180000;

// ------------------------------------------------------------------ tekst en paden
std::vector<wchar_t> ToWide (const std::string& utf8)
{
    const int n = MultiByteToWideChar (CP_UTF8, 0, utf8.c_str (), -1, nullptr, 0);
    std::vector<wchar_t> wide (n > 0 ? static_cast<size_t> (n) : 1, 0);
    if (n > 0) {
        MultiByteToWideChar (CP_UTF8, 0, utf8.c_str (), -1, wide.data (), n);
    }
    return wide;
}

std::string ToUtf8 (const wchar_t* wide)
{
    const int n = WideCharToMultiByte (CP_UTF8, 0, wide, -1, nullptr, 0, nullptr, nullptr);
    if (n <= 1) {
        return std::string ();
    }
    std::string utf8 (static_cast<size_t> (n), '\0');
    WideCharToMultiByte (CP_UTF8, 0, wide, -1, &utf8[0], n, nullptr, nullptr);
    utf8.resize (static_cast<size_t> (n) - 1);
    return utf8;
}

std::string Join (const std::string& a, const std::string& b)
{
    return a + "\\" + b;
}

std::string EnvironmentVariable (const wchar_t* name)
{
    const DWORD n = GetEnvironmentVariableW (name, nullptr, 0);
    if (n == 0) {
        return std::string ();
    }
    std::vector<wchar_t> buffer (static_cast<size_t> (n) + 1, 0);
    GetEnvironmentVariableW (name, buffer.data (), n + 1);
    return ToUtf8 (buffer.data ());
}

std::string SystemDirectory ()
{
    wchar_t buffer[MAX_PATH + 1] = {};
    GetSystemDirectoryW (buffer, MAX_PATH);
    return ToUtf8 (buffer);
}

bool PathExists (const std::string& path)
{
    return GetFileAttributesW (ToWide (path).data ()) != INVALID_FILE_ATTRIBUTES;
}

bool MakeDirectories (const std::string& path)
{
    // maakt elke map in het pad aan (bestaande zijn geen fout)
    for (size_t i = 3; i <= path.size (); ++i) {
        if (i == path.size () || path[i] == '\\') {
            const std::string part = path.substr (0, i);
            if (!PathExists (part) && !CreateDirectoryW (ToWide (part).data (), nullptr)) {
                if (GetLastError () != ERROR_ALREADY_EXISTS) {
                    return false;
                }
            }
        }
    }
    return true;
}

bool WriteBytes (const std::string& path, const void* data, DWORD size)
{
    const HANDLE file = CreateFileW (ToWide (path).data (), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return false;
    }
    const char* bytes = static_cast<const char*> (data);
    DWORD done = 0;
    bool ok = true;
    while (done < size && ok) {
        DWORD written = 0;
        ok = WriteFile (file, bytes + done, size - done, &written, nullptr) != 0 && written > 0;
        done += written;
    }
    CloseHandle (file);
    return ok;
}

std::string ReadText (const std::string& path, DWORD maxBytes)
{
    const HANDLE file = CreateFileW (ToWide (path).data (), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return std::string ();
    }
    const DWORD size = GetFileSize (file, nullptr);
    if (size != INVALID_FILE_SIZE && size > maxBytes) {
        SetFilePointer (file, -static_cast<LONG> (maxBytes), nullptr, FILE_END);   // alleen het einde
    }
    std::vector<char> buffer (static_cast<size_t> (maxBytes) + 1, 0);
    DWORD read = 0;
    ReadFile (file, buffer.data (), maxBytes, &read, nullptr);
    CloseHandle (file);
    return std::string (buffer.data (), read);
}

std::string TrimmedTail (const std::string& text)
{
    size_t end = text.size ();
    while (end > 0 && (text[end - 1] == '\r' || text[end - 1] == '\n' || text[end - 1] == ' ')) {
        --end;
    }
    return text.substr (0, end);
}

// ------------------------------------------------------------------ ingebouwde bestanden
bool GetEmbeddedResource (int id, const void*& data, DWORD& size)
{
    HMODULE module = nullptr;
    if (!GetModuleHandleExW (GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                             reinterpret_cast<LPCWSTR> (&GetEmbeddedResource), &module)) {
        return false;
    }
    const HRSRC resource = FindResourceW (module, MAKEINTRESOURCEW (id), RT_RCDATA);
    if (resource == nullptr) {
        return false;
    }
    const HGLOBAL loaded = LoadResource (module, resource);
    if (loaded == nullptr) {
        return false;
    }
    data = LockResource (loaded);
    size = SizeofResource (module, resource);
    return data != nullptr && size > 0;
}

// ------------------------------------------------------------------ processen
std::string QuoteArgument (const std::string& argument)
{
    return "\"" + argument + "\"";
}

// Start een programma verborgen en wacht tot het klaar is. Geeft false met een foutcode als het niet startte.
bool RunAndWait (const std::string& commandLine, const std::string& workingDirectory, DWORD timeoutMs, DWORD& exitCode, DWORD& lastError)
{
    std::vector<wchar_t> command = ToWide (commandLine);       // CreateProcessW mag in de opdrachtregel schrijven
    const std::vector<wchar_t> directory = ToWide (workingDirectory);

    STARTUPINFOW startupInfo = {};
    startupInfo.cb = static_cast<DWORD> (sizeof (startupInfo));
    startupInfo.dwFlags = STARTF_USESHOWWINDOW;
    startupInfo.wShowWindow = SW_HIDE;
    PROCESS_INFORMATION processInfo = {};
    const BOOL started = CreateProcessW (nullptr, command.data (), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr,
                                         workingDirectory.empty () ? nullptr : directory.data (), &startupInfo, &processInfo);
    if (!started) {
        lastError = GetLastError ();
        return false;
    }
    CloseHandle (processInfo.hThread);
    const DWORD waited = WaitForSingleObject (processInfo.hProcess, timeoutMs);
    if (waited == WAIT_TIMEOUT) {
        TerminateProcess (processInfo.hProcess, 1);
        exitCode = static_cast<DWORD> (-1);
        lastError = WAIT_TIMEOUT;
    } else {
        GetExitCodeProcess (processInfo.hProcess, &exitCode);
        lastError = 0;
    }
    CloseHandle (processInfo.hProcess);
    return waited != WAIT_TIMEOUT;
}

// Pakt een zip uit met tar.exe (zit in Windows 10 en nieuwer), en anders met PowerShell.
bool ExtractZip (const std::string& zipPath, const std::string& destination, std::string& error)
{
    if (!MakeDirectories (destination)) {
        error = "De map " + destination + " kon niet worden aangemaakt.";
        return false;
    }

    DWORD exitCode = 1;
    DWORD lastError = 0;
    const std::string system = SystemDirectory ();

    const std::string tar = Join (system, "tar.exe");
    if (PathExists (tar)) {
        const std::string commandLine = QuoteArgument (tar) + " -xf " + QuoteArgument (zipPath) + " -C " + QuoteArgument (destination);
        if (RunAndWait (commandLine, std::string (), kExtractTimeoutMs, exitCode, lastError) && exitCode == 0) {
            return true;
        }
    }

    std::string zipForPowerShell;       // een apostrof in een pad moet in PowerShell worden verdubbeld
    for (char c : zipPath) {
        zipForPowerShell += c;
        if (c == '\'') {
            zipForPowerShell += c;
        }
    }
    std::string destinationForPowerShell;
    for (char c : destination) {
        destinationForPowerShell += c;
        if (c == '\'') {
            destinationForPowerShell += c;
        }
    }
    const std::string powerShell = Join (Join (Join (system, "WindowsPowerShell"), "v1.0"), "powershell.exe");
    const std::string commandLine = QuoteArgument (powerShell) + " -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \"Expand-Archive -LiteralPath '" +
                                    zipForPowerShell + "' -DestinationPath '" + destinationForPowerShell + "' -Force\"";
    if (PathExists (powerShell) && RunAndWait (commandLine, std::string (), kExtractTimeoutMs, exitCode, lastError) && exitCode == 0) {
        return true;
    }

    error = "Het uitpakken van de motor is mislukt (tar.exe en PowerShell). Mogelijk blokkeert beveiligingssoftware dit. Doelmap: " + destination;
    return false;
}

bool ProcessIsAlive ()
{
    return g_process != nullptr && WaitForSingleObject (g_process, 0) == WAIT_TIMEOUT;
}

void CloseHandles ()
{
    if (g_process != nullptr) {
        CloseHandle (g_process);
        g_process = nullptr;
    }
    if (g_job != nullptr) {
        CloseHandle (g_job);        // sluit je de 'job', dan beëindigt Windows alle processen erin
        g_job = nullptr;
    }
}

std::string NumberToString (unsigned long value)
{
    return std::to_string (value);
}

} // namespace

// ------------------------------------------------------------------ openbaar
StartResult EnsureRunning (const std::string& buildId, int archicadPort)
{
    StartResult result;

    if (ProcessIsAlive () && g_port > 0) {
        result.ok = true;
        result.port = g_port;
        result.folder = g_folder;
        result.logPath = g_logPath;
        return result;
    }
    CloseHandles ();
    g_port = 0;

    const std::string localAppData = EnvironmentVariable (L"LOCALAPPDATA");
    if (localAppData.empty ()) {
        result.error = "De map %LOCALAPPDATA% is niet beschikbaar, dus de motor kan nergens worden uitgepakt.";
        return result;
    }
    const std::string folder = Join (Join (localAppData, "PDOKImport"), buildId);
    const std::string pythonFolder = Join (folder, "python");
    const std::string appFolder = Join (folder, "app");
    const std::string readyFile = Join (folder, "ready.txt");
    const std::string portFile = Join (folder, "port.txt");
    const std::string logPath = Join (folder, "engine.log");
    result.folder = folder;
    result.logPath = logPath;

    // 1. Uitpakken (eenmalig per versie)
    if (!PathExists (readyFile)) {
        if (!MakeDirectories (folder)) {
            result.error = "De map " + folder + " kon niet worden aangemaakt.";
            return result;
        }
        struct Part { int id; const char* zipName; const std::string* destination; };
        const Part parts[] = {
            { PDOK_RES_PYTHON_EMBED, "python-embed.zip", &pythonFolder },
            { PDOK_RES_ENGINE_APP, "engine-app.zip", &appFolder },
        };
        for (const Part& part : parts) {
            const void* data = nullptr;
            DWORD size = 0;
            if (!GetEmbeddedResource (part.id, data, size)) {
                result.error = std::string ("De motor zit niet in deze add-on (bron ") + part.zipName + " ontbreekt). Dit .apx is onvolledig gebouwd.";
                return result;
            }
            const std::string zipPath = Join (folder, part.zipName);
            if (!WriteBytes (zipPath, data, size)) {
                result.error = "Het bestand " + zipPath + " kon niet worden geschreven.";
                return result;
            }
            std::string extractError;
            const bool extracted = ExtractZip (zipPath, *part.destination, extractError);
            DeleteFileW (ToWide (zipPath).data ());
            if (!extracted) {
                result.error = extractError;
                return result;
            }
        }
        if (!PathExists (Join (pythonFolder, "python.exe")) || !PathExists (Join (appFolder, "engine.py"))) {
            result.error = "Na het uitpakken ontbreken python.exe of engine.py in " + folder + ". Mogelijk heeft beveiligingssoftware bestanden verwijderd.";
            return result;
        }
        WriteBytes (readyFile, "ok", 2);
    }

    // 2. Starten
    DeleteFileW (ToWide (portFile).data ());

    SECURITY_ATTRIBUTES inheritable = {};
    inheritable.nLength = static_cast<DWORD> (sizeof (inheritable));
    inheritable.bInheritHandle = TRUE;
    const HANDLE logHandle = CreateFileW (ToWide (logPath).data (), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, &inheritable, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    const HANDLE nullInput = CreateFileW (L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &inheritable, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);

    STARTUPINFOW startupInfo = {};
    startupInfo.cb = static_cast<DWORD> (sizeof (startupInfo));
    startupInfo.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
    startupInfo.wShowWindow = SW_HIDE;
    startupInfo.hStdInput = nullInput != INVALID_HANDLE_VALUE ? nullInput : nullptr;
    startupInfo.hStdOutput = logHandle != INVALID_HANDLE_VALUE ? logHandle : nullptr;
    startupInfo.hStdError = logHandle != INVALID_HANDLE_VALUE ? logHandle : nullptr;

    const std::string pythonExe = Join (pythonFolder, "python.exe");
    const std::string commandLine = QuoteArgument (pythonExe) + " -X utf8 -u " + QuoteArgument (Join (appFolder, "engine.py")) +
                                    " --port-file " + QuoteArgument (portFile) + " --parent-pid " + NumberToString (GetCurrentProcessId ()) +
                                    " --archicad-port " + NumberToString (static_cast<unsigned long> (archicadPort));
    std::vector<wchar_t> command = ToWide (commandLine);
    const std::vector<wchar_t> workingDirectory = ToWide (appFolder);

    PROCESS_INFORMATION processInfo = {};
    const BOOL started = CreateProcessW (nullptr, command.data (), nullptr, nullptr, TRUE, CREATE_NO_WINDOW | CREATE_SUSPENDED, nullptr,
                                         workingDirectory.data (), &startupInfo, &processInfo);
    const DWORD startError = started ? 0 : GetLastError ();
    if (logHandle != INVALID_HANDLE_VALUE) {
        CloseHandle (logHandle);
    }
    if (nullInput != INVALID_HANDLE_VALUE) {
        CloseHandle (nullInput);
    }
    if (!started) {
        result.error = "De motor kon niet worden gestart (Windows-foutcode " + NumberToString (startError) +
                       "). Beveiligingssoftware kan het starten van programma's in " + folder + " blokkeren.";
        return result;
    }

    // De motor hoort mee te sterven met Archicad, ook als Archicad crasht: een 'job' die zijn processen beëindigt bij sluiten.
    g_job = CreateJobObjectW (nullptr, nullptr);
    if (g_job != nullptr) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {};
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        SetInformationJobObject (g_job, JobObjectExtendedLimitInformation, &limits, static_cast<DWORD> (sizeof (limits)));
        AssignProcessToJobObject (g_job, processInfo.hProcess);   // mislukt dit, dan stopt de motor zelf via zijn ouder-controle
    }
    ResumeThread (processInfo.hThread);
    CloseHandle (processInfo.hThread);
    g_process = processInfo.hProcess;

    // 3. Wachten tot de motor zijn poort heeft doorgegeven
    const DWORD begin = GetTickCount ();
    while (GetTickCount () - begin < kStartTimeoutMs) {
        const std::string text = ReadText (portFile, 16);
        if (!text.empty ()) {
            const int port = std::atoi (text.c_str ());
            if (port > 0 && port < 65536) {
                g_port = port;
                g_folder = folder;
                g_logPath = logPath;
                result.ok = true;
                result.port = port;
                return result;
            }
        }
        if (!ProcessIsAlive ()) {
            result.error = "De motor stopte direct na het starten. Het einde van het logboek:\n" + TrimmedTail (ReadText (logPath, 1500));
            CloseHandles ();
            return result;
        }
        Sleep (100);
    }

    result.error = "De motor meldde zich niet binnen 25 seconden. Het einde van het logboek:\n" + TrimmedTail (ReadText (logPath, 1500));
    CloseHandles ();
    return result;
}

void Stop ()
{
    if (g_process != nullptr) {
        TerminateProcess (g_process, 0);
    }
    CloseHandles ();
    g_port = 0;
}

Status GetStatus ()
{
    Status status;
    status.running = ProcessIsAlive () && g_port > 0;
    status.port = status.running ? g_port : 0;
    status.folder = g_folder;
    status.logPath = g_logPath;
    return status;
}

}
