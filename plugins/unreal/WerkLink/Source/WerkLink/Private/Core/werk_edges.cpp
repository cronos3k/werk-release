#include "werk_edges.h"

#include <cstdio>
#include <map>
#include <set>

namespace werk
{

std::vector<DanglingEdge> FindDanglingEdges(const JsonValue& Nodes)
{
    std::vector<DanglingEdge> Out;
    if (!Nodes.IsArray())
    {
        return Out;
    }
    std::set<std::string> Ids;
    for (size_t i = 0; i < Nodes.Size(); ++i)
    {
        const JsonValue* N = Nodes.At(i);
        if (N && N->IsObject())
        {
            const JsonValue* Id = N->Find("node_id");
            if (Id && Id->IsString())
            {
                Ids.insert(Id->str);
            }
        }
    }
    for (size_t i = 0; i < Nodes.Size(); ++i)
    {
        const JsonValue* N = Nodes.At(i);
        if (!N || !N->IsObject())
        {
            continue;
        }
        const JsonValue* Edges = N->GetArray("edges");
        if (!Edges)
        {
            continue;
        }
        for (size_t k = 0; k < Edges->Size(); ++k)
        {
            const JsonValue* E = Edges->At(k);
            if (!E || !E->IsObject())
            {
                continue;
            }
            const JsonValue* To = E->Find("to");
            const std::string Target = (To && To->IsString()) ? To->str : std::string();
            if (Target.empty() || Ids.find(Target) == Ids.end())
            {
                Out.push_back({ N->GetString("node_id"), Target, E->GetString("kind") });
            }
        }
    }
    return Out;
}

std::string DescribeDanglingEdges(const std::vector<DanglingEdge>& Bad)
{
    std::string S;
    for (const DanglingEdge& D : Bad)
    {
        if (!S.empty())
        {
            S += ", ";
        }
        S += "`" + D.Source + "` " + (D.Kind.empty() ? std::string("?") : D.Kind)
             + " `" + D.Target + "`";
    }
    return S;
}

std::vector<std::string> FindSharedPaths(const JsonValue& Nodes)
{
    std::vector<std::string> Out;
    if (!Nodes.IsArray())
    {
        return Out;
    }
    std::map<std::string, std::string> Owner;
    std::set<std::string> Reported;
    for (size_t i = 0; i < Nodes.Size(); ++i)
    {
        const JsonValue* N = Nodes.At(i);
        if (!N || !N->IsObject())
        {
            continue;
        }
        const std::string Id = N->GetString("node_id");
        const JsonValue* Versions = N->GetArray("versions");
        for (size_t v = 0; Versions && v < Versions->Size(); ++v)
        {
            const JsonValue* Files = Versions->At(v) ? Versions->At(v)->GetArray("files") : nullptr;
            for (size_t f = 0; Files && f < Files->Size(); ++f)
            {
                const JsonValue* F = Files->At(f);
                if (!F || !F->IsObject())
                {
                    continue;
                }
                const std::string Path = F->GetString("path");
                auto It = Owner.find(Path);
                if (It == Owner.end())
                {
                    Owner[Path] = Id;
                }
                else if (It->second != Id && Reported.insert(Path).second)
                {
                    Out.push_back(Path + " (" + It->second + ", " + Id + ")");
                }
            }
        }
    }
    return Out;
}

std::vector<std::string> EdgeGuardSelftest(bool bVerbose)
{
    std::vector<std::string> Bad;
    auto Check = [&](const char* Name, const char* Json, size_t Want)
    {
        std::string Err;
        const std::string Text(Json);
        JsonPtr Doc = JsonParse(Text.data(), Text.size(), Err);
        if (!Doc)
        {
            Bad.push_back(std::string(Name) + ": test JSON did not parse: " + Err);
            return;
        }
        const std::vector<DanglingEdge> Got = FindDanglingEdges(*Doc);
        if (Got.size() != Want)
        {
            char Buf[160];
            std::snprintf(Buf, sizeof(Buf), "%s: %d dangling edge(s), want %d", Name,
                          int(Got.size()), int(Want));
            Bad.push_back(std::string(Buf) + " [" + DescribeDanglingEdges(Got) + "]");
        }
        else if (bVerbose)
        {
            std::printf("    %-34s %d dangling (%s)\n", Name, int(Got.size()),
                        DescribeDanglingEdges(Got).c_str());
        }
    };
    Check("all targets present",
          "[{\"node_id\":\"a\",\"edges\":[{\"to\":\"b\",\"kind\":\"requires\"}]},"
          "{\"node_id\":\"b\",\"edges\":[]}]", 0);
    Check("requires to an absent node",
          "[{\"node_id\":\"a\",\"edges\":[{\"to\":\"gone\",\"kind\":\"requires\"}]}]", 1);
    Check("enhances to an absent node",
          "[{\"node_id\":\"a\",\"edges\":[{\"to\":\"gone\",\"kind\":\"enhances\"}]}]", 1);
    Check("edge with no `to`",
          "[{\"node_id\":\"a\",\"edges\":[{\"kind\":\"requires\"}]}]", 1);
    Check("self edge (target exists)",
          "[{\"node_id\":\"a\",\"edges\":[{\"to\":\"a\",\"kind\":\"enhances\"}]}]", 0);
    Check("forward reference (later node)",
          "[{\"node_id\":\"m\",\"edges\":[{\"to\":\"t\",\"kind\":\"requires\"},"
          "{\"to\":\"x\",\"kind\":\"enhances\"}]},{\"node_id\":\"t\"}]", 1);

    // FindSharedPaths
    {
        const std::string Text =
            "[{\"node_id\":\"a\",\"versions\":[{\"files\":[{\"path\":\"g/x.glb\"}]},"
            "{\"files\":[{\"path\":\"g/x.glb\"}]}]},"
            "{\"node_id\":\"b\",\"versions\":[{\"files\":[{\"path\":\"g/x.glb\"},"
            "{\"path\":\"g/y.glb\"}]}]}]";
        std::string Err;
        JsonPtr Doc = JsonParse(Text.data(), Text.size(), Err);
        const std::vector<std::string> Got = Doc ? FindSharedPaths(*Doc) : std::vector<std::string>();
        if (!Doc || Got.size() != 1 || Got[0] != "g/x.glb (a, b)")
        {
            Bad.push_back("shared path across two nodes: want exactly 'g/x.glb (a, b)', got "
                          + std::to_string(Got.size()) + (Got.empty() ? "" : " first '" + Got[0] + "'"));
        }
        else if (bVerbose)
        {
            std::printf("    %-34s %s\n", "shared path (versions of one node ok)", Got[0].c_str());
        }
    }
    return Bad;
}

} // namespace werk
