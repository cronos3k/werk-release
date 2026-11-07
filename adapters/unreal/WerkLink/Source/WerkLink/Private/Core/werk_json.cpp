#include "werk_json.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <set>

namespace werk
{

const JsonValue* JsonValue::Find(const std::string& Key) const
{
    if (type != Type::Object)
    {
        return nullptr;
    }
    for (const auto& M : members)
    {
        if (M.first == Key)
        {
            return M.second.get();
        }
    }
    return nullptr;
}

std::string JsonValue::GetString(const std::string& Key, const std::string& Default) const
{
    const JsonValue* V = Find(Key);
    return (V && V->IsString()) ? V->str : Default;
}

double JsonValue::GetNumber(const std::string& Key, double Default) const
{
    const JsonValue* V = Find(Key);
    return (V && V->IsNumber()) ? V->number : Default;
}

bool JsonValue::GetBool(const std::string& Key, bool Default) const
{
    const JsonValue* V = Find(Key);
    return (V && V->IsBool()) ? V->boolean : Default;
}

const JsonValue* JsonValue::GetArray(const std::string& Key) const
{
    const JsonValue* V = Find(Key);
    return (V && V->IsArray()) ? V : nullptr;
}

const JsonValue* JsonValue::GetObject(const std::string& Key) const
{
    const JsonValue* V = Find(Key);
    return (V && V->IsObject()) ? V : nullptr;
}

JsonPtr JsonValue::MakeObject()
{
    auto P = std::make_shared<JsonValue>();
    P->type = Type::Object;
    return P;
}
JsonPtr JsonValue::MakeArray()
{
    auto P = std::make_shared<JsonValue>();
    P->type = Type::Array;
    return P;
}
JsonPtr JsonValue::MakeString(const std::string& S)
{
    auto P = std::make_shared<JsonValue>();
    P->type = Type::String;
    P->str = S;
    return P;
}
JsonPtr JsonValue::MakeNumber(double D, bool bInteger)
{
    auto P = std::make_shared<JsonValue>();
    P->type = Type::Number;
    P->number = D;
    P->bIsInteger = bInteger || (D == std::floor(D) && std::fabs(D) < 9007199254740992.0 && bInteger);
    return P;
}
JsonPtr JsonValue::MakeBool(bool B)
{
    auto P = std::make_shared<JsonValue>();
    P->type = Type::Bool;
    P->boolean = B;
    return P;
}
JsonPtr JsonValue::MakeNull()
{
    return std::make_shared<JsonValue>();
}

void JsonValue::Set(const std::string& Key, JsonPtr Value)
{
    type = Type::Object;
    for (auto& M : members)
    {
        if (M.first == Key)
        {
            M.second = std::move(Value);
            return;
        }
    }
    members.emplace_back(Key, std::move(Value));
}

// --- parser ----------------------------------------------------------------

namespace
{
    struct Parser
    {
        const char* P = nullptr;
        const char* End = nullptr;
        const char* Begin = nullptr;
        std::string Error;

        bool Fail(const char* Msg)
        {
            if (Error.empty())
            {
                char Buf[64];
                std::snprintf(Buf, sizeof(Buf), " at byte %lld", (long long)(P - Begin));
                Error = std::string(Msg) + Buf;
            }
            return false;
        }

        void SkipWs()
        {
            // MINI-SPECS 3: exactly these four, between any two tokens. No
            // comments, so no comment skipping here -- a '/' will fall through
            // to a parse error, which is the required behaviour.
            while (P < End && (*P == ' ' || *P == '\t' || *P == '\n' || *P == '\r'))
            {
                ++P;
            }
        }

        bool ParseValue(JsonPtr& Out, int Depth);

        bool ParseString(std::string& Out)
        {
            if (P >= End || *P != '"')
            {
                return Fail("expected a string");
            }
            ++P;
            Out.clear();
            while (true)
            {
                if (P >= End)
                {
                    return Fail("unterminated string");
                }
                const unsigned char C = (unsigned char)*P;
                if (C == '"')
                {
                    ++P;
                    return true;
                }
                if (C < 0x20)
                {
                    return Fail("raw control character in a string");
                }
                if (C == '\\')
                {
                    ++P;
                    if (P >= End)
                    {
                        return Fail("unterminated escape");
                    }
                    const char E = *P++;
                    switch (E)
                    {
                    case '"':  Out.push_back('"');  break;
                    case '\\': Out.push_back('\\'); break;
                    case '/':  Out.push_back('/');  break;
                    case 'b':  Out.push_back('\b'); break;
                    case 'f':  Out.push_back('\f'); break;
                    case 'n':  Out.push_back('\n'); break;
                    case 'r':  Out.push_back('\r'); break;
                    case 't':  Out.push_back('\t'); break;
                    case 'u':
                    {
                        unsigned int Cp = 0;
                        if (!ReadHex4(Cp))
                        {
                            return false;
                        }
                        // MINI-SPECS 3: a code point above U+FFFF is written
                        // as a surrogate pair, high surrogate first.
                        if (Cp >= 0xD800 && Cp <= 0xDBFF)
                        {
                            if (P + 1 >= End || P[0] != '\\' || P[1] != 'u')
                            {
                                return Fail("high surrogate without a low surrogate");
                            }
                            P += 2;
                            unsigned int Lo = 0;
                            if (!ReadHex4(Lo))
                            {
                                return false;
                            }
                            if (Lo < 0xDC00 || Lo > 0xDFFF)
                            {
                                return Fail("high surrogate followed by a non-low surrogate");
                            }
                            Cp = 0x10000 + ((Cp - 0xD800) << 10) + (Lo - 0xDC00);
                        }
                        else if (Cp >= 0xDC00 && Cp <= 0xDFFF)
                        {
                            return Fail("lone low surrogate");
                        }
                        AppendUtf8(Out, Cp);
                        break;
                    }
                    default:
                        return Fail("unknown escape sequence");
                    }
                    continue;
                }
                Out.push_back(*P++);
            }
        }

        bool ReadHex4(unsigned int& Out)
        {
            if (P + 4 > End)
            {
                return Fail("truncated \\u escape");
            }
            Out = 0;
            for (int i = 0; i < 4; ++i)
            {
                const char C = *P++;
                int D;
                if (C >= '0' && C <= '9') D = C - '0';
                else if (C >= 'a' && C <= 'f') D = C - 'a' + 10;
                else if (C >= 'A' && C <= 'F') D = C - 'A' + 10;
                else return Fail("non-hex digit in a \\u escape");
                Out = (Out << 4) | (unsigned int)D;
            }
            return true;
        }

        static void AppendUtf8(std::string& Out, unsigned int Cp)
        {
            if (Cp < 0x80)
            {
                Out.push_back(char(Cp));
            }
            else if (Cp < 0x800)
            {
                Out.push_back(char(0xC0 | (Cp >> 6)));
                Out.push_back(char(0x80 | (Cp & 0x3F)));
            }
            else if (Cp < 0x10000)
            {
                Out.push_back(char(0xE0 | (Cp >> 12)));
                Out.push_back(char(0x80 | ((Cp >> 6) & 0x3F)));
                Out.push_back(char(0x80 | (Cp & 0x3F)));
            }
            else
            {
                Out.push_back(char(0xF0 | (Cp >> 18)));
                Out.push_back(char(0x80 | ((Cp >> 12) & 0x3F)));
                Out.push_back(char(0x80 | ((Cp >> 6) & 0x3F)));
                Out.push_back(char(0x80 | (Cp & 0x3F)));
            }
        }
    };

    bool Parser::ParseValue(JsonPtr& Out, int Depth)
    {
        if (Depth > 200)
        {
            return Fail("nesting too deep");
        }
        SkipWs();
        if (P >= End)
        {
            return Fail("unexpected end of input");
        }

        const char C = *P;
        if (C == '{')
        {
            ++P;
            Out = JsonValue::MakeObject();
            // MINI-SPECS 3: duplicate object keys are illegal and a reader
            // MUST reject the file rather than pick a winner. This set is the
            // whole reason this parser exists.
            std::set<std::string> Seen;
            SkipWs();
            if (P < End && *P == '}')
            {
                ++P;
                return true;
            }
            while (true)
            {
                SkipWs();
                std::string Key;
                if (!ParseString(Key))
                {
                    return false;
                }
                if (!Seen.insert(Key).second)
                {
                    return Fail("duplicate object key");
                }
                SkipWs();
                if (P >= End || *P != ':')
                {
                    return Fail("expected ':'");
                }
                ++P;
                JsonPtr Value;
                if (!ParseValue(Value, Depth + 1))
                {
                    return false;
                }
                Out->members.emplace_back(std::move(Key), std::move(Value));
                SkipWs();
                if (P < End && *P == ',')
                {
                    ++P;
                    SkipWs();
                    if (P < End && *P == '}')
                    {
                        return Fail("trailing comma in an object");
                    }
                    continue;
                }
                if (P < End && *P == '}')
                {
                    ++P;
                    return true;
                }
                return Fail("expected ',' or '}'");
            }
        }

        if (C == '[')
        {
            ++P;
            Out = JsonValue::MakeArray();
            SkipWs();
            if (P < End && *P == ']')
            {
                ++P;
                return true;
            }
            while (true)
            {
                JsonPtr Value;
                if (!ParseValue(Value, Depth + 1))
                {
                    return false;
                }
                Out->items.push_back(std::move(Value));
                SkipWs();
                if (P < End && *P == ',')
                {
                    ++P;
                    SkipWs();
                    if (P < End && *P == ']')
                    {
                        return Fail("trailing comma in an array");
                    }
                    continue;
                }
                if (P < End && *P == ']')
                {
                    ++P;
                    return true;
                }
                return Fail("expected ',' or ']'");
            }
        }

        if (C == '"')
        {
            std::string S;
            if (!ParseString(S))
            {
                return false;
            }
            Out = JsonValue::MakeString(S);
            return true;
        }

        if (C == 't')
        {
            if (End - P < 4 || std::memcmp(P, "true", 4) != 0) return Fail("expected 'true'");
            P += 4;
            Out = JsonValue::MakeBool(true);
            return true;
        }
        if (C == 'f')
        {
            if (End - P < 5 || std::memcmp(P, "false", 5) != 0) return Fail("expected 'false'");
            P += 5;
            Out = JsonValue::MakeBool(false);
            return true;
        }
        if (C == 'n')
        {
            if (End - P < 4 || std::memcmp(P, "null", 4) != 0) return Fail("expected 'null'");
            P += 4;
            Out = JsonValue::MakeNull();
            return true;
        }

        // MINI-SPECS 3: no NaN, no Infinity, no -Infinity -- a JSON number in
        // werk is always finite. Named here rather than left to fall through
        // as a generic syntax error, because the diagnostic matters.
        if (C == 'N' || C == 'I' || (C == '-' && P + 1 < End && P[1] == 'I'))
        {
            return Fail("NaN/Infinity is not a werk JSON number");
        }

        // number = [ '-' ] int [ frac ] [ exp ], with int = '0' | digit1-9 *digit
        const char* Start = P;
        bool bInteger = true;
        if (P < End && *P == '-') ++P;
        if (P >= End) return Fail("truncated number");
        if (*P == '0')
        {
            ++P;
        }
        else if (*P >= '1' && *P <= '9')
        {
            while (P < End && *P >= '0' && *P <= '9') ++P;
        }
        else
        {
            return Fail("expected a value");
        }
        if (P < End && *P == '.')
        {
            bInteger = false;
            ++P;
            if (P >= End || *P < '0' || *P > '9') return Fail("digit expected after '.'");
            while (P < End && *P >= '0' && *P <= '9') ++P;
        }
        if (P < End && (*P == 'e' || *P == 'E'))
        {
            bInteger = false;
            ++P;
            if (P < End && (*P == '+' || *P == '-')) ++P;
            if (P >= End || *P < '0' || *P > '9') return Fail("digit expected in the exponent");
            while (P < End && *P >= '0' && *P <= '9') ++P;
        }

        const std::string Text(Start, size_t(P - Start));
        Out = JsonValue::MakeNumber(std::strtod(Text.c_str(), nullptr), bInteger);
        return true;
    }
}

JsonPtr JsonParse(const char* Data, size_t Length, std::string& OutError)
{
    OutError.clear();
    if (Length >= 3 && (unsigned char)Data[0] == 0xEF && (unsigned char)Data[1] == 0xBB
        && (unsigned char)Data[2] == 0xBF)
    {
        // MINI-SPECS 2: reject, never strip. A stripped BOM changes the file's
        // sha256 and sha256 is the store key.
        OutError = "UTF-8 byte order mark present; MINI-SPECS 2 requires rejecting it, not stripping it";
        return nullptr;
    }

    Parser Ps;
    Ps.Begin = Data;
    Ps.P = Data;
    Ps.End = Data + Length;
    JsonPtr Root;
    if (!Ps.ParseValue(Root, 0))
    {
        OutError = Ps.Error;
        return nullptr;
    }
    Ps.SkipWs();
    if (Ps.P != Ps.End)
    {
        OutError = "trailing content after the top-level value";
        return nullptr;
    }
    return Root;
}

JsonPtr JsonParse(const std::vector<unsigned char>& Bytes, std::string& OutError)
{
    return JsonParse(reinterpret_cast<const char*>(Bytes.data()), Bytes.size(), OutError);
}

// --- writer ----------------------------------------------------------------

namespace
{
    void EscapeInto(std::string& Out, const std::string& S)
    {
        // MINI-SPECS 3 canonical rule 3: only '"', '\\' and U+0000-U+001F are
        // escaped, the last as \u00XX except for the short forms.
        char Buf[8];
        for (unsigned char C : S)
        {
            switch (C)
            {
            case '"':  Out += "\\\""; break;
            case '\\': Out += "\\\\"; break;
            case '\b': Out += "\\b";  break;
            case '\f': Out += "\\f";  break;
            case '\n': Out += "\\n";  break;
            case '\r': Out += "\\r";  break;
            case '\t': Out += "\\t";  break;
            default:
                if (C < 0x20)
                {
                    std::snprintf(Buf, sizeof(Buf), "\\u%04x", (unsigned)C);
                    Out += Buf;
                }
                else
                {
                    Out.push_back(char(C));
                }
                break;
            }
        }
    }

    void WriteNumber(std::string& Out, const JsonValue& V)
    {
        char Buf[64];
        const bool bWhole = (V.number == std::floor(V.number))
                         && std::fabs(V.number) < 9007199254740992.0;
        if (V.bIsInteger && bWhole)
        {
            // Canonical rule 4: integers without a decimal point or exponent.
            std::snprintf(Buf, sizeof(Buf), "%lld", (long long)V.number);
            Out += Buf;
            return;
        }
        // Shortest form that round-trips through binary64.
        for (int Prec = 1; Prec <= 17; ++Prec)
        {
            std::snprintf(Buf, sizeof(Buf), "%.*g", Prec, V.number);
            if (std::strtod(Buf, nullptr) == V.number)
            {
                break;
            }
        }
        Out += Buf;
    }

    void WriteValue(std::string& Out, const JsonValue& V, bool bCanonical, int Indent)
    {
        const std::string Nl = bCanonical ? "" : "\n";
        auto Pad = [&](int N) { return bCanonical ? std::string() : std::string(size_t(N) * 2, ' '); };

        switch (V.type)
        {
        case JsonValue::Type::Null:   Out += "null"; return;
        case JsonValue::Type::Bool:   Out += V.boolean ? "true" : "false"; return;
        case JsonValue::Type::Number: WriteNumber(Out, V); return;
        case JsonValue::Type::String: Out.push_back('"'); EscapeInto(Out, V.str); Out.push_back('"'); return;

        case JsonValue::Type::Array:
        {
            if (V.items.empty()) { Out += "[]"; return; }
            Out.push_back('[');
            Out += Nl;
            for (size_t i = 0; i < V.items.size(); ++i)
            {
                Out += Pad(Indent + 1);
                WriteValue(Out, *V.items[i], bCanonical, Indent + 1);
                if (i + 1 < V.items.size()) Out.push_back(',');
                Out += Nl;
            }
            Out += Pad(Indent);
            Out.push_back(']');
            return;
        }

        case JsonValue::Type::Object:
        {
            if (V.members.empty()) { Out += "{}"; return; }
            std::vector<const std::pair<std::string, JsonPtr>*> Order;
            Order.reserve(V.members.size());
            for (const auto& M : V.members)
            {
                Order.push_back(&M);
            }
            if (bCanonical)
            {
                // Canonical rule 1: keys sorted ascending by UTF-8 byte
                // sequence. std::string's operator< is exactly a byte compare.
                std::sort(Order.begin(), Order.end(),
                          [](const std::pair<std::string, JsonPtr>* A,
                             const std::pair<std::string, JsonPtr>* B)
                          { return A->first < B->first; });
            }
            Out.push_back('{');
            Out += Nl;
            for (size_t i = 0; i < Order.size(); ++i)
            {
                Out += Pad(Indent + 1);
                Out.push_back('"');
                EscapeInto(Out, Order[i]->first);
                Out.push_back('"');
                Out.push_back(':');
                if (!bCanonical) Out.push_back(' ');
                WriteValue(Out, *Order[i]->second, bCanonical, Indent + 1);
                if (i + 1 < Order.size()) Out.push_back(',');
                Out += Nl;
            }
            Out += Pad(Indent);
            Out.push_back('}');
            return;
        }
        }
    }
}

std::string JsonWritePretty(const JsonValue& V)
{
    std::string Out;
    WriteValue(Out, V, false, 0);
    Out.push_back('\n');
    return Out;
}

std::string JsonWriteCanonical(const JsonValue& V)
{
    std::string Out;
    WriteValue(Out, V, true, 0);
    return Out; // rule 5: no trailing newline
}

// --- selftest --------------------------------------------------------------

std::vector<std::string> JsonSelftest(bool bVerbose)
{
    std::vector<std::string> Bad;
    std::string Err;

    auto MustReject = [&](const char* Text, const char* Why)
    {
        std::string E;
        JsonPtr V = JsonParse(Text, std::strlen(Text), E);
        if (V)
        {
            Bad.push_back(std::string("accepted what MINI-SPECS 3 bans: ") + Why);
        }
        else if (bVerbose)
        {
            std::printf("  OK rejected %s (%s)\n", Why, E.c_str());
        }
    };

    auto MustAccept = [&](const char* Text, const char* What)
    {
        std::string E;
        JsonPtr V = JsonParse(Text, std::strlen(Text), E);
        if (!V)
        {
            Bad.push_back(std::string("rejected valid JSON (") + What + "): " + E);
        }
        else if (bVerbose)
        {
            std::printf("  OK accepted %s\n", What);
        }
        return V;
    };

    MustAccept("{}", "empty object");
    MustAccept("[]", "empty array");
    MustAccept("{\"a\":1,\"b\":[1,2,3],\"c\":{\"d\":null},\"e\":true,\"f\":-1.5e3}", "a mixed document");
    MustAccept("  \t\n {\"a\" : 1}  \n ", "leading and trailing whitespace");
    MustAccept("\"\\u00e9\\ud83d\\ude00\"", "escapes including a surrogate pair");

    // The five bans of MINI-SPECS 3, plus the BOM ban of section 2.
    MustReject("{\"a\":1,\"a\":2}", "duplicate object keys");
    MustReject("{\"a\":1,}", "trailing comma");
    MustReject("{'a':1}", "single quotes");
    MustReject("{\"a\":NaN}", "NaN");
    MustReject("{\"a\":Infinity}", "Infinity");
    MustReject("{\"a\":-Infinity}", "-Infinity");
    MustReject("{\"a\":1} // note", "a comment");
    MustReject("\xEF\xBB\xBF{}", "a UTF-8 byte order mark");
    MustReject("{\"a\":01}", "a leading zero");
    MustReject("{\"a\":.5}", "a bare fraction");
    MustReject("{\"a\":\"raw\ncontrol\"}", "a raw control character in a string");
    MustReject("{\"a\":1}{\"b\":2}", "trailing content after the top-level value");
    MustReject("\"\\ud83d\"", "a lone high surrogate");

    // Surrogate pair decoding: \ud83d\ude00 is U+1F600, four UTF-8 bytes.
    {
        const char* Doc = "\"\\ud83d\\ude00\"";
        JsonPtr V = JsonParse(Doc, std::strlen(Doc), Err);
        if (!V || !V->IsString() || V->str.size() != 4
            || (unsigned char)V->str[0] != 0xF0 || (unsigned char)V->str[1] != 0x9F
            || (unsigned char)V->str[2] != 0x98 || (unsigned char)V->str[3] != 0x80)
        {
            Bad.push_back("surrogate pair did not decode to U+1F600");
        }
        else if (bVerbose)
        {
            std::printf("  OK surrogate pair -> 4 UTF-8 bytes\n");
        }
    }

    // Canonical form: sorted keys, no whitespace, integers bare.
    {
        const char* Doc = "{ \"b\" : 2, \"a\" : 1, \"A\" : 3 }";
        JsonPtr V = JsonParse(Doc, std::strlen(Doc), Err);
        if (!V)
        {
            Bad.push_back("canonical test input failed to parse: " + Err);
        }
        else
        {
            const std::string Got = JsonWriteCanonical(*V);
            const std::string Want = "{\"A\":3,\"a\":1,\"b\":2}";
            if (Got != Want)
            {
                Bad.push_back("canonical JSON: got " + Got + " want " + Want);
            }
            else if (bVerbose)
            {
                std::printf("  OK canonical JSON sorts by byte, uppercase first: %s\n", Got.c_str());
            }
        }
    }

    // Canonical form of the empty object is exactly two bytes -- the S-10 case.
    {
        JsonPtr V = JsonValue::MakeObject();
        if (JsonWriteCanonical(*V) != "{}")
        {
            Bad.push_back("canonical JSON of the empty object is not \"{}\"");
        }
    }

    // Number round trip through the shortest-form writer.
    {
        const char* Doc = "{\"a\":0.1,\"b\":1e300,\"c\":-0,\"d\":123456789012345,\"e\":0.30000000000000004}";
        JsonPtr V = JsonParse(Doc, std::strlen(Doc), Err);
        if (!V)
        {
            Bad.push_back("number document failed to parse: " + Err);
        }
        else
        {
            const std::string Canon = JsonWriteCanonical(*V);
            std::string E2;
            JsonPtr V2 = JsonParse(Canon.c_str(), Canon.size(), E2);
            if (!V2)
            {
                Bad.push_back("canonical output did not re-parse: " + E2);
            }
            else
            {
                const char* Keys[5] = { "a", "b", "c", "d", "e" };
                for (const char* K : Keys)
                {
                    if (V->GetNumber(K) != V2->GetNumber(K))
                    {
                        Bad.push_back(std::string("number ") + K + " did not round trip");
                    }
                }
                if (bVerbose)
                {
                    std::printf("  OK numbers round trip through canonical form\n");
                }
            }
        }
    }

    return Bad;
}

} // namespace werk
