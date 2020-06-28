from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import compas_rhino
from compas_rv2.rhino import get_scene
from compas.geometry import Translation
from compas_tna.equilibrium import horizontal_nodal
from compas_rv2.rhino import HorizontalConduit


__commandname__ = "RV2tna_horizontal"


def RunCommand(is_interactive):

    def redraw(k, xy, edges):
        if k % conduit.refreshrate:
            return
        print(k)
        conduit.lines = [[[xy[i][1], -xy[i][0]], [xy[j][1], -xy[j][0]]] for i, j in edges]
        conduit.redraw()

    scene = get_scene()
    if not scene:
        return

    form = scene.get('form')[0]
    force = scene.get('force')[0]
    thrust = scene.get('thrust')[0]

    if not form:
        print("There is no FormDiagram in the scene.")
        return

    if not force:
        print("There is no ForceDiagram in the scene.")
        return

    kmax = scene.settings['Solvers']['tna.horizontal.kmax']
    alpha = scene.settings['Solvers']['tna.horizontal.alpha']
    refresh = scene.settings['Solvers']['tna.horizontal.refreshrate']

    options = ['Alpha', 'Iterations', 'RefreshRate']

    while True:
        option = compas_rhino.rs.GetString('Options for horizontal equilibrium solver:', strings=options)

        if not option:
            break

        if option == 'Alpha':
            alpha_options = ['form{}'.format(int(i * 10)) for i in range(11)]
            alpha_default = 0
            for i in range(11):
                if alpha == i * 10:
                    alpha_default = i
                    break
            temp = compas_rhino.rs.GetString('Select parallelisation weight', alpha_options[alpha_default], alpha_options)
            if not temp:
                alpha = 100
            else:
                alpha = int(temp[4:])

        elif option == 'Iterations':
            kmax = compas_rhino.rs.GetInteger('Enter number of iterations', kmax, 1, 10000)

        elif option == 'RefreshRate':
            refresh = compas_rhino.rs.GetInteger('Refresh rate for dynamic visualisation', refresh, 0, 1000)

    if refresh > kmax:
        refresh = 0

    scene.settings['Solvers']['tna.horizontal.kmax'] = kmax
    scene.settings['Solvers']['tna.horizontal.alpha'] = alpha
    scene.settings['Solvers']['tna.horizontal.refreshrate'] = refresh

    if refresh > 0:
        conduit = HorizontalConduit([], refreshrate=refresh)
        with conduit.enabled():
            horizontal_nodal(form.datastructure, force.datastructure, kmax=kmax, alpha=alpha, callback=redraw)
    else:
        horizontal_nodal(form.datastructure, force.datastructure, kmax=kmax, alpha=alpha)

    bbox_form = form.datastructure.bounding_box_xy()
    bbox_force = force.datastructure.bounding_box_xy()
    xmin_form, xmax_form = bbox_form[0][0], bbox_form[1][0]
    xmin_force, _ = bbox_force[0][0], bbox_force[1][0]
    ymin_form, ymax_form = bbox_form[0][1], bbox_form[3][1]
    ymin_force, ymax_force = bbox_force[0][1], bbox_force[3][1]
    y_form = ymin_form + 0.5 * (ymax_form - ymin_form)
    y_force = ymin_force + 0.5 * (ymax_force - ymin_force)
    dx = 1.3 * (xmax_form - xmin_form) + (xmin_form - xmin_force)
    dy = y_form - y_force

    force.datastructure.transform(Translation.from_vector([dx, dy, 0]))
    force.datastructure.update_angle_deviations()

    thrust.settings['_is.valid'] = False

    scene.update()

    max_angle = max(form.datastructure.edges_attribute('_a'))
    tol = scene.settings['RV2']['tol.angles']

    if max_angle < tol:
        print('Horizontal equilibrium found!')
        print('Maximum angle deviation:', max_angle)
    else:
        print('Horizontal equilibrium NOT found! Consider running more iterations.')
        print('Maximum angle deviation:', max_angle)


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":

    RunCommand(True)
