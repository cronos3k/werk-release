// werk_edges -- the writer half of SPEC.md section 5, "Edge targets".
//
// Every `edges[].to` names a `node_id` in the same manifest's `nodes[]`. A
// writer MUST NOT emit an edge to an absent node (PR #11 / W1 note): a
// conformant reader kills the source of a `requires` edge to an absent node
// (`requires-missing-node`, error) and degrades an `enhances` edge to one
// (`edge-dangling`, warn). Like the release's `tools/edge_targets.py` and
// werk-core's `refuse_dangling_edges`, this refuses an edge of EITHER kind:
// the MUST NOT is for every edge.
//
// Engine-free, so the standalone gate measures the same code the exporter runs.

#pragma once

#include <string>
#include <vector>

#include "werk_json.h"

namespace werk
{

struct DanglingEdge
{
    std::string Source;   // node_id of the node that carries the edge
    std::string Target;   // the `to` that names no node
    std::string Kind;     // requires | enhances | whatever was written
};

// `Nodes` is the manifest's nodes[] array. Returns every edge whose `to` is not
// a node_id in that array, in manifest order. An edge with no string `to` is
// reported too (Target = ""), because it cannot name a node either.
std::vector<DanglingEdge> FindDanglingEdges(const JsonValue& Nodes);

// One line naming every dangling edge, for a refusal message.
std::string DescribeDanglingEdges(const std::vector<DanglingEdge>& Bad);

// The second writer guard (found by the W5c gate on UE 5.8): every container
// path is listed by exactly ONE node (SPEC 2: a file belongs to one node; a
// path may recur only across versions of that same node). Two nodes naming one
// path means two zip entries with one name, and the release readers disagree
// on which one they hash. Returns "path (node-a, node-b)" for each offender.
std::vector<std::string> FindSharedPaths(const JsonValue& Nodes);

std::vector<std::string> EdgeGuardSelftest(bool bVerbose = false);

} // namespace werk
