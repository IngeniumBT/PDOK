#include "Commands.hpp"

#include "AddOnVersion.hpp"
#include "AddOnBuildCommit.hpp"

namespace PdokCommands
{

namespace
{

// ------------------------------------------------------------------ hulpfuncties
GS::ObjectState ErrorResponse (GSErrCode code, const GS::UniString& message)
{
    GS::ObjectState error;
    error.Add ("code", code);
    error.Add ("message", message.ToCStr ().Get ());
    return GS::ObjectState ("error", error);
}

GS::ObjectState GuidObject (const API_Guid& guid)
{
    return GS::ObjectState ("guid", APIGuidToString (guid));
}

// Leest {"guid": "..."} uit het veld `field` van `item`.
API_Guid GuidOfField (const GS::ObjectState& item, const char* field)
{
    const GS::ObjectState* wrapper = item.Get (field);
    if (wrapper == nullptr) {
        return APINULLGuid;
    }
    GS::String guid;
    if (!wrapper->Get ("guid", guid)) {
        return APINULLGuid;
    }
    return APIGuidFromString (guid.ToCStr ());
}

Int32 IndexValue (const API_AttributeIndex& index)
{
    return index.ToInt32_Deprecated ();
}

GS::ObjectState ElementIdObject (const API_Guid& guid)
{
    return GS::ObjectState ("elementId", GuidObject (guid));
}

// ------------------------------------------------------------------ elementtypen
struct TypeName
{
    const char*     name;
    API_ElemTypeID  id;
};

const TypeName kTypeNames[] = {
    { "Wall", API_WallID },     { "Column", API_ColumnID },   { "Beam", API_BeamID },       { "Window", API_WindowID },
    { "Door", API_DoorID },     { "Object", API_ObjectID },   { "Lamp", API_LampID },       { "Slab", API_SlabID },
    { "Roof", API_RoofID },     { "Mesh", API_MeshID },       { "Zone", API_ZoneID },       { "Shell", API_ShellID },
    { "Morph", API_MorphID },   { "Line", API_LineID },       { "Arc", API_ArcID },         { "Polyline", API_PolyLineID },
    { "Spline", API_SplineID }, { "Text", API_TextID },       { "Hatch", API_HatchID },
};

bool TypeFromName (const GS::UniString& name, API_ElemTypeID& id)
{
    for (const TypeName& entry : kTypeNames) {
        if (name == entry.name) {
            id = entry.id;
            return true;
        }
    }
    return false;
}

GS::UniString NameOfType (API_ElemTypeID id)
{
    for (const TypeName& entry : kTypeNames) {
        if (entry.id == id) {
            return entry.name;
        }
    }
    return "Other";
}

// ------------------------------------------------------------------ het Element-ID (de eigenschap 'ID' van een element)
GSErrCode GetElementId (const API_Guid& guid, GS::UniString& id)
{
    return ACAPI_Element_GetElementInfoString (&guid, &id);
}

GSErrCode ChangeElementId (const API_Guid& guid, const GS::UniString& id)
{
    GSErrCode err = ACAPI_Element_ChangeElementInfoString (&guid, &id);
    if (err == NoError) {
        GS::UniString written;
        if (GetElementId (guid, written) != NoError || written != id) {
            return APIERR_REFUSEDPAR;       // Archicad zei NoError maar bewaarde het ID niet
        }
    }
    return err;
}

// ================================================================== opdrachten

// ---- GetAddOnVersion: de versie van de add-on (en een eenvoudige test of de verbinding werkt)
class GetAddOnVersionCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "GetAddOnVersion"; }

    virtual GS::ObjectState Execute (const GS::ObjectState&, GS::ProcessControl&) const override
    {
        GS::ObjectState response;
        response.Add ("version", GS::UniString (ADDON_VERSION));
        response.Add ("buildCommit", GS::UniString (ADDON_BUILD_COMMIT));
        return response;
    }
};

// ---- GetLayers: alle lagen van het project -> {layers: [{attributeId, index, name}]}
class GetLayersCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "GetLayers"; }

    virtual GS::ObjectState Execute (const GS::ObjectState&, GS::ProcessControl&) const override
    {
        GS::Array<API_Attribute> layers;
        const GSErrCode err = ACAPI_Attribute_GetAttributesByType (API_LayerID, layers);
        if (err != NoError) {
            return ErrorResponse (err, "De lagen konden niet worden gelezen.");
        }

        GS::ObjectState response;
        const auto& list = response.AddList<GS::ObjectState> ("layers");
        for (const API_Attribute& listed : layers) {
            GS::UniString name;
            API_Attribute attribute = {};
            attribute.header.typeID = API_LayerID;
            attribute.header.index = listed.header.index;
            attribute.header.uniStringNamePtr = &name;
            if (ACAPI_Attribute_Get (&attribute) != NoError) {
                continue;
            }
            GS::ObjectState layer;
            layer.Add ("attributeId", GuidObject (attribute.header.guid));
            layer.Add ("index", IndexValue (attribute.header.index));
            layer.Add ("name", name);
            list (layer);
        }
        return response;
    }
};

// ---- EnsureLayer {name, folder: [..]}: zoekt de laag op naam, maakt hem (in de map) als hij nog niet bestaat
//      -> {index, attributeId, created}
class EnsureLayerCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "EnsureLayer"; }

    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override
    {
        GS::UniString name;
        if (!parameters.Get ("name", name) || name.IsEmpty ()) {
            return ErrorResponse (APIERR_BADPARS, "De parameter name ontbreekt.");
        }
        GS::Array<GS::UniString> folderPath;
        parameters.Get ("folder", folderPath);

        GS::UniString lookupName = name;
        API_Attribute attribute = {};
        attribute.header.typeID = API_LayerID;
        attribute.header.uniStringNamePtr = &lookupName;
        const bool exists = ACAPI_Attribute_Get (&attribute) == NoError;
        bool created = false;

        if (!exists) {
            GS::UniString newName = name;
            attribute = {};
            attribute.header.typeID = API_LayerID;
            attribute.header.uniStringNamePtr = &newName;
            attribute.layer.conClassId = 1;
            const GSErrCode err = ACAPI_Attribute_Create (&attribute, nullptr);
            if (err != NoError) {
                return ErrorResponse (err, GS::UniString ("De laag '") + name + "' kon niet worden aangemaakt.");
            }
            created = true;

            if (!folderPath.IsEmpty ()) {
                // Een nieuwe laag komt in de map; een bestaande laag blijft waar hij stond.
                API_AttributeFolder folder;
                folder.typeID = API_LayerID;
                folder.path = folderPath;
                folder.guid = GS::Guid ();
                ACAPI_Attribute_CreateFolder (folder);       // maakt ontbrekende mappen aan, laat bestaande staan

                API_AttributeFolder target;
                target.typeID = API_LayerID;
                target.path = folderPath;
                target.guid = GS::Guid ();
                if (ACAPI_Attribute_GetFolder (target) == NoError && !target.guid.IsNull ()) {
                    GS::Array<API_AttributeFolder> noFolders;     // de eerste parameter zijn de te verplaatsen mappen
                    GS::Array<GS::Guid> layersToMove;
                    layersToMove.Push (APIGuid2GSGuid (attribute.header.guid));
                    ACAPI_Attribute_Move (noFolders, layersToMove, target);
                }
            }
        }

        GS::ObjectState response;
        response.Add ("index", IndexValue (attribute.header.index));
        response.Add ("attributeId", GuidObject (attribute.header.guid));
        response.Add ("created", created);
        return response;
    }
};

// ---- GetCurrentWindowType -> {currentWindowType: "FloorPlan" | "3DModel" | "Other"}
const char* WindowTypeName (API_WindowTypeID id)
{
    switch (id) {
        case APIWind_FloorPlanID:   return "FloorPlan";
        case APIWind_3DModelID:     return "3DModel";
        default:                    return "Other";
    }
}

class GetCurrentWindowTypeCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "GetCurrentWindowType"; }

    virtual GS::ObjectState Execute (const GS::ObjectState&, GS::ProcessControl&) const override
    {
        API_WindowInfo windowInfo = {};
        const GSErrCode err = ACAPI_Window_GetCurrentWindow (&windowInfo);
        if (err != NoError) {
            return ErrorResponse (err, "Het actieve venster kon niet worden gelezen.");
        }
        return GS::ObjectState ("currentWindowType", GS::UniString (WindowTypeName (windowInfo.typeID)));
    }
};

// ---- ChangeWindow {windowType: "FloorPlan" | "3DModel", storyIndex?}
class ChangeWindowCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "ChangeWindow"; }

    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override
    {
        GS::UniString windowType;
        if (!parameters.Get ("windowType", windowType)) {
            return ErrorResponse (APIERR_BADPARS, "De parameter windowType ontbreekt (FloorPlan of 3DModel).");
        }

        API_WindowInfo windowInfo = {};
        if (windowType == "FloorPlan") {
            windowInfo.typeID = APIWind_FloorPlanID;
        } else if (windowType == "3DModel") {
            windowInfo.typeID = APIWind_3DModelID;
        } else {
            return ErrorResponse (APIERR_BADPARS, "windowType moet FloorPlan of 3DModel zijn.");
        }

        // GetDatabaseInfo vult de database in die bij het venster hoort; aanmaken van elementen gebeurt in de huidige database.
        if (ACAPI_Window_GetDatabaseInfo (&windowInfo) == NoError) {
            ACAPI_Database_ChangeCurrentDatabase (&windowInfo);
        }
        GSErrCode err = ACAPI_Window_ChangeWindow (&windowInfo);
        if (err != NoError) {
            return ErrorResponse (err, "Het venster kon niet worden gewisseld.");
        }

        Int32 storyIndex = 0;
        if (windowInfo.typeID == APIWind_FloorPlanID && parameters.Get ("storyIndex", storyIndex)) {
            API_StoryInfo storyInfo = {};
            err = ACAPI_ProjectSetting_GetStorySettings (&storyInfo);
            BMKillHandle (reinterpret_cast<GSHandle*> (&storyInfo.data));
            if (err != NoError) {
                return ErrorResponse (err, "De verdiepingen konden niet worden gelezen.");
            }
            if (storyIndex < storyInfo.firstStory || storyIndex > storyInfo.lastStory) {
                return ErrorResponse (APIERR_BADINDEX, "storyIndex ligt buiten de verdiepingen van het project.");
            }
            API_StoryCmdType storyCommand = {};
            storyCommand.action = APIStory_GoTo;
            storyCommand.index = static_cast<short> (storyIndex);
            err = ACAPI_ProjectSetting_ChangeStorySettings (&storyCommand);
            if (err != NoError) {
                return ErrorResponse (err, "De verdieping kon niet worden gewisseld.");
            }
        }
        return GS::ObjectState ("success", true);
    }
};

// ---- GetElementsByType {elementType} -> {elements: [{elementId}]}   (in het actieve venster)
class GetElementsByTypeCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "GetElementsByType"; }

    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override
    {
        GS::UniString typeName;
        API_ElemTypeID typeId = API_ZombieElemID;
        if (!parameters.Get ("elementType", typeName) || !TypeFromName (typeName, typeId)) {
            return ErrorResponse (APIERR_BADPARS, "elementType ontbreekt of is onbekend.");
        }

        GS::Array<API_Guid> guids;
        const GSErrCode err = ACAPI_Element_GetElemList (typeId, &guids);
        if (err != NoError) {
            return ErrorResponse (err, "De elementen konden niet worden gelezen.");
        }

        GS::ObjectState response;
        const auto& list = response.AddList<GS::ObjectState> ("elements");
        for (const API_Guid& guid : guids) {
            list (ElementIdObject (guid));
        }
        return response;
    }
};

// ---- GetDetailsOfElements {elements: [{elementId}]} of {types: [..], layerIndices: [..]}
//      -> {detailsOfElements: [{elementId, type, layerIndex, floorIndex, id, details: {}}]}
class GetDetailsOfElementsCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "GetDetailsOfElements"; }

    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override
    {
        GS::Array<API_Guid> guids;

        GS::Array<GS::ObjectState> elements;
        if (parameters.Get ("elements", elements)) {
            for (const GS::ObjectState& item : elements) {
                guids.Push (GuidOfField (item, "elementId"));
            }
        } else {
            GS::Array<GS::UniString> typeNames;
            parameters.Get ("types", typeNames);
            for (const GS::UniString& typeName : typeNames) {
                API_ElemTypeID typeId = API_ZombieElemID;
                if (!TypeFromName (typeName, typeId)) {
                    return ErrorResponse (APIERR_BADPARS, GS::UniString ("Onbekend elementtype: ") + typeName);
                }
                GS::Array<API_Guid> ofType;
                if (ACAPI_Element_GetElemList (typeId, &ofType) == NoError) {
                    guids.Append (ofType);
                }
            }
        }

        GS::Array<Int32> layerIndices;
        parameters.Get ("layerIndices", layerIndices);

        GS::ObjectState response;
        const auto& list = response.AddList<GS::ObjectState> ("detailsOfElements");
        for (const API_Guid& guid : guids) {
            API_Elem_Head head = {};
            head.guid = guid;
            if (ACAPI_Element_GetHeader (&head) != NoError) {
                continue;
            }
            const Int32 layer = IndexValue (head.layer);
            if (!layerIndices.IsEmpty () && !layerIndices.Contains (layer)) {
                continue;
            }
            GS::UniString id;
            GetElementId (guid, id);

            GS::ObjectState detail;
            detail.Add ("elementId", GuidObject (guid));
            detail.Add ("type", NameOfType (head.type.typeID));
            detail.Add ("layerIndex", layer);
            detail.Add ("floorIndex", static_cast<Int32> (head.floorInd));
            detail.Add ("id", id);
            detail.Add ("details", GS::ObjectState ());
            list (detail);
        }
        return response;
    }
};

// ---- SetDetailsOfElements {elementsWithDetails: [{elementId, details: {layerIndex?, id?}}]}
//      -> {executionResults: [{success} | {success: false, error}]}
class SetDetailsOfElementsCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "SetDetailsOfElements"; }

    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override
    {
        GS::Array<GS::ObjectState> items;
        parameters.Get ("elementsWithDetails", items);

        GS::ObjectState response;
        const auto& results = response.AddList<GS::ObjectState> ("executionResults");

        const GSErrCode undoErr = ACAPI_CallUndoableCommand ("PDOK Import: elementen wijzigen", [&] () -> GSErrCode {
            for (const GS::ObjectState& item : items) {
                results (ChangeOne (item));
            }
            return NoError;
        });
        if (undoErr != NoError) {
            return ErrorResponse (undoErr, "De wijzigingen konden niet worden doorgevoerd.");
        }
        return response;
    }

private:
    static GS::ObjectState Failure (GSErrCode code, const GS::UniString& message)
    {
        GS::ObjectState result = ErrorResponse (code, message);
        result.Add ("success", false);
        return result;
    }

    static GS::ObjectState ChangeOne (const GS::ObjectState& item)
    {
        const API_Guid guid = GuidOfField (item, "elementId");
        const GS::ObjectState* details = item.Get ("details");
        if (guid == APINULLGuid || details == nullptr) {
            return Failure (APIERR_BADPARS, "elementId of details ontbreekt.");
        }

        API_Element element = {};
        element.header.guid = guid;
        GSErrCode err = ACAPI_Element_Get (&element);
        if (err != NoError) {
            return Failure (err, "Het element is niet gevonden.");
        }

        // Het Element-ID eerst, apart van de rest van de wijziging.
        GS::UniString id;
        if (details->Get ("id", id)) {
            err = ChangeElementId (guid, id);
            if (err != NoError) {
                return Failure (err, "Het ID van het element kon niet worden gezet.");
            }
        }

        Int32 layerIndex = 0;
        if (details->Get ("layerIndex", layerIndex)) {
            API_Element mask = {};
            ACAPI_ELEMENT_MASK_CLEAR (mask);
            element.header.layer = ACAPI_CreateAttributeIndex (layerIndex);
            ACAPI_ELEMENT_MASK_SET (mask, API_Elem_Head, layer);
            err = ACAPI_Element_Change (&element, &mask, nullptr, 0, true);
            if (err != NoError) {
                return Failure (err, "De laag van het element kon niet worden gezet.");
            }
        }
        return GS::ObjectState ("success", true);
    }
};

// ---- DeleteElements {elements: [{elementId}]} -> {deleted, notFound}
class DeleteElementsCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "DeleteElements"; }

    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override
    {
        GS::Array<GS::ObjectState> items;
        parameters.Get ("elements", items);

        // Een guid die niet in het project staat mag niet naar ACAPI_Element_Delete: dan mislukt de hele aanroep.
        GS::Array<API_Guid> toDelete;
        Int32 notFound = 0;
        for (const GS::ObjectState& item : items) {
            const API_Guid guid = GuidOfField (item, "elementId");
            API_Elem_Head head = {};
            head.guid = guid;
            if (guid != APINULLGuid && ACAPI_Element_GetHeader (&head) == NoError) {
                toDelete.Push (guid);
            } else {
                ++notFound;
            }
        }

        if (!toDelete.IsEmpty ()) {
            const GSErrCode err = ACAPI_CallUndoableCommand ("PDOK Import: elementen verwijderen", [&] () -> GSErrCode {
                return ACAPI_Element_Delete (toDelete);
            });
            if (err != NoError) {
                return ErrorResponse (err, "De elementen konden niet worden verwijderd.");
            }
        }

        GS::ObjectState response;
        response.Add ("deleted", static_cast<Int32> (toDelete.GetSize ()));
        response.Add ("notFound", notFound);
        return response;
    }
};

// ---- GetSelectedElements -> {elements: [{elementId}]}
class GetSelectedElementsCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "GetSelectedElements"; }

    virtual GS::ObjectState Execute (const GS::ObjectState&, GS::ProcessControl&) const override
    {
        API_SelectionInfo selectionInfo = {};
        GS::Array<API_Neig> selected;
        const GSErrCode err = ACAPI_Selection_Get (&selectionInfo, &selected, false);
        BMKillHandle (reinterpret_cast<GSHandle*> (&selectionInfo.marquee.coords));
        if (err != NoError && err != APIERR_NOSEL) {
            return ErrorResponse (err, "De selectie kon niet worden gelezen.");
        }

        GS::ObjectState response;
        const auto& list = response.AddList<GS::ObjectState> ("elements");
        if (err == APIERR_NOSEL || selectionInfo.typeID == API_SelEmpty) {
            return response;
        }
        for (const API_Neig& neig : selected) {
            list (ElementIdObject (neig.guid));
        }
        return response;
    }
};

template <class CommandType>
GSErrCode Register ()
{
    GS::Owner<CommandType> command = GS::NewOwned<CommandType> ();
    const GS::String name = command->GetName ();
    const GSErrCode err = ACAPI_AddOnAddOnCommunication_InstallAddOnCommandHandler (command.Pass ());
    if (err != NoError) {
        ACAPI_WriteReport ("PDOK Import: opdracht %s kon niet worden geregistreerd (fout %d).", false, name.ToCStr (), static_cast<int> (err));
    }
    return err;
}

} // namespace

GSErrCode RegisterAll ()
{
    GSErrCode err = NoError;
    err |= Register<GetAddOnVersionCommand> ();
    err |= Register<GetLayersCommand> ();
    err |= Register<EnsureLayerCommand> ();
    err |= Register<GetCurrentWindowTypeCommand> ();
    err |= Register<ChangeWindowCommand> ();
    err |= Register<GetElementsByTypeCommand> ();
    err |= Register<GetDetailsOfElementsCommand> ();
    err |= Register<SetDetailsOfElementsCommand> ();
    err |= Register<DeleteElementsCommand> ();
    err |= Register<GetSelectedElementsCommand> ();
    return err;
}

}
