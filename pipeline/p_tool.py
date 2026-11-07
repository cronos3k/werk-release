#!/usr/bin/env python3
"""p_tool.py — core.tool and core.tool.config: put a tool's CODE and the
settings it ran with inside the package it produced.

Gregor's order, 2026-08-08: werk must record the tools used to create or
convert its content as part of the data, and must be able to embed the code of
those tools and their configurations in the file. SPEC.md section 3.17 is the
narrative; `spec/schemas/core.tool.schema.json` and
`spec/schemas/core.tool.config.schema.json` are normative.

The doctrine, in one sentence, because it is easy to state and easy to get
subtly wrong: **source always, prebuilt never automatically.** Source is text,
a human or an agent can read it, and reading it is the point. A prebuilt binary
is inert data by default and is never executed, loaded, dlopened, linked or
JITted automatically under any circumstance including a valid signature —
SPEC.md section 7.1, unchanged, and this module refuses to write a prebuilt
tool node that does not carry the `built_from` source entrypoint the rule
requires.

The interesting part of this file is `embed`, which is nine lines of real work
and one paragraph of argument: the tool's own source is read off disk, hashed,
put into the package under `tools/<tool_id>/...`, and described by a JSON
payload that RESTATES the hashes. The restatement is deliberate. The manifest
says what the container holds; the payload says what the tool claims to be;
two independent statements of one fact is how a hand-edited package is caught,
and it is the same construction core.recipe already uses.
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from pipeline.common import jbytes, ROOT
else:
    from .common import jbytes, ROOT

TOOL = "pipeline/p_tool.py"
TOOL_VERSION = "1.0"

SCHEMA_TOOL = "spec/schemas/core.tool.schema.json"
SCHEMA_CONFIG = "spec/schemas/core.tool.config.schema.json"


def embed(ctx, tool_id, name, version, role, language, sources, license_block,
          invocation, node_id=None, entrypoint=None, config=None,
          config_nodes=(), repository=None, prebuilt=None, produced=(),
          note=None, dir_prefix="tools", edges=(), root=None):
    """Embed one tool.

    `sources` is an ordered list of repo-relative paths (or (repo_path,
    package_path) pairs). The FIRST is the entrypoint unless `entrypoint` says
    otherwise. Returns the node_id.
    """
    root = root or ROOT
    node_id = node_id or ("tool-" + tool_id)
    files, refs = [], []
    for item in sources:
        if isinstance(item, (tuple, list)):
            repo_path, pkg_path = item
        else:
            repo_path = item
            pkg_path = "%s/%s/%s" % (dir_prefix, tool_id, os.path.basename(item))
        with open(os.path.join(root, repo_path.replace("/", os.sep)), "rb") as fh:
            data = fh.read()
        f = ctx.put(pkg_path, data)
        files.append(f)
        refs.append({"path": f["path"], "sha256": f["sha256"], "size": f["size"]})

    entry = entrypoint or refs[0]["path"]
    if entry not in [r["path"] for r in refs]:
        raise ValueError("entrypoint %r is not one of this tool's files" % entry)

    form = "source"
    if prebuilt:
        # SPEC.md section 7.1: `built_from` MUST name a source entrypoint in the
        # SAME package, so a suspicious consumer can rebuild and compare rather
        # than trust. A writer that let this slide would be shipping an opaque
        # blob under a doctrine that exists to forbid exactly that.
        if prebuilt.get("built_from") not in [r["path"] for r in refs]:
            raise ValueError(
                "a prebuilt tool must name a `built_from` source entrypoint that "
                "is in this package (SPEC.md section 7.1); %r is not"
                % prebuilt.get("built_from"))
        prebuilt = dict(prebuilt)
        prebuilt["never_auto_execute"] = True
        form = "source+prebuilt"

    doc = {
        "schema_version": 1,
        "tool_id": tool_id,
        "name": name,
        "version": version,
        "role": role,
        "form": form,
        "language": language,
        "entrypoint": entry,
        "files": refs,
        "license": dict(license_block),
        "invocation": dict(invocation),
    }
    if config is not None:
        doc["config"] = config
    if config_nodes:
        doc["config_nodes"] = list(config_nodes)
    if repository:
        doc["repository"] = dict(repository)
    if prebuilt:
        doc["prebuilt"] = prebuilt
    if produced:
        doc["produced"] = list(produced)
    if note:
        doc["note"] = note

    desc = ctx.put("%s/%s/tool.json" % (dir_prefix, tool_id), jbytes(doc))
    ctx.node(node_id, "core.tool",
             ctx.version([desc] + files,
                         "The %s that %s, carried as SOURCE so a reader can "
                         "check what it did instead of believing a producer "
                         "string (SPEC.md section 3.17). %d file(s), entrypoint "
                         "%s. Reading it is the point; nothing in this package "
                         "is ever executed automatically."
                         % (role, _role_phrase(role), len(files), entry),
                         "authored", tool=TOOL, tver=TOOL_VERSION),
             edges=[dict(e) for e in edges],
             meta={"tool_id": tool_id, "role": role, "language": language,
                   "form": form, "file_count": len(files)})
    ctx.schemas["core.tool"] = SCHEMA_TOOL
    return node_id


def _role_phrase(role):
    return {
        "creator": "made this content",
        "converter": "changed this content's representation",
        "processor": "derived something in this package",
        "packager": "assembled this container",
        "validator": "checked this package",
        "viewer": "renders this content",
    }.get(role, "touched this content")


def embed_config(ctx, config_id, tool_node, params, params_provenance,
                 node_id=None, reconstruction=None, config_files=(),
                 environment=None, determinism=None, determinism_note=None,
                 unrecorded=(), ran_at=None, note=None, dir_prefix="tools",
                 edges=None):
    """Embed one RUN's configuration, referencing the tool by node id.

    `params_provenance` is mandatory and is the same three-way distinction
    core.recipe makes about prompts, for the same reason: 'recorded' means the
    running tool persisted this exact object, 'reconstructed' means it was
    rebuilt from the tool's own source and then `reconstruction` is mandatory,
    'authored-after' means a human wrote down what they believe it was.
    """
    node_id = node_id or ("tool-config-" + config_id)
    doc = {
        "schema_version": 1,
        "config_id": config_id,
        "tool_node": tool_node,
        "params": params,
        "params_provenance": params_provenance,
    }
    if params_provenance == "reconstructed" and not reconstruction:
        raise ValueError("params_provenance 'reconstructed' requires a "
                         "`reconstruction` block naming the source it was read "
                         "out of; the schema enforces it and so does this writer")
    if reconstruction:
        doc["reconstruction"] = dict(reconstruction)
    files = []
    if config_files:
        entries = []
        for pkg_path, data, fmt, verbatim, role in config_files:
            f = ctx.put(pkg_path, data)
            files.append(f)
            e = {"path": f["path"], "sha256": f["sha256"], "size": f["size"],
                 "format": fmt, "verbatim": bool(verbatim)}
            if role:
                e["role"] = role
            entries.append(e)
        doc["config_files"] = entries
    if environment:
        doc["environment"] = dict(environment)
    if determinism:
        if not determinism_note:
            raise ValueError("a determinism grade without a note saying WHICH "
                             "FACT puts it in that grade is the thing the field "
                             "exists to prevent")
        doc["determinism"] = determinism
        doc["determinism_note"] = determinism_note
    doc["unrecorded"] = list(unrecorded)
    if ran_at:
        doc["ran_at"] = ran_at
    if note:
        doc["note"] = note

    desc = ctx.put("%s/%s.config.json" % (dir_prefix, config_id), jbytes(doc))
    ctx.node(node_id, "core.tool.config",
             ctx.version([desc] + files,
                         "The exact settings %s ran with for this package: %d "
                         "parameter(s), provenance %r. The keys are the tool's "
                         "own and werk does not rename them."
                         % (tool_node, len(params), params_provenance),
                         "authored", tool=TOOL, tver=TOOL_VERSION),
             edges=(edges if edges is not None
                    else [{"to": tool_node, "kind": "requires",
                           "role": "configures"}]),
             meta={"config_id": config_id, "tool_node": tool_node,
                   "params_provenance": params_provenance})
    ctx.schemas["core.tool.config"] = SCHEMA_CONFIG
    return node_id
