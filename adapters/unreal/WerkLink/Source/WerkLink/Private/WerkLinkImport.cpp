// .werk -> UAssets.
//
// Graceful degradation is the governing rule and it is structural, not
// aspirational: every node produces exactly one FWerkNodeOutcome, an
// unreadable or unimplemented node produces a `skipped`/`refused` outcome, and
// nothing in this file can fail the whole file for one bad node. The only
// early return is a CONTAINER-scoped refusal (SPEC.md 10.1), which is the one
// scope allowed to be empty-handed.
//
// Findings B11: geometry is built as an FMeshDescription directly rather than
// handed to Interchange. The justification is in adapters/unreal/README.md and
// in docs/UE-CONTENTMOVER-FINDINGS.md; the short form is that werk's manifest
// is the authority on materials (SPEC.md 10.2 makes taking them from the GLB
// non-conformant), and a translator pipeline that helpfully builds materials
// out of the GLB is actively wrong here.

#include "CoreMinimal.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Factories/MaterialInstanceConstantFactoryNew.h"
#include "Factories/TextureFactory.h"
#include "Factories/SoundFactory.h"
#include "FileHelpers.h"
#include "HAL/PlatformFileManager.h"
#include "MaterialEditingLibrary.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/BoxElem.h"
#include "PhysicsEngine/SphereElem.h"
#include "Sound/SoundWave.h"
#include "StaticMeshAttributes.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

#include "WerkAssetUserData.h"
#include "WerkLinkAction.h"
#include "WerkLinkBridge.h"
#include "WerkMaterialSlots.h"
#include "WerkScopedQuietValidators.h"

#include "werk_basis.h"
#include "werk_glb.h"
#include "werk_json.h"
#include "werk_manifest.h"
#include "werk_report.h"

using namespace WerkBridge;

namespace
{
	struct FImportContext
	{
		werk::Package*        Pkg = nullptr;
		werk::Report*         Rep = nullptr;
		FWerkImportResult*    Result = nullptr;
		const FWerkImportRequest* Request = nullptr;
		FString               PackageRoot;   // e.g. /Game/Werk/WoodenCrate
		TArray<UPackage*>     Touched;
		/** node id -> created asset, so later nodes can attach to earlier ones. */
		TMap<FString, UObject*> ByNodeId;
	};

	void Note(FImportContext& Ctx, const werk::Node& N, EWerkOutcome Outcome,
	          const TCHAR* Code, const FString& Detail, const FString& AssetPath = FString())
	{
		FWerkNodeOutcome Out;
		Out.NodeId = ToF(N.nodeId);
		Out.NodeType = ToF(N.type);
		Out.Outcome = Outcome;
		Out.Code = Code;
		Out.Detail = Detail;
		Out.AssetPath = AssetPath;
		Ctx.Result->Outcomes.Add(MoveTemp(Out));

		switch (Outcome)
		{
		case EWerkOutcome::Imported:    ++Ctx.Result->NodesImported; break;
		case EWerkOutcome::Refused:     ++Ctx.Result->NodesRefused;  break;
		case EWerkOutcome::Substituted: ++Ctx.Result->NodesImported; break;
		default:                        ++Ctx.Result->NodesSkipped;  break;
		}
	}

	UPackage* MakePackage(FImportContext& Ctx, const FString& AssetName, FString& OutObjectPath)
	{
		const FString PackagePath = Ctx.PackageRoot / AssetName;
		OutObjectPath = PackagePath + TEXT(".") + AssetName;
		UPackage* Package = CreatePackage(*PackagePath);
		if (Package)
		{
			Package->FullyLoad();
			Ctx.Touched.AddUnique(Package);
		}
		return Package;
	}

	/** Stamps the identity bridge onto anything that can hold user data. */
	void StampIdentity(FImportContext& Ctx, UObject* Asset, const werk::Node& N)
	{
		IInterface_AssetUserData* Holder = Cast<IInterface_AssetUserData>(Asset);
		if (!Holder)
		{
			return;
		}
		UWerkAssetUserData* Data = NewObject<UWerkAssetUserData>(Asset);
		Data->NodeId = ToF(N.nodeId);
		Data->NodeType = ToF(N.type);
		Data->EntityUuid = ToF(Ctx.Pkg->EntityUuid());
		Data->EntityName = ToF(Ctx.Pkg->EntityName());
		Data->PartId = ToF(N.partId);
		Data->MaterialId = ToF(N.materialId);
		Data->ImportedFrom = Ctx.Request->WerkFilePath;
		if (const werk::NodeVersion* V = N.Resolved())
		{
			Data->SourceVersion = V->v;
			Data->WorkNote = ToF(V->note);
			Data->Epistemic = ToF(V->epistemic);
			if (!V->files.empty())
			{
				Data->SourceFilePath = ToF(V->files[0].path);
				Data->SourceSha256 = ToF(V->files[0].sha256);
			}
		}
		Holder->AddAssetUserData(Data);

#if WITH_METADATA
		// Package metadata, so the identity survives even for a consumer that
		// never looks at UAssetUserData. UMetaData became FMetaData on UPackage
		// in 5.6; this is the current spelling.
		if (UPackage* Package = Asset->GetPackage())
		{
			FMetaData& Meta = Package->GetMetaData();
			Meta.SetValue(Asset, TEXT("werk.node_id"), *ToF(N.nodeId));
			Meta.SetValue(Asset, TEXT("werk.node_type"), *ToF(N.type));
			Meta.SetValue(Asset, TEXT("werk.entity_uuid"), *ToF(Ctx.Pkg->EntityUuid()));
			if (const werk::NodeVersion* V = N.Resolved())
			{
				Meta.SetValue(Asset, TEXT("werk.epistemic"), *ToF(V->epistemic));
				Meta.SetValue(Asset, TEXT("werk.note"), *ToF(V->note));
			}
		}
#endif
	}

	/** The first payload of a node whose path ends with the given suffix. */
	bool ReadNodeFile(FImportContext& Ctx, const werk::Node& N, const char* Suffix,
	                  std::vector<uint8_t>& Out, std::string& OutPath)
	{
		const werk::NodeVersion* V = N.Resolved();
		if (!V)
		{
			return false;
		}
		const size_t SuffixLen = std::char_traits<char>::length(Suffix);
		for (const werk::FileRef& F : V->files)
		{
			if (SuffixLen == 0
				|| (F.path.size() >= SuffixLen
				    && F.path.compare(F.path.size() - SuffixLen, SuffixLen, Suffix) == 0))
			{
				OutPath = F.path;
				return Ctx.Pkg->ReadPayload(F.path, Out, *Ctx.Rep);
			}
		}
		return false;
	}

	// --- geometry ----------------------------------------------------------

	/**
	 * werk GLB -> FMeshDescription, crossing the basis exactly once.
	 *
	 * Every position is a PositionWerkToUe (metres -> centimetres, axes
	 * permuted, one negated); every normal and tangent is a
	 * DirectionWerkToUe (no unit scale); and every triangle's index order is
	 * reversed, because det(M) = -1. The reversal is done by emitting the
	 * corners in the order 0, 2, 1 rather than by mutating the index array, so
	 * a reader can see the winding decision at the point it takes effect.
	 */
	bool BuildMeshDescription(const werk::GlbMesh& Glb, FMeshDescription& Out, bool& bOutHadNormals)
	{
		Out.Empty();
		FStaticMeshAttributes Attributes(Out);
		Attributes.Register();

		// S10-6, and it is a silent one: SetNumUVChannels REALLOCATES the UV
		// attribute array, so a TVertexInstanceAttributesRef taken before it is
		// a view of the old storage. Writing through that stale ref succeeds --
		// no assert, no warning, no error -- and the mesh comes out with every
		// UV at (0, 0). Every count in every report was still correct, so the
		// import looked perfect and the crate rendered as one flat texel of its
		// own albedo. It was found by pointing a camera at it: an engine cube
		// with the same material and the same texture rendered the planks
		// correctly, which is what separated "the mesh" from "the material".
		//
		// So the channel count is decided FIRST and the refs are taken after.
		int32 UVChannels = 1;
		for (const werk::GlbPrimitive& P : Glb.primitives)
		{
			if (!P.uv1.empty())
			{
				UVChannels = 2;
			}
		}
		Out.SetNumUVChannels(UVChannels);

		TVertexAttributesRef<FVector3f> Positions = Attributes.GetVertexPositions();
		TVertexInstanceAttributesRef<FVector3f> Normals = Attributes.GetVertexInstanceNormals();
		TVertexInstanceAttributesRef<FVector3f> Tangents = Attributes.GetVertexInstanceTangents();
		TVertexInstanceAttributesRef<float> BinormalSigns = Attributes.GetVertexInstanceBinormalSigns();
		TVertexInstanceAttributesRef<FVector4f> Colors = Attributes.GetVertexInstanceColors();
		TVertexInstanceAttributesRef<FVector2f> UVs = Attributes.GetVertexInstanceUVs();

		bOutHadNormals = true;
		const FPolygonGroupID PolygonGroup = Out.CreatePolygonGroup();
		Attributes.GetPolygonGroupMaterialSlotNames()[PolygonGroup] = FName(TEXT("werk"));

		for (const werk::GlbPrimitive& P : Glb.primitives)
		{
			const int32 VertexCount = int32(P.VertexCount());
			if (VertexCount == 0 || P.indices.empty())
			{
				continue;
			}
			if (P.normals.empty())
			{
				bOutHadNormals = false;
			}

			TArray<FVertexID> VertexIds;
			VertexIds.Reserve(VertexCount);
			Out.ReserveNewVertices(VertexCount);
			for (int32 i = 0; i < VertexCount; ++i)
			{
				const werk::Vec3 W = { P.positions[size_t(i) * 3 + 0],
				                       P.positions[size_t(i) * 3 + 1],
				                       P.positions[size_t(i) * 3 + 2] };
				const werk::Vec3 U = werk::PositionWerkToUe(W);
				const FVertexID Id = Out.CreateVertex();
				Positions[Id] = FVector3f(float(U[0]), float(U[1]), float(U[2]));
				VertexIds.Add(Id);
			}

			// ONE vertex instance per vertex, created up front and shared by
			// every triangle that uses it.
			//
			// A GLB indexes every attribute with the same index buffer, so all
			// corners referring to vertex i carry identical attributes and
			// there is nothing a per-corner instance could express that a
			// per-vertex one cannot. Creating one instance per CORNER instead
			// (the obvious first version of this loop) is not wrong
			// geometrically, but it makes the mesh description hold 3x the
			// instances, and the exporter -- which emits one GLB vertex per
			// vertex instance -- then round-trips 272 vertices back out as
			// 1224. Measured, on the golden fixture, before this was fixed.
			TArray<FVertexInstanceID> InstanceIds;
			InstanceIds.Init(FVertexInstanceID::Invalid, VertexCount);
			auto MakeInstance = [&](int32 VertexIndex) -> FVertexInstanceID
			{
				if (InstanceIds[VertexIndex] != FVertexInstanceID::Invalid)
				{
					return InstanceIds[VertexIndex];
				}
				const FVertexInstanceID Inst = Out.CreateVertexInstance(VertexIds[VertexIndex]);
				InstanceIds[VertexIndex] = Inst;
				const size_t V = size_t(VertexIndex);

				if (!P.normals.empty() && V * 3 + 2 < P.normals.size())
				{
					const werk::Vec3 N = werk::DirectionWerkToUe(
						{ P.normals[V * 3 + 0], P.normals[V * 3 + 1], P.normals[V * 3 + 2] });
					Normals[Inst] = FVector3f(float(N[0]), float(N[1]), float(N[2]));
				}
				if (!P.tangents.empty() && V * 4 + 3 < P.tangents.size())
				{
					const werk::Vec3 T = werk::DirectionWerkToUe(
						{ P.tangents[V * 4 + 0], P.tangents[V * 4 + 1], P.tangents[V * 4 + 2] });
					Tangents[Inst] = FVector3f(float(T[0]), float(T[1]), float(T[2]));
					// SPEC.md 3.10: w is the bitangent sign, +1 or -1 exactly,
					// such that bitangent = cross(normal, tangent.xyz) * w.
					// The basis change mirrors, so the handedness of the
					// tangent frame flips with it and the sign negates.
					BinormalSigns[Inst] = -P.tangents[V * 4 + 3];
				}
				if (!P.colors.empty() && V * 4 + 3 < P.colors.size())
				{
					// SPEC.md 3.10: COLOR_0 is LINEAR, never sRGB. Handed over
					// unchanged; the material decides what to do with it.
					Colors[Inst] = FVector4f(P.colors[V * 4 + 0], P.colors[V * 4 + 1],
					                         P.colors[V * 4 + 2], P.colors[V * 4 + 3]);
				}
				if (!P.uv0.empty() && V * 2 + 1 < P.uv0.size())
				{
					// uv_origin is top-left on both sides, so UVs do NOT flip.
					// That is a deliberate non-conversion.
					UVs.Set(Inst, 0, FVector2f(P.uv0[V * 2 + 0], P.uv0[V * 2 + 1]));
				}
				if (UVChannels > 1 && !P.uv1.empty() && V * 2 + 1 < P.uv1.size())
				{
					UVs.Set(Inst, 1, FVector2f(P.uv1[V * 2 + 0], P.uv1[V * 2 + 1]));
				}
				return Inst;
			};

			for (size_t T = 0; T + 2 < P.indices.size(); T += 3)
			{
				const int32 A = int32(P.indices[T + 0]);
				const int32 B = int32(P.indices[T + 1]);
				const int32 C = int32(P.indices[T + 2]);
				if (A >= VertexCount || B >= VertexCount || C >= VertexCount)
				{
					continue;
				}
				// The winding reversal, at the one place it takes effect.
				const FVertexInstanceID I0 = MakeInstance(A);
				const FVertexInstanceID I1 = MakeInstance(C);
				const FVertexInstanceID I2 = MakeInstance(B);
				const FVertexInstanceID Corners[3] = { I0, I1, I2 };
				Out.CreatePolygon(PolygonGroup, Corners);
			}
		}

		return Out.Triangles().Num() > 0;
	}

	UStaticMesh* ImportGeometry(FImportContext& Ctx, const werk::Node& N,
	                            const TArray<const werk::Node*>& LodNodes)
	{
		std::vector<uint8_t> Bytes;
		std::string Path;
		if (!ReadNodeFile(Ctx, N, ".glb", Bytes, Path))
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("file-missing"),
			     TEXT("no readable .glb payload"));
			return nullptr;
		}

		const bool bRequireNormals = (N.type != "core.geom.source");
		werk::GlbMesh Glb;
		if (!werk::GlbRead(Bytes, bRequireNormals, Glb, N.nodeId, *Ctx.Rep))
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("payload-schema-invalid"),
			     TEXT("GLB did not parse"));
			return nullptr;
		}

		// The UV extent of the mesh as BUILT, not as parsed. S10-6 was a
		// write that went nowhere, so a check on the GLB would have passed
		// while the mesh was wrong; this measures the FMeshDescription that
		// actually becomes the asset. A textured entity whose UVs all collapse
		// to one point renders one texel and is otherwise indistinguishable
		// from a correct import, so the number is reported every time rather
		// than only when something looks wrong.
		auto UvExtent = [](const FMeshDescription& D, FVector2f& Lo, FVector2f& Hi) -> int32
		{
			FStaticMeshConstAttributes A(D);
			TVertexInstanceAttributesConstRef<FVector2f> U = A.GetVertexInstanceUVs();
			Lo = FVector2f(FLT_MAX, FLT_MAX);
			Hi = FVector2f(-FLT_MAX, -FLT_MAX);
			int32 Count = 0;
			if (U.GetNumChannels() == 0)
			{
				return 0;
			}
			for (const FVertexInstanceID Id : D.VertexInstances().GetElementIDs())
			{
				const FVector2f V = U.Get(Id, 0);
				Lo.X = FMath::Min(Lo.X, V.X); Lo.Y = FMath::Min(Lo.Y, V.Y);
				Hi.X = FMath::Max(Hi.X, V.X); Hi.Y = FMath::Max(Hi.Y, V.Y);
				++Count;
			}
			return Count;
		};

		FMeshDescription Lod0;
		bool bHadNormals = true;
		if (!BuildMeshDescription(Glb, Lod0, bHadNormals))
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("payload-schema-invalid"),
			     TEXT("GLB produced no triangles"));
			return nullptr;
		}

		const FString AssetName = FString(TEXT("SM_"))
		                        + FWerkLinkAction::WerkIdToObjectName(ToF(N.nodeId));
		FString ObjectPath;
		UPackage* Package = MakePackage(Ctx, AssetName, ObjectPath);
		if (!Package)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("container-invalid"),
			     TEXT("could not create the destination package"));
			return nullptr;
		}

		UStaticMesh* Mesh = NewObject<UStaticMesh>(Package, FName(*AssetName),
		                                           RF_Public | RF_Standalone);
		Mesh->InitResources();
		Mesh->SetLightingGuid();

		// Source models, not BuildFromMeshDescriptions: the exporter has to be
		// able to read this mesh's source data back (findings B1), and the
		// fast build path does not necessarily leave any.
		auto AddLod = [&Mesh](FMeshDescription& Desc, int32 LodIndex)
		{
			while (Mesh->GetNumSourceModels() <= LodIndex)
			{
				Mesh->AddSourceModel();
			}
			FMeshDescription* Slot = Mesh->CreateMeshDescription(LodIndex);
			if (Slot)
			{
				*Slot = MoveTemp(Desc);
				Mesh->CommitMeshDescription(LodIndex);
			}
		};

		AddLod(Lod0, 0);

		// LOD chain. SPEC.md 4: lod_level is 1..4 and is declared in the node
		// meta, so the order is read rather than inferred from node order.
		int32 LodsAdded = 0;
		for (const werk::Node* LodNode : LodNodes)
		{
			int32 Level = 1;
			if (LodNode->meta)
			{
				Level = int32(LodNode->meta->GetNumber("lod_level", 1));
			}
			if (Level < 1 || Level > 4)
			{
				Note(Ctx, *LodNode, EWerkOutcome::Skipped, TEXT("payload-schema-invalid"),
				     FString::Printf(TEXT("lod_level %d is outside 1..4"), Level));
				continue;
			}
			std::vector<uint8_t> LodBytes;
			std::string LodPath;
			if (!ReadNodeFile(Ctx, *LodNode, ".glb", LodBytes, LodPath))
			{
				Note(Ctx, *LodNode, EWerkOutcome::Refused, TEXT("file-missing"),
				     TEXT("no readable .glb payload"));
				continue;
			}
			werk::GlbMesh LodGlb;
			if (!werk::GlbRead(LodBytes, true, LodGlb, LodNode->nodeId, *Ctx.Rep))
			{
				Note(Ctx, *LodNode, EWerkOutcome::Refused, TEXT("payload-schema-invalid"),
				     TEXT("LOD GLB did not parse"));
				continue;
			}
			FMeshDescription LodDesc;
			bool bLodNormals = true;
			if (!BuildMeshDescription(LodGlb, LodDesc, bLodNormals))
			{
				Note(Ctx, *LodNode, EWerkOutcome::Refused, TEXT("payload-schema-invalid"),
				     TEXT("LOD GLB produced no triangles"));
				continue;
			}
			AddLod(LodDesc, Level);
			++LodsAdded;
			Note(Ctx, *LodNode, EWerkOutcome::Imported, TEXT("imported"),
			     FString::Printf(TEXT("LOD %d, %d triangles"), Level,
			                     int32(LodGlb.TotalTriangles())),
			     ObjectPath);
		}

		// One material SLOT, named after the polygon group the mesh description
		// actually declares.
		//
		// Found by the Stage 10B proof session and worth stating plainly,
		// because it was invisible from inside: a UStaticMesh built through
		// CreateMeshDescription/CommitMeshDescription has an EMPTY
		// StaticMaterials array. SetMaterial(0, ...) on such a mesh silently
		// does nothing -- it does not grow the array and it does not complain.
		// So the material import reported "assigned to 1 mesh" while assigning
		// to zero slots, and the only way to see it was to ask the live editor
		// what the mesh was actually shaded by. A report that is a claim rather
		// than a measurement is the failure mode this project exists to attack,
		// and this one was ours.
		if (Mesh->GetStaticMaterials().Num() == 0)
		{
			TArray<FStaticMaterial> Slots;
			Slots.Add(FStaticMaterial(nullptr, FName(TEXT("werk")), FName(TEXT("werk"))));
			Mesh->SetStaticMaterials(Slots);
		}

		Mesh->Build(/*bInSilent=*/true);
		Mesh->PostEditChange();

		StampIdentity(Ctx, Mesh, N);
		Ctx.ByNodeId.Add(ToF(N.nodeId), Mesh);
		Ctx.Result->CreatedAssetPaths.Add(ObjectPath);
		++Ctx.Result->AssetsCreated;

		FString Detail = FString::Printf(TEXT("%d verts, %d tris"),
		                                 int32(Glb.TotalVertices()), int32(Glb.TotalTriangles()));
		{
			FVector2f UvLo, UvHi;
			const int32 UvCount = UvExtent(Lod0, UvLo, UvHi);
			if (UvCount == 0)
			{
				Detail += TEXT("; NO UV channel");
			}
			else
			{
				const float SpanU = UvHi.X - UvLo.X;
				const float SpanV = UvHi.Y - UvLo.Y;
				Detail += FString::Printf(TEXT("; uv0 [%.4f,%.4f]-[%.4f,%.4f]"),
				                          UvLo.X, UvLo.Y, UvHi.X, UvHi.Y);
				if (SpanU <= 1e-6f && SpanV <= 1e-6f && !Glb.primitives.empty()
					&& !Glb.primitives[0].uv0.empty())
				{
					// The GLB HAS texture coordinates and the built mesh does
					// not: that is a write that went nowhere (S10-6), and it is
					// the one shape of failure that leaves every count correct.
					Ctx.Rep->Error(werk::code::PayloadSchemaInvalid, N.nodeId,
					               "the GLB declares TEXCOORD_0 but every UV in the built mesh "
					               "collapsed to a single point; a textured material on this mesh "
					               "would sample one texel");
					Detail += TEXT(" -- COLLAPSED, and the GLB has TEXCOORD_0");
				}
			}
		}
		if (LodsAdded > 0)
		{
			Detail += FString::Printf(TEXT(", %d LOD(s)"), LodsAdded);
		}
		if (!bHadNormals)
		{
			// SPEC.md 3.10 / S-9: a source without normals is conformant, and
			// the derived mesh that computes them says so.
			Detail += TEXT("; GLB carried no NORMAL, so normals are computed and this asset is "
			               "a measured derivation, not a faithful copy");
			Note(Ctx, N, EWerkOutcome::Substituted, TEXT("substituted-fallback"), Detail, ObjectPath);
		}
		else
		{
			Note(Ctx, N, EWerkOutcome::Imported, TEXT("imported"), Detail, ObjectPath);
		}
		return Mesh;
	}

	// --- collision ---------------------------------------------------------

	void ImportColliders(FImportContext& Ctx, const werk::Node& N, UStaticMesh* Mesh)
	{
		if (!Mesh)
		{
			Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
			     TEXT("no static mesh to attach simple collision to"));
			return;
		}

		std::vector<uint8_t> Bytes;
		std::string Path;
		if (!ReadNodeFile(Ctx, N, ".json", Bytes, Path))
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("file-missing"), TEXT("no readable payload"));
			return;
		}
		std::string Err;
		werk::JsonPtr Doc = werk::JsonParse(Bytes, Err);
		if (!Doc || !Doc->IsObject())
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("payload-schema-invalid"), ToF(Err));
			return;
		}

		if (!Mesh->GetBodySetup())
		{
			Mesh->CreateBodySetup();
		}
		UBodySetup* Body = Mesh->GetBodySetup();
		if (!Body)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("container-invalid"),
			     TEXT("could not create a body setup"));
			return;
		}
		Body->Modify();
		Body->RemoveSimpleCollision();

		// The shape is core.phys.colliders.schema.json, read rather than
		// guessed: { schema_version, space:"part-local", groups:[ { part_id,
		// spheres:[{center,radius}], boxes:[{center,half_extents,rotation}] } ] }
		// with additionalProperties FALSE at every level. An earlier draft of
		// this importer looked for a flat "colliders" array, which the schema
		// forbids outright.
		//
		// `space` is the const "part-local", i.e. the primitives are already
		// after the part's transform chain. WerkLink v1 imports a single part
		// whose transform is identity, so part-local and model space coincide;
		// when they would not, the group is reported rather than placed wrong.
		const std::string Space = Doc->GetString("space");
		if (!Space.empty() && Space != "part-local")
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("payload-schema-invalid"),
			     FString::Printf(TEXT("space is '%s'; the schema pins it to 'part-local'"),
			                     *ToF(Space)));
			return;
		}

		auto ReadVec3At = [](const werk::JsonValue* Arr) -> werk::Vec3
		{
			werk::Vec3 V = { 0, 0, 0 };
			if (Arr && Arr->Size() == 3)
			{
				for (int k = 0; k < 3; ++k)
				{
					if (const werk::JsonValue* E = Arr->At(size_t(k)))
					{
						V[size_t(k)] = E->number;
					}
				}
			}
			return V;
		};

		int32 Spheres = 0, Boxes = 0, ForeignParts = 0;
		const werk::JsonValue* Groups = Doc->GetArray("groups");
		if (Groups)
		{
			for (size_t g = 0; g < Groups->Size(); ++g)
			{
				const werk::JsonValue* Group = Groups->At(g);
				if (!Group || !Group->IsObject())
				{
					continue;
				}
				const std::string GroupPart = Group->GetString("part_id");

				// One static mesh carries one body setup, so a package with
				// several parts cannot have all its groups placed correctly on
				// one asset. Count them and say so rather than piling them all
				// onto the first mesh.
				if (Ctx.Pkg->Parts().size() > 1)
				{
					const werk::Part* First = Ctx.Pkg->Parts().empty() ? nullptr
					                                                   : &Ctx.Pkg->Parts()[0];
					if (First && GroupPart != First->partId)
					{
						++ForeignParts;
						continue;
					}
				}

				if (const werk::JsonValue* SphereArr = Group->GetArray("spheres"))
				{
					for (size_t i = 0; i < SphereArr->Size(); ++i)
					{
						const werk::JsonValue* S = SphereArr->At(i);
						if (!S || !S->IsObject())
						{
							continue;
						}
						const werk::Vec3 C = werk::PositionWerkToUe(ReadVec3At(S->GetArray("center")));
						FKSphereElem Elem;
						Elem.Center = FVector(C[0], C[1], C[2]);
						// A radius is a length: unit scale, no axis permutation.
						Elem.Radius = float(S->GetNumber("radius", 0.0) * werk::UeUnitsPerWerkUnit);
						Body->AggGeom.SphereElems.Add(Elem);
						++Spheres;
					}
				}

				if (const werk::JsonValue* BoxArr = Group->GetArray("boxes"))
				{
					for (size_t i = 0; i < BoxArr->Size(); ++i)
					{
						const werk::JsonValue* B = BoxArr->At(i);
						if (!B || !B->IsObject())
						{
							continue;
						}
						const werk::Vec3 C = werk::PositionWerkToUe(ReadVec3At(B->GetArray("center")));
						// Half extents are per-axis lengths along the BOX's own
						// axes, so they permute with the axes exactly as a
						// scale triple does, and never inherit the sign flip a
						// position carries.
						const werk::Vec3 H = werk::ScaleWerkToUe(ReadVec3At(B->GetArray("half_extents")));

						werk::Quat Q = { 1, 0, 0, 0 };
						if (const werk::JsonValue* RotArr = B->GetArray("rotation"))
						{
							if (RotArr->Size() == 4)
							{
								for (int k = 0; k < 4; ++k)
								{
									if (const werk::JsonValue* E = RotArr->At(size_t(k)))
									{
										Q[size_t(k)] = E->number; // werk wxyz
									}
								}
							}
						}
						const werk::Quat U = werk::QuatWerkToUe(Q); // UE xyzw

						FKBoxElem Elem;
						Elem.Center = FVector(C[0], C[1], C[2]);
						Elem.Rotation = FQuat(U[0], U[1], U[2], U[3]).Rotator();
						// UE box X/Y/Z are FULL extents; werk's are half.
						Elem.X = float(FMath::Abs(H[0]) * 2.0 * werk::UeUnitsPerWerkUnit);
						Elem.Y = float(FMath::Abs(H[1]) * 2.0 * werk::UeUnitsPerWerkUnit);
						Elem.Z = float(FMath::Abs(H[2]) * 2.0 * werk::UeUnitsPerWerkUnit);
						Body->AggGeom.BoxElems.Add(Elem);
						++Boxes;
					}
				}
			}
		}
		const int32 Unsupported = ForeignParts;

		Body->InvalidatePhysicsData();
		Body->CreatePhysicsMeshes();
		Mesh->PostEditChange();

		FString Detail = FString::Printf(TEXT("%d sphere(s), %d box(es)"), Spheres, Boxes);
		if (Unsupported > 0)
		{
			Detail += FString::Printf(
				TEXT("; %d collider group(s) belong to a part other than the first and are NOT "
				     "represented, because one static mesh carries one body setup"), Unsupported);
			Note(Ctx, N, EWerkOutcome::Substituted, TEXT("node-skipped-not-implemented"), Detail);
		}
		else
		{
			Note(Ctx, N, EWerkOutcome::Imported, TEXT("imported"), Detail);
		}
	}

	// --- textures ----------------------------------------------------------

	UTexture2D* ImportTexture(FImportContext& Ctx, const werk::Node& N)
	{
		std::vector<uint8_t> Bytes;
		std::string Path;
		if (!ReadNodeFile(Ctx, N, ".png", Bytes, Path))
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("file-missing"), TEXT("no readable .png payload"));
			return nullptr;
		}

		// SPEC.md 8.2 / MINI-SPECS 8.2: the colour space of a texture is
		// meta.color_space in MANIFEST.json, NOT the PNG's sRGB/gAMA/iCCP
		// chunk, because law 8 says a convention is a declared value and not
		// something recovered from an optional chunk half the tools drop.
		FString ColorSpace = TEXT("srgb");
		FString Usage;
		if (N.meta)
		{
			ColorSpace = ToF(N.meta->GetString("color_space", "srgb"));
			Usage = ToF(N.meta->GetString("usage"));
			if (Usage.IsEmpty())
			{
				// profile 2's spelling. core.image.* has no `usage`; what it has
				// is `derived_role` (preview, thumbnail) on a derived node and
				// nothing at all on the source. Mapped, not guessed.
				const FString Role = ToF(N.meta->GetString("derived_role"));
				Usage = Role.IsEmpty() ? TEXT("image-source") : (TEXT("image-") + Role);
			}
		}
		const bool bSrgb = ColorSpace.Equals(TEXT("srgb"), ESearchCase::IgnoreCase);

		const FString AssetName = FString(TEXT("T_"))
		                        + FWerkLinkAction::WerkIdToObjectName(ToF(N.nodeId));
		FString ObjectPath;
		UPackage* Package = MakePackage(Ctx, AssetName, ObjectPath);
		if (!Package)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("container-invalid"),
			     TEXT("could not create the destination package"));
			return nullptr;
		}

		UTextureFactory* Factory = NewObject<UTextureFactory>();
		Factory->AddToRoot();
		Factory->SuppressImportOverwriteDialog();
		Factory->bCreateMaterial = false; // the werk core.material node is the authority
		Factory->NoAlpha = false;

		const uint8* Ptr = Bytes.data();
		const uint8* End = Bytes.data() + Bytes.size();
		UObject* Created = Factory->FactoryCreateBinary(
			UTexture2D::StaticClass(), Package, FName(*AssetName), RF_Public | RF_Standalone,
			nullptr, TEXT("png"), Ptr, End, GWarn);
		Factory->RemoveFromRoot();

		UTexture2D* Texture = Cast<UTexture2D>(Created);
		if (!Texture)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("payload-schema-invalid"),
			     TEXT("the texture factory refused the PNG bytes"));
			return nullptr;
		}

		Texture->SRGB = bSrgb;
		if (Usage.Equals(TEXT("normal"), ESearchCase::IgnoreCase)
			|| Usage.Contains(TEXT("normal")))
		{
			Texture->CompressionSettings = TC_Normalmap;
			Texture->SRGB = false;
			Texture->LODGroup = TEXTUREGROUP_WorldNormalMap;
		}
		Texture->PostEditChange();

		StampIdentity(Ctx, Texture, N);
		if (UWerkAssetUserData* Data = Cast<UWerkAssetUserData>(
			Texture->GetAssetUserDataOfClass(UWerkAssetUserData::StaticClass())))
		{
			// The declared usage, kept verbatim. CompressionSettings can only
			// distinguish a normal map from everything else, so an export that
			// recomputed usage would flatten five declared values into two.
			Data->TextureUsage = Usage;
		}
		Ctx.ByNodeId.Add(ToF(N.nodeId), Texture);
		Ctx.Result->CreatedAssetPaths.Add(ObjectPath);
		++Ctx.Result->AssetsCreated;
		Note(Ctx, N, EWerkOutcome::Imported, TEXT("imported"),
		     FString::Printf(TEXT("colour space %s from the node meta, usage '%s'"),
		                     *ColorSpace, *Usage),
		     ObjectPath);
		return Texture;
	}

	// --- materials ---------------------------------------------------------

	void ImportMaterial(FImportContext& Ctx, const werk::Node& N)
	{
		if (!Ctx.Request->MasterMaterial.IsValid())
		{
			// Never invent a material. SPEC.md 10.2 makes the werk node the
			// authority, and with no master to bind it to there is nothing
			// truthful to create.
			Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
			     TEXT("no master material configured (Project Settings > Plugins > WerkLink); "
			          "no material instance was created rather than one being invented"));
			return;
		}
		UMaterialInterface* Master = Cast<UMaterialInterface>(Ctx.Request->MasterMaterial.TryLoad());
		if (!Master)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("external-reference"),
			     FString::Printf(TEXT("configured master material '%s' could not be loaded"),
			                     *Ctx.Request->MasterMaterial.ToString()));
			return;
		}

		std::vector<uint8_t> Bytes;
		std::string Path;
		if (!ReadNodeFile(Ctx, N, ".json", Bytes, Path))
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("file-missing"), TEXT("no readable payload"));
			return;
		}
		std::string Err;
		werk::JsonPtr Doc = werk::JsonParse(Bytes, Err);
		if (!Doc || !Doc->IsObject())
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("payload-schema-invalid"), ToF(Err));
			return;
		}

		const FString AssetName = FString(TEXT("MI_"))
		                        + FWerkLinkAction::WerkIdToObjectName(ToF(N.nodeId));
		FString ObjectPath;
		UPackage* Package = MakePackage(Ctx, AssetName, ObjectPath);
		if (!Package)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("container-invalid"),
			     TEXT("could not create the destination package"));
			return;
		}

		UMaterialInstanceConstantFactoryNew* Factory = NewObject<UMaterialInstanceConstantFactoryNew>();
		Factory->AddToRoot();
		Factory->InitialParent = Master;
		UObject* Created = Factory->FactoryCreateNew(
			UMaterialInstanceConstant::StaticClass(), Package, FName(*AssetName),
			RF_Public | RF_Standalone, nullptr, GWarn);
		Factory->RemoveFromRoot();

		UMaterialInstanceConstant* Instance = Cast<UMaterialInstanceConstant>(Created);
		if (!Instance)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("container-invalid"),
			     TEXT("could not create a material instance"));
			return;
		}

		// WerkLink ships no master material of its own, so which parameters
		// exist is not knowable at compile time. Every parameter is offered to
		// the master and the ones it does not have are REPORTED, not dropped
		// silently -- otherwise a roughness that never arrived looks exactly
		// like a roughness of zero.
		TArray<FString> Bound, Unbound;

		auto TrySetScalar = [&](const TCHAR* ParamName, float Value)
		{
			float Existing = 0.f;
			const FMaterialParameterInfo Info(ParamName);
			if (Master->GetScalarParameterValue(Info, Existing))
			{
				Instance->SetScalarParameterValueEditorOnly(Info, Value);
				Bound.Add(ParamName);
			}
			else
			{
				Unbound.Add(ParamName);
			}
		};
		auto TrySetVector = [&](const TCHAR* ParamName, const FLinearColor& Value)
		{
			FLinearColor Existing;
			const FMaterialParameterInfo Info(ParamName);
			if (Master->GetVectorParameterValue(Info, Existing))
			{
				Instance->SetVectorParameterValueEditorOnly(Info, Value);
				Bound.Add(ParamName);
			}
			else
			{
				Unbound.Add(ParamName);
			}
		};

		if (const werk::JsonValue* Bc = Doc->GetArray("base_color_factor"))
		{
			FLinearColor Color(1, 1, 1, 1);
			const float* Slots[4] = { &Color.R, &Color.G, &Color.B, &Color.A };
			for (size_t i = 0; i < Bc->Size() && i < 4; ++i)
			{
				if (const werk::JsonValue* E = Bc->At(i))
				{
					*const_cast<float*>(Slots[i]) = float(E->number);
				}
			}
			// The factor is a LINEAR multiplier (SPEC.md 3.10 pins COLOR_0 to
			// linear and the material JSON follows), so it goes across as is.
			//
			// Two spellings, ONE report. Trying both and reporting each is what
			// Stage 10B's first run did, and it printed "NOT bound {Color}" for
			// a material where base colour bound perfectly -- a report entry
			// that is technically true and reads as a failure. A parameter is
			// unbound only when NO spelling of it exists.
			FLinearColor Existing;
			bool bBoundBaseColour = false;
			for (const TCHAR* Alias : { TEXT("BaseColor"), TEXT("Color"), TEXT("BaseColorFactor") })
			{
				const FMaterialParameterInfo Info(Alias);
				if (Master->GetVectorParameterValue(Info, Existing))
				{
					Instance->SetVectorParameterValueEditorOnly(Info, Color);
					Bound.Add(Alias);
					bBoundBaseColour = true;
					break;
				}
			}
			if (!bBoundBaseColour)
			{
				Unbound.Add(TEXT("BaseColor"));
			}
		}
		TrySetScalar(TEXT("Metallic"), float(Doc->GetNumber("metallic_factor", 0.0)));
		TrySetScalar(TEXT("Roughness"), float(Doc->GetNumber("roughness_factor", 0.5)));
		if (Doc->Find("normal_scale"))       { TrySetScalar(TEXT("NormalScale"), float(Doc->GetNumber("normal_scale", 1.0))); }
		if (Doc->Find("occlusion_strength")) { TrySetScalar(TEXT("OcclusionStrength"), float(Doc->GetNumber("occlusion_strength", 1.0))); }
		if (Doc->Find("emissive_strength"))  { TrySetScalar(TEXT("EmissiveStrength"), float(Doc->GetNumber("emissive_strength", 1.0))); }
		if (const werk::JsonValue* Em = Doc->GetArray("emissive_factor"))
		{
			FLinearColor E(0, 0, 0, 1);
			float* Slots3[3] = { &E.R, &E.G, &E.B };
			for (size_t i = 0; i < Em->Size() && i < 3; ++i)
			{
				if (const werk::JsonValue* V = Em->At(i)) { *Slots3[i] = float(V->number); }
			}
			TrySetVector(TEXT("EmissiveColor"), E);
		}

		// --- texture slots -------------------------------------------------
		//
		// The schema requires each slot to carry BOTH `node` and `path`, and
		// says in as many words that a reader MUST resolve through the manifest
		// and MUST report a mismatch rather than silently prefer one. So this
		// resolves by node id -- identity, law 4 -- and compares the path it
		// actually resolved to against the one the payload advertises.
		TArray<FString> BoundSlots, UnresolvedSlots, MismatchedSlots;
		TMap<FString, FString> SlotNodes;
		TMap<FString, int32>   SlotUvSets;

		if (const werk::JsonValue* Textures = Doc->GetObject("textures"))
		{
			for (const FWerkMaterialSlot& S : WerkMaterialSlots())
			{
				const werk::JsonValue* Slot = Textures->GetObject(ToStd(FString(S.Slot)));
				if (!Slot)
				{
					continue;
				}
				const FString TexNodeId = ToF(Slot->GetString("node"));
				const FString DeclaredPath = ToF(Slot->GetString("path"));
				const int32 UvSet = int32(Slot->GetNumber("uv_set", 0.0));

				UObject** Found = Ctx.ByNodeId.Find(TexNodeId);
				UTexture2D* Tex = Found ? Cast<UTexture2D>(*Found) : nullptr;
				if (!Tex)
				{
					// Never substitute a texture. An absent slot renders as the
					// factor alone, which is visibly wrong; an invented texture
					// renders as something plausible, which is worse.
					UnresolvedSlots.Add(FString::Printf(TEXT("%s->%s"), S.Slot, *TexNodeId));
					continue;
				}

				// The mismatch check the schema asks for, made against the path
				// the resolved node's own asset was built from.
				if (const UWerkAssetUserData* TexData = Cast<UWerkAssetUserData>(
					Tex->GetAssetUserDataOfClass(UWerkAssetUserData::StaticClass())))
				{
					if (!DeclaredPath.IsEmpty() && !TexData->SourceFilePath.IsEmpty()
						&& DeclaredPath != TexData->SourceFilePath)
					{
						MismatchedSlots.Add(FString::Printf(
							TEXT("%s: payload says '%s', node '%s' resolved to '%s'"),
							S.Slot, *DeclaredPath, *TexNodeId, *TexData->SourceFilePath));
						Ctx.Rep->Warn(werk::code::SubstitutedFallback, N.nodeId,
						              "texture slot path/node disagreement, resolved through the "
						              "node as the schema requires");
					}
				}

				bool bBound = false;
				UTexture* Existing = nullptr;
				if (Master->GetTextureParameterValue(FMaterialParameterInfo(S.TextureParam), Existing))
				{
					Instance->SetTextureParameterValueEditorOnly(
						FMaterialParameterInfo(S.TextureParam), Tex);
					bBound = true;
				}
				// The static switch is what actually enables the sampler in the
				// shipped master. A master that has no such switch is fine --
				// the bind above still happened -- and one that has it and does
				// not get it set would sample nothing, which is the silent
				// failure this exists to prevent.
				bool bSwitchValue = false;
				FGuid SwitchGuid;
				if (Master->GetStaticSwitchParameterValue(FMaterialParameterInfo(S.SwitchParam),
				                                          bSwitchValue, SwitchGuid))
				{
					UMaterialEditingLibrary::SetMaterialInstanceStaticSwitchParameterValue(
						Instance, FName(S.SwitchParam), true);
				}

				if (bBound)
				{
					BoundSlots.Add(S.Slot);
					SlotNodes.Add(FString(S.Slot), TexNodeId);
					SlotUvSets.Add(FString(S.Slot), UvSet);
					if (UvSet != 0)
					{
						// One declared narrowness, named rather than hidden:
						// the shipped master samples UV0 only.
						Ctx.Rep->Warn(werk::code::SubstitutedFallback, N.nodeId,
						              "slot '" + ToStd(FString(S.Slot)) + "' declares uv_set "
						                  + std::to_string(UvSet)
						                  + "; the shipped master samples UV0 only, so the "
						                    "declared channel was NOT honoured");
					}
				}
				else
				{
					Unbound.Add(S.TextureParam);
				}
			}
		}

		const std::string AlphaMode = Doc->GetString("alpha_mode", "opaque");
		const bool bDoubleSided = Doc->GetBool("double_sided", false);
		if (bDoubleSided)
		{
			Instance->BasePropertyOverrides.bOverride_TwoSided = true;
			Instance->BasePropertyOverrides.TwoSided = true;
		}
		Instance->PostEditChange();

		StampIdentity(Ctx, Instance, N);
		if (UWerkAssetUserData* Data = Cast<UWerkAssetUserData>(
			Instance->GetAssetUserDataOfClass(UWerkAssetUserData::StaticClass())))
		{
			Data->TextureSlotNodes = SlotNodes;
			Data->TextureSlotUvSets = SlotUvSets;
		}
		Ctx.ByNodeId.Add(ToF(N.nodeId), Instance);
		Ctx.Result->CreatedAssetPaths.Add(ObjectPath);
		++Ctx.Result->AssetsCreated;

		// Assign the instance to the meshes this material governs, so "import it
		// and it is shaded" is true without a human step.
		//
		// Three rules, tried in order, and WHICH one fired is reported --
		// because rules 2 and 3 are inferences and an inference presented as a
		// fact is exactly what this project exists to argue against.
		//
		//   1. the geometry node itself declares this material_id  (a fact)
		//   2. manifest materials[] maps this material_id to a part_id and the
		//      geometry node declares that part_id                (a fact, one
		//      hop through the manifest, which is what materials[] is for)
		//   3. the package has exactly ONE core.material and at least one mesh
		//                                                          (an inference)
		const FString ThisMaterialId = ToF(N.materialId).IsEmpty()
			? ToF(Doc->GetString("material_id")) : ToF(N.materialId);

		FString PartForMaterial;
		for (const werk::MaterialEntry& M : Ctx.Pkg->Materials())
		{
			if (ToF(M.materialId) == ThisMaterialId)
			{
				PartForMaterial = ToF(M.partId);
				break;
			}
		}

		int32 MaterialNodeCount = 0;
		for (const werk::Node& Other : Ctx.Pkg->Nodes())
		{
			if (Other.type == "core.material" && Other.bAlive)
			{
				++MaterialNodeCount;
			}
		}

		int32 MeshesAssigned = 0;
		const TCHAR* Rule = TEXT("none");
		for (const TPair<FString, UObject*>& Pair : Ctx.ByNodeId)
		{
			UStaticMesh* Mesh = Cast<UStaticMesh>(Pair.Value);
			if (!Mesh)
			{
				continue;
			}
			const UWerkAssetUserData* MeshData = Cast<UWerkAssetUserData>(
				Mesh->GetAssetUserDataOfClass(UWerkAssetUserData::StaticClass()));

			const TCHAR* WhichRule = nullptr;
			if (MeshData && !ThisMaterialId.IsEmpty() && MeshData->MaterialId == ThisMaterialId)
			{
				WhichRule = TEXT("node material_id");
			}
			else if (MeshData && !PartForMaterial.IsEmpty()
				&& MeshData->PartId == PartForMaterial)
			{
				WhichRule = TEXT("manifest materials[].part_id");
			}
			else if (MaterialNodeCount == 1)
			{
				WhichRule = TEXT("INFERRED: the package declares exactly one core.material");
			}
			if (!WhichRule)
			{
				continue;
			}

			const int32 SlotCount = Mesh->GetStaticMaterials().Num();
			if (SlotCount == 0)
			{
				// Never count an assignment that did not happen.
				Ctx.Rep->Warn(werk::code::SubstitutedFallback, N.nodeId,
				              "mesh '" + ToStd(Mesh->GetName())
				                  + "' has no material slots, so nothing was assigned");
				continue;
			}
			for (int32 Slot = 0; Slot < SlotCount; ++Slot)
			{
				Mesh->SetMaterial(Slot, Instance);
			}
			Mesh->PostEditChange();
			Mesh->MarkPackageDirty();
			MeshesAssigned += SlotCount;
			Rule = WhichRule;
		}

		FString Detail = FString::Printf(TEXT("parent %s; bound {%s}"),
		                                 *Master->GetName(), *FString::Join(Bound, TEXT(", ")));
		if (BoundSlots.Num() > 0)
		{
			Detail += FString::Printf(TEXT("; textures {%s}"),
			                          *FString::Join(BoundSlots, TEXT(", ")));
		}
		Detail += FString::Printf(TEXT("; assigned to %d mesh material slot(s) by rule '%s'"),
		                          MeshesAssigned, Rule);
		if (UnresolvedSlots.Num() > 0)
		{
			Detail += FString::Printf(
				TEXT("; slots {%s} name texture nodes that did not resolve and were left EMPTY, "
				     "never substituted"),
				*FString::Join(UnresolvedSlots, TEXT(", ")));
		}
		if (MismatchedSlots.Num() > 0)
		{
			Detail += FString::Printf(TEXT("; node/path disagreement on {%s}"),
			                          *FString::Join(MismatchedSlots, TEXT("; ")));
		}
		if (Unbound.Num() > 0)
		{
			Detail += FString::Printf(
				TEXT("; NOT bound {%s} -- the master has no such parameter, so those values are "
				     "absent from the instance and are not defaults"),
				*FString::Join(Unbound, TEXT(", ")));
			Detail += FString::Printf(TEXT("; alpha_mode '%s' is carried in metadata only"),
			                          *ToF(AlphaMode));
			Note(Ctx, N, EWerkOutcome::Substituted, TEXT("substituted-fallback"), Detail, ObjectPath);
		}
		else
		{
			Note(Ctx, N, EWerkOutcome::Imported, TEXT("imported"), Detail, ObjectPath);
		}
	}

	// --- audio -------------------------------------------------------------

	/**
	 * A landmine this build FOUND rather than inherited, recorded here because
	 * the next person will otherwise spend an hour on it.
	 *
	 * Importing a WAV through USoundFactory in a commandlet trips a handled
	 * ensure inside the engine:
	 *
	 *   Ensure condition failed: Factory
	 *   [Engine/Source/Runtime/Engine/Private/SoundWave.cpp] [Line: 248]
	 *   Decoder for AudioFormat 'BINKA' not found
	 *
	 * FSoundWaveData::CacheRuntimeFormatDependentState asks
	 * IAudioInfoFactoryRegistry for a decoder for the project's default wave
	 * format, which is BINKA. The factory that answers is registered by the
	 * BinkAudioDecoder module (Runtime/BinkAudioDecoder/Module,
	 * BinkAudioInfo.cpp:737), and in a commandlet nothing has loaded it --
	 * -nosound does not help, because the ensure is in the ASSET path, not the
	 * device path.
	 *
	 * It is only an ensure: the sound waves import correctly either way. But
	 * an ensure logs as an Error, and UnrealEditor-Cmd exits non-zero when
	 * errors were logged, so an otherwise clean batch reports failure.
	 *
	 * Loading the module by name fixes it. It is done lazily and once, and the
	 * outcome is REPORTED rather than assumed, because a future engine version
	 * may rename the module and a silent failure here would look like the
	 * ensure coming back for no reason.
	 */
	void EnsureAudioDecoderModule(FImportContext& Ctx)
	{
		static const TCHAR* ModuleName = TEXT("BinkAudioDecoder");
		if (FModuleManager::Get().IsModuleLoaded(ModuleName))
		{
			return;
		}
		const bool bLoaded = FModuleManager::Get().LoadModule(ModuleName) != nullptr;
		FWerkReportLine L;
		L.Code = bLoaded ? TEXT("imported") : TEXT("substituted-fallback");
		L.Severity = bLoaded ? TEXT("info") : TEXT("warn");
		L.Subject = ModuleName;
		L.Detail = bLoaded
			? TEXT("audio decoder module loaded so USoundWave can resolve its runtime format; "
			       "without it the engine raises a handled ensure that makes a clean commandlet "
			       "run exit non-zero")
			: TEXT("audio decoder module could not be loaded; expect a handled ensure "
			       "'Decoder for AudioFormat BINKA not found' and a non-zero exit status. The "
			       "sound waves themselves still import correctly.");
		Ctx.Result->Report.Add(MoveTemp(L));
	}

	void ImportAudio(FImportContext& Ctx, const werk::Node& N)
	{
		const werk::NodeVersion* V = N.Resolved();
		if (!V)
		{
			return;
		}

		EnsureAudioDecoderModule(Ctx);

		int32 Made = 0;
		FString LastPath;
		for (const werk::FileRef& F : V->files)
		{
			if (F.path.size() < 4 || F.path.compare(F.path.size() - 4, 4, ".wav") != 0)
			{
				continue;
			}
			// SPEC.md 3.9: files[].role distinguishes best / raw / variation.
			// Only the take the package calls best becomes an asset; the
			// others are recorded so nobody thinks they were lost.
			if (!F.role.empty() && F.role != "best")
			{
				continue;
			}

			std::vector<uint8_t> Bytes;
			if (!Ctx.Pkg->ReadPayload(F.path, Bytes, *Ctx.Rep))
			{
				continue;
			}

			FString Base = FPaths::GetBaseFilename(ToF(F.path));
			const FString AssetName = FString(TEXT("SW_"))
			                        + FWerkLinkAction::WerkIdToObjectName(Base);
			FString ObjectPath;
			UPackage* Package = MakePackage(Ctx, AssetName, ObjectPath);
			if (!Package)
			{
				continue;
			}

			USoundFactory* Factory = NewObject<USoundFactory>();
			Factory->AddToRoot();
			Factory->SuppressImportDialogs();
			Factory->bAutoCreateCue = false;

			const uint8* Ptr = Bytes.data();
			const uint8* End = Bytes.data() + Bytes.size();
			UObject* Created = Factory->FactoryCreateBinary(
				USoundWave::StaticClass(), Package, FName(*AssetName),
				RF_Public | RF_Standalone, nullptr, TEXT("wav"), Ptr, End, GWarn);
			Factory->RemoveFromRoot();

			if (USoundWave* Wave = Cast<USoundWave>(Created))
			{
				StampIdentity(Ctx, Wave, N);
				Ctx.Result->CreatedAssetPaths.Add(ObjectPath);
				++Ctx.Result->AssetsCreated;
				++Made;
				LastPath = ObjectPath;
			}
		}

		if (Made == 0)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("file-missing"),
			     TEXT("no WAV take with role 'best' could be imported"));
		}
		else
		{
			int32 Others = 0;
			for (const werk::FileRef& F : V->files)
			{
				if (F.path.size() >= 4 && F.path.compare(F.path.size() - 4, 4, ".wav") == 0
					&& !F.role.empty() && F.role != "best")
				{
					++Others;
				}
			}
			Note(Ctx, N, EWerkOutcome::Imported, TEXT("imported"),
			     FString::Printf(TEXT("%d sound wave(s); %d further take(s) (raw/variation) are in "
			                          "the package and were deliberately not imported"),
			                     Made, Others),
			     LastPath);
		}
	}

	// --- metadata-only nodes ----------------------------------------------

	void ImportMetadataNode(FImportContext& Ctx, const werk::Node& N, UStaticMesh* Mesh)
	{
		std::vector<uint8_t> Bytes;
		std::string Path;
		if (!ReadNodeFile(Ctx, N, ".json", Bytes, Path))
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("file-missing"), TEXT("no readable payload"));
			return;
		}
		std::string Err;
		werk::JsonPtr Doc = werk::JsonParse(Bytes, Err);
		if (!Doc || !Doc->IsObject())
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("payload-schema-invalid"), ToF(Err));
			return;
		}

		UObject* Target = Mesh;
		if (!Target)
		{
			Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
			     TEXT("no mesh to attach this metadata to"));
			return;
		}

#if WITH_METADATA
		UPackage* Package = Target->GetPackage();
		FMetaData& Meta = Package->GetMetaData();
		int32 Written = 0;

		if (N.type == "core.phys.bounds")
		{
			if (const werk::JsonValue* Ent = Doc->GetObject("entity"))
			{
				werk::Vec3 Mn = { 0, 0, 0 }, Mx = { 0, 0, 0 };
				const werk::JsonValue* A = Ent->GetArray("aabb_min");
				const werk::JsonValue* B = Ent->GetArray("aabb_max");
				if (A && B && A->Size() == 3 && B->Size() == 3)
				{
					for (int k = 0; k < 3; ++k)
					{
						Mn[size_t(k)] = A->At(size_t(k))->number;
						Mx[size_t(k)] = B->At(size_t(k))->number;
					}
					werk::Vec3 UMn, UMx;
					// Both corners transformed, then re-min/re-maxed: the axes
					// permute and one negates, so the transformed "min" can
					// hold the larger value.
					werk::AabbWerkToUe(Mn, Mx, UMn, UMx);
					Meta.SetValue(Target, TEXT("werk.bounds.aabb_min_cm"),
					              *FString::Printf(TEXT("%.4f %.4f %.4f"), UMn[0], UMn[1], UMn[2]));
					Meta.SetValue(Target, TEXT("werk.bounds.aabb_max_cm"),
					              *FString::Printf(TEXT("%.4f %.4f %.4f"), UMx[0], UMx[1], UMx[2]));
					Written += 2;
				}
				const double Radius = Ent->GetNumber("sphere_radius", 0.0);
				if (Radius > 0.0)
				{
					Meta.SetValue(Target, TEXT("werk.bounds.sphere_radius_cm"),
					              *FString::Printf(TEXT("%.4f"), Radius * werk::UeUnitsPerWerkUnit));
					Meta.SetValue(Target, TEXT("werk.bounds.sphere_method"),
					              *ToF(Ent->GetString("sphere_method")));
					Written += 2;
				}
				Meta.SetValue(Target, TEXT("werk.bounds.volume_m3"),
				              *FString::Printf(TEXT("%.6f"), Ent->GetNumber("volume_m3", 0.0)));
				Meta.SetValue(Target, TEXT("werk.bounds.watertight"),
				              Ent->GetBool("watertight", false) ? TEXT("true") : TEXT("false"));
				Written += 2;
			}
		}
		else if (N.type == "core.phys.body")
		{
			Meta.SetValue(Target, TEXT("werk.body.mass_kg"),
			              *FString::Printf(TEXT("%.6f"), Doc->GetNumber("mass_kg", 0.0)));
			++Written;
		}
		else if (N.type == "core.semantics")
		{
			// Asset tags, so a Content Browser filter can find them. Written
			// as package metadata because a UStaticMesh cannot grow arbitrary
			// asset registry tags without a subclass, and a subclass would
			// mean imported meshes are not ordinary static meshes.
			for (const char* Facet : { "style", "function", "environment", "era",
			                           "mood", "condition", "scale-class" })
			{
				const werk::JsonValue* Tags = Doc->GetArray(Facet);
				if (!Tags)
				{
					if (const werk::JsonValue* Facets = Doc->GetObject("facets"))
					{
						Tags = Facets->GetArray(Facet);
					}
				}
				if (!Tags)
				{
					continue;
				}
				TArray<FString> Values;
				for (size_t i = 0; i < Tags->Size(); ++i)
				{
					if (const werk::JsonValue* T = Tags->At(i))
					{
						if (T->IsString())
						{
							Values.Add(ToF(T->str));
						}
					}
				}
				if (Values.Num() > 0)
				{
					Meta.SetValue(Target, *FString::Printf(TEXT("werk.semantics.%s"),
					                                       ANSI_TO_TCHAR(Facet)),
					              *FString::Join(Values, TEXT(",")));
					++Written;
				}
			}
		}
		else if (N.type == "core.props")
		{
			Meta.SetValue(Target, TEXT("werk.props"), TEXT("present"));
			++Written;
		}

		Note(Ctx, N, EWerkOutcome::Imported, TEXT("imported"),
		     FString::Printf(TEXT("%d metadata key(s) written onto %s"), Written, *Target->GetName()));
#else
		Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
		     TEXT("this build has no metadata support"));
#endif
	}
}

// --- the entry point -------------------------------------------------------

FWerkImportResult FWerkLinkAction::Import(const FWerkImportRequest& Request)
{
	FWerkImportResult Result;

	werk::Report Rep;
	werk::Package Pkg;

	if (!FPlatformFileManager::Get().GetPlatformFile().FileExists(*Request.WerkFilePath))
	{
		Result.ErrorMessage = FString::Printf(TEXT("no such file: %s"), *Request.WerkFilePath);
		AppendReport(Rep, Result.Report);
		return Result;
	}

	// S10-4, found by a shell that helpfully rewrote "/Game/Werk" into a
	// Windows path: a destination that is not a valid long package name was
	// carried all the way to FPackageName::LongPackageNameToFilename, which is
	// a CHECKED conversion -- it calls appError and takes the process down.
	//
	// SPEC 10.1 does not have a "die" outcome. A bad destination is a
	// container-scoped refusal: named, reported, exit 2. Checked HERE rather
	// than at the commandlet's argument parse, because the GUI path and the
	// batch-manifest path reach the same code with the same freedom to be
	// wrong, and one guard at the point of use covers all three.
	{
		FPackageName::EErrorCode Code = FPackageName::EErrorCode::PackageNameUnknown;
		if (Request.DestinationPath.IsEmpty()
			|| !FPackageName::IsValidLongPackageName(Request.DestinationPath,
			                                        /*bIncludeReadOnlyRoots=*/true, &Code))
		{
			const FString Reason =
				FPackageName::FormatErrorAsString(Request.DestinationPath, Code);
			Result.ErrorMessage = FString::Printf(
				TEXT("container-scoped refusal: destination '%s' is not a valid Unreal content "
				     "path (%s). It must look like /Game/Werk. NOTHING was imported."),
				*Request.DestinationPath,
				Reason.IsEmpty() ? TEXT("empty") : *Reason);
			FWerkReportLine L;
			L.Code = TEXT("container-invalid");
			L.Severity = TEXT("error");
			L.Subject = Request.DestinationPath;
			L.Detail = Result.ErrorMessage;
			// ExitStatusFrom(bSuccess || NodesTotal > 0, ...) is 2 here, which is
			// the container scope, because nothing was opened.
			Result.Report.Add(MoveTemp(L));
			AppendReport(Rep, Result.Report);
			return Result;
		}
	}

	if (!Pkg.OpenFile(ToStd(Request.WerkFilePath), Rep))
	{
		// The one container-scoped refusal that may be empty-handed.
		Result.ErrorMessage = TEXT("container-scoped refusal: the package could not be opened");
		AppendReport(Rep, Result.Report);
		return Result;
	}

	Result.EntityUuid = ToF(Pkg.EntityUuid());
	Result.EntityName = ToF(Pkg.EntityName());
	Result.SignatureState = ToF(Pkg.SignatureState());
	Result.NodesTotal = int32(Pkg.Nodes().size());

	for (const werk::Node& N : Pkg.Nodes())
	{
		if (const werk::NodeVersion* V = N.Resolved())
		{
			Result.FilesVerified += int32(V->files.size());
		}
	}

	const FString EntityFolder = FWerkLinkAction::WerkIdToObjectName(
		Result.EntityName.IsEmpty() ? ToF(Pkg.EntityUuid()) : Result.EntityName);

	FImportContext Ctx;
	Ctx.Pkg = &Pkg;
	Ctx.Rep = &Rep;
	Ctx.Result = &Result;
	Ctx.Request = &Request;
	Ctx.PackageRoot = Request.DestinationPath / EntityFolder;

	// Collect the LOD nodes up front, so the mesh import can attach them.
	TArray<const werk::Node*> LodNodes;
	for (const werk::Node& N : Pkg.Nodes())
	{
		if (N.type == "core.geom.lod" && N.bAlive)
		{
			LodNodes.Add(&N);
		}
	}

	UStaticMesh* PrimaryMesh = nullptr;

	// Two passes: geometry first, because collision, bounds and semantics all
	// attach to a mesh that must already exist. Node order in the manifest is
	// not a dependency order and must not be treated as one.
	for (const werk::Node& N : Pkg.Nodes())
	{
		if (!N.bAlive)
		{
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("hash-mismatch"),
			     TEXT("node did not resolve; see the report for which file failed"));
			continue;
		}

		std::string FailedConvention;
		if (!Pkg.ConventionsSatisfiedFor(N.type, FailedConvention))
		{
			// SPEC.md 10.1: node-scoped, not container-scoped.
			Note(Ctx, N, EWerkOutcome::Refused, TEXT("unsupported-convention"),
			     FString::Printf(TEXT("convention '%s' is not one this adapter supports"),
			                     *ToF(FailedConvention)));
			continue;
		}

		if (Request.bDryRun)
		{
			Note(Ctx, N, EWerkOutcome::Skipped, TEXT("imported"),
			     TEXT("dry run: nothing was created"));
			continue;
		}

		if (N.type == "core.geom.game")
		{
			UStaticMesh* Mesh = ImportGeometry(Ctx, N, LodNodes);
			if (Mesh && !PrimaryMesh)
			{
				PrimaryMesh = Mesh;
			}
		}
		else if (N.type == "core.geom.source")
		{
			// The archival anchor. Imported as its own asset rather than
			// merged, because SPEC.md 3.10 says it may lack attributes a
			// renderer needs and every derived node's input_hash is computed
			// against it -- so it is a different thing, not a better LOD.
			ImportGeometry(Ctx, N, TArray<const werk::Node*>());
		}
	}

	if (!Request.bDryRun)
	{
		// THREE ORDERED PHASES over the same node list, and the order is a
		// dependency rather than a preference:
		//
		//   0. core.tex        -- a material slot names a texture NODE, so the
		//                         UTexture2D has to exist before the binding can
		//                         be made. Manifest order does not guarantee it.
		//   1. core.material   -- creates the instances and binds the textures,
		//                         then assigns the instances to the meshes
		//                         imported in the first pass.
		//   2. everything else.
		//
		// Stage 10 ran a single pass in manifest order, which was safe only
		// because nothing bound anything.
		for (int32 Phase = 0; Phase < 3; ++Phase)
		{
		for (const werk::Node& N : Pkg.Nodes())
		{
			if (!N.bAlive)
			{
				continue;
			}
			std::string FailedConvention;
			if (!Pkg.ConventionsSatisfiedFor(N.type, FailedConvention))
			{
				continue; // already reported in the first pass
			}

			const bool bIsImageNode = (N.type == "core.tex"
			                        || N.type == "core.image.source"
			                        || N.type == "core.image.derived");
			const int32 NodePhase = bIsImageNode ? 0
			                      : (N.type == "core.material") ? 1 : 2;
			if (NodePhase != Phase)
			{
				continue;
			}

			if (N.type == "core.geom.game" || N.type == "core.geom.source"
				|| N.type == "core.geom.lod")
			{
				continue; // handled above
			}
			else if (bIsImageNode)
			{
				// profile 2, `image/1`. A core.image.* node is a PNG with a
				// declared colour space and declared dimensions, which is
				// exactly what core.tex is, so it goes down the same path
				// rather than through a second one that could disagree with it.
				// The profile is not this adapter's, and the node outcome says
				// so -- an image/1 package produces textures and metadata and
				// no geometry, which is the correct answer, not a degraded one.
				ImportTexture(Ctx, N);
			}
			else if (N.type == "core.material")
			{
				ImportMaterial(Ctx, N);
			}
			else if (N.type == "core.phys.colliders")
			{
				if (Request.bImportCollision)
				{
					ImportColliders(Ctx, N, PrimaryMesh);
				}
				else
				{
					Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
					     TEXT("collision import is switched off in settings"));
				}
			}
			else if (N.type == "core.phys.bounds" || N.type == "core.phys.body"
				|| N.type == "core.props")
			{
				ImportMetadataNode(Ctx, N, PrimaryMesh);
			}
			else if (N.type == "core.semantics")
			{
				if (Request.bImportSemanticTags)
				{
					ImportMetadataNode(Ctx, N, PrimaryMesh);
				}
				else
				{
					Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
					     TEXT("semantic tag import is switched off in settings"));
				}
			}
			else if (N.type == "core.audio.effect" || N.type == "core.audio.ambience")
			{
				if (Request.bImportAudio)
				{
					ImportAudio(Ctx, N);
				}
				else
				{
					Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
					     TEXT("audio import is switched off in settings"));
				}
			}
			else if (N.type == "core.skeleton" || N.type == "core.anim.clip")
			{
				// The honest "not yet" the brief allows. It is a declared
				// narrowness, not an undeclared silence.
				Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
				     TEXT("skeleton and animation import are not implemented in v1; the payload "
				          "is present and verified in the package, it is simply not turned into "
				          "a UAsset"));
			}
			else if (N.type == "core.spec" || N.type == "core.loader"
				|| N.type == "core.license" || N.type == "core.readme"
				|| N.type == "core.provenance" || N.type == "core.audio.package")
			{
				Note(Ctx, N, EWerkOutcome::Skipped, TEXT("node-skipped-not-implemented"),
				     TEXT("carried by the package for a reader, not turned into a UAsset"));
			}
			else
			{
				// Unknown-because-newer and unknown-because-extension degrade
				// through the same path, which is checklist step 8.
				Note(Ctx, N, EWerkOutcome::Unknown, TEXT("node-skipped-unknown-type"),
				     FString::Printf(TEXT("node type '%s' is not one this adapter implements"),
				                     *ToF(N.type)));
			}
		}
		}   // phase
	}

	// --- save ---------------------------------------------------------------
	if (!Request.bDryRun && Request.bSavePackages && Ctx.Touched.Num() > 0)
	{
		// Findings B5: silence the validator that opens a modal on a batch
		// save. Inert when the DataValidation plugin is not loaded.
		FWerkScopedQuietValidators Quiet(TEXT("Localization"));

		IAssetRegistry& Registry =
			FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry").Get();
		TArray<FString> WrittenFiles;

		for (UPackage* Package : Ctx.Touched)
		{
			if (!Package)
			{
				continue;
			}
			const FString FileName = FPackageName::LongPackageNameToFilename(
				Package->GetName(), FPackageName::GetAssetPackageExtension());

			// Findings B8: clear read-only before touching a file. A
			// source-controlled read-only asset otherwise fails the save with
			// a message nobody reads.
			IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
			if (PlatformFile.FileExists(*FileName) && PlatformFile.IsReadOnly(*FileName))
			{
				PlatformFile.SetReadOnly(*FileName, false);
			}

			// Findings B7: the force-save incantation. SaveDirtyPackages alone
			// is not enough headless, and FSavePackageArgs members are
			// assigned individually because the all-argument constructor is
			// UE_DEPRECATED(5.6).
			FSavePackageArgs Args;
			Args.TopLevelFlags = RF_Public | RF_Standalone;
			Args.SaveFlags = SAVE_NoError | SAVE_KeepDirty;
			Args.bWarnOfLongFilename = false;
			Args.bSlowTask = false;
			Args.Error = GError;

			Package->SetDirtyFlag(true);
			const FSavePackageResultStruct SaveResult =
				UPackage::Save(Package, nullptr, *FileName, Args);

			// GenerateStub counts as success: the package was written.
			if (SaveResult.Result == ESavePackageResult::Success
				|| SaveResult.Result == ESavePackageResult::GenerateStub)
			{
				++Result.PackagesSaved;
				WrittenFiles.Add(FileName);
			}
			else
			{
				FWerkReportLine L;
				L.Code = TEXT("container-invalid");
				L.Severity = TEXT("error");
				L.Subject = Package->GetName();
				L.Detail = TEXT("UPackage::Save did not report success");
				Result.Report.Add(MoveTemp(L));
			}
		}

		// Findings B6 (and A7, which proves the invisibility is real): files
		// written out-of-band are invisible to the registry until it is told
		// to look, and it takes BOTH calls.
		if (WrittenFiles.Num() > 0)
		{
			Registry.ScanModifiedAssetFiles(WrittenFiles);
			TArray<FString> Paths;
			Paths.Add(Ctx.PackageRoot);
			Registry.ScanPathsSynchronous(Paths, /*bForceRescan=*/true);
		}
	}

	AppendReport(Rep, Result.Report);
	Result.bSuccess = true;
	return Result;
}
