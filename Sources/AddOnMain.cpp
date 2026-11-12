// PDOK Import - Archicad Add-On.
//
// Stap A: de motor (Python, ingebouwd in dit .apx) wordt gestart en de kaart staat in een palet in Archicad.

#include "APIEnvir.h"
#include "ACAPinc.h"

#include "DGModule.hpp"
#include "RS.hpp"
#include "UniString.hpp"

#include <string>

#include "AddOnBuildCommit.hpp"
#include "AddOnVersion.hpp"
#include "ResourceIds.hpp"
#include "EngineHost.hpp"
#include "ImportPalette.hpp"

// Het hoofdversienummer van Archicad (bijvoorbeeld 29), vastgelegd in CheckEnvironment.
static Int32 g_archicadMainVersion = 0;

// De map van de motor: de versie, met de bouwcode erbij zodat elke nieuwe bouw een verse motor krijgt.
static std::string BuildId ()
{
    std::string id = ADDON_VERSION;
    const std::string commit = ADDON_BUILD_COMMIT;
    if (!commit.empty ()) {
        id += "-" + commit;
    }
    return id;
}

static GS::UniString FromUtf8 (const std::string& text)
{
    return GS::UniString (text.c_str (), CC_UTF8);
}

static void ShowAlert (short type, const GS::UniString& message, const GS::UniString& subMessage)
{
    const GS::UniString title ("PDOK Import");
    const GS::UniString ok ("OK");
    const GS::UniString none;
    DGAlert (type, title, message, subMessage, ok, none, none);
}

static void OpenImportPalette ()
{
    const EngineHost::StartResult engine = EngineHost::EnsureRunning (BuildId ());
    if (!engine.ok) {
        ShowAlert (DG_ERROR, GS::UniString ("De motor van PDOK Import kon niet worden gestart."),
                   FromUtf8 (engine.error + "\n\nLogboek: " + engine.logPath));
        return;
    }

    // De pagina stuurt door naar de motor (die luistert alleen op deze computer, 127.0.0.1).
    GS::UniString html;
    html += "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>PDOK Import</title></head>";
    html += "<body style=\"font-family:Segoe UI,Arial,sans-serif;margin:16px\">De kaart wordt geladen...";
    html += "<script>location.replace('http://127.0.0.1:" + GS::ValueToUniString (static_cast<Int32> (engine.port)) + "/');</script>";
    html += "</body></html>";
    ImportPalette::Instance ().ShowHTML (html);
}

static void ShowAbout ()
{
    const EngineHost::Status status = EngineHost::GetStatus ();

    const GS::UniString message = GS::UniString ("Versie ") + ADDON_VERSION + " (" + FromUtf8 (BuildId ()) + ")";
    GS::UniString subMessage = GS::UniString::Printf ("Gebouwd voor Archicad %d.", static_cast<int> (g_archicadMainVersion));
    if (status.running) {
        subMessage += GS::UniString ("\nDe motor draait op poort ") + GS::ValueToUniString (static_cast<Int32> (status.port)) + ".";
        subMessage += "\nMap: " + FromUtf8 (status.folder);
        subMessage += "\nLogboek: " + FromUtf8 (status.logPath);
    } else {
        subMessage += "\nDe motor is nog niet gestart (kies PDOK Import openen).";
    }
    ShowAlert (DG_INFORMATION, message, subMessage);
}

static GSErrCode MenuCommandHandler (const API_MenuParams* menuParams)
{
    switch (menuParams->menuItemRef.menuResID) {
        case ID_ADDON_MENU_FOR_OPEN:
            switch (menuParams->menuItemRef.itemIndex) {
                case ID_ADDON_MENU_OPEN:
                    OpenImportPalette ();
                    break;
            }
            break;
        case ID_ADDON_MENU:
            switch (menuParams->menuItemRef.itemIndex) {
                case ID_ADDON_MENU_ABOUT:
                    ShowAbout ();
                    break;
            }
            break;
    }
    return NoError;
}

API_AddonType CheckEnvironment (API_EnvirParams* envir)
{
    RSGetIndString (&envir->addOnInfo.name, ID_ADDON_INFO, ID_ADDON_INFO_NAME, ACAPI_GetOwnResModule ());
    RSGetIndString (&envir->addOnInfo.description, ID_ADDON_INFO, ID_ADDON_INFO_DESC, ACAPI_GetOwnResModule ());
    envir->addOnInfo.description += GS::UniString (" ") + ADDON_VERSION;

    g_archicadMainVersion = envir->serverInfo.mainVersion;

    // Preload: de add-on blijft geladen, zodat het palet en de motor blijven bestaan.
    return APIAddon_Preload;
}

GSErrCode RegisterInterface (void)
{
    GSErrCode err = NoError;
#ifdef ServerMainVers_2700
    err |= ACAPI_MenuItem_RegisterMenu (ID_ADDON_MENU_FOR_OPEN, 0, MenuCode_UserDef, MenuFlag_Default);
    err |= ACAPI_MenuItem_RegisterMenu (ID_ADDON_MENU, 0, MenuCode_UserDef, MenuFlag_SeparatorBefore);
#else
    err |= ACAPI_Register_Menu (ID_ADDON_MENU_FOR_OPEN, 0, MenuCode_UserDef, MenuFlag_Default);
    err |= ACAPI_Register_Menu (ID_ADDON_MENU, 0, MenuCode_UserDef, MenuFlag_SeparatorBefore);
#endif
    return err;
}

GSErrCode Initialize (void)
{
    GSErrCode err = NoError;
#ifdef ServerMainVers_2700
    err |= ACAPI_MenuItem_InstallMenuHandler (ID_ADDON_MENU_FOR_OPEN, MenuCommandHandler);
    err |= ACAPI_MenuItem_InstallMenuHandler (ID_ADDON_MENU, MenuCommandHandler);
#else
    err |= ACAPI_Install_MenuHandler (ID_ADDON_MENU_FOR_OPEN, MenuCommandHandler);
    err |= ACAPI_Install_MenuHandler (ID_ADDON_MENU, MenuCommandHandler);
#endif
    err |= ImportPalette::RegisterPaletteControlCallBack ();
    ACAPI_WriteReport ("PDOK Import geladen.", false);
    return err;
}

GSErrCode FreeData (void)
{
    EngineHost::Stop ();
    // Het palet moet worden opgeruimd terwijl de browser van Archicad nog bestaat.
    ImportPalette::Release ();
    return NoError;
}
