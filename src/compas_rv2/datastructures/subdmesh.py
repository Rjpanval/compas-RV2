from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import Rhino

from compas.datastructures import Mesh
from compas.datastructures import meshes_join
from compas.datastructures.mesh.subdivision import mesh_fast_copy

from compas.utilities import geometric_key

from compas_rhino.geometry import RhinoSurface


class SubdMesh(Mesh):

    def __init__(self, *args, **kwargs):
        super(SubdMesh, self).__init__(*args, **kwargs)
        self.default_edge_attributes.update({
            'brep_curve': None,
            'brep_curve_pts': None,
            'brep_curve_dir': None
        })
        self.default_face_attributes.update({
            'is_quad': False,
            'u_edge': None,
            'v_edge': None,
            'nu': 2,
            'nv': 2,
            'n': 1,
            'brep_face': None
        })
        self._edge_strips = {}

    @classmethod
    def from_guid(cls, guid):
        rhinosurface = RhinoSurface.from_guid(guid)
        brep = Rhino.Geometry.Brep.TryConvertBrep(rhinosurface.geometry)
        subdmesh = rhinosurface.to_compas_mesh(cls=cls)

        gkeys = {geometric_key(subdmesh.vertex_coordinates(vertex)): vertex for vertex in subdmesh.vertices()}

        for brep_face, face in zip(brep.Faces, subdmesh.faces()):

            loop = brep_face.OuterLoop
            curve = loop.To3dCurve()
            segments = curve.Explode()

            if len(segments) == 4:
                domain_u = brep_face.Domain(0)
                domain_v = brep_face.Domain(1)
                u0_xyz = brep_face.PointAt(domain_u[0], domain_v[0])
                u1_xyz = brep_face.PointAt(domain_u[1], domain_v[0])
                v0_xyz = brep_face.PointAt(domain_u[0], domain_v[0])
                v1_xyz = brep_face.PointAt(domain_u[0], domain_v[1])
                u0 = gkeys[geometric_key(u0_xyz)]
                u1 = gkeys[geometric_key(u1_xyz)]
                v0 = gkeys[geometric_key(v0_xyz)]
                v1 = gkeys[geometric_key(v1_xyz)]
                attr = ['is_quad', 'u_edge', 'v_edge', 'brep_face']
                values = [True, (u0, u1), (v0, v1), brep_face]
                subdmesh.face_attributes(face, attr, values)

            else:
                for curve, edge in zip(segments, subdmesh.face_halfedges(face)):
                    sp = curve.PointAtStart
                    ep = curve.PointAtEnd
                    u = gkeys[geometric_key(sp)]
                    v = gkeys[geometric_key(ep)]
                    subdmesh.edge_attribute(edge, 'brep_curve_dir', (u, v))

        return subdmesh

    # ==========================================================================
    #   topology
    # ==========================================================================

    def subd_edge_strip(self, edge):
        """Find the edge strip through quad and nonquad faces"""

        def strip_end_faces(strip):
            # return nonquads at the end of edge strips
            faces1 = self.edge_faces(strip[0][0], strip[0][1])
            faces2 = self.edge_faces(strip[-1][0], strip[-1][1])
            nonquads = []
            for face in faces1 + faces2:
                if face is not None and len(self.face_vertices(face)) != 4:
                    nonquads.append(face)
            return nonquads

        strip = self.edge_strip(edge)

        all_edges = list(strip)

        end_faces = set(strip_end_faces(strip))
        seen = set()

        while len(end_faces) > 0:
            face = end_faces.pop()
            if face not in seen:
                seen.add(face)
                for u, v in self.face_halfedges(face):
                    halfedge = (u, v)
                    if halfedge not in all_edges:
                        rev_hf_face = self.halfedge_face(v, u)
                        if rev_hf_face is not None:
                            if len(self.face_vertices(rev_hf_face)) != 4:
                                end_faces.add(self.halfedge_face(v, u))
                                all_edges.append(halfedge)
                                continue
                        halfedge_strip = self.edge_strip(halfedge)
                        all_edges.extend(halfedge_strip)
                        end_faces.update(strip_end_faces(halfedge_strip))
        return all_edges

    def edge_strip_faces(self, edge_strip):
        """Identify all edge faces of the edge strip"""
        edge_strip_faces = set()
        for u, v in edge_strip:
            face1, face2 = self.edge_faces(u, v)
            if face1 is not None:
                edge_strip_faces.add(face1)
            if face2 is not None:
                edge_strip_faces.add(face2)
        return list(edge_strip_faces)

    def split_boundary(self, subdmesh):
        """Split the ordered list of boundary vertices at the corners of the quadmesh."""
        boundaries = subdmesh.vertices_on_boundaries()
        exterior = boundaries[0]
        opening = []
        openings = [opening]
        for vertex in exterior:
            opening.append(vertex)
            if subdmesh.vertex_degree(vertex) == 2:
                opening = [vertex]
                openings.append(opening)
        openings[-1] += openings[0]
        del openings[0]
        openings[:] = [opening for opening in openings if len(opening) > 2]
        return openings

    # ==========================================================================
    #   remapping
    # ==========================================================================

    def divide_brep_curve(self, edge, n):
        """Divide the brep curve corresponding to the edge"""
        curve = self.edge_attribute(edge, 'brep_curve')
        params = curve.DivideByCount(n, True)
        pts = []
        for param in params:
            pt = curve.PointAt(param)
            pts.append(pt)
        self.edge_attribute(edge, 'brep_curve_pts', pts)
        return pts

    def remap_boundary_vertices(self, edge, subdmesh):
        """Remap the boundary vertices of a subdmesh"""
        pts = self.edge_attribute(edge, 'brep_curve_pts')
        if u != self.edge_attribute(edge, 'brep_curve_dir')[0]:
            pts = pts[::-1]
        subdmesh.vertices_attributes('xyz', pts[1:-1], vertex_loop[1:-1])
        return subdmesh

    # ==========================================================================
    #   subdivision
    # ==========================================================================

    def subdivide_nonquad(self, face, nu, nv):
        """Subdivide a single quad brep_face"""

        brep_face = self.face_attribute(face, 'brep_face')

        domain_u = brep_face.Domain(0)
        domain_v = brep_face.Domain(1)

        du = (domain_u[1] - domain_u[0]) / (nu)
        dv = (domain_v[1] - domain_v[0]) / (nv)

        def point_at(i, j):
            return brep_face.PointAt(i, j)

        quads = []
        for i in range(nu):
            for j in range(nv):
                a = point_at(domain_u[0] + (i + 0) * du, domain_v[0] + (j + 0) * dv)
                b = point_at(domain_u[0] + (i + 1) * du, domain_v[0] + (j + 0) * dv)
                c = point_at(domain_u[0] + (i + 1) * du, domain_v[0] + (j + 1) * dv)
                d = point_at(domain_u[0] + (i + 0) * du, domain_v[0] + (j + 1) * dv)
                quads.append([a, b, c, d])

        return Mesh.from_polygons(quads)


    def subdivide_quad(self, face, n):

        mesh = Mesh()
        vertices = self.face_vertices(face)
        for vertex in vertices:
            x, y, z = self.vertex_coordinates(vertex)
            mesh.add_vertex(vertex, {'x': x, 'y': y, 'z': z})
        mesh.add_face(vertices)
        cls = type(mesh)

        # subdivide mesh -----------------------------------------------------------
        for _ in range(n):
            subd = mesh_fast_copy(mesh)

            edgepoints = []
            for u, v in mesh.edges():
                w = subd.split_edge(u, v, allow_boundary=True)
                edgepoints.append([w, True])

            fkey_xyz = {fkey: mesh.face_centroid(fkey) for fkey in mesh.faces()}

            for fkey in mesh.faces():
                descendant = {i: j for i, j in subd.face_halfedges(fkey)}
                ancestor = {j: i for i, j in subd.face_halfedges(fkey)}

                x, y, z = fkey_xyz[fkey]
                c = subd.add_vertex(x=x, y=y, z=z)

                for key in mesh.face_vertices(fkey):
                    a = ancestor[key]
                    d = descendant[key]
                    subd.add_face([a, key, d, c])

                del subd.face[fkey]

            mesh = subd

        subdmesh = cls.from_data(mesh.data)

        vertex_loops = self.split_boundary(subdmesh)
        for vertex_loop in vertex_loops:
            u = vertex_loop[0]
            v = vertex_loop[-1]
            edge = (u, v)
            self.divide_brep_curve(edge, 2 ** n)
            self.remap_boundary_vertices(edge, subdmesh)

        return subdmesh


    def subdivide_faces(self):

        subd_meshes = []

        for face in self.faces():


            self.subdivide_nonquad()

            self.subdivide_quad()


        return meshes_join(subd_meshes)
