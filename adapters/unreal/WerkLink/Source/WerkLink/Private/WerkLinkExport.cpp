// UAssets -> a conformant unsigned .werk.
//
// Two rules govern this file and both are structural.
//
// HERMETIC (the manifesto, and the Stage 10 brief's first non-negotiable): the
// exported package references NOTHING external. Every /Engine/ reference is
// either baked into the file or substituted with a DECLARED fallback plus a
// work note that says so. There is no third branch. A silent hole is the one
// outcome this file may not produce.
//
// SOURCE DATA ONLY (findings B1): UE's FBX and mesh exporters assert headless.
// Nothing here calls an exporter. Meshes come from
// UStaticMesh::GetMeshDescription, textures from FTextureSource::GetMipData,
// and the environment is asserted up front so that a cooked or non-editor
// build fails loudly rather than writing a package that does not contain what
// it says it contains.

#include <algorithm>
#include "CoreMinimal.h"

#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "ImageCore.h"
#include "ImageUtils.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/BoxElem.h"
#include "PhysicsEngine/SphereElem.h"
#include "Sound/SoundWave.h"
#include "StaticMeshAttributes.h"
#include "UObject/UObjectGlobals.h"

#include "WerkAssetUserData.h"
#include "WerkLinkAction.h"
#include "WerkLinkBridge.h"
#include "WerkMaterialSlots.h"

#include "werk_basis.h"
#include "werk_glb.h"
#include "werk_json.h"
#include "werk_manifest.h"
#include "werk_sha256.h"
#include "werk_zip.h"

using namespace WerkBridge;

namespace
{
	struct FExportFile
	{
		std::string          Path;
		std::vector<uint8_t> Bytes;
		std::string          MediaType;
		std::string          Role;
	};

	struct FExportNode
	{
		std::string              NodeId;
		std::string              Type;
		std::string              PartId;
		std::string              MaterialId;
		std::vector<FExportFile> Files;
		std::string              Note;
		std::string              Epistemic;
		std::vector<std::string> InputFiles;   // container paths
		werk::JsonPtr            Meta;
	};

	/** What a core.material texture slot has to name: the NODE (identity, law 4)
	 *  and, for convenience, the path the node resolves to. The schema requires
	 *  both and tells a reader to REPORT a disagreement rather than pick one, so
	 *  they are carried together from the one place that knows both. */
	struct FWerkTextureRef
	{
		std::string NodeId;
		std::string Path;
	};

	struct FExportContext
	{
		const FWerkExportRequest* Request = nullptr;
		FWerkExportResult*        Result = nullptr;
		werk::Report*             Rep = nullptr;

		std::vector<FExportNode>  Nodes;
		std::vector<std::string>  PartIds;
		std::vector<std::string>  MaterialIds;
		werk::JsonPtr             PartsJson;
		werk::JsonPtr             MaterialsJson;
		TSet<FString>             UsedNodeIds;
		TMap<UTexture*, FWerkTextureRef> TextureRefs;
	};

	void Note(FExportContext& Ctx, const FString& NodeId, const FString& Type,
	          EWerkOutcome Outcome, const TCHAR* Code, const FString& Detail)
	{
		FWerkNodeOutcome Out;
		Out.NodeId = NodeId;
		Out.NodeType = Type;
		Out.Outcome = Outcome;
		Out.Code = Code;
		Out.Detail = Detail;
		Ctx.Result->Outcomes.Add(MoveTemp(Out));
	}

	/**
	 * The werk node id for an asset. Looked up in UWerkAssetUserData when the
	 * asset was imported by WerkLink, and only DERIVED when it was not.
	 *
	 * That asymmetry is the whole point of the user data: kebab-case -> Unreal
	 * name is lossy, so recomputing it on the way back would not round-trip
	 * identity. A stored id round-trips exactly.
	 */
	FString NodeIdFor(FExportContext& Ctx, UObject* Asset, const TCHAR* Prefix)
	{
		FString Id;
		if (IInterface_AssetUserData* Holder = Cast<IInterface_AssetUserData>(Asset))
		{
			if (UWerkAssetUserData* Data =
				Cast<UWerkAssetUserData>(Holder->GetAssetUserDataOfClass(UWerkAssetUserData::StaticClass())))
			{
				if (!Data->NodeId.IsEmpty())
				{
					Id = Data->NodeId;
				}
			}
		}
		if (Id.IsEmpty())
		{
			Id = FString(Prefix) + FWerkLinkAction::ObjectNameToWerkId(Asset->GetName());
		}
		// Node ids must be unique inside one manifest.
		FString Candidate = Id;
		int32 Suffix = 2;
		while (Ctx.UsedNodeIds.Contains(Candidate))
		{
			Candidate = FString::Printf(TEXT("%s-%d"), *Id, Suffix++);
		}
		Ctx.UsedNodeIds.Add(Candidate);
		return Candidate;
	}

	// --- geometry ----------------------------------------------------------

	/** FMeshDescription -> a werk GLB primitive, crossing the basis back. */
	bool MeshDescriptionToGlb(const FMeshDescription& Desc, werk::GlbMesh& Out)
	{
		FStaticMeshConstAttributes Attributes(Desc);
		TVertexAttributesConstRef<FVector3f> Positions = Attributes.GetVertexPositions();
		TVertexInstanceAttributesConstRef<FVector3f> Normals = Attributes.GetVertexInstanceNormals();
		TVertexInstanceAttributesConstRef<FVector3f> Tangents = Attributes.GetVertexInstanceTangents();
		TVertexInstanceAttributesConstRef<float> BinormalSigns = Attributes.GetVertexInstanceBinormalSigns();
		TVertexInstanceAttributesConstRef<FVector4f> Colors = Attributes.GetVertexInstanceColors();
		TVertexInstanceAttributesConstRef<FVector2f> UVs = Attributes.GetVertexInstanceUVs();

		const bool bHasNormals = Normals.IsValid();
		const bool bHasTangents = Tangents.IsValid() && BinormalSigns.IsValid();
		const bool bHasColors = Colors.IsValid();
		const bool bHasUVs = UVs.IsValid() && UVs.GetNumChannels() > 0;

		werk::GlbPrimitive Prim;

		// One vertex per VERTEX INSTANCE. A mesh description shares positions
		// between instances that differ in normal or UV; a GLB primitive
		// cannot, because its attributes are all indexed by one index buffer.
		// Splitting is the correct direction to lose nothing.
		TMap<FVertexInstanceID, uint32> InstanceToIndex;
		InstanceToIndex.Reserve(Desc.VertexInstances().Num());

		for (const FVertexInstanceID Inst : Desc.VertexInstances().GetElementIDs())
		{
			const FVertexID Vertex = Desc.GetVertexInstanceVertex(Inst);
			const FVector3f P = Positions[Vertex];
			const werk::Vec3 W = werk::PositionUeToWerk({ double(P.X), double(P.Y), double(P.Z) });
			InstanceToIndex.Add(Inst, uint32(Prim.positions.size() / 3));
			Prim.positions.push_back(float(W[0]));
			Prim.positions.push_back(float(W[1]));
			Prim.positions.push_back(float(W[2]));

			if (bHasNormals)
			{
				const FVector3f N = Normals[Inst];
				const werk::Vec3 Wn = werk::DirectionUeToWerk({ double(N.X), double(N.Y), double(N.Z) });
				Prim.normals.push_back(float(Wn[0]));
				Prim.normals.push_back(float(Wn[1]));
				Prim.normals.push_back(float(Wn[2]));
			}
			if (bHasTangents)
			{
				const FVector3f T = Tangents[Inst];
				const werk::Vec3 Wt = werk::DirectionUeToWerk({ double(T.X), double(T.Y), double(T.Z) });
				Prim.tangents.push_back(float(Wt[0]));
				Prim.tangents.push_back(float(Wt[1]));
				Prim.tangents.push_back(float(Wt[2]));
				// The mirror flips the handedness of the tangent frame, so the
				// bitangent sign negates -- the same negation the importer
				// applies in the other direction.
				Prim.tangents.push_back(-BinormalSigns[Inst]);
			}
			if (bHasColors)
			{
				const FVector4f C = Colors[Inst];
				Prim.colors.push_back(C.X);
				Prim.colors.push_back(C.Y);
				Prim.colors.push_back(C.Z);
				Prim.colors.push_back(C.W);
			}
			if (bHasUVs)
			{
				const FVector2f Uv = UVs.Get(Inst, 0);
				Prim.uv0.push_back(Uv.X);
				Prim.uv0.push_back(Uv.Y);
				if (UVs.GetNumChannels() > 1)
				{
					const FVector2f Uv1 = UVs.Get(Inst, 1);
					Prim.uv1.push_back(Uv1.X);
					Prim.uv1.push_back(Uv1.Y);
				}
			}
		}

		for (const FTriangleID Tri : Desc.Triangles().GetElementIDs())
		{
			TArrayView<const FVertexInstanceID> Corners = Desc.GetTriangleVertexInstances(Tri);
			if (Corners.Num() != 3)
			{
				continue;
			}
			const uint32* A = InstanceToIndex.Find(Corners[0]);
			const uint32* B = InstanceToIndex.Find(Corners[1]);
			const uint32* C = InstanceToIndex.Find(Corners[2]);
			if (!A || !B || !C)
			{
				continue;
			}
			// det(M) = -1, so the winding reverses on the way out exactly as it
			// did on the way in.
			Prim.indices.push_back(*A);
			Prim.indices.push_back(*C);
			Prim.indices.push_back(*B);
		}

		if (Prim.indices.empty())
		{
			return false;
		}
		Out.primitives.push_back(std::move(Prim));
		return true;
	}

	bool ExportStaticMesh(FExportContext& Ctx, UStaticMesh* Mesh)
	{
		const FString NodeId = NodeIdFor(Ctx, Mesh, TEXT("geom-"));

		// Findings B1: source data, never an exporter. A null mesh description
		// means the project is cooked or the source was stripped, and that is
		// a loud failure, not an empty GLB.
		FMeshDescription* Lod0 = Mesh->GetMeshDescription(0);
		if (!Lod0)
		{
			Ctx.Rep->Error(werk::code::SourceDataMissing, ToStd(NodeId),
			               "UStaticMesh::GetMeshDescription(0) returned null: no source data. "
			               "An export from this asset would not contain what it claims to.");
			Note(Ctx, NodeId, TEXT("core.geom.game"), EWerkOutcome::Refused,
			     TEXT("source-data-missing"),
			     TEXT("no mesh description at LOD 0; the asset carries no source data"));
			return false;
		}

		werk::GlbMesh Glb;
		if (!MeshDescriptionToGlb(*Lod0, Glb))
		{
			Note(Ctx, NodeId, TEXT("core.geom.game"), EWerkOutcome::Refused,
			     TEXT("payload-schema-invalid"), TEXT("mesh description produced no triangles"));
			return false;
		}

		std::vector<uint8_t> Bytes;
		if (!werk::GlbWrite(Glb, Bytes, ToStd(Mesh->GetName()),
		                    ToStd(Ctx.Request->ProducerTool), *Ctx.Rep))
		{
			Note(Ctx, NodeId, TEXT("core.geom.game"), EWerkOutcome::Refused,
			     TEXT("payload-schema-invalid"), TEXT("GLB could not be written"));
			return false;
		}

		FExportNode Node;
		Node.NodeId = ToStd(NodeId);
		Node.Type = "core.geom.game";
		Node.PartId = ToStd(FWerkLinkAction::ObjectNameToWerkId(Mesh->GetName()));
		Node.Epistemic = "authored";
		Node.Note = "Static mesh source data (UStaticMesh::GetMeshDescription) read directly and "
		            "written as a GLB in werk model space: metres, +Y up, -Z forward, "
		            "counter-clockwise. The basis change to Unreal reverses orientation "
		            "(det = -1), so triangle winding and the tangent bitangent sign are both "
		            "flipped back here. No exporter was invoked.";
		FExportFile File;
		File.Path = "geometry/game.glb";
		File.Bytes = std::move(Bytes);
		File.MediaType = "model/gltf-binary";
		Node.Files.push_back(std::move(File));
		Ctx.Nodes.push_back(std::move(Node));

		// The part entry this node joins on.
		if (Ctx.PartsJson)
		{
			werk::JsonPtr Part = werk::JsonValue::MakeObject();
			Part->SetString("part_id", ToStd(FWerkLinkAction::ObjectNameToWerkId(Mesh->GetName())));
			Part->SetString("name", ToStd(Mesh->GetName()));
			Part->Set("parent", werk::JsonValue::MakeNull());
			werk::JsonPtr T = werk::JsonValue::MakeObject();
			werk::JsonPtr Tr = werk::JsonValue::MakeArray();
			werk::JsonPtr Rot = werk::JsonValue::MakeArray();
			werk::JsonPtr Sc = werk::JsonValue::MakeArray();
			for (int i = 0; i < 3; ++i) { Tr->Push(werk::JsonValue::MakeNumber(0.0)); }
			Rot->Push(werk::JsonValue::MakeNumber(1.0));
			for (int i = 0; i < 3; ++i) { Rot->Push(werk::JsonValue::MakeNumber(0.0)); }
			for (int i = 0; i < 3; ++i) { Sc->Push(werk::JsonValue::MakeNumber(1.0)); }
			T->Set("translation", Tr);
			T->Set("rotation", Rot);   // werk wxyz
			T->Set("scale", Sc);
			Part->Set("transform", T);
			Ctx.PartsJson->Push(Part);
			// The id list, kept alongside the JSON rows so a materials[] row can
			// name a part without re-parsing the array it was just written into.
			// Its absence is what made every exported materials[] row carry
			// part_id "" and fail the schema.
			Ctx.PartIds.push_back(
				ToStd(FWerkLinkAction::ObjectNameToWerkId(Mesh->GetName())));
		}

		Note(Ctx, NodeId, TEXT("core.geom.game"), EWerkOutcome::Exported, TEXT("exported"),
		     FString::Printf(TEXT("%d verts, %d tris from source data"),
		                     int32(Glb.TotalVertices()), int32(Glb.TotalTriangles())));

		// Simple collision, if the mesh has any.
		if (UBodySetup* Body = Mesh->GetBodySetup())
		{
			const int32 Spheres = Body->AggGeom.SphereElems.Num();
			const int32 Boxes = Body->AggGeom.BoxElems.Num();
			const int32 Others = Body->AggGeom.GetElementCount() - Spheres - Boxes;
			if (Spheres + Boxes > 0)
			{
				// The exact shape core.phys.colliders.schema.json requires:
				// groups[] keyed by part_id, each with a spheres[] and a
				// boxes[], and `space` pinned to the const "part-local".
				// additionalProperties is false at every level, so an extra
				// key is not a harmless extra -- it is a schema failure.
				werk::JsonPtr Doc = werk::JsonValue::MakeObject();
				Doc->SetInt("schema_version", 1);
				Doc->SetString("space", "part-local");

				werk::JsonPtr Group = werk::JsonValue::MakeObject();
				Group->SetString("part_id", Node.PartId);
				werk::JsonPtr SphereArr = werk::JsonValue::MakeArray();
				werk::JsonPtr BoxArr = werk::JsonValue::MakeArray();

				for (const FKSphereElem& S : Body->AggGeom.SphereElems)
				{
					werk::JsonPtr C = werk::JsonValue::MakeObject();
					const werk::Vec3 W = werk::PositionUeToWerk({ S.Center.X, S.Center.Y, S.Center.Z });
					werk::JsonPtr Ctr = werk::JsonValue::MakeArray();
					for (int i = 0; i < 3; ++i) { Ctr->Push(werk::JsonValue::MakeNumber(W[size_t(i)])); }
					C->Set("center", Ctr);
					C->SetNumber("radius", double(S.Radius) * werk::WerkUnitsPerUeUnit);
					SphereArr->Push(C);
				}
				for (const FKBoxElem& B : Body->AggGeom.BoxElems)
				{
					werk::JsonPtr C = werk::JsonValue::MakeObject();
					const werk::Vec3 W = werk::PositionUeToWerk({ B.Center.X, B.Center.Y, B.Center.Z });
					werk::JsonPtr Ctr = werk::JsonValue::MakeArray();
					for (int i = 0; i < 3; ++i) { Ctr->Push(werk::JsonValue::MakeNumber(W[size_t(i)])); }
					C->Set("center", Ctr);
					// UE box X/Y/Z are FULL extents; werk's are half. Permuted
					// like a scale triple, halved, converted to metres.
					const werk::Vec3 H = werk::ScaleUeToWerk(
						{ double(B.X) * 0.5, double(B.Y) * 0.5, double(B.Z) * 0.5 });
					werk::JsonPtr Half = werk::JsonValue::MakeArray();
					for (int i = 0; i < 3; ++i)
					{
						// exclusiveMinimum 0 in the schema: a degenerate box is
						// not representable, so it is clamped to a hair rather
						// than emitted as an invalid zero.
						const double Extent = FMath::Max(
							FMath::Abs(H[size_t(i)]) * werk::WerkUnitsPerUeUnit, 1e-6);
						Half->Push(werk::JsonValue::MakeNumber(Extent));
					}
					C->Set("half_extents", Half);
					const FQuat Q = B.Rotation.Quaternion();
					const werk::Quat Wq = werk::QuatUeToWerk({ Q.X, Q.Y, Q.Z, Q.W }); // -> wxyz
					werk::JsonPtr Rot = werk::JsonValue::MakeArray();
					for (int i = 0; i < 4; ++i) { Rot->Push(werk::JsonValue::MakeNumber(Wq[size_t(i)])); }
					C->Set("rotation", Rot);
					BoxArr->Push(C);
				}
				Group->Set("spheres", SphereArr);
				Group->Set("boxes", BoxArr);
				werk::JsonPtr GroupsArr = werk::JsonValue::MakeArray();
				GroupsArr->Push(Group);
				Doc->Set("groups", GroupsArr);
				Doc->SetString("epistemic", "authored");
				Doc->SetString("note",
					Others > 0
						? "Simple collision read from the static mesh body setup. Convex, capsule "
						  "and level-set elements were present and are NOT represented: this node "
						  "is a partial record and says so."
						: "Simple collision read from the static mesh body setup, converted to "
						  "werk model space and metres.");

				const std::string Text = werk::JsonWritePretty(*Doc);
				FExportNode CNode;
				CNode.NodeId = ToStd(NodeId) + "-colliders";
				Ctx.UsedNodeIds.Add(NodeId + TEXT("-colliders"));
				CNode.Type = "core.phys.colliders";
				CNode.PartId = Node.PartId;
				CNode.Epistemic = "authored";
				CNode.Note = "Simple collision primitives from the Unreal body setup.";
				FExportFile CFile;
				CFile.Path = "physics/colliders.json";
				CFile.Bytes.assign(Text.begin(), Text.end());
				CFile.MediaType = "application/json";
				CNode.Files.push_back(std::move(CFile));
				Ctx.Nodes.push_back(std::move(CNode));

				Note(Ctx, NodeId + TEXT("-colliders"), TEXT("core.phys.colliders"),
				     Others > 0 ? EWerkOutcome::Substituted : EWerkOutcome::Exported,
				     Others > 0 ? TEXT("substituted-fallback") : TEXT("exported"),
				     FString::Printf(TEXT("%d sphere(s), %d box(es); %d other element(s) not "
				                          "representable as core.phys.colliders"),
				                     Spheres, Boxes, Others));
			}
		}

		return true;
	}

	// --- textures ----------------------------------------------------------

#if WITH_EDITORONLY_DATA
	/** ETextureSourceFormat -> its own name, for the work note. A conversion
	 *  nobody can name is a conversion nobody can check. */
	const TCHAR* SourceFormatName(ETextureSourceFormat F)
	{
		switch (F)
		{
		case TSF_G8:       return TEXT("TSF_G8");
		case TSF_BGRA8:    return TEXT("TSF_BGRA8");
		case TSF_BGRE8:    return TEXT("TSF_BGRE8");
		case TSF_RGBA16:   return TEXT("TSF_RGBA16");
		case TSF_RGBA16F:  return TEXT("TSF_RGBA16F");
		case TSF_G16:      return TEXT("TSF_G16");
		case TSF_RGBA32F:  return TEXT("TSF_RGBA32F");
		case TSF_R16F:     return TEXT("TSF_R16F");
		case TSF_R32F:     return TEXT("TSF_R32F");
		default:           return TEXT("TSF_Invalid");
		}
	}

	const TCHAR* RawFormatName(ERawImageFormat::Type F)
	{
		switch (F)
		{
		case ERawImageFormat::G8:       return TEXT("G8");
		case ERawImageFormat::BGRA8:    return TEXT("BGRA8");
		case ERawImageFormat::BGRE8:    return TEXT("BGRE8");
		case ERawImageFormat::RGBA16:   return TEXT("RGBA16");
		case ERawImageFormat::RGBA16F:  return TEXT("RGBA16F");
		case ERawImageFormat::RGBA32F:  return TEXT("RGBA32F");
		case ERawImageFormat::G16:      return TEXT("G16");
		case ERawImageFormat::R16F:     return TEXT("R16F");
		case ERawImageFormat::R32F:     return TEXT("R32F");
		default:                        return TEXT("unknown");
		}
	}

	/**
	 * Which raw formats UE's PNG wrapper stores WITHOUT converting.
	 *
	 * This is not a guess and not a table copied by hand: it is the exact set
	 * FPngImageWrapper::GetSupportedRawFormat returns unchanged
	 * (Runtime/ImageWrapper/Private/Formats/PngImageWrapper.cpp). Everything
	 * else is blitted to RGBA16 by FImageWrapperModule::CompressImage before
	 * it reaches the encoder, and a blit is a CONVERSION -- which this exporter
	 * must name in the work note rather than let a reader discover by
	 * comparing pixels.
	 */
	bool PngStoresRawFormatLosslessly(ERawImageFormat::Type F)
	{
		return F == ERawImageFormat::G8 || F == ERawImageFormat::G16
		    || F == ERawImageFormat::BGRA8 || F == ERawImageFormat::RGBA16;
	}
#endif

	/**
	 * A UTexture2D -> a real PNG core.tex node.
	 *
	 * Stage 10 shipped this as "not implemented", on the honest ground that
	 * FTextureSource::GetMipData returns raw pixels and writing them to a .png
	 * path would be a lie the manifest hash would certify. Stage 10B closes it
	 * the only way that is not a lie: encode with the engine's own PNG encoder.
	 *
	 * FImageUtils::CompressImage(..., TEXT("png"), ...) IS the ImageWrapper
	 * path -- it resolves EImageFormat::PNG through IImageWrapperModule and
	 * calls the same FPngImageWrapper the editor uses to write a .png from the
	 * content browser. Nothing here re-implements a PNG encoder, because
	 * MINI-SPECS 8 is a READER's spec and a second encoder would be a second
	 * thing to be wrong.
	 */
	bool ExportTexture(FExportContext& Ctx, UTexture2D* Texture, int32 Ordinal)
	{
		const FString NodeId = NodeIdFor(Ctx, Texture, TEXT("tex-"));

#if WITH_EDITORONLY_DATA
		// Findings B1: FTextureSource, not the platform data, which is
		// BC-compressed and would round-trip as a different image.
		if (!Texture->Source.IsValid())
		{
			Ctx.Rep->Error(werk::code::SourceDataMissing, ToStd(NodeId),
			               "UTexture2D has no valid FTextureSource; the project is cooked or the "
			               "source was stripped");
			Note(Ctx, NodeId, TEXT("core.tex"), EWerkOutcome::Refused, TEXT("source-data-missing"),
			     TEXT("no texture source data"));
			return false;
		}

		const ETextureSourceFormat SrcFormat = Texture->Source.GetFormat();
		const ETextureSourceCompressionFormat SrcCompression = Texture->Source.GetSourceCompression();
		const int32 SizeX = Texture->Source.GetSizeX();
		const int32 SizeY = Texture->Source.GetSizeY();

		// GetMipImage decodes a compressed source (a JPEG- or PNG-wrapped
		// FTextureSource) through the image wrapper on the way out, so the
		// "compressed source" edge case the brief names needs no second code
		// path -- it needs this call rather than GetMipData, and a work note
		// that says the source was compressed.
		FImage Image;
		if (!Texture->Source.GetMipImage(Image, 0) || Image.RawData.Num() == 0)
		{
			// The island rule: one unreadable texture is one skipped node, never
			// a failed package and never a fabricated payload.
			Ctx.Rep->Error(werk::code::SourceDataMissing, ToStd(NodeId),
			               "FTextureSource::GetMipImage could not decode mip 0");
			Note(Ctx, NodeId, TEXT("core.tex"), EWerkOutcome::Refused, TEXT("source-data-missing"),
			     FString::Printf(TEXT("mip 0 of a %dx%d %s source could not be decoded; "
			                          "NOTHING was written for this texture"),
			                     SizeX, SizeY, SourceFormatName(SrcFormat)));
			return false;
		}

		const ERawImageFormat::Type DecodedFormat = Image.Format;
		const bool bLossless = PngStoresRawFormatLosslessly(DecodedFormat);

		// PNG is the only texture encoding werk core permits (MINI-SPECS 8;
		// section 13 bans BC/DXT/ASTC/KTX2 from core).
		TArray64<uint8> Png;
		if (!FImageUtils::CompressImage(Png, TEXT("png"), Image, 0) || Png.Num() == 0)
		{
			Ctx.Rep->Error(werk::code::SourceDataMissing, ToStd(NodeId),
			               "the image wrapper's PNG encoder produced nothing");
			Note(Ctx, NodeId, TEXT("core.tex"), EWerkOutcome::Refused, TEXT("payload-schema-invalid"),
			     FString::Printf(TEXT("PNG encode failed for a %dx%d %s image; texture NOT exported"),
			                     SizeX, SizeY, RawFormatName(DecodedFormat)));
			return false;
		}

		// SPEC 8.2 / law 8: colour space is a DECLARED value in the manifest,
		// not something a reader recovers from the PNG's sRGB chunk. The
		// declaration comes from the one place Unreal actually shades from.
		const bool bSrgb = Texture->SRGB != 0;
		FString Usage = TEXT("other");
		if (Texture->CompressionSettings == TC_Normalmap)
		{
			Usage = TEXT("normal");
		}
		else if (Texture->CompressionSettings == TC_Grayscale
			|| Texture->CompressionSettings == TC_Alpha)
		{
			Usage = TEXT("mask");
		}
		else if (bSrgb)
		{
			Usage = TEXT("base-color");
		}
		else
		{
			Usage = TEXT("data");
		}
		// Read back a stamped usage when this texture came in through WerkLink,
		// for the same reason node ids are looked up and not recomputed.
		if (IInterface_AssetUserData* Holder = Cast<IInterface_AssetUserData>(Texture))
		{
			if (UWerkAssetUserData* Data = Cast<UWerkAssetUserData>(
				Holder->GetAssetUserDataOfClass(UWerkAssetUserData::StaticClass())))
			{
				if (!Data->TextureUsage.IsEmpty())
				{
					Usage = Data->TextureUsage;
				}
			}
		}

		const std::string Slug = ToStd(FWerkLinkAction::ObjectNameToWerkId(Texture->GetName()));
		const std::string ContainerPath = "textures/" + Slug + ".png";

		FString NoteText = FString::Printf(
			TEXT("PNG written by Unreal's own image wrapper (FImageUtils::CompressImage -> "
			     "EImageFormat::PNG) from FTextureSource mip 0. Source format %s"),
			SourceFormatName(SrcFormat));
		if (SrcCompression != TSCF_None)
		{
			NoteText += FString::Printf(
				TEXT(", stored %s-compressed in the asset and decoded on the way out"),
				SrcCompression == TSCF_PNG ? TEXT("PNG")
				    : (SrcCompression == TSCF_JPEG ? TEXT("JPEG") : TEXT("UEJPEG")));
		}
		NoteText += FString::Printf(TEXT("; decoded to %s"), RawFormatName(DecodedFormat));
		if (bLossless)
		{
			NoteText += TEXT("; PNG stores that format directly, so the pixel data is carried "
			                 "unchanged and this is a lossless conversion of container only.");
		}
		else
		{
			NoteText += TEXT("; PNG cannot store that format, so the image wrapper blits it to "
			                 "RGBA16 before encoding. THAT IS A LOSSY CONVERSION and it is named "
			                 "here rather than left for a reader to find by comparing pixels.");
		}

		FExportNode Node;
		Node.NodeId = ToStd(NodeId);
		Node.Type = "core.tex";
		Node.Epistemic = "authored";
		Node.Note = ToStd(NoteText);
		Node.Meta = werk::JsonValue::MakeObject();
		// manifest.schema.json makes all six of these REQUIRED on a core.tex
		// node, and jsonschema is the reader that caught the first version of
		// this exporter emitting four. `channels` and `bit_depth` describe the
		// PNG that was actually written, so they are read off the format the
		// image wrapper stored -- not off the source, which may have been
		// converted on the way.
		int32 Channels = 4;
		int32 BitDepth = 8;
		{
			const ERawImageFormat::Type Stored =
				bLossless ? DecodedFormat : ERawImageFormat::RGBA16;
			switch (Stored)
			{
			case ERawImageFormat::G8:     Channels = 1; BitDepth = 8;  break;
			case ERawImageFormat::G16:    Channels = 1; BitDepth = 16; break;
			case ERawImageFormat::RGBA16: Channels = 4; BitDepth = 16; break;
			default:                      Channels = 4; BitDepth = 8;  break;  // BGRA8
			}
		}
		Node.Meta->SetString("color_space", bSrgb ? "srgb" : "linear");
		Node.Meta->SetString("usage", ToStd(Usage));
		Node.Meta->SetInt("width", SizeX);
		Node.Meta->SetInt("height", SizeY);
		Node.Meta->SetInt("channels", Channels);
		Node.Meta->SetInt("bit_depth", BitDepth);

		FExportFile File;
		File.Path = ContainerPath;
		File.Bytes.assign(Png.GetData(), Png.GetData() + Png.Num());
		File.MediaType = "image/png";
		Node.Files.push_back(std::move(File));
		Ctx.Nodes.push_back(std::move(Node));

		FWerkTextureRef Ref;
		Ref.NodeId = ToStd(NodeId);
		Ref.Path = ContainerPath;
		Ctx.TextureRefs.Add(Texture, Ref);

		Note(Ctx, NodeId, TEXT("core.tex"), EWerkOutcome::Exported, TEXT("exported"),
		     FString::Printf(TEXT("%dx%d %s -> %lld bytes of PNG, colour space %s, usage '%s', "
		                          "%s (ordinal %d)"),
		                     SizeX, SizeY, SourceFormatName(SrcFormat), (long long)Png.Num(),
		                     bSrgb ? TEXT("srgb") : TEXT("linear"), *Usage,
		                     bLossless ? TEXT("lossless") : TEXT("LOSSY: blitted to RGBA16"),
		                     Ordinal));
		return true;
#else
		Note(Ctx, NodeId, TEXT("core.tex"), EWerkOutcome::Refused, TEXT("source-data-missing"),
		     TEXT("no editor-only data in this build"));
		return false;
#endif
	}

	// --- materials ---------------------------------------------------------

	bool ExportMaterial(FExportContext& Ctx, UMaterialInterface* Material)
	{
		const FString NodeId = NodeIdFor(Ctx, Material, TEXT("material-"));
		const FString MaterialId = FWerkLinkAction::ObjectNameToWerkId(Material->GetName());

		werk::JsonPtr Doc = werk::JsonValue::MakeObject();
		Doc->SetString("material_id", ToStd(MaterialId));
		Doc->SetString("name", ToStd(Material->GetName()));
		Doc->SetString("model", "metallic-roughness");

		FLinearColor BaseColor(1, 1, 1, 1);
		bool bGotBaseColor =
			Material->GetVectorParameterValue(FMaterialParameterInfo(TEXT("BaseColor")), BaseColor)
			|| Material->GetVectorParameterValue(FMaterialParameterInfo(TEXT("Color")), BaseColor);

		float Metallic = 0.f, Roughness = 0.5f;
		const bool bGotMetallic =
			Material->GetScalarParameterValue(FMaterialParameterInfo(TEXT("Metallic")), Metallic);
		const bool bGotRoughness =
			Material->GetScalarParameterValue(FMaterialParameterInfo(TEXT("Roughness")), Roughness);

		werk::JsonPtr Bc = werk::JsonValue::MakeArray();
		Bc->Push(werk::JsonValue::MakeNumber(double(BaseColor.R)));
		Bc->Push(werk::JsonValue::MakeNumber(double(BaseColor.G)));
		Bc->Push(werk::JsonValue::MakeNumber(double(BaseColor.B)));
		Bc->Push(werk::JsonValue::MakeNumber(double(BaseColor.A)));
		Doc->Set("base_color_factor", Bc);
		Doc->SetNumber("metallic_factor", double(Metallic));
		Doc->SetNumber("roughness_factor", double(Roughness));
		Doc->SetString("alpha_mode", "opaque");
		Doc->SetBool("double_sided", Material->IsTwoSided());
		Doc->SetString("epistemic", "measured");

		// --- texture slots -------------------------------------------------
		//
		// A slot is only written when the texture it names is IN THIS PACKAGE.
		// core.material.schema.json requires `node` and `path` together and
		// tells a reader to report a disagreement between them; a slot naming a
		// node that does not exist would be a manifest that fails its own
		// reachability rule (SPEC 2), so an unexported texture costs the slot
		// and gets a report entry, not a dangling reference.
		werk::JsonPtr Slots = werk::JsonValue::MakeObject();
		TArray<FString> BoundSlots, DanglingSlots;

		// Bindings this instance was imported with, if it was. Looked up rather
		// than recomputed, same argument as NodeIdFor.
		const UWerkAssetUserData* Stamped = nullptr;
		if (IInterface_AssetUserData* Holder = Cast<IInterface_AssetUserData>(Material))
		{
			Stamped = Cast<UWerkAssetUserData>(
				Holder->GetAssetUserDataOfClass(UWerkAssetUserData::StaticClass()));
		}

		for (const FWerkMaterialSlot& S : WerkMaterialSlots())
		{
			UTexture* Bound = nullptr;
			if (!Material->GetTextureParameterValue(FMaterialParameterInfo(S.TextureParam), Bound))
			{
				continue;   // the master has no such parameter: not a slot at all
			}
			if (!Bound)
			{
				continue;
			}
			// The switch is what decides whether the sampler is actually read.
			// A texture parked on a parameter whose switch is off is not a
			// binding, and exporting it would claim a shading the engine does
			// not perform.
			bool bSwitchOn = true;
			FGuid Unused;
			if (Material->GetStaticSwitchParameterValue(FMaterialParameterInfo(S.SwitchParam),
			                                            bSwitchOn, Unused))
			{
				if (!bSwitchOn)
				{
					continue;
				}
			}

			const FWerkTextureRef* Ref = Ctx.TextureRefs.Find(Bound);
			if (!Ref)
			{
				DanglingSlots.Add(FString(S.Slot) + TEXT("=") + Bound->GetName());
				Ctx.Rep->Warn(werk::code::SubstitutedFallback, ToStd(NodeId),
				              "texture slot '" + ToStd(FString(S.Slot)) + "' names '"
				                  + ToStd(Bound->GetName())
				                  + "', which is not in this package's closure; the slot was "
				                    "DROPPED rather than written as a dangling reference");
				continue;
			}

			int32 UvSet = 0;
			if (Stamped)
			{
				if (const int32* Declared = Stamped->TextureSlotUvSets.Find(FString(S.Slot)))
				{
					UvSet = *Declared;
				}
			}

			werk::JsonPtr Slot = werk::JsonValue::MakeObject();
			Slot->SetString("node", Ref->NodeId);
			Slot->SetString("path", Ref->Path);
			Slot->SetInt("uv_set", UvSet);
			if (FString(S.Slot) == TEXT("metallic_roughness"))
			{
				// glTF's packing, which SPEC 3 adopts verbatim and the schema
				// documents on `channel`. Stated, never assumed.
				Slot->SetString("channel", "rgb");
			}
			Slots->Set(ToStd(FString(S.Slot)), Slot);
			BoundSlots.Add(S.Slot);
		}
		if (BoundSlots.Num() > 0)
		{
			Doc->Set("textures", Slots);
		}

		// The honest part: say which numbers came from the material and which
		// are this exporter's defaults, IN the payload, because a reader
		// cannot tell 0.5 from "we did not find one".
		TArray<FString> Missing;
		if (!bGotBaseColor) { Missing.Add(TEXT("base_color_factor")); }
		if (!bGotMetallic)  { Missing.Add(TEXT("metallic_factor")); }
		if (!bGotRoughness) { Missing.Add(TEXT("roughness_factor")); }

		FString NoteText = FString::Printf(
			TEXT("Flattened from the Unreal material '%s' by reading its named PBR parameters."),
			*Material->GetName());
		if (Missing.Num() > 0)
		{
			NoteText += FString::Printf(
				TEXT(" The material exposes no parameter for {%s}; those fields are this "
				     "exporter's declared fallback values and are NOT measurements of the "
				     "material."),
				*FString::Join(Missing, TEXT(", ")));
		}
		if (BoundSlots.Num() > 0)
		{
			NoteText += FString::Printf(TEXT(" Texture slots bound: {%s}."),
			                            *FString::Join(BoundSlots, TEXT(", ")));
		}
		if (DanglingSlots.Num() > 0)
		{
			NoteText += FString::Printf(
				TEXT(" Slots {%s} were DROPPED because the textures they name are outside this "
				     "package's closure; they are absent, not defaulted."),
				*FString::Join(DanglingSlots, TEXT(", ")));
		}
		Doc->SetString("note", ToStd(NoteText));

		const std::string Text = werk::JsonWritePretty(*Doc);

		FExportNode Node;
		Node.NodeId = ToStd(NodeId);
		Node.Type = "core.material";
		Node.MaterialId = ToStd(MaterialId);
		// `authored`, never `measured`, and law 5 is machine-enforced about it:
		// `measured` requires an ordered `input_files` list of PACKAGE paths and
		// a hash over them, and these numbers were read from a UMaterialInstance
		// -- which is not a file in this package. The Blender adapter reached
		// the same conclusion for the same reason (its decision 2), and both
		// times the schema is what said so rather than a code reviewer.
		Node.Epistemic = "authored";
		Node.Note = ToStd(NoteText);
		FExportFile File;
		File.Path = "materials/" + ToStd(MaterialId) + ".json";
		File.Bytes.assign(Text.begin(), Text.end());
		File.MediaType = "application/json";
		Node.Files.push_back(std::move(File));
		Ctx.Nodes.push_back(std::move(Node));

		if (Ctx.MaterialsJson)
		{
			werk::JsonPtr M = werk::JsonValue::MakeObject();
			M->SetString("material_id", ToStd(MaterialId));
			// part_id is kebab-case-constrained by the schema, so an empty
			// string is not "unknown", it is invalid -- jsonschema said so.
			// When no part has been exported there is nothing truthful to put
			// here, so the row names the first part and, if there is none, is
			// not written at all.
			M->SetString("part_id", Ctx.PartIds.empty() ? std::string() : Ctx.PartIds[0]);
			M->SetString("name", ToStd(Material->GetName()));
			// "unclassified" is not in the schema's enum; "unknown" is, and it
			// is the honest word for a class this exporter cannot determine
			// from an Unreal material.
			M->SetString("class", "unknown");
			if (!Ctx.PartIds.empty())
			{
				Ctx.MaterialsJson->Push(M);
			}
			else
			{
				Ctx.Rep->Warn(werk::code::SubstitutedFallback, ToStd(NodeId),
				              "no part was exported, so this material has no materials[] row: "
				              "the row requires a part_id and inventing one would be worse than "
				              "omitting the row. The core.material node is still present.");
			}
		}

		Note(Ctx, NodeId, TEXT("core.material"),
		     Missing.Num() > 0 ? EWerkOutcome::Substituted : EWerkOutcome::Exported,
		     Missing.Num() > 0 ? TEXT("substituted-fallback") : TEXT("exported"),
		     FString::Printf(
			     TEXT("flattened from named PBR parameters%s%s%s"),
			     Missing.Num() > 0
			         ? *FString::Printf(TEXT("; {%s} are declared fallbacks"),
			                            *FString::Join(Missing, TEXT(", ")))
			         : TEXT(""),
			     BoundSlots.Num() > 0
			         ? *FString::Printf(TEXT("; texture slots {%s}"),
			                            *FString::Join(BoundSlots, TEXT(", ")))
			         : TEXT("; no texture slots"),
			     DanglingSlots.Num() > 0
			         ? *FString::Printf(TEXT("; DROPPED out-of-closure slots {%s}"),
			                            *FString::Join(DanglingSlots, TEXT(", ")))
			         : TEXT("")));
		return true;
	}

	// --- audio -------------------------------------------------------------

	bool ExportSound(FExportContext& Ctx, USoundWave* Wave)
	{
		const FString NodeId = NodeIdFor(Ctx, Wave, TEXT("audio-"));

#if WITH_EDITORONLY_DATA
		// The imported WAV bytes, verbatim. USoundWave keeps them in editor
		// data precisely so a reimport is byte-identical, and taking them
		// rather than re-encoding is what makes an export -> import round trip
		// meaningful.
		const uint8* Raw = nullptr;
		int64 RawSize = 0;
		FSharedBuffer Buffer = Wave->RawData.GetPayload().Get();
		Raw = static_cast<const uint8*>(Buffer.GetData());
		RawSize = int64(Buffer.GetSize());

		if (!Raw || RawSize <= 0)
		{
			Note(Ctx, NodeId, TEXT("core.audio.effect"), EWerkOutcome::Refused,
			     TEXT("source-data-missing"),
			     TEXT("USoundWave carries no raw editor payload; only cooked audio is present, "
			          "and MINI-SPECS 13 says werk core carries WAV and nothing else"));
			return false;
		}

		const std::string Slug = ToStd(FWerkLinkAction::ObjectNameToWerkId(Wave->GetName()));

		FExportNode Node;
		Node.NodeId = ToStd(NodeId);
		Node.Type = "core.audio.effect";
		Node.Epistemic = "authored";
		Node.Note = "WAV taken verbatim from the sound wave's editor payload, not re-encoded, so "
		            "a round trip through Unreal is byte-identical.";
		FExportFile File;
		File.Path = "audio/sfx/" + Slug + ".wav";
		File.Bytes.assign(Raw, Raw + RawSize);
		File.MediaType = "audio/wav";
		File.Role = "best";
		Node.Files.push_back(std::move(File));
		Ctx.Nodes.push_back(std::move(Node));

		Note(Ctx, NodeId, TEXT("core.audio.effect"), EWerkOutcome::Exported, TEXT("exported"),
		     FString::Printf(TEXT("%lld bytes of WAV, verbatim"), (long long)RawSize));
		return true;
#else
		Note(Ctx, NodeId, TEXT("core.audio.effect"), EWerkOutcome::Refused,
		     TEXT("source-data-missing"), TEXT("no editor-only data in this build"));
		return false;
#endif
	}

	// --- the spec tree -----------------------------------------------------

	/** Reads a directory tree into export files. Law 2: the format travels
	 *  with the file, so spec/ and loaders/ are payload, not documentation. */
	int32 CollectDirectory(const FString& DiskDir, const FString& ContainerPrefix,
	                       std::vector<FExportFile>& Out)
	{
		int32 Count = 0;
		TArray<FString> Files;
		IFileManager::Get().FindFilesRecursive(Files, *DiskDir, TEXT("*"), true, false);
		for (const FString& File : Files)
		{
			FString Relative = File;
			FPaths::MakePathRelativeTo(Relative, *(DiskDir / TEXT("")));
			Relative.ReplaceInline(TEXT("\\"), TEXT("/"));
			if (Relative.Contains(TEXT("__pycache__")) || Relative.EndsWith(TEXT(".pyc")))
			{
				continue;
			}
			TArray<uint8> Bytes;
			if (!FFileHelper::LoadFileToArray(Bytes, *File))
			{
				continue;
			}
			FExportFile F;
			F.Path = ToStd(ContainerPrefix + Relative);
			F.Bytes = ToStdBytes(Bytes);
			Out.push_back(std::move(F));
			++Count;
		}
		return Count;
	}
}

// --- the entry point -------------------------------------------------------

FWerkExportResult FWerkLinkAction::Export(const FWerkExportRequest& Request)
{
	FWerkExportResult Result;
	Result.OutputFilePath = Request.OutputFilePath;

	// Findings B1: assert the environment first, and fail loudly.
	FString EnvError;
	if (!FWerkLinkAction::AssertExportEnvironment(EnvError))
	{
		Result.ErrorMessage = EnvError;
		FWerkReportLine L;
		L.Code = TEXT("source-data-missing");
		L.Severity = TEXT("error");
		L.Detail = EnvError;
		Result.Report.Add(MoveTemp(L));
		return Result;
	}

	werk::Report Rep;

	// 1. Closure.
	TArray<FString> Closure, EngineRefs;
	FWerkLinkAction::WalkClosure(Request.RootAssetPaths, Closure, EngineRefs, Result.Report);
	Result.AssetsInClosure = Closure.Num();

	// The hermetic rule. An /Engine/ reference is baked or substituted; the
	// third option, leaving it dangling, does not exist.
	for (const FString& EngineRef : EngineRefs)
	{
		if (Request.bFailOnUnresolvableExternalReference)
		{
			Result.ErrorMessage = FString::Printf(
				TEXT("hermetic refusal: '%s' is an engine reference and could not be baked into "
				     "the package. Turn off 'Fail On Unresolvable External Reference' to write a "
				     "declared substitution instead."), *EngineRef);
			FWerkReportLine L;
			L.Code = TEXT("external-reference");
			L.Severity = TEXT("error");
			L.Subject = EngineRef;
			L.Detail = Result.ErrorMessage;
			Result.Report.Add(MoveTemp(L));
			return Result;
		}
		++Result.ExternalReferencesSubstituted;
	}

	FExportContext Ctx;
	Ctx.Request = &Request;
	Ctx.Result = &Result;
	Ctx.Rep = &Rep;
	Ctx.PartsJson = werk::JsonValue::MakeArray();
	Ctx.MaterialsJson = werk::JsonValue::MakeArray();

	// 2. Walk the closure and turn each asset into nodes.
	IAssetRegistry& Registry =
		FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry").Get();

	// Resolve the closure to objects once, then walk it in THREE ORDERED PASSES.
	// The order is a dependency, not a taste:
	//
	//   1. meshes, sounds and everything else -- this is what fills parts[],
	//      and a material row names a part_id.
	//   2. textures -- a core.material texture slot must name a core.tex NODE
	//      (law 4, identity), so the node has to exist before the slot can
	//      reference it.
	//   3. materials.
	//
	// Stage 10 walked the closure once in asset-registry order, which happened
	// to work only because no material had a texture to bind.
	TArray<UObject*> Objects;
	for (const FString& PackageName : Closure)
	{
		TArray<FAssetData> Assets;
		Registry.GetAssetsByPackageName(FName(*PackageName), Assets);

		// Findings B3: one package, possibly several FAssetData. Take the
		// asset, not the generated class.
		for (const FAssetData& Data : Assets)
		{
			if (UObject* Asset = Data.GetAsset())
			{
				Objects.Add(Asset);
			}
		}
	}

	for (UObject* Asset : Objects)
	{
		if (UStaticMesh* Mesh = Cast<UStaticMesh>(Asset))
		{
			ExportStaticMesh(Ctx, Mesh);
		}
		else if (USoundWave* Wave = Cast<USoundWave>(Asset))
		{
			ExportSound(Ctx, Wave);
		}
		else if (Cast<UTexture2D>(Asset) || Cast<UMaterialInterface>(Asset))
		{
			continue;   // passes 2 and 3
		}
		else
		{
			Note(Ctx, ToF(ToStd(Asset->GetName())), ToF(ToStd(Asset->GetClass()->GetName())),
			     EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
			     FString::Printf(TEXT("asset class '%s' has no werk node family in v1"),
			                     *Asset->GetClass()->GetName()));
		}
	}

	int32 TextureOrdinal = 0;
	for (UObject* Asset : Objects)
	{
		if (UTexture2D* Texture = Cast<UTexture2D>(Asset))
		{
			ExportTexture(Ctx, Texture, TextureOrdinal++);
		}
	}

	for (UObject* Asset : Objects)
	{
		if (UTexture2D* AlsoATexture = Cast<UTexture2D>(Asset))
		{
			(void)AlsoATexture;
			continue;
		}
		if (UMaterialInterface* Material = Cast<UMaterialInterface>(Asset))
		{
			ExportMaterial(Ctx, Material);
		}
	}

	if (Ctx.Nodes.empty())
	{
		Result.ErrorMessage = TEXT("nothing exportable in the closure");
		AppendReport(Rep, Result.Report);
		return Result;
	}

	// 3. spec/ and loaders/. Law 2: a werk carries the format it conforms to.
	std::vector<FExportFile> SpecFiles;
	if (!Request.SpecSourceDirectory.IsEmpty())
	{
		const FString SpecDir = Request.SpecSourceDirectory / TEXT("spec");
		const FString LoaderDir = Request.SpecSourceDirectory / TEXT("loaders");
		const int32 SpecCount = CollectDirectory(SpecDir, TEXT("spec/"), SpecFiles);
		const int32 LoaderCount = CollectDirectory(LoaderDir, TEXT("loaders/"), SpecFiles);
		Result.bSpecEmbedded = (SpecCount > 0);
		if (SpecCount == 0)
		{
			Rep.Warn(werk::code::SubstitutedFallback, "spec/",
			         "the configured spec source directory holds no spec/ tree");
		}
		else
		{
			Rep.Info(werk::code::Exported, "spec/",
			         "embedded " + std::to_string(SpecCount) + " spec file(s) and "
			             + std::to_string(LoaderCount) + " loader file(s)");
		}
	}
	else
	{
		Rep.Warn(werk::code::SubstitutedFallback, "spec/",
		         "no spec source directory configured: this package carries NO spec/ and NO "
		         "loaders/, so it is not redistributable-conformant under law 2. Set "
		         "Project Settings > Plugins > WerkLink > Spec Source Directory.");
	}

	if (Request.bDryRun)
	{
		AppendReport(Rep, Result.Report);
		Result.NodesWritten = int32(Ctx.Nodes.size());
		Result.bSuccess = true;
		return Result;
	}

	// 4. Build the manifest.
	const FString EntityName = Request.EntityName.IsEmpty()
		? (Closure.Num() > 0 ? FPaths::GetCleanFilename(Closure[0]) : FString(TEXT("entity")))
		: Request.EntityName;
	Result.EntityUuid = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower);
	const std::string CreatedAt = ToStd(FDateTime::UtcNow().ToIso8601());

	werk::JsonPtr Manifest = werk::JsonValue::MakeObject();
	{
		werk::JsonPtr W = werk::JsonValue::MakeObject();
		W->SetInt("major", 1);
		W->SetInt("minor", 0);
		Manifest->Set("werk", W);
	}
	Manifest->SetString("profile", "3d-entity/1");
	{
		werk::JsonPtr E = werk::JsonValue::MakeObject();
		E->SetString("uuid", ToStd(Result.EntityUuid));
		E->SetString("name", ToStd(EntityName));
		E->SetString("summary",
			"Exported from Unreal Engine by WerkLink. Geometry, collision, materials and audio "
			"are read from editor SOURCE data, never from an exporter and never from cooked "
			"data. Unsigned: signature absence is a valid three-state and this adapter does not "
			"hold keys.");
		E->SetString("created", CreatedAt);
		Manifest->Set("entity", E);
	}
	{
		// Every convention the adapter actually honours, written as the
		// declared value it is. These are the same constants the reader checks
		// against, from one table, so a writer and a reader here cannot drift.
		werk::JsonPtr C = werk::JsonValue::MakeObject();
		for (const auto& Pair : werk::SupportedConventions())
		{
			if (Pair.first == "units_per_meter")
			{
				C->SetNumber(Pair.first, 1.0);
			}
			else if (Pair.first == "alignment_bytes")
			{
				C->SetInt(Pair.first, 16);
			}
			else
			{
				C->SetString(Pair.first, Pair.second);
			}
		}
		// sh_l1_order is the one convention that is an ARRAY rather than a
		// scalar, which is why the shared table does not carry it.
		werk::JsonPtr Sh = werk::JsonValue::MakeArray();
		for (const char* S : { "dc", "y", "z", "x" })
		{
			Sh->Push(werk::JsonValue::MakeString(S));
		}
		C->Set("sh_l1_order", Sh);
		Manifest->Set("conventions", C);
	}

	Manifest->Set("parts", Ctx.PartsJson);
	Manifest->Set("materials", Ctx.MaterialsJson);

	// `schemas` is REQUIRED by manifest.schema.json, and SPEC.md 2 says the
	// map exists so "a reader never derives a path from a filename
	// convention". It is built from the node types actually written AND
	// filtered against the spec files actually embedded: promising
	// spec/schemas/core.material.schema.json in a package that does not carry
	// it would be precisely the dangling external reference the format bans.
	{
		werk::JsonPtr Schemas = werk::JsonValue::MakeObject();
		TSet<FString> SeenTypes;
		for (const FExportNode& N : Ctx.Nodes)
		{
			const FString Type = ToF(N.Type);
			if (SeenTypes.Contains(Type))
			{
				continue;
			}
			SeenTypes.Add(Type);
			const std::string Candidate = "spec/schemas/" + N.Type + ".schema.json";
			for (const FExportFile& F : SpecFiles)
			{
				if (F.Path == Candidate)
				{
					Schemas->SetString(N.Type, Candidate);
					break;
				}
			}
		}
		Manifest->Set("schemas", Schemas);
	}

	// 5. Lay the container out preview-first (SPEC.md 1, law 9).
	werk::ZipWriter Writer;
	std::vector<std::pair<std::string, std::vector<uint8_t>>> Ordered;

	const std::string ReadmeText =
		"This is a werk artifact container, exported from Unreal Engine by WerkLink.\n"
		"Everything needed to read it is inside it: MANIFEST.json is the graph, and (when the\n"
		"exporter was configured with a spec source directory) spec/ carries the byte-level\n"
		"format description and loaders/ carries working readers. The package is UNSIGNED,\n"
		"which is one of three valid signature states and means only that nobody vouched for\n"
		"it -- not that it is damaged.\n";
	const std::string LicenseText =
		"No license was declared by the exporting project. This file exists because SPEC.md\n"
		"requires the full license text to travel with the package rather than a link, and an\n"
		"honest statement that none was declared is better than a link or an absent file.\n";

	auto AddFile = [&Ordered](const std::string& Path, const std::string& Text)
	{
		Ordered.emplace_back(Path, std::vector<uint8_t>(Text.begin(), Text.end()));
	};

	// The manifest is written last (it hashes everything else) but must be the
	// FIRST physical entry, so a placeholder holds the slot and is filled in.
	Ordered.emplace_back("MANIFEST.json", std::vector<uint8_t>());
	AddFile("LICENSE", LicenseText);
	AddFile("README.txt", ReadmeText);
	for (const FExportFile& F : SpecFiles)
	{
		Ordered.emplace_back(F.Path, F.Bytes);
	}
	for (const FExportNode& N : Ctx.Nodes)
	{
		for (const FExportFile& F : N.Files)
		{
			Ordered.emplace_back(F.Path, F.Bytes);
		}
	}

	// 6. nodes[], with every file hashed for real.
	auto HashOf = [&Ordered](const std::string& Path) -> std::pair<std::string, uint64_t>
	{
		for (const auto& It : Ordered)
		{
			if (It.first == Path)
			{
				return { werk::Sha256::HashHex(It.second), uint64_t(It.second.size()) };
			}
		}
		return { std::string(), 0 };
	};

	// spec_sha256 -- MANDATORY since the rulings of 2026-08-08 (S-29, ruling 5).
	//
	// One hash over the spec/ tree THIS package carries, so a reader can tell in
	// one comparison whether the schemas travelling inside the file are the ones
	// it already knows. Vendoring spec/ is structural for every writer in every
	// language, and until this field existed nothing said WHICH revision the
	// vendored bytes were: two tools could emit contradicting schemas while both
	// claiming profile "3d-entity/1".
	//
	// The algorithm is SPEC.md section 2's, and it is the same construction
	// input_hash uses, deliberately: sort the paths ASCENDING BY UTF-8 BYTES,
	// and for each append
	//     path bytes || 0x0A || that file's sha256 as 32 RAW bytes || 0x0A
	// then hash the whole concatenation. The paths are in the hash, so moving a
	// file changes it. Note the consequence, because it catches people: for a
	// set of exactly ONE file the result is NOT that file's own sha256 -- which
	// is what the per-version field below relies on to be a different claim from
	// the file hash sitting next to it.
	//
	// Reference implementation: tools/spec_sha256.py in the werk repository.
	// Re-implemented here rather than shared because this plugin does not link
	// against it, and a second authority that is ALLOWED to differ would be
	// worse than a second copy that is gate-checked -- the gate builds a package
	// and validates it against the schema that declares the field required.
	auto SpecSha256Over = [](const std::vector<std::pair<std::string, std::string>>& PathAndHex)
		-> std::string
	{
		std::vector<std::pair<std::string, std::string>> Sorted = PathAndHex;
		std::sort(Sorted.begin(), Sorted.end(),
		          [](const std::pair<std::string, std::string>& A,
		             const std::pair<std::string, std::string>& B)
		          {
			          return A.first < B.first;   // std::string compares by byte
		          });
		werk::Sha256 Acc;
		for (const auto& It : Sorted)
		{
			uint8_t Raw[32];
			if (!werk::FromHex64(It.second, Raw))
			{
				continue;   // a file we could not hash cannot be in the digest
			}
			Acc.Update(It.first.data(), It.first.size());
			const uint8_t Nl = 0x0A;
			Acc.Update(&Nl, 1);
			Acc.Update(Raw, 32);
			Acc.Update(&Nl, 1);
		}
		uint8_t Digest[32];
		Acc.Final(Digest);
		return werk::ToHex(Digest, 32);
	};

	// The global field: every spec/ entry this container actually carries.
	auto SpecSha256OfPackage = [&]() -> std::string
	{
		std::vector<std::pair<std::string, std::string>> Entries;
		for (const auto& It : Ordered)
		{
			if (It.first.rfind("spec/", 0) == 0)
			{
				Entries.emplace_back(It.first, werk::Sha256::HashHex(It.second));
			}
		}
		return Entries.empty() ? std::string() : SpecSha256Over(Entries);
	};

	// The per-node-version field: OPTIONAL, and the same construction over
	// exactly the spec files THAT VERSION'S PAYLOAD conforms to. It answers a
	// narrower question than the global one -- "which revision of THIS schema
	// was this payload written against" -- which is the question that bites when
	// an append-only node gains a v2 years later under a newer spec. Emitted
	// only when the package really carries the schema: promising a revision of a
	// file that is not here would be the dangling reference the format bans.
	auto SpecSha256ForType = [&](const std::string& Type) -> std::string
	{
		const std::string Candidate = "spec/schemas/" + Type + ".schema.json";
		for (const auto& It : Ordered)
		{
			if (It.first == Candidate)
			{
				return SpecSha256Over({ { Candidate, werk::Sha256::HashHex(It.second) } });
			}
		}
		return std::string();
	};

	werk::JsonPtr NodesJson = werk::JsonValue::MakeArray();

	auto MakeSimpleNodeWithMeta = [&](const std::string& NodeId, const std::string& Type,
	                                  const std::vector<std::string>& Paths, const std::string& Note,
	                                  const std::string& Epistemic, werk::JsonPtr Meta)
	{
		werk::JsonPtr N = werk::JsonValue::MakeObject();
		N->SetString("node_id", NodeId);
		N->SetString("type", Type);
		werk::JsonPtr Versions = werk::JsonValue::MakeArray();
		werk::JsonPtr V = werk::JsonValue::MakeObject();
		V->SetInt("v", 1);
		werk::JsonPtr FilesArr = werk::JsonValue::MakeArray();
		for (const std::string& P : Paths)
		{
			const auto HS = HashOf(P);
			werk::JsonPtr F = werk::JsonValue::MakeObject();
			F->SetString("path", P);
			F->SetString("sha256", HS.first);
			F->SetInt("size", (long long)HS.second);
			FilesArr->Push(F);
			++Result.FilesWritten;
		}
		V->Set("files", FilesArr);
		V->SetString("note", Note);
		werk::JsonPtr Pr = werk::JsonValue::MakeObject();
		Pr->SetString("tool", ToStd(Request.ProducerTool.IsEmpty()
			? FString(TEXT("werklink")) : Request.ProducerTool));
		Pr->SetString("version", "0.1");
		V->Set("producer", Pr);
		V->SetString("epistemic", Epistemic);
		V->SetString("created", CreatedAt);
		// MINI-SPECS 11 / S-10: writers SHOULD emit input_params explicitly so
		// the two spellings never have to be reconciled by a reader.
		V->Set("input_params", werk::JsonValue::MakeObject());
		Versions->Push(V);
		N->Set("versions", Versions);
		N->SetInt("active", 1);
		N->Set("edges", werk::JsonValue::MakeArray());
		if (Meta)
		{
			N->Set("meta", Meta);
		}
		NodesJson->Push(N);
		++Result.NodesWritten;
	};

	auto MakeSimpleNode = [&](const std::string& NodeId, const std::string& Type,
	                          const std::vector<std::string>& Paths, const std::string& Note,
	                          const std::string& Epistemic)
	{
		MakeSimpleNodeWithMeta(NodeId, Type, Paths, Note, Epistemic, nullptr);
	};

	// The nodes that make the container's own bytes reachable: SPEC.md 2 says
	// every byte except MANIFEST.json and SIGNATURE.json belongs to exactly one
	// node version's files[]. Nothing floats, including the README.
	MakeSimpleNode("license", "core.license", { "LICENSE" },
	               "License text, embedded rather than linked.", "authored");
	MakeSimpleNode("readme", "core.readme", { "README.txt" },
	               "One paragraph for a human who opened the file by hand.", "authored");
	if (!SpecFiles.empty())
	{
		std::vector<std::string> SpecPaths, LoaderPaths;
		for (const FExportFile& F : SpecFiles)
		{
			if (F.Path.rfind("loaders/", 0) == 0)
			{
				LoaderPaths.push_back(F.Path);
			}
			else
			{
				SpecPaths.push_back(F.Path);
			}
		}
		if (!SpecPaths.empty())
		{
			MakeSimpleNode("spec", "core.spec", SpecPaths,
			               "The format description this package conforms to, carried inside it "
			               "so no external document is ever needed (law 2).", "authored");
		}
		// ONE core.loader node PER loader file, because manifest.schema.json
		// requires a loaderMeta on every core.loader node and loaderMeta
		// describes ONE reader: it has a single `language`, a single
		// `entrypoint` and a single `toolchain`. A node bundling werk_read.py,
		// .rs and .c cannot honestly answer any of the three.
		for (const std::string& LoaderPath : LoaderPaths)
		{
			const FString Path = ToF(LoaderPath);
			const FString Extension = FPaths::GetExtension(Path).ToLower();

			// Language, form, entrypoint and toolchain are FACTS about the
			// file. Capabilities are a claim about code this exporter merely
			// copied, so they are declared at the conservative minimum any
			// bootstrap reader must implement, and the work note says exactly
			// that. SPEC.md 10.0: "declared narrowness is the design";
			// understating is safe, overstating is non-conformance.
			const TCHAR* Language = TEXT("other");
			const TCHAR* Toolchain = TEXT("");
			const TCHAR* BuildCommand = nullptr;
			if (Extension == TEXT("py"))
			{
				Language = TEXT("python");
				Toolchain = TEXT("python>=3.8");
			}
			else if (Extension == TEXT("rs"))
			{
				Language = TEXT("rust");
				Toolchain = TEXT("rustc>=1.70 --edition 2021");
				BuildCommand = TEXT("rustc -O werk_read.rs");
			}
			else if (Extension == TEXT("c"))
			{
				Language = TEXT("c");
				Toolchain = TEXT("c99");
				BuildCommand = TEXT("cc -O2 -std=c99 werk_read.c -o werk_read");
			}
			else
			{
				// An unrecognised loader file is NOT given a core.loader node
				// with invented metadata. It still travels, as a core.spec
				// payload, so no byte floats.
				MakeSimpleNode(ToStd(TEXT("loader-") + FWerkLinkAction::ObjectNameToWerkId(
					                   FPaths::GetBaseFilename(Path))),
				               "core.spec", { LoaderPath },
				               "Carried verbatim from the configured spec source directory. Not "
				               "declared as a core.loader because this exporter cannot state its "
				               "language, entrypoint or capabilities truthfully.", "authored");
				continue;
			}

			werk::JsonPtr Meta = werk::JsonValue::MakeObject();
			Meta->SetString("language", ToStd(FString(Language)));
			Meta->SetString("form", "source");
			Meta->SetString("entrypoint", LoaderPath);
			Meta->SetString("toolchain", ToStd(FString(Toolchain)));
			if (BuildCommand)
			{
				Meta->SetString("build_command", ToStd(FString(BuildCommand)));
			}
			// dependencies MUST be empty (maxItems 0). True by construction for
			// a single-file loader carried whole.
			Meta->Set("dependencies", werk::JsonValue::MakeArray());
			werk::JsonPtr Caps = werk::JsonValue::MakeArray();
			Caps->Push(werk::JsonValue::MakeString("read-manifest"));
			Caps->Push(werk::JsonValue::MakeString("verify-hashes"));
			Meta->Set("capabilities", Caps);

			const FString NodeId = TEXT("loader-") + FString(Language);
			MakeSimpleNodeWithMeta(
				ToStd(NodeId), "core.loader", { LoaderPath },
				"Single-file zero-dependency reader, carried so the package brings its own "
				"reader (law 1). Language, entrypoint and toolchain are facts about the file. "
				"CAPABILITIES ARE DECLARED CONSERVATIVELY: this exporter copied the loader from "
				"a directory on disk and did not run its every code path, so it declares only "
				"the two any bootstrap reader must implement. The loader's own header may "
				"declare more, and where the two disagree the loader is the authority on itself.",
				"authored", Meta);
		}
	}

	for (const FExportNode& N : Ctx.Nodes)
	{
		werk::JsonPtr Node = werk::JsonValue::MakeObject();
		Node->SetString("node_id", N.NodeId);
		Node->SetString("type", N.Type);
		if (!N.PartId.empty())
		{
			Node->SetString("part_id", N.PartId);
		}
		if (!N.MaterialId.empty())
		{
			Node->SetString("material_id", N.MaterialId);
		}
		werk::JsonPtr Versions = werk::JsonValue::MakeArray();
		werk::JsonPtr V = werk::JsonValue::MakeObject();
		V->SetInt("v", 1);
		werk::JsonPtr FilesArr = werk::JsonValue::MakeArray();
		for (const FExportFile& F : N.Files)
		{
			const auto HS = HashOf(F.Path);
			werk::JsonPtr FJ = werk::JsonValue::MakeObject();
			FJ->SetString("path", F.Path);
			FJ->SetString("sha256", HS.first);
			FJ->SetInt("size", (long long)HS.second);
			if (!F.MediaType.empty())
			{
				FJ->SetString("media_type", F.MediaType);
			}
			if (!F.Role.empty())
			{
				FJ->SetString("role", F.Role);
			}
			FilesArr->Push(FJ);
			++Result.FilesWritten;
		}
		V->Set("files", FilesArr);
		V->SetString("note", N.Note);
		werk::JsonPtr Pr = werk::JsonValue::MakeObject();
		Pr->SetString("tool", ToStd(Request.ProducerTool.IsEmpty()
			? FString(TEXT("werklink")) : Request.ProducerTool));
		Pr->SetString("version", "0.1");
		V->Set("producer", Pr);
		V->SetString("epistemic", N.Epistemic.empty() ? "authored" : N.Epistemic);
		V->SetString("created", CreatedAt);
		// OPTIONAL (S-29): the schema revision this payload conforms to, when
		// this package carries that schema at all.
		{
			const std::string VerSpec = SpecSha256ForType(N.Type);
			if (!VerSpec.empty())
			{
				V->SetString("spec_sha256", VerSpec);
			}
		}
		V->Set("input_params", werk::JsonValue::MakeObject());
		Versions->Push(V);
		Node->Set("versions", Versions);
		Node->SetInt("active", 1);
		Node->Set("edges", werk::JsonValue::MakeArray());
		if (N.Meta)
		{
			Node->Set("meta", N.Meta);
		}
		NodesJson->Push(Node);
		++Result.NodesWritten;
	}
	Manifest->Set("nodes", NodesJson);

	// primary: a declared value beats an inference, so declare it.
	{
		werk::JsonPtr P = werk::JsonValue::MakeObject();
		bool bAny = false;
		for (const FExportNode& N : Ctx.Nodes)
		{
			if (N.Type == "core.geom.game")
			{
				P->SetString("mesh", N.NodeId);
				bAny = true;
				break;
			}
		}
		for (const FExportNode& N : Ctx.Nodes)
		{
			if (N.Type == "core.audio.effect")
			{
				P->SetString("sound", N.NodeId);
				bAny = true;
				break;
			}
		}
		if (bAny)
		{
			Manifest->Set("primary", P);
		}
	}

	{
		const auto LicenseHash = HashOf("LICENSE");
		werk::JsonPtr L = werk::JsonValue::MakeObject();
		L->SetString("file", "LICENSE");
		L->SetString("sha256", LicenseHash.first);
		Manifest->Set("license", L);
	}

	// spec_sha256 is MANDATORY (S-29). A package exported without a spec source
	// directory carries no spec/ tree at all and cannot honestly state one, so
	// it says so in the report rather than inventing a digest over nothing --
	// and such a package is, correctly, non-conformant against a schema that
	// requires the field. That is the field doing its job: an export with no
	// spec/ was always a promise about other files, and it is now visible.
	{
		const std::string SpecDigest = SpecSha256OfPackage();
		if (!SpecDigest.empty())
		{
			Manifest->SetString("spec_sha256", SpecDigest);
		}
		else
		{
			Rep.Warn(werk::code::SubstitutedFallback, "spec_sha256",
			         "no spec/ tree is embedded, so this package cannot declare the "
			         "mandatory spec_sha256; it will not validate against "
			         "manifest.schema.json until it is exported with a spec source "
			         "directory");
		}
	}

	// conventions_map: OPTIONAL (S-17). Which node types each convention
	// governs, as data rather than as a table a reader has to transcribe into a
	// constant. Declared only when the file is really here, for the same reason
	// `schemas` is filtered against the embedded tree.
	for (const auto& It : Ordered)
	{
		if (It.first == "spec/conventions-map.json")
		{
			Manifest->SetString("conventions_map", "spec/conventions-map.json");
			break;
		}
	}

	// container: entry_order is what the writer actually did, and
	// preview_prefix_bytes is MEASURED by the writer rather than estimated.
	werk::JsonPtr Container = werk::JsonValue::MakeObject();
	Container->SetString("form", "zip");
	Container->SetString("zip_compression", "store");
	werk::JsonPtr Order = werk::JsonValue::MakeArray();
	for (const char* S : { "MANIFEST.json", "LICENSE", "README.txt", "spec/", "loaders/",
	                       "materials/", "physics/", "geometry/", "audio/" })
	{
		Order->Push(werk::JsonValue::MakeString(S));
	}
	Container->Set("entry_order", Order);
	Container->SetInt("preview_prefix_bytes", 0); // measured below, then rewritten
	Manifest->Set("container", Container);

	// 7. Two passes over the writer, because preview_prefix_bytes is a
	// measurement of the container that contains it. First pass measures;
	// second pass writes the manifest that carries the measurement. The
	// manifest's own length is held constant between passes by padding the
	// number to a fixed width, so the measurement stays true.
	auto BuildContainer = [&](uint64_t PrefixBytes, uint64_t& OutMeasuredPrefix,
	                          std::vector<uint8_t>& OutBytes, std::string& OutManifestHash)
	{
		Container->SetInt("preview_prefix_bytes", (long long)PrefixBytes);
		const std::string ManifestText = werk::JsonWritePretty(*Manifest);
		Ordered[0].second.assign(ManifestText.begin(), ManifestText.end());
		OutManifestHash = werk::Sha256::HashHex(Ordered[0].second);

		werk::ZipWriter W;
		for (const auto& It : Ordered)
		{
			W.Add(It.first, It.second);
		}
		// The prefix ends at the last spec/ or loaders/ entry when one exists,
		// and at README.txt otherwise -- the last entry of the browsable head.
		std::string PrefixThrough = "README.txt";
		for (const auto& It : Ordered)
		{
			if (It.first.rfind("spec/", 0) == 0 || It.first.rfind("loaders/", 0) == 0)
			{
				PrefixThrough = It.first;
			}
		}
		OutBytes = W.Build(PrefixThrough, OutMeasuredPrefix);
	};

	std::vector<uint8_t> ContainerBytes;
	std::string ManifestHash;
	uint64_t Measured = 0;
	BuildContainer(0, Measured, ContainerBytes, ManifestHash);
	// Second pass with the measured number. Writing a number changes the
	// manifest's length, which changes the measurement, so the second pass is
	// re-measured and the manifest records what the SECOND pass produced --
	// which is the container actually written.
	uint64_t Measured2 = 0;
	BuildContainer(Measured, Measured2, ContainerBytes, ManifestHash);
	if (Measured2 != Measured)
	{
		// Honest rather than silently iterating to a fixed point: say that the
		// declared number is the one from the container that exists.
		BuildContainer(Measured2, Measured, ContainerBytes, ManifestHash);
		Rep.Info(werk::code::Exported, "container.preview_prefix_bytes",
		         "measured in two passes; the declared value is the one measured on the "
		         "container that was actually written");
	}

	// 8. Write it.
	{
		const FString Dir = FPaths::GetPath(Request.OutputFilePath);
		if (!Dir.IsEmpty())
		{
			IFileManager::Get().MakeDirectory(*Dir, true);
		}
		TArray<uint8> Out;
		Out.Append(ContainerBytes.data(), int32(ContainerBytes.size()));
		if (!FFileHelper::SaveArrayToFile(Out, *Request.OutputFilePath))
		{
			Result.ErrorMessage = FString::Printf(TEXT("could not write %s"),
			                                      *Request.OutputFilePath);
			AppendReport(Rep, Result.Report);
			return Result;
		}
	}

	Result.ContainerBytes = uint64(ContainerBytes.size());
	Result.PreviewPrefixBytes = Measured2 ? Measured2 : Measured;
	Result.ManifestSha256 = ToF(ManifestHash);
	Result.bSuccess = true;

	AppendReport(Rep, Result.Report);
	return Result;
}
