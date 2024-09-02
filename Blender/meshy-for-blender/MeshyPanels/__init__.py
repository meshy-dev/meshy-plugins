import bpy
from . import TextToTexturePanel
from . import TextToModelPanel
from . import AssetBrowser


class APIKeySetting(bpy.types.AddonPreferences):
    bl_idname = "meshy-for-blender"

    # Addon preferences
    api_key: bpy.props.StringProperty(
        name="API Key", description="Enter your API key", default="", subtype="NONE"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_key", full_event=True)


def register():
    bpy.utils.register_class(APIKeySetting)
    AssetBrowser.register()
    TextToTexturePanel.register()
    TextToModelPanel.register()


def unregister():
    TextToModelPanel.unregister()
    TextToTexturePanel.unregister()
    AssetBrowser.unregister()
    bpy.utils.unregister_class(APIKeySetting)
