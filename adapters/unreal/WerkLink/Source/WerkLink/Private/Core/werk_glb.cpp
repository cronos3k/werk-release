#include "werk_glb.h"

#include <cmath>
#include <cstdio>
#include <cstring>

#include "werk_json.h"

namespace werk
{

namespace
{
    constexpr uint32_t kGlbMagic = 0x46546C67; // "glTF"
    constexpr uint32_t kChunkJson = 0x4E4F534A;
    constexpr uint32_t kChunkBin  = 0x004E4942;

    uint32_t Rd32(const uint8_t* P)
    {
        return uint32_t(P[0]) | (uint32_t(P[1]) << 8) | (uint32_t(P[2]) << 16) | (uint32_t(P[3]) << 24);
    }
    void Wr32(std::vector<uint8_t>& V, uint32_t X)
    {
        V.push_back(uint8_t(X & 0xFF));
        V.push_back(uint8_t((X >> 8) & 0xFF));
        V.push_back(uint8_t((X >> 16) & 0xFF));
        V.push_back(uint8_t((X >> 24) & 0xFF));
    }

    int ComponentSize(int ComponentType)
    {
        switch (ComponentType)
        {
        case 5120: case 5121: return 1;
        case 5122: case 5123: return 2;
        case 5125: case 5126: return 4;
        default: return 0;
        }
    }

    int ComponentCount(const std::string& Type)
    {
        if (Type == "SCALAR") return 1;
        if (Type == "VEC2")   return 2;
        if (Type == "VEC3")   return 3;
        if (Type == "VEC4")   return 4;
        if (Type == "MAT2")   return 4;
        if (Type == "MAT3")   return 9;
        if (Type == "MAT4")   return 16;
        return 0;
    }

    // Reads accessor `Index` as floats, normalising integer component types
    // when the accessor says `normalized`. Returns component count per element
    // in OutComponents, or 0 on failure.
    int ReadAccessorFloats(const JsonValue& Doc, const std::vector<uint8_t>& Bin, int Index,
                           std::vector<float>& Out, const std::string& Subject, Report& Rep)
    {
        Out.clear();
        const JsonValue* Accessors = Doc.GetArray("accessors");
        if (!Accessors || size_t(Index) >= Accessors->Size())
        {
            Rep.Error(code::EnvelopeInvalid, Subject, "accessor index out of range");
            return 0;
        }
        const JsonValue* A = Accessors->At(size_t(Index));
        const int ComponentType = int(A->GetNumber("componentType", 0));
        const int Count = int(A->GetNumber("count", 0));
        const std::string Type = A->GetString("type");
        const bool bNormalized = A->GetBool("normalized", false);
        const int NComp = ComponentCount(Type);
        const int CSize = ComponentSize(ComponentType);
        if (NComp == 0 || CSize == 0 || Count <= 0)
        {
            Rep.Error(code::EnvelopeInvalid, Subject, "accessor has an unknown type or component type");
            return 0;
        }

        const JsonValue* Views = Doc.GetArray("bufferViews");
        const int ViewIndex = int(A->GetNumber("bufferView", -1));
        if (!Views || ViewIndex < 0 || size_t(ViewIndex) >= Views->Size())
        {
            Rep.Error(code::EnvelopeInvalid, Subject, "accessor without a bufferView");
            return 0;
        }
        const JsonValue* V = Views->At(size_t(ViewIndex));
        const size_t ViewOffset = size_t(V->GetNumber("byteOffset", 0));
        const size_t ViewLength = size_t(V->GetNumber("byteLength", 0));
        const size_t Packed = size_t(NComp) * size_t(CSize);
        // MINI-SPECS 10.2: stride is byteStride when present, otherwise the
        // tightly packed element size.
        const size_t Stride = size_t(V->GetNumber("byteStride", 0)) ? size_t(V->GetNumber("byteStride", 0)) : Packed;
        const size_t AccOffset = size_t(A->GetNumber("byteOffset", 0));

        const size_t Need = AccOffset + Stride * size_t(Count - 1) + Packed;
        if (ViewOffset + Need > Bin.size() || Need > ViewLength + Stride)
        {
            Rep.Error(code::EnvelopeInvalid, Subject, "accessor runs past its bufferView or the BIN chunk");
            return 0;
        }

        Out.resize(size_t(Count) * size_t(NComp));
        for (int i = 0; i < Count; ++i)
        {
            const uint8_t* P = Bin.data() + ViewOffset + AccOffset + Stride * size_t(i);
            for (int c = 0; c < NComp; ++c)
            {
                const uint8_t* Q = P + size_t(c) * size_t(CSize);
                double Value = 0.0;
                switch (ComponentType)
                {
                case 5120: { int8_t X;  std::memcpy(&X, Q, 1); Value = bNormalized ? double(X) / 127.0 : double(X); break; }
                case 5121: { uint8_t X; std::memcpy(&X, Q, 1); Value = bNormalized ? double(X) / 255.0 : double(X); break; }
                case 5122: { int16_t X;  std::memcpy(&X, Q, 2); Value = bNormalized ? double(X) / 32767.0 : double(X); break; }
                case 5123: { uint16_t X; std::memcpy(&X, Q, 2); Value = bNormalized ? double(X) / 65535.0 : double(X); break; }
                case 5125: { uint32_t X; std::memcpy(&X, Q, 4); Value = double(X); break; }
                case 5126: { float X;    std::memcpy(&X, Q, 4); Value = double(X); break; }
                default: break;
                }
                Out[size_t(i) * size_t(NComp) + size_t(c)] = float(Value);
            }
        }
        return NComp;
    }

    bool ReadIndices(const JsonValue& Doc, const std::vector<uint8_t>& Bin, int Index,
                     std::vector<unsigned int>& Out, const std::string& Subject, Report& Rep)
    {
        Out.clear();
        const JsonValue* Accessors = Doc.GetArray("accessors");
        if (!Accessors || size_t(Index) >= Accessors->Size())
        {
            Rep.Error(code::EnvelopeInvalid, Subject, "indices accessor out of range");
            return false;
        }
        const JsonValue* A = Accessors->At(size_t(Index));
        const int ComponentType = int(A->GetNumber("componentType", 0));
        // SPEC.md 3.10: u16 or u32. u8 indices exist in glTF but are not
        // conformant here, and guessing would be exactly the silent wrongness
        // the spec forbids.
        if (ComponentType != 5123 && ComponentType != 5125)
        {
            Rep.Error(code::PayloadSchemaInvalid, Subject,
                      "indices componentType " + std::to_string(ComponentType)
                          + "; SPEC 3.10 permits 5123 (u16) or 5125 (u32) only");
            return false;
        }
        std::vector<float> Tmp;
        if (ReadAccessorFloats(Doc, Bin, Index, Tmp, Subject, Rep) != 1)
        {
            return false;
        }
        Out.resize(Tmp.size());
        for (size_t i = 0; i < Tmp.size(); ++i)
        {
            Out[i] = (unsigned int)(Tmp[i] + 0.5f);
        }
        return true;
    }
}

bool GlbRead(const std::vector<uint8_t>& Bytes, bool bRequireNormals,
             GlbMesh& Out, const std::string& Subject, Report& Rep)
{
    Out = GlbMesh();

    if (Bytes.size() < 20)
    {
        Rep.Error(code::EnvelopeInvalid, Subject, "shorter than a GLB header");
        return false;
    }
    if (Rd32(Bytes.data()) != kGlbMagic)
    {
        Rep.Error(code::EnvelopeInvalid, Subject, "not a GLB: magic is not 'glTF'");
        return false;
    }
    if (Rd32(Bytes.data() + 4) != 2)
    {
        Rep.Error(code::EnvelopeInvalid, Subject, "GLB version is not 2");
        return false;
    }
    const uint32_t TotalLength = Rd32(Bytes.data() + 8);
    if (TotalLength > Bytes.size())
    {
        Rep.Error(code::EnvelopeInvalid, Subject, "GLB length field exceeds the file");
        return false;
    }

    std::vector<uint8_t> JsonChunk, BinChunk;
    size_t P = 12;
    while (P + 8 <= size_t(TotalLength))
    {
        const uint32_t ChunkLength = Rd32(Bytes.data() + P);
        const uint32_t ChunkType = Rd32(Bytes.data() + P + 4);
        P += 8;
        if (P + ChunkLength > size_t(TotalLength))
        {
            Rep.Error(code::EnvelopeInvalid, Subject, "GLB chunk runs past the declared length");
            return false;
        }
        if (ChunkType == kChunkJson && JsonChunk.empty())
        {
            JsonChunk.assign(Bytes.begin() + P, Bytes.begin() + P + ChunkLength);
        }
        else if (ChunkType == kChunkBin && BinChunk.empty())
        {
            BinChunk.assign(Bytes.begin() + P, Bytes.begin() + P + ChunkLength);
        }
        P += ChunkLength;
        // Chunks are padded so the length is a multiple of 4; the padding is
        // inside the declared length in a conformant file, but be forgiving on
        // the way in.
        while ((P % 4) != 0 && P < size_t(TotalLength))
        {
            ++P;
        }
    }

    if (JsonChunk.empty())
    {
        Rep.Error(code::EnvelopeInvalid, Subject, "GLB has no JSON chunk");
        return false;
    }

    std::string Err;
    // The JSON chunk is padded with spaces, which the parser skips as
    // whitespace, so it is passed through unchanged.
    JsonPtr Doc = JsonParse(reinterpret_cast<const char*>(JsonChunk.data()), JsonChunk.size(), Err);
    if (!Doc || !Doc->IsObject())
    {
        Rep.Error(code::EnvelopeInvalid, Subject, "GLB JSON chunk did not parse: " + Err);
        return false;
    }

    if (const JsonValue* Asset = Doc->GetObject("asset"))
    {
        Out.generator = Asset->GetString("generator");
    }

    const JsonValue* Meshes = Doc->GetArray("meshes");
    if (!Meshes || Meshes->Size() == 0)
    {
        Rep.Error(code::PayloadSchemaInvalid, Subject, "GLB has no meshes");
        return false;
    }

    for (size_t m = 0; m < Meshes->Size(); ++m)
    {
        const JsonValue* Mesh = Meshes->At(m);
        const JsonValue* Prims = Mesh ? Mesh->GetArray("primitives") : nullptr;
        if (!Prims)
        {
            continue;
        }
        for (size_t p = 0; p < Prims->Size(); ++p)
        {
            const JsonValue* Pr = Prims->At(p);
            if (!Pr || !Pr->IsObject())
            {
                continue;
            }
            const std::string Where = Subject + " mesh[" + std::to_string(m) + "].primitive["
                                    + std::to_string(p) + "]";

            // SPEC.md 3.10: mode 4 only. glTF's default when absent is 4.
            const int Mode = int(Pr->GetNumber("mode", 4));
            if (Mode != 4)
            {
                Rep.Warn(code::PayloadSchemaInvalid, Where,
                         "mode " + std::to_string(Mode) + " is not triangles; primitive skipped");
                continue;
            }
            const JsonValue* Attr = Pr->GetObject("attributes");
            if (!Attr)
            {
                Rep.Warn(code::PayloadSchemaInvalid, Where, "primitive has no attributes; skipped");
                continue;
            }

            GlbPrimitive Out2;

            const JsonValue* Pos = Attr->Find("POSITION");
            if (!Pos || !Pos->IsNumber())
            {
                Rep.Warn(code::PayloadSchemaInvalid, Where, "no POSITION attribute; primitive skipped");
                continue;
            }
            if (ReadAccessorFloats(*Doc, BinChunk, int(Pos->number), Out2.positions, Where, Rep) != 3)
            {
                continue;
            }

            const JsonValue* Nrm = Attr->Find("NORMAL");
            if (Nrm && Nrm->IsNumber())
            {
                ReadAccessorFloats(*Doc, BinChunk, int(Nrm->number), Out2.normals, Where, Rep);
            }
            else if (bRequireNormals)
            {
                // SPEC.md 3.10: NORMAL is required for renderable geometry.
                // core.geom.source is the exception and the caller says which
                // it is holding, because this parser cannot know.
                Rep.Warn(code::PayloadSchemaInvalid, Where,
                         "renderable geometry without NORMAL; normals will be computed and the "
                         "outcome recorded as measured");
            }

            const JsonValue* Tan = Attr->Find("TANGENT");
            if (Tan && Tan->IsNumber())
            {
                ReadAccessorFloats(*Doc, BinChunk, int(Tan->number), Out2.tangents, Where, Rep);
            }
            const JsonValue* Uv0 = Attr->Find("TEXCOORD_0");
            if (Uv0 && Uv0->IsNumber())
            {
                ReadAccessorFloats(*Doc, BinChunk, int(Uv0->number), Out2.uv0, Where, Rep);
            }
            const JsonValue* Uv1 = Attr->Find("TEXCOORD_1");
            if (Uv1 && Uv1->IsNumber())
            {
                ReadAccessorFloats(*Doc, BinChunk, int(Uv1->number), Out2.uv1, Where, Rep);
            }
            const JsonValue* Col = Attr->Find("COLOR_0");
            if (Col && Col->IsNumber())
            {
                std::vector<float> C;
                const int NC = ReadAccessorFloats(*Doc, BinChunk, int(Col->number), C, Where, Rep);
                if (NC == 4)
                {
                    Out2.colors = std::move(C);
                }
                else if (NC == 3)
                {
                    // Widen VEC3 to VEC4 with opaque alpha, so consumers have
                    // one shape to handle.
                    Out2.colors.resize(C.size() / 3 * 4);
                    for (size_t i = 0; i * 3 + 2 < C.size(); ++i)
                    {
                        Out2.colors[i * 4 + 0] = C[i * 3 + 0];
                        Out2.colors[i * 4 + 1] = C[i * 3 + 1];
                        Out2.colors[i * 4 + 2] = C[i * 3 + 2];
                        Out2.colors[i * 4 + 3] = 1.0f;
                    }
                }
            }

            const JsonValue* Idx = Pr->Find("indices");
            if (!Idx || !Idx->IsNumber())
            {
                Rep.Warn(code::PayloadSchemaInvalid, Where,
                         "non-indexed primitive; SPEC 3.10 says that is not conformant, skipped");
                continue;
            }
            if (!ReadIndices(*Doc, BinChunk, int(Idx->number), Out2.indices, Where, Rep))
            {
                continue;
            }
            if (Out2.indices.size() % 3 != 0)
            {
                Rep.Warn(code::PayloadSchemaInvalid, Where, "index count is not a multiple of 3; skipped");
                continue;
            }

            const size_t VertexCount = Out2.VertexCount();
            bool bBadIndex = false;
            for (unsigned int I : Out2.indices)
            {
                if (size_t(I) >= VertexCount)
                {
                    bBadIndex = true;
                    break;
                }
            }
            if (bBadIndex)
            {
                Rep.Warn(code::PayloadSchemaInvalid, Where, "index out of range; primitive skipped");
                continue;
            }

            Out.primitives.push_back(std::move(Out2));
        }
    }

    if (Out.primitives.empty())
    {
        Rep.Error(code::PayloadSchemaInvalid, Subject, "no usable primitive in the GLB");
        return false;
    }
    return true;
}

bool GlbWrite(const GlbMesh& Mesh, std::vector<uint8_t>& Out, const std::string& NodeName,
              const std::string& Generator, Report& Rep)
{
    Out.clear();
    if (Mesh.primitives.empty())
    {
        Rep.Error(code::PayloadSchemaInvalid, NodeName, "cannot write a GLB with no primitives");
        return false;
    }

    std::vector<uint8_t> Bin;
    JsonPtr Doc = JsonValue::MakeObject();

    JsonPtr Asset = JsonValue::MakeObject();
    Asset->SetString("version", "2.0");
    Asset->SetString("generator", Generator);
    Doc->Set("asset", Asset);

    JsonPtr Views = JsonValue::MakeArray();
    JsonPtr Accessors = JsonValue::MakeArray();

    auto Align4 = [&Bin]()
    {
        while (Bin.size() % 4 != 0)
        {
            Bin.push_back(0);
        }
    };

    // Adds a float accessor and returns its index.
    auto AddFloats = [&](const std::vector<float>& Data, int NComp, bool bWithMinMax) -> int
    {
        Align4();
        const size_t Offset = Bin.size();
        const size_t ByteLength = Data.size() * sizeof(float);
        Bin.resize(Offset + ByteLength);
        if (ByteLength)
        {
            std::memcpy(Bin.data() + Offset, Data.data(), ByteLength);
        }

        JsonPtr V = JsonValue::MakeObject();
        V->SetInt("buffer", 0);
        V->SetInt("byteOffset", (long long)Offset);
        V->SetInt("byteLength", (long long)ByteLength);
        Views->Push(V);
        const int ViewIndex = int(Views->Size()) - 1;

        JsonPtr A = JsonValue::MakeObject();
        A->SetInt("bufferView", ViewIndex);
        A->SetInt("componentType", 5126);
        A->SetInt("count", (long long)(Data.size() / size_t(NComp)));
        A->SetString("type", NComp == 2 ? "VEC2" : (NComp == 3 ? "VEC3" : "VEC4"));
        if (bWithMinMax && !Data.empty())
        {
            // glTF requires min/max on the POSITION accessor and nowhere else.
            JsonPtr Mn = JsonValue::MakeArray();
            JsonPtr Mx = JsonValue::MakeArray();
            for (int c = 0; c < NComp; ++c)
            {
                float LoV = Data[size_t(c)], HiV = Data[size_t(c)];
                for (size_t i = 0; i * size_t(NComp) + size_t(c) < Data.size(); ++i)
                {
                    const float X = Data[i * size_t(NComp) + size_t(c)];
                    if (X < LoV) LoV = X;
                    if (X > HiV) HiV = X;
                }
                Mn->Push(JsonValue::MakeNumber(double(LoV)));
                Mx->Push(JsonValue::MakeNumber(double(HiV)));
            }
            A->Set("min", Mn);
            A->Set("max", Mx);
        }
        Accessors->Push(A);
        return int(Accessors->Size()) - 1;
    };

    auto AddIndices = [&](const std::vector<unsigned int>& Data) -> int
    {
        Align4();
        const size_t Offset = Bin.size();
        const size_t ByteLength = Data.size() * sizeof(uint32_t);
        Bin.resize(Offset + ByteLength);
        for (size_t i = 0; i < Data.size(); ++i)
        {
            const uint32_t X = Data[i];
            Bin[Offset + i * 4 + 0] = uint8_t(X & 0xFF);
            Bin[Offset + i * 4 + 1] = uint8_t((X >> 8) & 0xFF);
            Bin[Offset + i * 4 + 2] = uint8_t((X >> 16) & 0xFF);
            Bin[Offset + i * 4 + 3] = uint8_t((X >> 24) & 0xFF);
        }

        JsonPtr V = JsonValue::MakeObject();
        V->SetInt("buffer", 0);
        V->SetInt("byteOffset", (long long)Offset);
        V->SetInt("byteLength", (long long)ByteLength);
        Views->Push(V);

        JsonPtr A = JsonValue::MakeObject();
        A->SetInt("bufferView", int(Views->Size()) - 1);
        A->SetInt("componentType", 5125); // u32 always: simpler and conformant
        A->SetInt("count", (long long)Data.size());
        A->SetString("type", "SCALAR");
        Accessors->Push(A);
        return int(Accessors->Size()) - 1;
    };

    JsonPtr Primitives = JsonValue::MakeArray();
    for (const GlbPrimitive& Pr : Mesh.primitives)
    {
        if (Pr.positions.empty() || Pr.indices.empty())
        {
            continue;
        }
        JsonPtr Attributes = JsonValue::MakeObject();
        Attributes->SetInt("POSITION", AddFloats(Pr.positions, 3, true));
        if (!Pr.normals.empty())
        {
            Attributes->SetInt("NORMAL", AddFloats(Pr.normals, 3, false));
        }
        if (!Pr.tangents.empty())
        {
            Attributes->SetInt("TANGENT", AddFloats(Pr.tangents, 4, false));
        }
        if (!Pr.uv0.empty())
        {
            Attributes->SetInt("TEXCOORD_0", AddFloats(Pr.uv0, 2, false));
        }
        if (!Pr.uv1.empty())
        {
            Attributes->SetInt("TEXCOORD_1", AddFloats(Pr.uv1, 2, false));
        }
        if (!Pr.colors.empty())
        {
            Attributes->SetInt("COLOR_0", AddFloats(Pr.colors, 4, false));
        }

        JsonPtr P = JsonValue::MakeObject();
        P->Set("attributes", Attributes);
        P->SetInt("indices", AddIndices(Pr.indices));
        P->SetInt("mode", 4);
        Primitives->Push(P);
    }
    if (Primitives->Size() == 0)
    {
        Rep.Error(code::PayloadSchemaInvalid, NodeName, "every primitive was empty");
        return false;
    }

    JsonPtr MeshObj = JsonValue::MakeObject();
    MeshObj->Set("primitives", Primitives);
    JsonPtr MeshesArr = JsonValue::MakeArray();
    MeshesArr->Push(MeshObj);
    Doc->Set("meshes", MeshesArr);

    JsonPtr NodeObj = JsonValue::MakeObject();
    NodeObj->SetString("name", NodeName);
    NodeObj->SetInt("mesh", 0);
    JsonPtr NodesArr = JsonValue::MakeArray();
    NodesArr->Push(NodeObj);
    Doc->Set("nodes", NodesArr);

    JsonPtr SceneObj = JsonValue::MakeObject();
    JsonPtr SceneNodes = JsonValue::MakeArray();
    SceneNodes->Push(JsonValue::MakeNumber(0, true));
    SceneObj->Set("nodes", SceneNodes);
    JsonPtr ScenesArr = JsonValue::MakeArray();
    ScenesArr->Push(SceneObj);
    Doc->Set("scenes", ScenesArr);
    Doc->SetInt("scene", 0);

    Align4();
    JsonPtr Buffer = JsonValue::MakeObject();
    Buffer->SetInt("byteLength", (long long)Bin.size());
    JsonPtr BuffersArr = JsonValue::MakeArray();
    BuffersArr->Push(Buffer);
    Doc->Set("buffers", BuffersArr);
    Doc->Set("bufferViews", Views);
    Doc->Set("accessors", Accessors);

    std::string JsonText = JsonWriteCanonical(*Doc);
    // MINI-SPECS 10.1: the JSON chunk is padded with spaces, the BIN chunk
    // with zeros, and both lengths are multiples of 4.
    while (JsonText.size() % 4 != 0)
    {
        JsonText.push_back(' ');
    }

    const uint32_t Total = 12 + 8 + uint32_t(JsonText.size()) + (Bin.empty() ? 0 : (8 + uint32_t(Bin.size())));
    Out.reserve(Total);
    Wr32(Out, kGlbMagic);
    Wr32(Out, 2);
    Wr32(Out, Total);
    Wr32(Out, uint32_t(JsonText.size()));
    Wr32(Out, kChunkJson);
    Out.insert(Out.end(), JsonText.begin(), JsonText.end());
    if (!Bin.empty())
    {
        Wr32(Out, uint32_t(Bin.size()));
        Wr32(Out, kChunkBin);
        Out.insert(Out.end(), Bin.begin(), Bin.end());
    }
    return true;
}

std::vector<std::string> GlbSelftest(bool bVerbose)
{
    std::vector<std::string> Bad;

    // Round trip a two-triangle quad with every attribute family populated.
    GlbMesh In;
    {
        GlbPrimitive P;
        P.positions = { 0, 0, 0,   1, 0, 0,   1, 1, 0,   0, 1, 0 };
        P.normals   = { 0, 0, 1,   0, 0, 1,   0, 0, 1,   0, 0, 1 };
        P.tangents  = { 1, 0, 0, 1,  1, 0, 0, 1,  1, 0, 0, 1,  1, 0, 0, 1 };
        P.uv0       = { 0, 0,  1, 0,  1, 1,  0, 1 };
        P.colors    = { 1, 0, 0, 1,  0, 1, 0, 1,  0, 0, 1, 1,  1, 1, 1, 1 };
        P.indices   = { 0, 1, 2,  0, 2, 3 };
        In.primitives.push_back(std::move(P));
    }

    Report Rep;
    std::vector<uint8_t> Bytes;
    if (!GlbWrite(In, Bytes, "quad", "werklink-selftest", Rep))
    {
        Bad.push_back("GlbWrite failed on a trivial quad");
        return Bad;
    }
    if (Bytes.size() % 4 != 0)
    {
        Bad.push_back("GLB total length is not a multiple of 4");
    }

    GlbMesh Back;
    if (!GlbRead(Bytes, true, Back, "selftest", Rep))
    {
        Bad.push_back("GlbRead could not read what GlbWrite produced");
        return Bad;
    }
    if (Back.primitives.size() != 1)
    {
        Bad.push_back("round trip: primitive count changed");
        return Bad;
    }
    const GlbPrimitive& B = Back.primitives[0];
    const GlbPrimitive& A = In.primitives[0];

    auto SameF = [&](const std::vector<float>& X, const std::vector<float>& Y, const char* What)
    {
        if (X.size() != Y.size())
        {
            Bad.push_back(std::string("round trip: ") + What + " length changed");
            return;
        }
        for (size_t i = 0; i < X.size(); ++i)
        {
            if (std::fabs(X[i] - Y[i]) > 1e-6f)
            {
                Bad.push_back(std::string("round trip: ") + What + " value changed");
                return;
            }
        }
    };
    SameF(A.positions, B.positions, "POSITION");
    SameF(A.normals,   B.normals,   "NORMAL");
    SameF(A.tangents,  B.tangents,  "TANGENT");
    SameF(A.uv0,       B.uv0,       "TEXCOORD_0");
    SameF(A.colors,    B.colors,    "COLOR_0");
    if (A.indices != B.indices)
    {
        Bad.push_back("round trip: indices changed");
    }
    else if (bVerbose)
    {
        std::printf("  OK GLB round trip: %zu verts, %zu tris, all attributes preserved\n",
                    B.VertexCount(), B.TriangleCount());
    }

    // A non-GLB must be refused rather than misread.
    {
        Report R2;
        GlbMesh M;
        std::vector<uint8_t> NotGlb = { 'P', 'K', 3, 4, 0, 0, 0, 0, 0, 0, 0, 0,
                                        0, 0, 0, 0, 0, 0, 0, 0 };
        if (GlbRead(NotGlb, true, M, "notglb", R2))
        {
            Bad.push_back("GlbRead accepted a non-GLB");
        }
    }

    return Bad;
}

} // namespace werk
