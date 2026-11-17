"""Where the werk repository, the release libraries and the add-on are.

One resolver for every script in this plug-in folder, so the same files work
in two layouts:

  * the plug-in staging folder   <ws>/plugins/blender/{tools,werk_blender}
                                  <ws>/stage/werk   (repo)  <ws>/stage/libs
  * inside the werk repository   <repo>/plugins/blender/{tools,werk_blender}
                                  <repo>/libs (or a sibling libs/ folder)

Overrides, in this order: $WERK_REPO, $WERK_LIBS, $WERK_BLENDER_ADDON.
Nothing here is ever a user-profile path.
"""

import os

TOOLS = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(TOOLS)


def _is_repo(path):
    return os.path.isfile(os.path.join(path, "spec", "SPEC.md")) and \
        os.path.isfile(os.path.join(path, "loaders", "werk_read.py"))


def repo_root():
    env = os.environ.get("WERK_REPO")
    if env:
        return os.path.abspath(env)
    up2 = os.path.dirname(os.path.dirname(PLUGIN))
    for cand in (up2, os.path.join(up2, "stage", "werk")):
        if _is_repo(cand):
            return os.path.abspath(cand)
    raise SystemExit("cannot find the werk repository: set WERK_REPO")


def libs_root():
    env = os.environ.get("WERK_LIBS")
    if env:
        return os.path.abspath(env)
    repo = repo_root()
    for cand in (os.path.join(repo, "libs"),
                 os.path.join(os.path.dirname(repo), "libs")):
        if os.path.isfile(os.path.join(cand, "python", "werk_single.py")):
            return os.path.abspath(cand)
    raise SystemExit("cannot find the werk release libraries: set WERK_LIBS")


def addon_dir():
    env = os.environ.get("WERK_BLENDER_ADDON")
    if env:
        return os.path.abspath(env)
    return os.path.join(PLUGIN, "werk_blender")
