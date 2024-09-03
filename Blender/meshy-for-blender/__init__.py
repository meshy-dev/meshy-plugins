bl_info = {
    "name": "Meshy for Blender",
    "author": "Meshy",
    "description": "Meshy for Blender",
    "blender": (3, 3, 0),
    "version": (0, 2, 3),
    "category": "3D View",
    "location": "View3D",
}

from . import MeshyPanels  # noqa: E402

modules = (MeshyPanels,)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
