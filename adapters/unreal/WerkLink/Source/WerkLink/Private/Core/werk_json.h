// RFC 8259 JSON, restricted to the subset MINI-SPECS.md section 3 permits.
//
// Why not the engine's Json module: because FJsonObject cannot express the one
// rule that matters most here. MINI-SPECS 3 says
//
//     "Duplicate object keys are illegal; a reader encountering one MUST
//      reject the file rather than pick a winner."
//
// A TMap-backed parser picks a winner by construction, silently. It also
// accepts a BOM (MINI-SPECS 2: a reader MUST REJECT a BOM rather than strip
// it, because a stripped BOM changes the file's sha256 and sha256 is the store
// key) and will happily parse NaN and Infinity spellings that section 3 bans.
// Three MUSTs that a general-purpose parser gets wrong is enough reason to
// write two hundred lines.
//
// The second reason is the gate: this file compiles into the standalone MSVC
// target as well as the UE module, so "manifest-parse" can be measured without
// an engine.
//
// Also here: the canonical JSON form of MINI-SPECS 3, used for
// version.input_params only -- keys sorted by UTF-8 byte sequence, no
// whitespace, minimal escaping, integers without a decimal point.

#pragma once

#include <map>
#include <memory>
#include <string>
#include <vector>

namespace werk
{

class JsonValue;
using JsonPtr = std::shared_ptr<JsonValue>;

class JsonValue
{
public:
    enum class Type { Null, Bool, Number, String, Array, Object };

    Type type = Type::Null;
    bool boolean = false;
    double number = 0.0;
    bool bIsInteger = false;   // parsed without a fraction or exponent
    std::string str;
    std::vector<JsonPtr> items;
    // Insertion order is kept alongside the map so a writer can round-trip a
    // document without reordering it. The map is only the lookup index.
    std::vector<std::pair<std::string, JsonPtr>> members;

    bool IsNull()   const { return type == Type::Null; }
    bool IsObject() const { return type == Type::Object; }
    bool IsArray()  const { return type == Type::Array; }
    bool IsString() const { return type == Type::String; }
    bool IsNumber() const { return type == Type::Number; }
    bool IsBool()   const { return type == Type::Bool; }

    // Object access. Returns nullptr when absent or when this is not an object.
    const JsonValue* Find(const std::string& Key) const;
    std::string GetString(const std::string& Key, const std::string& Default = "") const;
    double GetNumber(const std::string& Key, double Default = 0.0) const;
    bool GetBool(const std::string& Key, bool Default = false) const;
    const JsonValue* GetArray(const std::string& Key) const;
    const JsonValue* GetObject(const std::string& Key) const;

    // Array access.
    size_t Size() const { return items.size(); }
    const JsonValue* At(size_t Index) const
    {
        return Index < items.size() ? items[Index].get() : nullptr;
    }

    // Builders, for the export direction.
    static JsonPtr MakeObject();
    static JsonPtr MakeArray();
    static JsonPtr MakeString(const std::string& S);
    static JsonPtr MakeNumber(double D, bool bInteger = false);
    static JsonPtr MakeBool(bool B);
    static JsonPtr MakeNull();

    void Set(const std::string& Key, JsonPtr Value);
    void SetString(const std::string& Key, const std::string& S) { Set(Key, MakeString(S)); }
    void SetNumber(const std::string& Key, double D) { Set(Key, MakeNumber(D)); }
    void SetInt(const std::string& Key, long long I)
    {
        Set(Key, MakeNumber(double(I), true));
    }
    void SetBool(const std::string& Key, bool B) { Set(Key, MakeBool(B)); }
    void Push(JsonPtr Value) { items.push_back(std::move(Value)); }
};

// Parses the restricted subset. On failure returns nullptr and fills OutError
// with a message that names the byte offset. Rejects: a UTF-8 BOM, duplicate
// object keys, NaN/Infinity spellings, comments, trailing commas, single
// quotes, control characters inside strings, and trailing non-whitespace.
JsonPtr JsonParse(const char* Data, size_t Length, std::string& OutError);
JsonPtr JsonParse(const std::vector<unsigned char>& Bytes, std::string& OutError);

// Pretty form, two-space indent, for files a human will read.
std::string JsonWritePretty(const JsonValue& V);
// MINI-SPECS 3 "Canonical JSON (for hashing only)": sorted keys, no
// whitespace, minimal escaping, integers without a decimal point, no trailing
// newline. Used for version.input_params and nowhere else -- everywhere else
// werk hashes the bytes of the file as they are.
std::string JsonWriteCanonical(const JsonValue& V);

std::vector<std::string> JsonSelftest(bool bVerbose = false);

} // namespace werk
