import json
import bpy
import tempfile
from .Utils import get_api_key
import requests
import os

T2M_URL = "https://api.meshy.ai/v2/text-to-3d"
taskList = []


# Submit task
class SendSubmitRequest(bpy.types.Operator):
    bl_label = "Submit Task"
    bl_idname = "meshy.t2m_submit_task"

    def execute(self, context):
        if context.scene.t2m_prompt == "" or context.scene.t2m_prompt is None:
            self.report(type={"ERROR"}, message="Prompt cannot be empty!")
            return {"FINISHED"}

        # create preview task
        payload = {
            "mode": "preview",
            "prompt": context.scene.t2m_prompt,
            "art_style": context.scene.t2m_art_style,
            "negative_prompt": context.scene.t2m_negative_prompt,
            "name": context.scene.t2m_task_name,
        }
        # with seed
        if context.scene.t2m_seed != "":
            payload["seed"] = int(context.scene.t2m_seed)
        headers = {"Authorization": f"Bearer {get_api_key()}"}
        response = requests.post(
            T2M_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        self.report({"INFO"}, response.text)
        return {"FINISHED"}


# Refresh task list
class RefreshTaskList(bpy.types.Operator):
    bl_label = "Refresh Task List"
    bl_idname = "meshy.t2m_refresh_task_list"

    def refreshOnePage(self, context):
        headers = {"Authorization": f"Bearer {get_api_key()}"}
        response = requests.get(T2M_URL + "?sortBy=-created_at", headers=headers)
        # response = requests.get(T2M_URL, headers=headers)
        response.raise_for_status()

        if response.text != "[]":
            global taskList
            taskList = json.loads(response.text)
            self.report(type={"INFO"}, message="Refreshing completed.")

    def execute(self, context):
        self.refreshOnePage(context)
        # print(taskList)
        return {"FINISHED"}


# Download the model
class DownloadModel(bpy.types.Operator):
    bl_label = "Download Model"
    bl_idname = "t2m.download_model"
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


# Refine the model
class RefineModel(bpy.types.Operator):
    bl_label = "Refine Model"
    bl_idname = "t2m.refine_model"
    modelId: bpy.props.StringProperty(name="model id", default="")
    taskName: bpy.props.StringProperty(name="task name", default="")

    def execute(self, context):
        payload = {
            "mode": "refine",
            "preview_task_id": self.modelId,
            "name": self.taskName,
        }
        headers = {"Authorization": f"Bearer {get_api_key()}"}
        response = requests.post(
            T2M_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        self.report({"INFO"}, response.text)
        return {"FINISHED"}


# Delete the task
class DeleteTask(bpy.types.Operator):
    bl_label = "Delete Task"
    bl_idname = "t2m.delete_task"
    modelId: bpy.props.StringProperty(name="model id", default="")

    def execute(self, context):
        headers = {"Authorization": f"Bearer {get_api_key()}"}
        response = requests.delete(
            T2M_URL + f"/{self.modelId}",
            headers=headers,
        )
        response.raise_for_status()
        self.report({"INFO"}, response.text)
        return {"FINISHED"}


class MeshyTextToModel(bpy.types.Panel):
    bl_idname = "MESHY_PT_text_to_model"
    bl_label = "Text To Model"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Meshy"
    bl_options = {"DEFAULT_CLOSED"}

    # Draw the panel UI
    def draw(self, context):
        layout = self.layout
        # Display a collapsible box for task generation settings
        col = layout.box().column(align=True)
        row = col.row()
        row.prop(
            context.scene,
            "t2m_expanded_task_settings",
            icon=(
                "TRIA_DOWN"
                if context.scene.t2m_expanded_task_settings
                else "TRIA_RIGHT"
            ),
            icon_only=True,
            emboss=False,
        )
        row.label(text="Generation Settings")
        if context.scene.t2m_expanded_task_settings:
            col.label(text="Prompt:")
            col.prop(context.scene, property="t2m_prompt", text="")
            col.label(text="Negative Prompt:")
            col.prop(context.scene, "t2m_negative_prompt", text="")
            col.label(text="Task Name:")
            col.prop(context.scene, "t2m_task_name", text="")
            col.separator()
            col.prop(context.scene, "t2m_art_style")
            col.prop(context.scene, "t2m_seed", text="Seed")

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
            "t2m_expanded_task_list",
            icon="TRIA_DOWN" if context.scene.t2m_expanded_task_list else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        row.label(text="Task List")
        if context.scene.t2m_expanded_task_list:
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
                    row.label(text="Mode")
                    row.label(text=task["mode"])
                    row = col.row()
                    row.label(text=f"Status {task['status']}")
                    if task["status"] == "IN_PROGRESS":
                        row.label(text=f"Progress {str(task['progress'])}")

                row = col.row()
                if task["status"] == "SUCCEEDED":
                    downloadButton = row.operator(
                        DownloadModel.bl_idname, text="Download", icon="SORT_ASC"
                    )
                    downloadButton.downloadPath = task["model_urls"]["glb"]

                if task["status"] == "SUCCEEDED" and task["mode"] != "refine":
                    refineButton = row.operator(
                        RefineModel.bl_idname, text="Refine", icon="IMAGE"
                    )
                    refineButton.modelId = task["id"]
                    refineButton.taskName = task["name"]

                deleteButton = row.operator(
                    DeleteTask.bl_idname, text="Delete", icon="TRASH"
                )
                deleteButton.modelId = task["id"]


# Create value we will use in all of the windows
def CreateValue():
    # The value we will use in text to texture
    bpy.types.Scene.t2m_expanded_task_settings = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.t2m_expanded_task_list = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.t2m_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="Text to model prompt",
        default="",
    )
    bpy.types.Scene.t2m_art_style = bpy.props.EnumProperty(
        name="Art style",
        items=[
            ("realistic", "Realistic", ""),
            ("cartoon", "Cartoon", ""),
            ("low-poly", "Low poly", ""),
        ],
        description="Text to model art style",
        default="realistic",
    )
    bpy.types.Scene.t2m_negative_prompt = bpy.props.StringProperty(
        name="Negative prompt",
        description="Text to model negative prompt",
        default="",
    )
    bpy.types.Scene.t2m_seed = bpy.props.StringProperty(
        name="Seed",
        description="When you use the same prompt and seed, you will generate the same result.",
        default="",
    )
    bpy.types.Scene.t2m_task_name = bpy.props.StringProperty(
        name="Task name",
        description="Text to model task name",
        default="Meshy_model",
    )


# Delete the value we have created
def DeleteValue():
    del bpy.types.Scene.t2m_prompt
    del bpy.types.Scene.t2m_art_style
    del bpy.types.Scene.t2m_negative_prompt
    del bpy.types.Scene.t2m_task_name
    del bpy.types.Scene.t2m_expanded_task_settings
    del bpy.types.Scene.t2m_expanded_task_list


classes = (
    MeshyTextToModel,
    SendSubmitRequest,
    RefreshTaskList,
    DownloadModel,
    RefineModel,
    DeleteTask,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    CreateValue()


def unregister():
    DeleteValue()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
