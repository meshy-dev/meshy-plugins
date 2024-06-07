import json
import bpy
import tempfile
from .Utils import GetApiKey
import requests
import os

T2T_URL = "https://api.meshy.ai/v1/text-to-texture"
taskList = []


# Submit a task
class SubmitTaskToRemote(bpy.types.Operator):
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
                "art_style": context.scene.t2t_art_syle,
                "name": context.scene.t2t_task_name,
            }
            headers = {"Authorization": f"Bearer {GetApiKey()}"}
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


# Refresh the task list
class RefreshTaskList(bpy.types.Operator):
    bl_label = "Refresh Task List"
    bl_idname = "t2t.refresh_task_list"

    def refreshOnePage(self, context):
        headers = {"Authorization": f"Bearer {GetApiKey()}"}

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
class AcquireResultsFromRemote(bpy.types.Operator):
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


# Text to Texture panel
class TextToTexturePanel(bpy.types.Panel):
    bl_idname = "MESHY_PT_text_to_texture"
    bl_label = "Text To Texture"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Meshy"

    # Draw the panel UI
    def draw(self, context):
        layout = self.layout
        column = layout.column()
        column.label(text="Object Prompt:")
        column.prop(context.scene, "t2t_object_prompt", text="")
        column.label(text="Style Prompt:")
        column.prop(context.scene, "t2t_style_prompt", text="")
        column.prop(context.scene, "t2t_enable_original_UV", text="Enable Orginal UV")
        column.prop(context.scene, "t2t_enable_PBR", text="Enable PBR")
        column.label(text="Negative Prompt:")
        column.prop(context.scene, "t2t_negative_prompt", text="")
        column.label(text="Task Name:")
        column.prop(context.scene, "t2t_task_name", text="")
        column.label(text="Resolution:")
        column.prop(context.scene, "t2t_resolution", text="")
        column.label(text="Art Style:")
        column.prop(context.scene, "t2t_art_syle", text="")
        column.operator(SubmitTaskToRemote.bl_idname, text="Submit Task")
        column.operator(RefreshTaskList.bl_idname, text="Refresh Task List")

        if len(taskList) == 0:
            return

        def create_col(header: str, content_key: str):
            col = split.column()
            col.label(text=header)
            for task in taskList:
                if task["status"] in ["SUCCEEDED", "FAILED", "PENDING", "IN_PROGRESS"]:
                    col.label(text=str(task[content_key]))

        split = layout.split()
        col = split.column()
        col.label(text="Download")
        for task in taskList:
            if task["status"] == "SUCCEEDED":
                downloadButton = col.operator(
                    AcquireResultsFromRemote.bl_idname, text="Download"
                )
                downloadButton.downloadPath = task["model_urls"]["glb"]
            else:
                col.label(text=" ")
        create_col("Task Name", "name")
        create_col("Art Style", "art_style")
        create_col("Status", "status")
        create_col("Progress", "progress")


# Create properties shown in the panel
def RegisterProperties():
    bpy.types.Scene.t2t_object_prompt = bpy.props.StringProperty(
        name="t2t_object_prompt",
        description="text_to_texture_object_prompt",
        default="",
    )
    bpy.types.Scene.t2t_style_prompt = bpy.props.StringProperty(
        name="t2t_style_prompt", description="text_to_texture_style_prompt", default=""
    )
    bpy.types.Scene.t2t_enable_original_UV = bpy.props.BoolProperty(
        name="t2t_enable_original_UV",
        description="text_to_texture_enable_original_UV",
        default=False,
    )
    bpy.types.Scene.t2t_enable_PBR = bpy.props.BoolProperty(
        name="t2t_enable_PBR", description="text_to_texture_enable_PBR", default=False
    )
    bpy.types.Scene.t2t_negative_prompt = bpy.props.StringProperty(
        name="t2t_negative_prompt",
        description="text_to_texture_negative_prompt",
        default="",
    )
    bpy.types.Scene.t2t_art_syle = bpy.props.EnumProperty(
        items=[
            ("realistic", "Realistic", ""),
            ("fake-3d-cartoon", "2.5D Cartoon", ""),
            ("cartoon-line-art", "Cartoon Line Art", ""),
            ("fake-3d-hand-drawn", "2.5D Hand-drawn", ""),
            ("japanese-anime", "Japanese Anime", ""),
            ("realistic-hand-drawn", "Realistic Hand-drawn", ""),
            ("oriental-comic-ink", "Oriental Comic Lnk", ""),
        ],
    )
    bpy.types.Scene.t2t_resolution = bpy.props.EnumProperty(
        items=[
            ("1024", "1024", ""),
            ("2048", "2048", ""),
            ("4096", "4096", ""),
        ]
    )
    bpy.types.Scene.t2t_task_name = bpy.props.StringProperty(
        name="t2t_task_name",
        description="text_to_texture_task_name",
        default="Meshy_model",
    )


def UnRegisterProperties():
    del bpy.types.Scene.t2t_object_prompt
    del bpy.types.Scene.t2t_style_prompt
    del bpy.types.Scene.t2t_enable_original_UV
    del bpy.types.Scene.t2t_enable_PBR
    del bpy.types.Scene.t2t_negative_prompt
    del bpy.types.Scene.t2t_art_syle
    del bpy.types.Scene.t2t_resolution
    del bpy.types.Scene.t2t_task_name


classes = (
    TextToTexturePanel,
    SubmitTaskToRemote,
    RefreshTaskList,
    AcquireResultsFromRemote,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    RegisterProperties()


def unregister():
    UnRegisterProperties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
