import bpy


def GetApiKey():
    user_preferences = bpy.context.preferences
    addon_preferences = user_preferences.addons["meshy-for-blender"].preferences
    return addon_preferences.api_key
