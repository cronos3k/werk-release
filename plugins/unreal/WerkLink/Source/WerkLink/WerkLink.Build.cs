using UnrealBuildTool;

public class WerkLink : ModuleRules
{
	public WerkLink(ReadOnlyTargetRules Target) : base(Target)
	{
		// No shared PCH and no unity build, and both for concrete reasons
		// rather than caution:
		//
		//  * A shared PCH is force-included into every .cpp in the module,
		//    which would push Unreal headers into Private/Core -- the files
		//    that must stay engine-free so the standalone gate can compile
		//    them.
		//  * A unity build concatenates .cpp files into one translation unit.
		//    werk_zip.cpp and werk_glb.cpp both define `Rd32`/`Wr32` in an
		//    anonymous namespace inside `namespace werk`, which is correct in
		//    separate translation units and a redefinition in a merged one.
		//
		// The module is small enough that neither costs anything measurable.
		PCHUsage = PCHUsageMode.NoSharedPCHs;
		bUseUnity = false;

		// Private/Core is plain C++17 with no Unreal types: it is the same
		// source the standalone gate compiles. The include path is added so
		// those files can include each other by bare name from either target.
		PrivateIncludePaths.Add(ModuleDirectory + "/Private/Core");

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"DeveloperSettings",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Slate",
			"SlateCore",
			"UnrealEd",          // UFactory, FEditorFileUtils, editor asset plumbing
			"ContentBrowser",    // the legacy context menu extender arrays
			"AssetTools",
			"AssetRegistry",
			"ToolMenus",
			"Settings",
			"Projects",
			"MeshDescription",         // FMeshDescription
			"StaticMeshDescription",   // FStaticMeshAttributes
			"AudioEditor",             // USoundFactory
			"PhysicsCore",             // UBodySetup, FKBoxElem, FKSphereElem
			"InputCore",
			// Texture export. FImageUtils::CompressImage(..., "png", ...) is
			// the ImageWrapper PNG encoder reached through IImageWrapperModule
			// -- the same encoder the content browser writes a .png with. It
			// lives in Engine, but FImage/FImageView are ImageCore's and the
			// module has to be named for the include to resolve.
			"ImageCore",
			"ImageWrapper",
			// UMaterialEditingLibrary::SetMaterialInstanceStaticSwitchParameterValue.
			// A static switch is the only honest way to say "this slot has no
			// texture": a white default is right for base colour and wrong for
			// metallic-roughness and for a normal map.
			"MaterialEditor",
		});

		// The Core files use the C++ standard library (std::string, std::vector,
		// std::shared_ptr). That is deliberate: it is what lets the gate
		// compile them without an engine. Unreal permits it; it just does not
		// use it itself.
		bUseRTTI = false;
		bEnableExceptions = false;
	}
}
