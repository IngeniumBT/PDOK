#include "Commands.hpp"

#include "Location.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <map>
#include <utility>

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

// ---- de gegevens van een mesh, voor GetDetailsOfElements: de omtrek met hoogtes (gesloten, zoals Archicad hem geeft), de gaten,
//      het niveau en de onderkant (skirt). De gaten staan als {polygonCoordinates}. Naar Tapirs GetPolygonsFromMemoCoords.
GS::ObjectState CoordinateWithZ (const API_Coord& coordinate, double z)
{
    GS::ObjectState state;
    state.Add ("x", coordinate.x);
    state.Add ("y", coordinate.y);
    state.Add ("z", z);
    return state;
}

GS::ObjectState MeshDetails (const API_Guid& guid)
{
    GS::ObjectState details;
    API_Element element = {};
    element.header.guid = guid;
    if (ACAPI_Element_Get (&element) != NoError) {
        return details;
    }
    details.Add ("level", element.mesh.level);
    details.Add ("skirtLevel", element.mesh.skirtLevel);
    details.Add ("skirtType", GS::UniString (element.mesh.skirt == 3 ? "SurfaceOnlyWithoutSkirt" : (element.mesh.skirt == 2 ? "WithSkirt" : "SolidBodyWithSkirt")));
    details.Add ("showLines", element.mesh.showLines != 0);

    API_ElementMemo memo = {};
    if (ACAPI_Element_GetMemo (guid, &memo, APIMemoMask_Polygon | APIMemoMask_MeshPolyZ) == NoError && memo.coords != nullptr && memo.meshPolyZ != nullptr) {
        const GSSize contourCount = memo.pends == nullptr ? 1 : BMhGetSize (reinterpret_cast<GSHandle> (memo.pends)) / sizeof (Int32) - 1;
        const auto& outline = details.AddList<GS::ObjectState> ("polygonCoordinates");
        const auto& holes = details.AddList<GS::ObjectState> ("holes");
        Int32 start = 1;
        for (GSIndex contour = 0; contour < contourCount; ++contour) {
            const Int32 end = memo.pends == nullptr ? static_cast<Int32> (BMhGetSize (reinterpret_cast<GSHandle> (memo.coords)) / sizeof (API_Coord)) - 1
                                                    : (*memo.pends)[contour + 1];
            if (contour == 0) {
                for (Int32 i = start; i <= end; ++i) {
                    outline (CoordinateWithZ ((*memo.coords)[i], (*memo.meshPolyZ)[i]));
                }
            } else {
                GS::ObjectState hole;
                const auto& holeCoordinates = hole.AddList<GS::ObjectState> ("polygonCoordinates");
                for (Int32 i = start; i <= end; ++i) {
                    holeCoordinates (CoordinateWithZ ((*memo.coords)[i], (*memo.meshPolyZ)[i]));
                }
                holes (hole);
            }
            start = end + 1;
        }
    }
    ACAPI_DisposeElemMemoHdls (&memo);
    return details;
}

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
        // Met withDetails false krijg je alleen type, laag, verdieping en ID: veel sneller als je de omtrek van meshes niet nodig hebt.
        bool withDetails = true;
        parameters.Get ("withDetails", withDetails);

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
            detail.Add ("details", (withDetails && head.type.typeID == API_MeshID) ? MeshDetails (guid) : GS::ObjectState ());
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
    // Een morph krijgt zijn geheugenblok niet uit de standaardwaarden (anders zou het oude lichaam lekken).
    virtual bool WantsDefaultMemo () const { return true; }
    // Een stap na het aanmaken, nog met het geheugenblok (bijvoorbeeld de oppervlakken per vlak van een morph).
    virtual GS::Optional<GS::ObjectState> AfterCreate (API_Element&, API_ElementMemo&, const GS::ObjectState&) const { return {}; }

private:
    GS::ObjectState CreateOne (const GS::ObjectState& item) const
    {
        API_Element element = {};
        API_ElementMemo memo = {};
        element.header.type = TypeId ();
        GSErrCode err = ACAPI_Element_GetDefaults (&element, WantsDefaultMemo () ? &memo : nullptr);
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
        if (err != NoError) {
            ACAPI_DisposeElemMemoHdls (&memo);
            return ErrorResponse (err, GS::UniString (Description ()) + " kon niet worden aangemaakt.");
        }
        const GS::Optional<GS::ObjectState> afterError = AfterCreate (element, memo, item);
        ACAPI_DisposeElemMemoHdls (&memo);
        if (afterError.HasValue ()) {
            return *afterError;
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


// ================================================================== groep 3 (deel 1): objecten (bibliotheekobjecten, bijvoorbeeld bomen)

// De hoogte (het niveau) van een verdieping, om een absolute hoogte om te rekenen naar een afstand tot die verdieping.
bool StoryLevel (short floorIndex, double& level)
{
    API_StoryInfo storyInfo = {};
    if (ACAPI_ProjectSetting_GetStorySettings (&storyInfo) != NoError) {
        return false;
    }
    bool found = false;
    if (storyInfo.data != nullptr) {
        const short numberOfStories = storyInfo.lastStory - storyInfo.firstStory + 1;
        for (short i = 0; i < numberOfStories; ++i) {
            if ((*storyInfo.data)[i].index == floorIndex) {
                level = (*storyInfo.data)[i].level;
                found = true;
                break;
            }
        }
    }
    BMKillHandle (reinterpret_cast<GSHandle*> (&storyInfo.data));
    return found;
}

bool EqualsIgnoreCase (const char* a, const char* b)
{
    while (*a != '\0' && *b != '\0') {
        if (std::tolower (static_cast<unsigned char> (*a)) != std::tolower (static_cast<unsigned char> (*b))) {
            return false;
        }
        ++a;
        ++b;
    }
    return *a == *b;
}

// Een getalparameter (bijvoorbeeld A, B of ZZYZX) van een bibliotheekobject zetten.
bool SetNumericParameter (API_AddParType** params, const char* name, double value)
{
    if (params == nullptr) {
        return false;
    }
    const GSSize count = BMGetHandleSize (reinterpret_cast<GSHandle> (params)) / sizeof (API_AddParType);
    for (GSIndex i = 0; i < count; ++i) {
        API_AddParType& parameter = (*params)[i];
        if (parameter.typeMod != API_ParArray && EqualsIgnoreCase (parameter.name, name)) {
            parameter.value.real = value;
            return true;
        }
    }
    return false;
}

// De eigen afmeting (A en B) van een bibliotheekobject. Blijft 1 als het object die niet heeft.
GSErrCode LibraryPartOwnSize (Int32 libInd, double& a, double& b)
{
    double libraryPartA = 0.0;
    double libraryPartB = 0.0;
    Int32 addParNum = 0;
    API_AddParType** addPars = nullptr;
    const GSErrCode err = ACAPI_LibraryPart_GetParams (libInd, &libraryPartA, &libraryPartB, &addParNum, &addPars);
    if (addPars != nullptr) {
        ACAPI_DisposeAddParHdl (&addPars);
    }
    if (err != NoError) {
        return err;
    }
    if (libraryPartA > 1e-6) {
        a = libraryPartA;
    }
    if (libraryPartB > 1e-6) {
        b = libraryPartB;
    }
    return NoError;
}

// De standaardparameters van het bibliotheekobject in het geheugenblok van het element zetten. Naar Tapirs LoadLibraryPartDefaults.
GSErrCode LoadLibraryPartDefaults (API_Element& element, API_ElementMemo& memo)
{
    double a = 0.0;
    double b = 0.0;
    Int32 addParNum = 0;
    API_AddParType** addPars = nullptr;
    const GSErrCode err = ACAPI_LibraryPart_GetParams (element.object.libInd, &a, &b, &addParNum, &addPars);
    if (err != NoError) {
        if (addPars != nullptr) {
            ACAPI_DisposeAddParHdl (&addPars);
        }
        return err;
    }
    if (memo.params != nullptr) {
        ACAPI_DisposeAddParHdl (&memo.params);
    }
    memo.params = addPars;

    // xRatio en yRatio zijn de afmeting zelf met useXYFixSize aan, anders de afmeting gedeeld door de eigen A en B.
    if (a > 1e-6) {
        element.object.xRatio = element.object.useXYFixSize ? a : 1.0;
        SetNumericParameter (memo.params, "A", a);
    }
    if (b > 1e-6) {
        element.object.yRatio = element.object.useXYFixSize ? b : 1.0;
        SetNumericParameter (memo.params, "B", b);
    }
    return NoError;
}

// ---- CreateObjects {objectsData: [{libraryPartName, coordinates: {x, y, z}, dimensions?: {x, y, z}, floorIndex?, layerIndex?,
//      angle?, id?}]}   z is een absolute hoogte; de add-on rekent die om naar de verdieping (floorIndex, standaard 0).
class CreateObjectsCommand final : public Create2DCommand
{
public:
    virtual GS::String GetName () const override { return "CreateObjects"; }

protected:
    virtual const char*     ArrayField () const override { return "objectsData"; }
    virtual const char*     UndoText () const override { return "PDOK Import: objecten plaatsen"; }
    virtual API_ElemTypeID  TypeId () const override { return API_ObjectID; }
    virtual GS::UniString   Description () const override { return "Het object"; }

    virtual GS::Optional<GS::ObjectState> Fill (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const override
    {
        // 1. het bibliotheekobject op naam zoeken
        GS::UniString name;
        if (!item.Get ("libraryPartName", name) || name.IsEmpty ()) {
            return ErrorResponse (APIERR_BADPARS, "libraryPartName ontbreekt.");
        }
        API_LibPart libPart = {};
        const USize maxNameLength = sizeof (libPart.docu_UName) / sizeof (libPart.docu_UName[0]) - 1;
        GS::ucscpy (libPart.docu_UName, name.ToUStr (0, GS::Min (name.GetLength (), maxNameLength)).Get ());
        GSErrCode err = ACAPI_LibraryPart_Search (&libPart, false, true);
        delete libPart.location;
        if (err != NoError) {
            return ErrorResponse (err, GS::UniString ("Het bibliotheekobject '") + name + "' is niet gevonden in de geladen bibliotheken.");
        }
        element.object.libInd = libPart.index;

        // 2. de standaardparameters van dat object
        err = LoadLibraryPartDefaults (element, memo);
        if (err != NoError) {
            return ErrorResponse (err, "De standaardparameters van het bibliotheekobject konden niet worden gelezen.");
        }

        // 3. positie: x en y, en een absolute hoogte die wordt omgerekend naar de verdieping
        GS::ObjectState coordinates;
        if (!item.Get ("coordinates", coordinates)) {
            return ErrorResponse (APIERR_BADPARS, "coordinates ontbreekt.");
        }
        double x = 0.0, y = 0.0, z = 0.0;
        coordinates.Get ("x", x);
        coordinates.Get ("y", y);
        coordinates.Get ("z", z);

        short floorIndex = 0;
        item.Get ("floorIndex", floorIndex);
        double storyLevel = 0.0;
        StoryLevel (floorIndex, storyLevel);       // onbekende verdieping: niveau 0
        element.header.floorInd = floorIndex;
        element.object.pos.x = x;
        element.object.pos.y = y;
        element.object.level = z - storyLevel;

        // 4. afmetingen (A, B en ZZYZX)
        GS::ObjectState dimensions;
        if (item.Get ("dimensions", dimensions)) {
            double dx = 0.0, dy = 0.0, dz = 0.0;
            dimensions.Get ("x", dx);
            dimensions.Get ("y", dy);
            dimensions.Get ("z", dz);

            double ownA = 1.0;
            double ownB = 1.0;
            if (!element.object.useXYFixSize) {
                err = LibraryPartOwnSize (element.object.libInd, ownA, ownB);
                if (err != NoError) {
                    return ErrorResponse (err, "De eigen afmeting (A en B) van het bibliotheekobject kon niet worden gelezen.");
                }
            }
            element.object.xRatio = dx / ownA;
            element.object.yRatio = dy / ownB;
            SetNumericParameter (memo.params, "A", dx);
            SetNumericParameter (memo.params, "B", dy);
            SetNumericParameter (memo.params, "ZZYZX", dz);
        }

        // 5. draaiing (in radialen)
        double angle = 0.0;
        if (item.Get ("angle", angle)) {
            element.object.angle = angle;
        }
        return {};
    }
};


// ================================================================== groep 2 (deel 2): teksten

// Een tekst bestaat in Archicad uit het tekstblok, een alinea met een stuk opmaak (run) en de regeleinden (eolPos).
// Naar Tapirs SetParagraph, SetRun, SetEOL en SetLineEnds.
GSErrCode SetParagraph (API_ParagraphType** paragraph, UInt32 parNum, Int32 from, Int32 range, Int32 numOfTabs, Int32 numOfRuns, Int32 numOfEolPos)
{
    if (paragraph == nullptr || parNum >= (BMhGetSize (reinterpret_cast<GSHandle> (paragraph)) / sizeof (API_ParagraphType))) {
        return APIERR_BADPARS;
    }
    if (numOfTabs < 1 || numOfRuns < 1 || numOfEolPos < 0) {
        return APIERR_BADPARS;
    }
    (*paragraph)[parNum].from = from;
    (*paragraph)[parNum].range = range;
    (*paragraph)[parNum].tab = reinterpret_cast<API_TabType*> (BMpAllClear (numOfTabs * sizeof (API_TabType)));
    (*paragraph)[parNum].run = reinterpret_cast<API_RunType*> (BMpAllClear (numOfRuns * sizeof (API_RunType)));
    if (numOfEolPos > 0) {
        (*paragraph)[parNum].eolPos = reinterpret_cast<Int32*> (BMpAllClear (numOfEolPos * sizeof (Int32)));
    }
    return NoError;
}

GSErrCode SetRun (API_ParagraphType** paragraph, UInt32 parNum, UInt32 runNum, Int32 from, Int32 range, short pen, unsigned short faceBits,
                  short font, Int32 effectBits, double size)
{
    if (paragraph == nullptr || parNum >= (BMhGetSize (reinterpret_cast<GSHandle> (paragraph)) / sizeof (API_ParagraphType))) {
        return APIERR_BADPARS;
    }
    if (runNum >= BMGetPtrSize (reinterpret_cast<GSPtr> ((*paragraph)[parNum].run)) / sizeof (API_RunType)) {
        return APIERR_BADPARS;
    }
    (*paragraph)[parNum].run[runNum].from = from;
    (*paragraph)[parNum].run[runNum].range = range;
    (*paragraph)[parNum].run[runNum].pen = pen;
    (*paragraph)[parNum].run[runNum].faceBits = faceBits;
    (*paragraph)[parNum].run[runNum].font = font;
    (*paragraph)[parNum].run[runNum].effectBits = static_cast<unsigned short> (effectBits);
    (*paragraph)[parNum].run[runNum].size = size;
    return NoError;
}

GSErrCode SetEndOfLine (API_ParagraphType** paragraph, UInt32 parNum, UInt32 eolNum, Int32 offset)
{
    if (paragraph == nullptr || parNum >= (BMhGetSize (reinterpret_cast<GSHandle> (paragraph)) / sizeof (API_ParagraphType))) {
        return APIERR_BADPARS;
    }
    if (eolNum >= BMGetPtrSize (reinterpret_cast<GSPtr> ((*paragraph)[parNum].eolPos)) / sizeof (Int32)) {
        return APIERR_BADPARS;
    }
    if (offset < 0) {
        return APIERR_BADPARS;
    }
    (*paragraph)[parNum].eolPos[eolNum] = offset;
    return NoError;
}

// Per regel de positie van het laatste teken, groeiend van regel tot regel (zie Tapirs toelichting, #2461).
void SetLineEnds (API_ParagraphType** paragraph, const GS::UniString& text, Int32 nLine)
{
    const GS::UniChar newlineChar = GS::UniChar (char ('\n'));
    const Int32 textLength = static_cast<Int32> (text.GetLength ());
    Int32 lineStart = 0;
    for (Int32 eolIndex = 0; eolIndex < nLine; ++eolIndex) {
        const UIndex newlinePos = (lineStart < textLength) ? text.FindFirst (newlineChar, static_cast<UIndex> (lineStart)) : MaxUIndex;
        const Int32 lineEnd = (newlinePos != MaxUIndex) ? static_cast<Int32> (newlinePos) : textLength;
        SetEndOfLine (paragraph, 0, static_cast<UInt32> (eolIndex), GS::Max (lineEnd - 1, static_cast<Int32> (0)));
        lineStart = lineEnd + 1;
    }
}

// ---- CreateTexts {textsData: [{text, coordinate: {x, y}, floorIndex?, layerIndex?, height?, pen?, angle?, justification?, id?}]}
class CreateTextsCommand final : public Create2DCommand
{
public:
    virtual GS::String GetName () const override { return "CreateTexts"; }

protected:
    virtual const char*     ArrayField () const override { return "textsData"; }
    virtual const char*     UndoText () const override { return "PDOK Import: teksten maken"; }
    virtual API_ElemTypeID  TypeId () const override { return API_TextID; }
    virtual GS::UniString   Description () const override { return "De tekst"; }

    virtual GS::Optional<GS::ObjectState> Fill (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const override
    {
        const GS::ObjectState* coordinate = item.Get ("coordinate");
        if (coordinate == nullptr) {
            return ErrorResponse (APIERR_BADPARS, "coordinate ontbreekt.");
        }
        GS::UniString text;
        if (!item.Get ("text", text)) {
            return ErrorResponse (APIERR_BADPARS, "text ontbreekt.");
        }
        text.ReplaceAll ("\r\n", "\n");
        text.ReplaceAll ("\r", "\n");

        short floorIndex = 0;
        if (item.Get ("floorIndex", floorIndex)) {
            element.header.floorInd = floorIndex;
        }
        coordinate->Get ("x", element.text.loc.x);
        coordinate->Get ("y", element.text.loc.y);

        item.Get ("height", element.text.size);
        item.Get ("pen", element.text.pen);
        item.Get ("angle", element.text.angle);
        GS::UniString justification;
        if (item.Get ("justification", justification)) {
            element.text.just = justification == "Center" ? APIJust_Center : (justification == "Right" ? APIJust_Right : APIJust_Left);
        }

        // De inhoud: het tekstblok, een alinea met een run, en de regeleinden.
        delete memo.textContent;
        memo.textContent = new GS::UniString { text };

        const GS::UniChar newlineChar = GS::UniChar (char ('\n'));
        element.text.nLine = text.Count (newlineChar) + 1;

        // Oude alinea's en regelstarten (voor de standaardinhoud) moeten weg voordat de nieuwe inhoud erin komt.
        if (memo.paragraphs != nullptr) {
            ACAPI_DisposeParagraphsHdl (&memo.paragraphs);
            memo.paragraphs = nullptr;
        }
        if (memo.textLineStarts != nullptr) {
            BMKillHandle (reinterpret_cast<GSHandle*> (&memo.textLineStarts));
        }

        memo.paragraphs = reinterpret_cast<API_ParagraphType**> (BMhAll (1 * sizeof (API_ParagraphType)));
        SetParagraph (memo.paragraphs, 0, 0, static_cast<Int32> (text.GetLength ()), 1, 1, element.text.nLine);
        (*memo.paragraphs)[0].just = element.text.just;
        SetRun (memo.paragraphs, 0, 0, 0, static_cast<Int32> (text.GetLength ()), element.text.pen, element.text.faceBits,
                element.text.font, element.text.effectsBits, element.text.size);
        SetLineEnds (memo.paragraphs, text, element.text.nLine);

        // Automatische breedte, een stijl per run (zonder dit maakt Archicad een run in de elementstijl).
        element.text.width = 0;
        element.text.height = 0;
        element.text.nonBreaking = true;
        element.text.multiStyle = true;
        element.text.useEolPos = true;
        return {};
    }
};


// ================================================================== groep 3 (deel 2): oppervlakken en morphs (gebouwen)

// Een attribuut (bijvoorbeeld een oppervlak) opzoeken aan de hand van {"guid": "..."}.
bool ResolveAttributeIndex (const GS::ObjectState& attributeId, API_AttrTypeID type, API_AttributeIndex& index)
{
    API_Attribute attribute = {};
    attribute.header.typeID = type;
    attribute.header.guid = GuidOfObject (attributeId);
    if (attribute.header.guid == APINULLGuid || ACAPI_Attribute_Get (&attribute) != NoError) {
        return false;
    }
    index = attribute.header.index;
    return true;
}

API_Coord3D Coordinate3D (const GS::ObjectState& os)
{
    API_Coord3D coordinate = {};
    os.Get ("x", coordinate.x);
    os.Get ("y", coordinate.y);
    os.Get ("z", coordinate.z);
    return coordinate;
}

// De verdieping bij een absolute hoogte: de hoogste verdieping waarvan het niveau niet boven die hoogte ligt,
// en anders de laagste. Naar Tapirs GetFloorIndexAndOffset.
short FloorIndexOfZ (double z)
{
    API_StoryInfo storyInfo = {};
    short result = 0;
    if (ACAPI_ProjectSetting_GetStorySettings (&storyInfo) != NoError) {
        return result;
    }
    if (storyInfo.data != nullptr) {
        const short numberOfStories = storyInfo.lastStory - storyInfo.firstStory + 1;
        bool found = false;
        double bestLevel = 0.0;
        short lowest = 0;
        double lowestLevel = 0.0;
        for (short i = 0; i < numberOfStories; ++i) {
            const short index = (*storyInfo.data)[i].index;
            const double level = (*storyInfo.data)[i].level;
            if (level <= z && (!found || level >= bestLevel)) {
                result = index;
                bestLevel = level;
                found = true;
            }
            if (i == 0 || level < lowestLevel) {
                lowest = index;
                lowestLevel = level;
            }
        }
        if (!found) {
            result = lowest;
        }
    }
    BMKillHandle (reinterpret_cast<GSHandle*> (&storyInfo.data));
    return result;
}

// ---- EnsureSurface {name, update?, materialType?, ambientReflection?, diffuseReflection?, specularReflection?, transparency?,
//      shine?, transparencyAttenuation?, emissionAttenuation?, surfaceColor?, specularColor?, emissionColor?}
//      -> {attributeId, created, updated}
//      Een bestaand oppervlak blijft ongemoeid, behalve met update of als het nog nulwaarden heeft (dan is het zwart).
class EnsureSurfaceCommand final : public CommandBase
{
public:
    virtual GS::String GetName () const override { return "EnsureSurface"; }

    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const override
    {
        GS::UniString name;
        if (!parameters.Get ("name", name) || name.IsEmpty ()) {
            return ErrorResponse (APIERR_BADPARS, "De parameter name ontbreekt.");
        }
        bool update = false;
        parameters.Get ("update", update);

        GS::UniString lookupName = name;
        API_Attribute attribute = {};
        attribute.header.typeID = API_MaterialID;
        attribute.header.uniStringNamePtr = &lookupName;
        const bool exists = ACAPI_Attribute_Get (&attribute) == NoError;
        const bool emptyValues = exists && attribute.material.diffusePc == 0 && attribute.material.ambientPc == 0;

        if (exists && !update && !emptyValues) {
            GS::ObjectState existing;
            existing.Add ("attributeId", GuidObject (attribute.header.guid));
            existing.Add ("created", false);
            existing.Add ("updated", false);
            return existing;
        }

        if (!exists) {
            attribute = {};
            attribute.header.typeID = API_MaterialID;
            GS::UniString newName = name;
            attribute.header.uniStringNamePtr = &newName;
            attribute.material.mtype = APIMater_GeneralID;
            ApplyFields (parameters, attribute);
            API_AttributeDef definition = {};
            const GSErrCode err = ACAPI_Attribute_Create (&attribute, &definition);
            ACAPI_DisposeAttrDefsHdls (&definition);
            if (err != NoError) {
                return ErrorResponse (err, GS::UniString ("Het oppervlak '") + name + "' kon niet worden aangemaakt.");
            }
            GS::ObjectState created;
            created.Add ("attributeId", GuidObject (attribute.header.guid));
            created.Add ("created", true);
            created.Add ("updated", false);
            return created;
        }

        ApplyFields (parameters, attribute);
        API_AttributeDef definition = {};
        const GSErrCode err = ACAPI_Attribute_Modify (&attribute, &definition);
        ACAPI_DisposeAttrDefsHdls (&definition);
        if (err != NoError) {
            return ErrorResponse (err, GS::UniString ("Het oppervlak '") + name + "' kon niet worden bijgewerkt.");
        }
        GS::ObjectState updated;
        updated.Add ("attributeId", GuidObject (attribute.header.guid));
        updated.Add ("created", false);
        updated.Add ("updated", true);
        return updated;
    }

private:
    static void ApplyFields (const GS::ObjectState& parameters, API_Attribute& attribute)
    {
        // Als getal gelezen (niet als short): een JSON-getal wordt als double bewaard (zie Tapirs toelichting bij CreateSurfaces).
        double value = 0.0;
        if (parameters.Get ("ambientReflection", value)) { attribute.material.ambientPc = static_cast<short> (value); }
        if (parameters.Get ("diffuseReflection", value)) { attribute.material.diffusePc = static_cast<short> (value); }
        if (parameters.Get ("specularReflection", value)) { attribute.material.specularPc = static_cast<short> (value); }
        if (parameters.Get ("transparency", value)) { attribute.material.transpPc = static_cast<short> (value); }
        if (parameters.Get ("shine", value)) { attribute.material.shine = static_cast<short> (value); }
        if (parameters.Get ("transparencyAttenuation", value)) { attribute.material.transpAtt = static_cast<short> (value); }
        if (parameters.Get ("emissionAttenuation", value)) { attribute.material.emissionAtt = static_cast<short> (value); }
        ReadColor (parameters, "surfaceColor", attribute.material.surfaceRGB);
        ReadColor (parameters, "specularColor", attribute.material.specularRGB);
        ReadColor (parameters, "emissionColor", attribute.material.emissionRGB);
    }
};

// De rand tussen twee hoekpunten hergebruiken: twee aangrenzende vlakken delen dezelfde rand, in tegengestelde richting.
// Naar Tapirs GetOrAddEdge (het DevKit eist: "an edge can be used with at most 2 polygons, in opposite directions").
Int32 GetOrAddEdge (void* bodyData, UInt32 a, UInt32 b, std::map<std::pair<UInt32, UInt32>, Int32>& edgeCache)
{
    const bool flipped = a > b;
    const std::pair<UInt32, UInt32> key = flipped ? std::make_pair (b, a) : std::make_pair (a, b);
    const auto found = edgeCache.find (key);
    if (found != edgeCache.end ()) {
        return flipped ? -found->second : found->second;
    }
    Int32 index = 0;
    ACAPI_Body_AddEdge (bodyData, key.first, key.second, index);
    edgeCache[key] = index;
    return flipped ? -index : index;
}

struct BodyHolder
{
    void* data = nullptr;
    ~BodyHolder ()
    {
        if (data != nullptr) {
            ACAPI_Body_Dispose (&data);
        }
    }
};

// Bouwt het lichaam van een morph uit {vertices: [{x, y, z}], polygons: [{vertexIds, surfaceId?, holes?: [{vertexIds}]}]}.
// Naar Tapirs BuildMorphBodyFromGeometry (zonder draadranden).
bool BuildMorphBody (const GS::ObjectState& bodyOS, API_ElementMemo& memo, GS::UniString& errorOut, bool& hasFaceSurfaces)
{
    hasFaceSurfaces = false;
    GS::Array<GS::ObjectState> verticesOS;
    GS::Array<GS::ObjectState> polygonsOS;
    bodyOS.Get ("vertices", verticesOS);
    bodyOS.Get ("polygons", polygonsOS);

    GS::UniString bodyTypeText;
    bodyOS.Get ("bodyType", bodyTypeText);
    if (bodyTypeText == "Surface") {
        if (verticesOS.GetSize () < 3 || polygonsOS.GetSize () < 1) {
            errorOut = "Een open lichaam heeft minstens 3 hoekpunten en 1 vlak nodig.";
            return false;
        }
    } else if (verticesOS.GetSize () < 4 || polygonsOS.GetSize () < 4) {
        errorOut = "Een gesloten lichaam heeft minstens 4 hoekpunten en 4 vlakken nodig.";
        return false;
    }

    BodyHolder body;
    if (ACAPI_Body_Create (nullptr, nullptr, &body.data) != NoError || body.data == nullptr) {
        errorOut = "Het lichaam van de morph kon niet worden gestart.";
        return false;
    }

    GS::Array<UInt32> vertexIndices;
    vertexIndices.SetSize (verticesOS.GetSize ());      // SetSize, niet de constructor met een getal (dat reserveert alleen)
    for (UIndex i = 0; i < verticesOS.GetSize (); ++i) {
        UInt32 index = 0;
        ACAPI_Body_AddVertex (body.data, Coordinate3D (verticesOS[i]), index);
        vertexIndices[i] = index;
    }

    std::map<std::pair<UInt32, UInt32>, Int32> edgeCache;
    auto resolveLoop = [&] (const GS::Array<Int32>& loop, GS::Array<Int32>& edgeIndices) -> bool {
        for (UIndex i = 0; i < loop.GetSize (); ++i) {
            const Int32 from = loop[i];
            const Int32 to = loop[(i + 1) % loop.GetSize ()];
            if (from < 0 || static_cast<UIndex> (from) >= vertexIndices.GetSize () || to < 0 || static_cast<UIndex> (to) >= vertexIndices.GetSize ()) {
                return false;
            }
            edgeIndices.Push (GetOrAddEdge (body.data, vertexIndices[from], vertexIndices[to], edgeCache));
        }
        return true;
    };

    for (const GS::ObjectState& polygonOS : polygonsOS) {
        GS::Array<Int32> outer;
        polygonOS.Get ("vertexIds", outer);
        if (outer.GetSize () < 3) {
            errorOut = "Elk vlak heeft minstens 3 hoekpunten nodig.";
            return false;
        }
        GS::Array<Int32> edgeIndices;
        if (!resolveLoop (outer, edgeIndices)) {
            errorOut = "Een vlak verwijst naar een hoekpunt dat niet bestaat.";
            return false;
        }

        GS::Array<GS::ObjectState> holesOS;
        if (polygonOS.Get ("holes", holesOS)) {
            for (const GS::ObjectState& holeOS : holesOS) {
                GS::Array<Int32> hole;
                holeOS.Get ("vertexIds", hole);
                if (hole.GetSize () < 3) {
                    errorOut = "Elk gat heeft minstens 3 hoekpunten nodig.";
                    return false;
                }
                edgeIndices.Push (0);                               // 0 scheidt de buitenrand van een gat
                if (!resolveLoop (hole, edgeIndices)) {
                    errorOut = "Een gat verwijst naar een hoekpunt dat niet bestaat.";
                    return false;
                }
            }
        }

        // Het oppervlak van dit vlak (een surface, geen bouwmateriaal); zonder oppervlak erft het vlak dat van de morph.
        API_OverriddenAttribute material = {};
        const GS::ObjectState* faceSurface = polygonOS.Get ("surfaceId");
        if (faceSurface != nullptr) {
            API_AttributeIndex faceSurfaceIndex = APIInvalidAttributeIndex;
            if (!ResolveAttributeIndex (*faceSurface, API_MaterialID, faceSurfaceIndex)) {
                errorOut = "Een vlak verwijst naar een oppervlak dat niet bestaat.";
                return false;
            }
            material = faceSurfaceIndex;
            hasFaceSurfaces = true;
        }

        UInt32 polygonIndex = 0;
        if (ACAPI_Body_AddPolygon (body.data, edgeIndices, 0, material, polygonIndex) != NoError) {
            errorOut = "Een vlak van de morph kon niet worden opgebouwd (controleer de volgorde van de hoekpunten).";
            return false;
        }
    }

    if (ACAPI_Body_Finish (body.data, &memo.morphBody, &memo.morphMaterialMapTable) != NoError) {
        errorOut = "Het lichaam van de morph kon niet worden afgerond.";
        return false;
    }
    return true;
}

// ---- CreateMorphs {morphsData: [{basePoint: {x, y, z}, body: {bodyType?, vertices, polygons}, layerIndex?, floorIndex?, id?}]}
//      De hoekpunten staan in lokale coordinaten; het basispunt is een absolute plek (z in NAP).
class CreateMorphsCommand final : public Create2DCommand
{
public:
    virtual GS::String GetName () const override { return "CreateMorphs"; }

protected:
    virtual const char*     ArrayField () const override { return "morphsData"; }
    virtual const char*     UndoText () const override { return "PDOK Import: morphs maken"; }
    virtual API_ElemTypeID  TypeId () const override { return API_MorphID; }
    virtual GS::UniString   Description () const override { return "De morph"; }
    virtual bool            WantsDefaultMemo () const override { return false; }

    virtual GS::Optional<GS::ObjectState> Fill (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const override
    {
        const GS::ObjectState* basePointOS = item.Get ("basePoint");
        const GS::ObjectState* bodyOS = item.Get ("body");
        if (basePointOS == nullptr || bodyOS == nullptr) {
            return ErrorResponse (APIERR_BADPARS, "basePoint en body zijn verplicht.");
        }
        const API_Coord3D basePoint = Coordinate3D (*basePointOS);

        // Zonder floorIndex hoort de morph bij de verdieping waarin zijn basispunt ligt.
        short floorIndex = 0;
        if (!item.Get ("floorIndex", floorIndex)) {
            floorIndex = FloorIndexOfZ (basePoint.z);
        }
        element.header.floorInd = floorIndex;

        // Geen draaiing, alleen een verplaatsing naar het basispunt (de z is absoluut).
        double* tmx = element.morph.tranmat.tmx;
        tmx[0] = 1.0;  tmx[4] = 0.0;  tmx[8] = 0.0;
        tmx[1] = 0.0;  tmx[5] = 1.0;  tmx[9] = 0.0;
        tmx[2] = 0.0;  tmx[6] = 0.0;  tmx[10] = 1.0;
        tmx[3] = basePoint.x;
        tmx[7] = basePoint.y;
        tmx[11] = basePoint.z;

        bool hasFaceSurfaces = false;
        GS::UniString bodyError;
        if (!BuildMorphBody (*bodyOS, memo, bodyError, hasFaceSurfaces)) {
            return ErrorResponse (APIERR_GENERAL, bodyError);
        }
        GS::UniString bodyType;
        element.morph.bodyType = (bodyOS->Get ("bodyType", bodyType) && bodyType == "Surface") ? APIMorphBodyType_SurfaceBody
                                                                                               : APIMorphBodyType_SolidBody;
        return {};
    }

    // ACAPI_Element_Create bewaart de oppervlakken per vlak niet: het lichaam wordt daarna nog eens geschreven
    // (zoals Tapir en het Element_Test-voorbeeld van het DevKit doen).
    virtual GS::Optional<GS::ObjectState> AfterCreate (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const override
    {
        const GS::ObjectState* bodyOS = item.Get ("body");
        bool hasFaceSurfaces = false;
        if (bodyOS != nullptr) {
            GS::Array<GS::ObjectState> polygons;
            bodyOS->Get ("polygons", polygons);
            for (const GS::ObjectState& polygon : polygons) {
                if (polygon.Get ("surfaceId") != nullptr) {
                    hasFaceSurfaces = true;
                    break;
                }
            }
        }
        if (!hasFaceSurfaces) {
            return {};
        }
        API_Element emptyMask = {};
        ACAPI_ELEMENT_MASK_CLEAR (emptyMask);
        const GSErrCode err = ACAPI_Element_Change (&element, &emptyMask, &memo, APIMemoMask_All, true);
        if (err != NoError) {
            return ErrorResponse (err, "De morph is gemaakt, maar de oppervlakken per vlak konden niet worden gezet.");
        }
        return {};
    }
};


// ================================================================== groep 3 (deel 3): meshes (terrein)

// Een geheugenblok reserveren, of vergroten als het er al is (de standaardwaarden van een mesh brengen er al mee).
template <class T>
void EnsureHandle (T**& handle, size_t bytes)
{
    handle = reinterpret_cast<T**> (handle == nullptr ? BMAllocateHandle (bytes, ALLOCATE_CLEAR, 0)
                                                      : BMReallocHandle (reinterpret_cast<GSHandle> (handle), bytes, REALLOC_CLEAR, 0));
}

// De omtrek van een mesh (met een hoogte z per punt) en zijn gaten. Naar Tapirs BuildMeshPolyMemoFromGeometry en AddPolyToMemo:
// de punten beginnen bij index 1, elke contour (de buitenrand en elk gat) herhaalt zijn eerste punt als sluitpunt, en
// meshPolyZ bevat de hoogte van elk punt.
bool BuildMeshPolygon (const GS::Array<GS::ObjectState>& outlineIn, const GS::Array<GS::ObjectState>& holes, API_Element& element, API_ElementMemo& memo)
{
    const GS::Array<GS::ObjectState> outline = OpenOutline (outlineIn);
    GS::Array<GS::Array<GS::ObjectState>> holeList;
    Int32 nCoords = static_cast<Int32> (outline.GetSize ()) + 1;
    for (const GS::ObjectState& hole : holes) {
        GS::Array<GS::ObjectState> holeCoordinates;
        if (HoleCoordinates (hole, holeCoordinates) && holeCoordinates.GetSize () >= 3) {
            nCoords += static_cast<Int32> (holeCoordinates.GetSize ()) + 1;
            holeList.Push (holeCoordinates);
        }
    }
    const Int32 nSubPolys = 1 + static_cast<Int32> (holeList.GetSize ());

    element.mesh.poly.nCoords = nCoords;
    element.mesh.poly.nSubPolys = nSubPolys;
    element.mesh.poly.nArcs = 0;

    EnsureHandle (memo.coords, (nCoords + 1) * sizeof (API_Coord));
    EnsureHandle (memo.meshPolyZ, (nCoords + 1) * sizeof (double));
    EnsureHandle (memo.pends, (nSubPolys + 1) * sizeof (Int32));
    if (memo.parcs != nullptr) {
        BMKillHandle (reinterpret_cast<GSHandle*> (&memo.parcs));
        memo.parcs = nullptr;
    }
    if (memo.vertexIDs != nullptr) {
        EnsureHandle (memo.vertexIDs, (nCoords + 1) * sizeof (UInt32));
    }
    if (memo.coords == nullptr || memo.meshPolyZ == nullptr || memo.pends == nullptr) {
        return false;
    }

    Int32 iCoord = 1;
    Int32 iPends = 1;
    auto writeContour = [&] (const GS::Array<GS::ObjectState>& contour) {
        const Int32 start = iCoord;
        for (const GS::ObjectState& c : contour) {
            (*memo.coords)[iCoord] = Coordinate2D (c);
            double z = 0.0;
            c.Get ("z", z);
            (*memo.meshPolyZ)[iCoord] = z;
            ++iCoord;
        }
        (*memo.coords)[iCoord] = (*memo.coords)[start];            // het sluitpunt
        (*memo.meshPolyZ)[iCoord] = (*memo.meshPolyZ)[start];
        (*memo.pends)[iPends++] = iCoord;
        ++iCoord;
    };
    writeContour (outline);
    for (const GS::Array<GS::ObjectState>& holeCoordinates : holeList) {
        writeContour (holeCoordinates);
    }
    return true;
}

// De extra hoogtepunten (sublines) binnen de mesh. Naar Tapirs BuildMeshSublinesMemoFromGeometry.
void BuildMeshSublines (const GS::Array<GS::ObjectState>& sublines, API_Element& element, API_ElementMemo& memo)
{
    Int32 totalCoords = 0;
    Int32 lineCount = 0;
    for (const GS::ObjectState& subline : sublines) {
        GS::Array<GS::ObjectState> coordinates;
        if (subline.Get ("coordinates", coordinates) && !coordinates.IsEmpty ()) {
            totalCoords += static_cast<Int32> (coordinates.GetSize ());
            ++lineCount;
        }
    }
    element.mesh.levelLines.nCoords = totalCoords;
    element.mesh.levelLines.nSubLines = lineCount;

    EnsureHandle (memo.meshLevelCoords, totalCoords * sizeof (API_MeshLevelCoord));
    EnsureHandle (memo.meshLevelEnds, lineCount * sizeof (Int32));

    Int32 iCoord = 0;
    Int32 iLine = 0;
    for (const GS::ObjectState& subline : sublines) {
        GS::Array<GS::ObjectState> coordinates;
        if (!subline.Get ("coordinates", coordinates) || coordinates.IsEmpty ()) {
            continue;
        }
        for (const GS::ObjectState& c : coordinates) {
            (*memo.meshLevelCoords)[iCoord].c = Coordinate3D (c);
            ++iCoord;
        }
        (*memo.meshLevelEnds)[iLine++] = iCoord;
    }
}

// Een oppervlak van een mesh: {overridden, attributeId: {guid}}. Overridden false laat het oppervlak van het gereedschap staan.
bool ReadOverriddenSurface (const GS::ObjectState& item, const char* key, API_OverriddenAttribute& target, GS::UniString& errorOut)
{
    GS::ObjectState materialOs;
    if (!item.Get (key, materialOs)) {
        return true;
    }
    bool overridden = true;
    materialOs.Get ("overridden", overridden);
    if (!overridden) {
        target = API_OverriddenAttribute ();
        return true;
    }
    GS::ObjectState attributeId;
    API_AttributeIndex index = APIInvalidAttributeIndex;
    if (!materialOs.Get ("attributeId", attributeId) || !ResolveAttributeIndex (attributeId, API_MaterialID, index)) {
        errorOut = GS::UniString ("Het oppervlak in ") + key + " bestaat niet in dit project.";
        return false;
    }
    target = index;
    return true;
}

// ---- CreateMeshes {meshesData: [{polygonCoordinates: [{x, y, z}], holes?: [{polygonCoordinates}], sublines?: [{coordinates: [{x, y, z}]}],
//      level?, floorIndex?, skirtType?, skirtLevel?, ridges?, showLines?, contourPen?, levelPen?, topMaterial?, sideMaterial?,
//      bottomMaterial?, layerIndex?, id?}]}
class CreateMeshesCommand final : public Create2DCommand
{
public:
    virtual GS::String GetName () const override { return "CreateMeshes"; }

protected:
    virtual const char*     ArrayField () const override { return "meshesData"; }
    virtual const char*     UndoText () const override { return "PDOK Import: meshes maken"; }
    virtual API_ElemTypeID  TypeId () const override { return API_MeshID; }
    virtual GS::UniString   Description () const override { return "De mesh"; }

    virtual GS::Optional<GS::ObjectState> Fill (API_Element& element, API_ElementMemo& memo, const GS::ObjectState& item) const override
    {
        item.Get ("floorIndex", element.header.floorInd);
        item.Get ("level", element.mesh.level);
        item.Get ("skirtLevel", element.mesh.skirtLevel);

        GS::UniString skirtType;
        if (item.Get ("skirtType", skirtType)) {
            if (skirtType == "SurfaceOnlyWithoutSkirt") {
                element.mesh.skirt = 3;
            } else if (skirtType == "WithSkirt") {
                element.mesh.skirt = 2;
            } else if (skirtType == "SolidBodyWithSkirt") {
                element.mesh.skirt = 1;
            }
        }
        GS::UniString ridges;
        if (item.Get ("ridges", ridges)) {
            if (ridges == "AllSharp") {
                element.mesh.smoothRidges = APIRidge_AllSharp;
            } else if (ridges == "AllSmooth") {
                element.mesh.smoothRidges = APIRidge_AllSmooth;
            } else if (ridges == "UserDefined") {
                element.mesh.smoothRidges = APIRidge_UserSharp;
            }
        }
        bool showLines = false;
        if (item.Get ("showLines", showLines)) {
            element.mesh.showLines = showLines ? 1 : 0;
        }
        short pen = 0;
        if (item.Get ("contourPen", pen) && pen > 0) {
            element.mesh.contPen = pen;
        }
        if (item.Get ("levelPen", pen) && pen > 0) {
            element.mesh.levelPen = pen;
        }

        GS::Array<GS::ObjectState> coordinates;
        GS::Array<GS::ObjectState> holes;
        item.Get ("polygonCoordinates", coordinates);
        item.Get ("holes", holes);
        if (OpenOutline (coordinates).GetSize () < 3) {
            return ErrorResponse (APIERR_BADPARS, "polygonCoordinates moet minstens 3 punten bevatten.");
        }
        if (!BuildMeshPolygon (coordinates, holes, element, memo)) {
            return ErrorResponse (APIERR_MEMFULL, "Het geheugen voor de omtrek van de mesh kon niet worden gereserveerd.");
        }
        GS::Array<GS::ObjectState> sublines;
        item.Get ("sublines", sublines);
        BuildMeshSublines (sublines, element, memo);

        GS::UniString surfaceError;
        if (!ReadOverriddenSurface (item, "topMaterial", element.mesh.topMat, surfaceError) ||
            !ReadOverriddenSurface (item, "sideMaterial", element.mesh.sideMat, surfaceError) ||
            !ReadOverriddenSurface (item, "bottomMaterial", element.mesh.botMat, surfaceError)) {
            return ErrorResponse (APIERR_BADPARS, surfaceError);
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
    err |= Register<CreateObjectsCommand> ();
    err |= Register<CreateTextsCommand> ();
    err |= Register<EnsureSurfaceCommand> ();
    err |= Register<CreateMorphsCommand> ();
    err |= Register<CreateMeshesCommand> ();
    return err;
}

}
