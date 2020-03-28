from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import compas_rhino
from compas_rv2.rhino import get_scene


__commandname__ = "RV2boundaryconditions_loads"


HERE = compas_rhino.get_document_dirname()


def RunCommand(is_interactive):
    scene = get_scene()
    if not scene:
        return

    pattern = scene.get("pattern")[0]

    if not pattern:
        return

    raise NotImplementedError


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":

    RunCommand(True)
