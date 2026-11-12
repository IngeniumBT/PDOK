#include "Commands.hpp"

#include <algorithm>
#include <cmath>

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

// Leest de guid uit een object {"guid": "..."}.
API_Guid GuidOfObject (const GS::ObjectState& wrapper)
{
    GS::String guid;
    if (!wrapper.Get ("guid", guid)) {
        return APINULLGuid;
    }
    return APIGuidFromString (guid.ToCStr ());
}

// Leest {"guid": "..."} uit het veld `field` van `item`.
API_Guid GuidOfField (const GS::ObjectState& item, const char* field)
{
    const GS::ObjectState* wrapper = item.Get (field);
    return wrapper == nullptr ? APINULLGuid : GuidOfObject (*wrapper);
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
        GS::ObjectState response ("currentWindowType", GS::UniString (WindowTypeName (windowInfo.typeID)));
        // De database waarin de opdrachten werken is iets anders dan het venster dat je ziet.
        API_DatabaseInfo databaseInfo = {};
        if (ACAPI_Database_GetCurrentDatabase (&databaseInfo) == NoError) {
            response.Add ("currentDatabaseType", GS::UniString (WindowTypeName (databaseInfo.typeID)));
        }
        return response;
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
        GSErrCode databaseErr = ACAPI_Window_GetDatabaseInfo (&windowInfo);
        if (databaseErr == NoError) {
            databaseErr = ACAPI_Database_ChangeCurrentDatabase (&windowInfo);
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
        GS::ObjectState response ("success", true);
        response.Add ("databaseSwitched", databaseErr == NoError);
        if (databaseErr != NoError) {
            response.Add ("databaseError", static_cast<Int32> (databaseErr));
        }
        API_DatabaseInfo databaseInfo = {};
        if (ACAPI_Database_GetCurrentDatabase (&databaseInfo) == NoError) {
            response.Add ("currentDatabaseType", GS::UniString (WindowTypeName (databaseInfo.typeID)));
        }
        return response;
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

        // Het Element-ID eerst, apart van de rest van de wijziging. Een element zonder ID (een lijn of polylijn)
        // weigert dat met APIERR_BADELEMENTTYPE; de rest van de wijziging gaat dan gewoon door.
        bool idIgnored = false;
        GS::UniString id;
        if (details->Get ("id", id)) {
            err = ChangeElementId (guid, id);
            if (err == APIERR_BADELEMENTTYPE) {
                idIgnored = true;
            } else if (err != NoError) {
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
        GS::ObjectState success ("success", true);
        if (idIgnored) {
            success.Add ("idIgnored", true);
        }
        return success;
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


// ================================================================== groep 2: 2D (polylijnen en vlakken)

API_Coord Coordinate2D (const GS::ObjectState& os)
{
    API_Coord coordinate = {};
    os.Get ("x", coordinate.x);
    os.Get ("y", coordinate.y);
    return coordinate;
}

bool SamePoint (const GS::ObjectState& a, const GS::ObjectState& b)
{
    const API_Coord p = Coordinate2D (a);
    const API_Coord q = Coordinate2D (b);
    return std::abs (p.x - q.x) < 1e-9 && std::abs (p.y - q.y) < 1e-9;
}

// Een vlak is een gesloten veelhoek: een herhaling van het eerste punt aan het eind wordt weggelaten.
GS::Array<GS::ObjectState> OpenOutline (const GS::Array<GS::ObjectState>& coordinates)
{
    GS::Array<GS::ObjectState> outline = coordinates;
    if (outline.GetSize () > 1 && SamePoint (outline.GetFirst (), outline.GetLast ())) {
        outline.Pop ();
    }
    return outline;
}

// De coordinaten van een gat: {polygonOutline: [...]} (of de oudere sleutel polygonCoordinates).
bool HoleCoordinates (const GS::ObjectState& hole, GS::Array<GS::ObjectState>& coordinates)
{
    if (!hole.Get ("polygonCoordinates", coordinates) && !hole.Get ("polygonOutline", coordinates)) {
        return false;
    }
    if (!coordinates.IsEmpty () && SamePoint (coordinates.GetFirst (), coordinates.GetLast ())) {
        coordinates.Pop ();
    }
    return true;
}

// Het geheugenblok van een polylijn (open, een deelveelhoek, geen bogen). Naar Tapirs AddPolyToMemo.
void BuildPolylineMemo (const GS::Array<GS::ObjectState>& coordinates, API_Polygon& poly, API_ElementMemo& memo)
{
    poly.nCoords = static_cast<Int32> (coordinates.GetSize ());
    poly.nSubPolys = 1;
    poly.nArcs = 0;

    memo.coords = reinterpret_cast<API_Coord**> (BMAllocateHandle ((poly.nCoords + 1) * sizeof (API_Coord), ALLOCATE_CLEAR, 0));
    memo.pends = reinterpret_cast<Int32**> (BMAllocateHandle ((poly.nSubPolys + 1) * sizeof (Int32), ALLOCATE_CLEAR, 0));
    memo.parcs = reinterpret_cast<API_PolyArc**> (BMAllocateHandle (poly.nArcs * sizeof (API_PolyArc), ALLOCATE_CLEAR, 0));

    Int32 iCoord = 0;
    for (const GS::ObjectState& c : coordinates) {
        (*memo.coords)[++iCoord] = Coordinate2D (c);
    }
    (*memo.pends)[1] = iCoord;
}

// Het geheugenblok van een vlak met gaten, zonder bogen. Naar Tapirs BuildHatchPolygonMemo: elke contour (de buitenrand
// en elk gat) krijgt een eigen sluitpunt dat het eerste punt herhaalt, en de punt-ID's beginnen per contour opnieuw bij 1.
bool BuildHatchMemo (const GS::Array<GS::ObjectState>& outlineIn, const GS::Array<GS::ObjectState>& holes, API_Polygon& poly, API_ElementMemo& memo)
{
    const GS::Array<GS::ObjectState> outline = OpenOutline (outlineIn);

    Int32 totalCoords = static_cast<Int32> (outline.GetSize ()) + 1;
    GS::Array<GS::Array<GS::ObjectState>> holeList;
    for (const GS::ObjectState& hole : holes) {
        GS::Array<GS::ObjectState> holeCoordinates;
        if (HoleCoordinates (hole, holeCoordinates) && holeCoordinates.GetSize () >= 3) {
            totalCoords += static_cast<Int32> (holeCoordinates.GetSize ()) + 1;
            holeList.Push (holeCoordinates);
        }
    }
    const Int32 nSubPolys = 1 + static_cast<Int32> (holeList.GetSize ());

    memo.coords = reinterpret_cast<API_Coord**> (BMAllocateHandle ((totalCoords + 1) * sizeof (API_Coord), ALLOCATE_CLEAR, 0));
    memo.pends = reinterpret_cast<Int32**> (BMAllocateHandle ((nSubPolys + 1) * sizeof (Int32), ALLOCATE_CLEAR, 0));
    memo.parcs = reinterpret_cast<API_PolyArc**> (BMAllocateHandle (0 * sizeof (API_PolyArc), ALLOCATE_CLEAR, 0));
    memo.vertexIDs = reinterpret_cast<UInt32**> (BMAllocateHandle ((totalCoords + 1) * sizeof (UInt32), ALLOCATE_CLEAR, 0));
    if (memo.coords == nullptr || memo.pends == nullptr || memo.vertexIDs == nullptr) {
        return false;
    }

    Int32 maxContourUnique = static_cast<Int32> (outline.GetSize ());
    for (const GS::Array<GS::ObjectState>& holeCoordinates : holeList) {
        maxContourUnique = std::max (maxContourUnique, static_cast<Int32> (holeCoordinates.GetSize ()));
    }
    (*memo.coords)[0] = { 0.0, 0.0 };
    (*memo.vertexIDs)[0] = static_cast<UInt32> (maxContourUnique);
    (*memo.pends)[0] = 0;

    Int32 iCoord = 0;
    Int32 subPolyIndex = 1;
    auto writeContour = [&] (const GS::Array<GS::ObjectState>& contour) {
        const Int32 firstIndex = iCoord + 1;
        for (UIndex i = 0; i < contour.GetSize (); ++i) {
            ++iCoord;
            (*memo.coords)[iCoord] = Coordinate2D (contour[i]);
            (*memo.vertexIDs)[iCoord] = static_cast<UInt32> (i + 1);       // per contour opnieuw vanaf 1
        }
        ++iCoord;
        (*memo.coords)[iCoord] = (*memo.coords)[firstIndex];                // het sluitpunt
        (*memo.vertexIDs)[iCoord] = (*memo.vertexIDs)[firstIndex];
        (*memo.pends)[subPolyIndex++] = iCoord;
    };
    writeContour (outline);
    for (const GS::Array<GS::ObjectState>& holeCoordinates : holeList) {
        writeContour (holeCoordinates);
    }

    poly.nCoords = totalCoords;
    poly.nSubPolys = nSubPolys;
    poly.nArcs = 0;
    return true;
}

// Een kleur {red, green, blue} met waarden van 0 tot 1.
bool ReadColor (const GS::ObjectState& parameters, const char* field, API_RGBColor& color)
{
    GS::ObjectState colorObject;
    if (!parameters.Get (field, colorObject)) {
        return false;
    }
    color = {};
    colorObject.Get ("red", color.f_red);
    colorObject.Get ("green", color.f_green);
    colorObject.Get ("blue", color.f_blue);
    return true;
}

bool FillIndexOfGuid (const API_Guid& guid, API_AttributeIndex& index)
{
    API_Attribute attribute = {};
    attribute.header.typeID = API_FilltypeID;
    attribute.header.guid = guid;
    if (ACAPI_Attribute_Get (&attribute) != NoError) {
        return false;
    }
    index = attribute.header.index;
    return true;
}

// Gemeenschappelijk deel van CreatePolylines en CreateHatches: per item de standaardwaarden ophalen, de velden invullen,
// het element aanmaken en het geheugenblok opruimen. Alles in een ongedaan-te-maken blok.
class Create2DCommand : public CommandBase
{
public:
    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override final
    {
        GS::Array<GS::ObjectState> items;
        parameters.Get (ArrayField (), items);

        GS::ObjectState response;
        const auto& results = response.AddList<GS::ObjectState> ("elements");

        const GSErrCode undoErr = ACAPI_CallUndoableCommand (UndoText (), [&] () -> GSErrCode {
            for (const GS::ObjectState& item : items) {
                results (CreateOne (item));
            }
            return NoError;
        });
        if (undoErr != NoError) {
            return ErrorResponse (undoErr, "De elementen konden niet worden aangemaakt.");
        }
        return response;
    }

protected:
    virtual const char*         ArrayField () const = 0;
    virtual const char*         UndoText () const = 0;
    virtual API_ElemTypeID      TypeId () const = 0;
    virtual GS::UniString       Description () const = 0;
    // Vult de velden en het geheugenblok. Geeft een foutantwoord, of niets als alles goed ging.
    virtual GS::Optional<GS::ObjectState> Fill (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const = 0;

private:
    GS::ObjectState CreateOne (const GS::ObjectState& item) const
    {
        API_Element element = {};
        API_ElementMemo memo = {};
        element.header.type = TypeId ();
        GSErrCode err = ACAPI_Element_GetDefaults (&element, &memo);
        if (err != NoError) {
            ACAPI_DisposeElemMemoHdls (&memo);
            return ErrorResponse (err, GS::UniString ("De standaardwaarden van ") + Description () + " konden niet worden gelezen.");
        }

        // De velden die elk element deelt.
        item.Get ("floorInd", element.header.floorInd);
        Int32 layerIndex = 0;
        if (item.Get ("layerIndex", layerIndex) && layerIndex > 0) {
            element.header.layer = ACAPI_CreateAttributeIndex (layerIndex);
        }

        const GS::Optional<GS::ObjectState> fillError = Fill (element, memo, item);
        if (fillError.HasValue ()) {
            ACAPI_DisposeElemMemoHdls (&memo);
            return *fillError;
        }

        err = ACAPI_Element_Create (&element, &memo);
        ACAPI_DisposeElemMemoHdls (&memo);
        if (err != NoError) {
            return ErrorResponse (err, GS::UniString (Description ()) + " kon niet worden aangemaakt.");
        }

        // Het ID zetten gebeurt na het aanmaken. Lijnen, polylijnen, bogen, cirkels en splines hebben in Archicad geen
        // Element-ID (APIERR_BADELEMENTTYPE): dat is geen reden om het element te verwijderen; het wordt gemeld.
        GS::ObjectState created = ElementIdObject (element.header.guid);
        GS::UniString id;
        if (item.Get ("id", id) && !id.IsEmpty ()) {
            err = ChangeElementId (element.header.guid, id);
            if (err == APIERR_BADELEMENTTYPE) {
                created.Add ("idIgnored", true);
            } else if (err != NoError) {
                GS::Array<API_Guid> unfinished;
                unfinished.Push (element.header.guid);
                ACAPI_Element_Delete (unfinished);
                return ErrorResponse (err, GS::UniString ("Het ID van ") + Description () + " kon niet worden gezet; het element is weer verwijderd.");
            }
        }
        return created;
    }
};

// ---- CreatePolylines {polylinesData: [{floorInd, layerIndex, coordinates: [{x, y}], linePenIndex?, id?}]}
class CreatePolylinesCommand final : public Create2DCommand
{
public:
    virtual GS::String GetName () const override { return "CreatePolylines"; }

protected:
    virtual const char*     ArrayField () const override { return "polylinesData"; }
    virtual const char*     UndoText () const override { return "PDOK Import: polylijnen maken"; }
    virtual API_ElemTypeID  TypeId () const override { return API_PolyLineID; }
    virtual GS::UniString   Description () const override { return "De polylijn"; }

    virtual GS::Optional<GS::ObjectState> Fill (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const override
    {
        short linePenIndex = 0;
        if (item.Get ("linePenIndex", linePenIndex) && linePenIndex > 0) {
            element.polyLine.linePen.penIndex = linePenIndex;
            element.polyLine.linePen.colorOverridePenIndex = 0;
        }

        GS::Array<GS::ObjectState> coordinates;
        item.Get ("coordinates", coordinates);
        if (coordinates.GetSize () < 2) {
            return ErrorResponse (APIERR_BADPARS, "Een polylijn heeft minstens 2 punten nodig.");
        }
        BuildPolylineMemo (coordinates, element.polyLine.poly, memo);
        return {};
    }
};

// ---- CreateHatches {hatchesData: [{floorInd, layerIndex, coordinates, holes: [{polygonOutline}], contourPenIndex?,
//      fillPenIndex?, foregroundColor?: {red, green, blue}, fillId?: {guid}, id?}]}
class CreateHatchesCommand final : public Create2DCommand
{
public:
    virtual GS::String GetName () const override { return "CreateHatches"; }

protected:
    virtual const char*     ArrayField () const override { return "hatchesData"; }
    virtual const char*     UndoText () const override { return "PDOK Import: vlakken maken"; }
    virtual API_ElemTypeID  TypeId () const override { return API_HatchID; }
    virtual GS::UniString   Description () const override { return "Het vlak"; }

    virtual GS::Optional<GS::ObjectState> Fill (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const override
    {
        GS::Array<GS::ObjectState> coordinates;
        GS::Array<GS::ObjectState> holes;
        item.Get ("coordinates", coordinates);
        item.Get ("holes", holes);
        if (OpenOutline (coordinates).GetSize () < 3) {
            return ErrorResponse (APIERR_BADPARS, "De buitenrand van een vlak heeft minstens 3 punten nodig.");
        }
        for (const GS::ObjectState& hole : holes) {
            GS::Array<GS::ObjectState> holeCoordinates;
            if (!HoleCoordinates (hole, holeCoordinates) || holeCoordinates.GetSize () < 3) {
                return ErrorResponse (APIERR_BADPARS, "Elk gat heeft een polygonOutline met minstens 3 punten nodig.");
            }
        }
        if (!BuildHatchMemo (coordinates, holes, element.hatch.poly, memo)) {
            return ErrorResponse (APIERR_MEMFULL, "Het geheugen voor de omtrek van het vlak kon niet worden gereserveerd.");
        }

        short contourPenIndex = 0;
        if (item.Get ("contourPenIndex", contourPenIndex)) {
            element.hatch.contPen.penIndex = contourPenIndex;
            element.hatch.contPen.colorOverridePenIndex = 0;
        }
        short fillPenIndex = 0;
        if (item.Get ("fillPenIndex", fillPenIndex)) {
            element.hatch.fillPen.penIndex = fillPenIndex;
            element.hatch.fillPen.colorOverridePenIndex = 0;
            element.hatch.hatchFlags &= ~APIHatch_HasFgRGBColor;
        }
        // Een opgegeven kleur zet de kleur van de vulling en wint van de pen.
        if (ReadColor (item, "foregroundColor", element.hatch.foregroundRGB)) {
            element.hatch.hatchFlags |= APIHatch_HasFgRGBColor;
        }
        // Een opgegeven vulling (attribuut) zet ook het soort vlak op 'vulling'.
        const GS::ObjectState* fillId = item.Get ("fillId");
        if (fillId != nullptr) {
            API_AttributeIndex fillIndex;
            if (!FillIndexOfGuid (GuidOfObject (*fillId), fillIndex)) {
                return ErrorResponse (APIERR_BADID, "De vulling (fillId) bestaat niet in dit project.");
            }
            element.hatch.fillInd = fillIndex;
            element.hatch.hatchType = API_FillHatch;
        }
        return {};
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
    err |= Register<CreatePolylinesCommand> ();
    err |= Register<CreateHatchesCommand> ();
    return err;
}

}
