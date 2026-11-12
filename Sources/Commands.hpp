#pragma once

#include "APIEnvir.h"
#include "ACAPinc.h"
#include "ObjectState.hpp"

// De opdrachten van PDOK Import: de motor (Python) stuurt ze via Archicads JSON-interface
// (API.ExecuteAddOnCommand, namespace "PDOKImport") naar deze add-on.
// Opgezet naar de opdrachten van Tapir (MIT), maar zonder zijn schema- en controle-apparaat.
namespace PdokCommands
{

constexpr const char* kNamespace = "PDOKImport";

class CommandBase : public API_AddOnCommand
{
public:
    virtual GS::String                                  GetNamespace () const override final { return kNamespace; }
    virtual GS::Optional<GS::UniString>                 GetSchemaDefinitions () const override final { return {}; }
    virtual GS::Optional<GS::UniString>                 GetInputParametersSchema () const override final { return {}; }
    virtual GS::Optional<GS::UniString>                 GetResponseSchema () const override final { return {}; }
    virtual API_AddOnCommandExecutionPolicy             GetExecutionPolicy () const override final { return API_AddOnCommandExecutionPolicy::ScheduleForExecutionOnMainThread; }
    virtual void                                        OnResponseValidationFailed (const GS::ObjectState&) const override final {}
#ifdef ServerMainVers_2600
    virtual bool                                        IsProcessWindowVisible () const override final { return false; }
#endif
};

// Registreert alle opdrachten bij Archicad. Aanroepen vanuit Initialize.
GSErrCode RegisterAll ();

}
