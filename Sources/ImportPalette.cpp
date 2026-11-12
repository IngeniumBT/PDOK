#include "ImportPalette.hpp"
#include "ResourceIds.hpp"

// Dit GUID is van dit palet; Archicad onthoudt er de plek van het palet mee. Nooit wijzigen.
const GS::Guid                  ImportPalette::paletteGuid ("{E8625848-DD18-4276-894C-C548B9ABA4F5}");
GS::Ref<ImportPalette>          ImportPalette::instance;

ImportPalette::ImportPalette ()
    : DG::Palette (ACAPI_GetOwnResModule (), ID_IMPORT_PALETTE, ACAPI_GetOwnResModule (), paletteGuid)
    , browser (GetReference (), 1)
{
    Attach (*this);
    BeginEventProcessing ();
}

ImportPalette::~ImportPalette ()
{
    EndEventProcessing ();
}

bool ImportPalette::HasInstance ()
{
    return instance != nullptr;
}

ImportPalette& ImportPalette::Instance ()
{
    if (!HasInstance ()) {
        instance = new ImportPalette ();
    }
    return *instance;
}

void ImportPalette::Release ()
{
    instance = nullptr;
}

void ImportPalette::ShowHTML (const GS::UniString& html)
{
    if (!sizeIsSet) {
        // De GDLG-grootte (600x450) is de beginmaat; DG houdt die ook als minimum, tenzij je het minimum verlaagt.
        SetGrowType (DG::Dialog::HVGrow);
        SetMinClientSize (320, 240);
        SetClientSize (1100, 760);
        sizeIsSet = true;
    }
    browser.SetScrollBarVisibility (true);
    browser.DisableNavigation (false);       // de pagina stuurt zelf door naar de motor
    browser.LoadHTML (html);
    ShowPalette ();
}

void ImportPalette::HidePalette ()
{
    hiddenByForcedHideBegin = false;
    DG::Palette::Hide ();
}

bool ImportPalette::IsOpen ()
{
    return IsVisible () || hiddenByForcedHideBegin;
}

void ImportPalette::ShowPalette ()
{
    DG::Palette::Show ();
}

void ImportPalette::HideTemporarily ()
{
    DG::Palette::Hide ();
}

void ImportPalette::PanelCloseRequested (const DG::PanelCloseRequestEvent&, bool* accepted)
{
    hiddenByForcedHideBegin = false;
    DG::Palette::Hide ();
    *accepted = true;
}

void ImportPalette::PanelResized (const DG::PanelResizeEvent& ev)
{
    BeginMoveResizeItems ();
    browser.Resize (ev.GetHorizontalChange (), ev.GetVerticalChange ());
    EndMoveResizeItems ();
}

GSErrCode ImportPalette::PaletteControlCallBack (Int32 /*paletteId*/, API_PaletteMessageID messageID, GS::IntPtr param)
{
    switch (messageID) {
        case APIPalMsg_OpenPalette:
            // Archicad heropent het palet als het bij het vorige afsluiten open stond; de pagina is dan weg.
            // Alleen heropenen als de pagina in deze sessie is getoond (dan bestaat het palet al).
            if (HasInstance ()) {
                Instance ().ShowPalette ();
            }
            break;

        case APIPalMsg_ClosePalette:
            if (HasInstance ()) {
                Instance ().HidePalette ();
            }
            break;

        case APIPalMsg_HidePalette_Begin:
            if (HasInstance ()) {
                ImportPalette& palette = Instance ();
                palette.hiddenByForcedHideBegin = palette.IsVisible ();
                if (palette.hiddenByForcedHideBegin) {
                    palette.HideTemporarily ();   // tijdelijk, bijvoorbeeld tijdens een dialoog
                }
            }
            break;

        case APIPalMsg_HidePalette_End:
            if (HasInstance ()) {
                ImportPalette& palette = Instance ();
                if (palette.hiddenByForcedHideBegin) {
                    palette.ShowPalette ();
                }
                palette.hiddenByForcedHideBegin = false;
            }
            break;

        case APIPalMsg_IsPaletteVisible:
            *(reinterpret_cast<bool*> (param)) = HasInstance () && Instance ().IsVisible ();
            break;

        default:
            break;
    }

    return NoError;
}

GSErrCode ImportPalette::RegisterPaletteControlCallBack ()
{
    return ACAPI_RegisterModelessWindow (
        GS::CalculateHashValue (paletteGuid),
        PaletteControlCallBack,
        API_PalEnabled_FloorPlan + API_PalEnabled_Section + API_PalEnabled_Elevation +
        API_PalEnabled_InteriorElevation + API_PalEnabled_3D + API_PalEnabled_Detail +
        API_PalEnabled_Worksheet + API_PalEnabled_Layout + API_PalEnabled_DocumentFrom3D,
        GSGuid2APIGuid (paletteGuid));
}
