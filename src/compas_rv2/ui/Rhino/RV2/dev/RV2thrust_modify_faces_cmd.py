from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import compas_rhino

from compas_rv2.rhino import get_scene
from compas_rv2.rhino import rv2_undo
from compas_rv2.rhino import rv2_error
# from compas_rv2.rhino import ModifyAttributesForm


__commandname__ = "RV2thrust_modify_faces"


@rv2_error()
@rv2_undo
def RunCommand(is_interactive):

    scene = get_scene()
    if not scene:
        return

    form = scene.get("form")[0]
    if not form:
        print("There is no FormDiagram in the scene.")
        return

    thrust = scene.get("thrust")[0]
    if not thrust:
        print("There is no ThrustDiagram in the scene.")
        return

    # hide the form vertices
    form_vertices = "{}::vertices".format(form.settings['layer'])
    compas_rhino.rs.HideGroup(form_vertices)

    # selection options
    options = ["Manual"]
    option = compas_rhino.rs.GetString("Selection Type.", strings=options)
    if not option:
        scene.update()
        return

    if option == "Manual":
        keys = thrust.select_faces()

    thrust_name = thrust.name

    if keys:
        public = [name for name in form.datastructure.default_face_attributes.keys() if not name.startswith('_')]
        if form.update_faces_attributes(keys, names=public):
            thrust.datastructure.data = form.datastructure.data
            thrust.name = thrust_name
            thrust.settings['_is.valid'] = False

    scene.update()


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":

    RunCommand(True)
