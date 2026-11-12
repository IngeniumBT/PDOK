#pragma once

#include "APIEnvir.h"
#include "ACAPinc.h"
#include "DGModule.hpp"
#include "DGBrowser.hpp"

// Het palet van PDOK Import: een Archicad-palet met een ingebouwde browser (DG::Browser). Opgezet naar het Script
// UI-palet van Tapir (MIT), dat in Archicad 25 tot en met 30 werkt.
class ImportPalette final : public DG::Palette,
                            public DG::PanelObserver
{
public:
    virtual ~ImportPalette ();

    static bool             HasInstance ();
    static ImportPalette&   Instance ();

    // Moet vanuit FreeData worden aangeroepen, terwijl de browser van Archicad nog bestaat (anders kan Archicad
    // crashen bij het afsluiten).
    static void             Release ();

    // Toont de pagina (HTML-tekst) en maakt het palet zichtbaar.
    void                    ShowHTML (const GS::UniString& html);
    void                    HidePalette ();
    bool                    IsOpen ();

    static GSErrCode        RegisterPaletteControlCallBack ();

private:
    DG::Browser browser;
    bool        hiddenByForcedHideBegin = false;
    bool        sizeIsSet = false;

    ImportPalette ();

    void ShowPalette ();
    void HideTemporarily ();      // verbergt het palet zonder het als 'gesloten door de gebruiker' te markeren

    virtual void PanelCloseRequested (const DG::PanelCloseRequestEvent& ev, bool* accepted) override;
    virtual void PanelResized (const DG::PanelResizeEvent& ev) override;

    static GSErrCode PaletteControlCallBack (Int32 paletteId, API_PaletteMessageID messageID, GS::IntPtr param);

    static const GS::Guid               paletteGuid;
    static GS::Ref<ImportPalette>       instance;
};
