cmake_minimum_required (VERSION 3.17)

include (Tools/CMakeCommon.cmake)

set_property (GLOBAL PROPERTY USE_FOLDERS ON)

set (CMAKE_CONFIGURATION_TYPES Debug;Release;RelWithDebInfo)
set (AC_API_DEVKIT_DIR ${AC_API_DEVKIT_DIR} CACHE PATH "API DevKit directory (de map Support van de DevKit).")
set (AC_VERSION ${AC_VERSION} CACHE STRING "Archicad version, bijvoorbeeld 29.")

if (NOT AC_VERSION)
    message (FATAL_ERROR "AC_VERSION is niet opgegeven, bijvoorbeeld -DAC_VERSION=29.")
endif ()
if (NOT AC_API_DEVKIT_DIR)
    message (FATAL_ERROR "AC_API_DEVKIT_DIR is niet opgegeven.")
endif ()

SetGlobalCompilerDefinitions (${AC_VERSION})

# De motor (Python + onze Python-code) wordt als bron in het .apx ingebouwd: Tools/pack_engine.py zet hem klaar
# in Sources/python-embed.zip en Sources/engine-app.zip (zie Sources/RFIX.win/AddOnMain.rc2).
find_package (Python COMPONENTS Interpreter REQUIRED)
execute_process (
    COMMAND "${Python_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/Tools/pack_engine.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    RESULT_VARIABLE PackEngineResult
)
if (NOT PackEngineResult EQUAL 0)
    message (FATAL_ERROR "Tools/pack_engine.py is mislukt (zie de regels hierboven).")
endif ()
set_property (DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_LIST_DIR}/Engine/engine.py")

# Het bestand dat de gebruiker in Archicad toevoegt: PDOKImport_AC29.apx
set (AddOnName "PDOKImport_AC${AC_VERSION}")

project (${AddOnName})

set (AddOnSourcesFolder Sources)
set (AddOnResourcesFolder Sources)

# De taal van de gebruikersinterface: de teksten komen uit Sources/R<taal>/AddOn.grc.
set (AC_ADDON_LANGUAGE "INT" CACHE STRING "Taalcode van de add-on, de R<code>-map in Sources.")
if (NOT EXISTS "${CMAKE_CURRENT_LIST_DIR}/${AddOnResourcesFolder}/R${AC_ADDON_LANGUAGE}/AddOn.grc")
    message (FATAL_ERROR "AC_ADDON_LANGUAGE ${AC_ADDON_LANGUAGE}: ${AddOnResourcesFolder}/R${AC_ADDON_LANGUAGE}/AddOn.grc bestaat niet.")
endif ()

GenerateAddOnProject (AddOn ${AC_VERSION} ${AC_API_DEVKIT_DIR} ${AddOnName} ${AddOnSourcesFolder} ${AddOnResourcesFolder} ${AC_ADDON_LANGUAGE})
