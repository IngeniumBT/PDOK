// PDOK Import - Archicad Add-On (skelet).
//
// Dit skelet bewijst alleen dat de hele keten werkt: bouwen met GitHub, het .apx toevoegen in de
// Add-On Manager, en een menuopdracht in Archicad. De echte functies komen er daarna in.

#include "APIEnvir.h"
#include "ACAPinc.h"

#include "DGModule.hpp"
#include "RS.hpp"
#include "UniString.hpp"

#include "AddOnVersion.hpp"
#include "ResourceIds.hpp"

// Het hoofdversienummer van Archicad (bijvoorbeeld 29), vastgelegd in CheckEnvironment.
static Int32 g_archicadMainVersion = 0;

static void ShowAboutAlert ()
{
    const GS::UniString title ("PDOK Import");
    const GS::UniString message = GS::UniString ("Versie ") + ADDON_VERSION;
    const GS::UniString subMessage = GS::UniString::Printf ("Dit is het skelet van de add-on; het werkt in Archicad %d.", static_cast<int> (g_archicadMainVersion));
    const GS::UniString ok ("OK");
    const GS::UniString none;

    DGAlert (DG_INFORMATION, title, message, subMessage, ok, none, none);
}

static GSErrCode MenuCommandHandler (const API_MenuParams* menuParams)
{
    switch (menuParams->menuItemRef.menuResID) {
        case ID_ADDON_MENU:
            switch (menuParams->menuItemRef.itemIndex) {
                case ID_ADDON_MENU_ABOUT:
                    ShowAboutAlert ();
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

    return APIAddon_Normal;
}

GSErrCode RegisterInterface (void)
{
#ifdef ServerMainVers_2700
    return ACAPI_MenuItem_RegisterMenu (ID_ADDON_MENU, 0, MenuCode_UserDef, MenuFlag_Default);
#else
    return ACAPI_Register_Menu (ID_ADDON_MENU, 0, MenuCode_UserDef, MenuFlag_Default);
#endif
}

GSErrCode Initialize (void)
{
    ACAPI_WriteReport ("PDOK Import geladen.", false);
#ifdef ServerMainVers_2700
    return ACAPI_MenuItem_InstallMenuHandler (ID_ADDON_MENU, MenuCommandHandler);
#else
    return ACAPI_Install_MenuHandler (ID_ADDON_MENU, MenuCommandHandler);
#endif
}

GSErrCode FreeData (void)
{
    return NoError;
}
