import json
import bpy
import tempfile
from .Utils import get_api_key
import requests
import os

T2T_URL = "https://api.meshy.ai/v1/text-to-texture"
taskList = []


# Submit task
class SendSubmitRequest(bpy.types.Operator):
    bl_label = "Submit Task"
    bl_idname = "t2t.submit_task"

    def execute(self, context):
        if len(bpy.context.selected_objects) == 0:
            self.report(type={"ERROR"}, message="No selected objects!")
            return {"FINISHED"}

        if (
            context.scene.t2t_object_prompt == ""
            or context.scene.t2t_object_prompt is None
        ):
            self.report(type={"ERROR"}, message="Object prompt cannot be empty!")
            return {"FINISHED"}

        if (
            context.scene.t2t_style_prompt == ""
            or context.scene.t2t_object_prompt is None
        ):
            self.report(type={"ERROR"}, message="Style prompt cannot be empty!")
            return {"FINISHED"}

        with tempfile.TemporaryDirectory() as tempDir:
            fp = os.path.join(tempDir, "exported.glb")
            bpy.ops.export_scene.gltf(filepath=fp, use_selection=True)
            postData = {
                "object_prompt": context.scene.t2t_object_prompt,
                "style_prompt": context.scene.t2t_style_prompt,
                "enable_original_uv": context.scene.t2t_enable_original_UV,
                "enable_pbr": context.scene.t2t_enable_PBR,
                "negative_prompt": context.scene.t2t_negative_prompt,
                "resolution": context.scene.t2t_resolution,
                "art_style": context.scene.t2t_art_style,
                "name": context.scene.t2t_task_name,
            }
            headers = {"Authorization": f"Bearer {get_api_key()}"}
            response = requests.post(
                T2T_URL,
                files={
                    "model_file": (
                        context.scene.t2t_task_name + ".glb",
                        open(fp, "rb"),
                    )
                },
                headers=headers,
                data=postData,
            )

        response.raise_for_status()
        self.report({"INFO"}, response.text)
        json_res = response.json()
        print(json_res)
        return {"FINISHED"}


# Refresh task list
class RefreshTaskList(bpy.types.Operator):
    bl_label = "Refresh Task List"
    bl_idname = "t2t.refresh_task_list"

    def refreshOnePage(self, context):
        headers = {"Authorization": f"Bearer {get_api_key()}"}

        response = requests.get(T2T_URL + "?sortBy=-created_at", headers=headers)

        response.raise_for_status()

        if response.text != "[]":
            global taskList
            taskList = json.loads(response.text)
            self.report(type={"INFO"}, message="Refreshing completed.")

    def execute(self, context):
        self.refreshOnePage(context)
        return {"FINISHED"}


# Download the model
class DownloadModel(bpy.types.Operator):
    bl_label = "Download Model"
    bl_idname = "t2t.download_model"
    downloadPath: bpy.props.StringProperty(name="download path", default="")

    def execute(self, context):
        req = requests.get(self.downloadPath)
        with tempfile.TemporaryDirectory() as tempDir:
            fp = os.path.join(tempDir, "downloaded.glb")
            with open(fp, "wb") as f:
                f.write(req.content)
            bpy.ops.import_scene.gltf(filepath=fp)
        bpy.context.active_object.scale = (1, 1, 1)
        bpy.context.active_object.location = (0, 0, 0)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
        return {"FINISHED"}


# Create text to texture GUI
class MeshyTextToTexture(bpy.types.Panel):
    bl_idname = "MESHY_PT_text_to_texture"
    bl_label = "Text To Texture"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Meshy"

    # Draw the panel UI
    def draw(self, context):
        layout = self.layout

        # Display a collapsible box for task generation settings
        col = layout.box().column(align=True)
        row = col.row()
        row.prop(
            context.scene,
            "t2t_expanded_task_settings",
            icon=(
                "TRIA_DOWN"
                if context.scene.t2t_expanded_task_settings
                else "TRIA_RIGHT"
            ),
            icon_only=True,
            emboss=False,
        )
        row.label(text="Generation Settings")
        if context.scene.t2t_expanded_task_settings:
            col.label(text="Object Prompt:")
            col.prop(context.scene, "t2t_object_prompt", text="")
            col.label(text="Style Prompt:")
            col.prop(context.scene, "t2t_style_prompt", text="")

            row = col.row()
            row.prop(context.scene, "t2t_enable_original_UV", text="Enable Orginal UV")
            row.prop(context.scene, "t2t_enable_PBR", text="Enable PBR")

            col.label(text="Negative Prompt:")
            col.prop(context.scene, "t2t_negative_prompt", text="")
            col.separator()
            col.prop(context.scene, "t2t_task_name")
            col.prop(context.scene, "t2t_resolution")
            col.prop(context.scene, "t2t_art_style")
            col.separator()

            # bigger button
            row = col.row()
            row.scale_y = 1.5
            row.operator(SendSubmitRequest.bl_idname, text="Submit Task", icon="PLUS")

        # Display a collapsible box for task list
        col = layout.box().column(align=True)
        row = col.row()
        row.prop(
            context.scene,
            "t2t_expanded_task_list",
            icon="TRIA_DOWN" if context.scene.t2t_expanded_task_list else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        row.label(text="Task List")
        if context.scene.t2t_expanded_task_list:
            col.operator(
                RefreshTaskList.bl_idname, text="Refresh Task List", icon="FILE_REFRESH"
            )

            if len(taskList) == 0:
                return

            for task in taskList:
                col.separator()
                if task["status"] in ["SUCCEEDED", "FAILED", "PENDING", "IN_PROGRESS"]:
                    row = col.row()
                    row.label(text=task["name"])
                    row.label(text=task["art_style"])
                    row = col.row()
                    row.label(text=f"Status {task['status']}")
                    if task["status"] == "IN_PROGRESS":
                        row.label(text=f"Progress {str(task['progress'])}")

                if task["status"] == "SUCCEEDED":
                    downloadButton = col.operator(
                        DownloadModel.bl_idname, text="Download", icon="SORT_ASC"
                    )
                    downloadButton.downloadPath = task["model_urls"]["glb"]


# Create value we will use in all of the windows
def CreateValue():
    # The value we will use in text to texture
    bpy.types.Scene.t2t_expanded_task_settings = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.t2t_expanded_task_list = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.t2t_object_prompt = bpy.props.StringProperty(
        name="Object prompt",
        description="Text to texture object prompt",
        default="",
    )
    bpy.types.Scene.t2t_style_prompt = bpy.props.StringProperty(
        name="Style prompt", description="Text to texture style prompt", default=""
    )
    bpy.types.Scene.t2t_enable_original_UV = bpy.props.BoolProperty(
        name="Enable original UV",
        description="Text to texture enable original UV",
        default=False,
    )
    bpy.types.Scene.t2t_enable_PBR = bpy.props.BoolProperty(
        name="Enable PBR", description="Text to texture enable PBR", default=False
    )
    bpy.types.Scene.t2t_negative_prompt = bpy.props.StringProperty(
        name="Negative prompt",
        description="Text to texture negative prompt",
        default="",
    )
    bpy.types.Scene.t2t_art_style = bpy.props.EnumProperty(
        name="Art Style",
        items=[
            ("realistic", "Realistic", ""),
            ("fake-3d-cartoon", "2.5D Cartoon", ""),
            ("cartoon-line-art", "Cartoon Line Art", ""),
            ("fake-3d-hand-drawn", "2.5D Hand-drawn", ""),
            ("japanese-anime", "Japanese Anime", ""),
            ("realistic-hand-drawn", "Realistic Hand-drawn", ""),
            ("oriental-comic-ink", "Oriental Comic Lnk", ""),
        ],
        description="Text to texture art style",
        default="realistic",
    )
    bpy.types.Scene.t2t_resolution = bpy.props.EnumProperty(
        name="Resolution",
        items=[
            ("1024", "1024", ""),
            ("2048", "2048", ""),
            ("4096", "4096", ""),
        ],
        description="Text to texture resolution",
        default="1024",
    )
    bpy.types.Scene.t2t_task_name = bpy.props.StringProperty(
        name="Task Name",
        description="Text to texture task name",
        default="Meshy_model",
    )


# Delete the value we have created
def DeleteValue():
    del bpy.types.Scene.t2t_object_prompt
    del bpy.types.Scene.t2t_style_prompt
    del bpy.types.Scene.t2t_enable_original_UV
    del bpy.types.Scene.t2t_enable_PBR
    del bpy.types.Scene.t2t_negative_prompt
    del bpy.types.Scene.t2t_art_style
    del bpy.types.Scene.t2t_resolution
    del bpy.types.Scene.t2t_task_name
    del bpy.types.Scene.t2t_expanded_task_settings
    del bpy.types.Scene.t2t_expanded_task_list


classes = (
    MeshyTextToTexture,
    SendSubmitRequest,
    RefreshTaskList,
    DownloadModel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    CreateValue()


def unregister():
    DeleteValue()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
