import json
import bpy
import tempfile
from .Utils import get_api_key
import requests
import os

I2M_URL = "https://api.meshy.ai/v1/image-to-3d"
taskList = []


# Submit Image Task
class SendImageSubmitRequest(bpy.types.Operator):
    bl_label = "Submit Image Task"
    bl_idname = "meshy.i2m_submit_task"

    def execute(self, context):
        if not context.scene.i2m_image_path:
            self.report({"ERROR"}, "Image path cannot be empty!")
            return {"FINISHED"}

        # Create task payload
        payload = {
            "enable_pbr": context.scene.i2m_enable_pbr,
            "name": context.scene.i2m_task_name,
        }

        headers = {"Authorization": f"Bearer {get_api_key()}"}

        image_path = bpy.path.abspath(context.scene.i2m_image_path)
        try:
            with open(image_path, "rb") as image_file:
                files = {"image_file": image_file}
                response = requests.post(
                    I2M_URL,
                    headers=headers,
                    data=payload,
                    files=files,
                )
                response.raise_for_status()
                self.report({"INFO"}, "Task submitted successfully.")
        except Exception as e:
            self.report({"ERROR"}, f"Error submitting task: {str(e)}")
            return {"FINISHED"}

        return {"FINISHED"}


# Refresh task list
class RefreshTaskList(bpy.types.Operator):
    bl_label = "Refresh Task List"
    bl_idname = "meshy.i2m_refresh_task_list"

    def refresh_tasks(self, context):
        headers = {"Authorization": f"Bearer {get_api_key()}"}
        response = requests.get(I2M_URL + "?sortBy=-created_at", headers=headers)
        response.raise_for_status()

        if response.text != "[]":
            global taskList
            taskList = json.loads(response.text)
            self.report({"INFO"}, "Task list refreshed.")

    def execute(self, context):
        self.refresh_tasks(context)
        return {"FINISHED"}


# Download the model
class DownloadModel(bpy.types.Operator):
    bl_label = "Download Model"
    bl_idname = "i2m.download_model"
    download_url: bpy.props.StringProperty(name="Download URL", default="")

    def execute(self, context):
        req = requests.get(self.download_url)
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "downloaded.glb")
            with open(file_path, "wb") as f:
                f.write(req.content)
            bpy.ops.import_scene.gltf(filepath=file_path)
        bpy.context.active_object.scale = (1, 1, 1)
        bpy.context.active_object.location = (0, 0, 0)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
        return {"FINISHED"}


# Delete the task
class DeleteTask(bpy.types.Operator):
    bl_label = "Delete Task"
    bl_idname = "i2m.delete_task"
    task_id: bpy.props.StringProperty(name="Task ID", default="")

    def execute(self, context):
        headers = {"Authorization": f"Bearer {get_api_key()}"}
        response = requests.delete(
            f"{I2M_URL}/{self.task_id}",
            headers=headers,
        )
        response.raise_for_status()
        self.report({"INFO"}, "Task deleted successfully.")
        return {"FINISHED"}


class MeshyImageToModel(bpy.types.Panel):
    bl_idname = "MESHY_PT_image_to_model"
    bl_label = "Image To Model"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Meshy"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        # Generation Settings
        col = layout.box().column(align=True)
        row = col.row()
        row.prop(
            context.scene,
            "i2m_expanded_task_settings",
            icon=(
                "TRIA_DOWN"
                if context.scene.i2m_expanded_task_settings
                else "TRIA_RIGHT"
            ),
            icon_only=True,
            emboss=False,
        )
        row.label(text="Generation Settings")
        if context.scene.i2m_expanded_task_settings:
            col.label(text="Image File:")
            col.prop(context.scene, "i2m_image_path", text="")
            col.prop(context.scene, "i2m_enable_pbr", text="Enable PBR")
            col.label(text="Task Name:")
            col.prop(context.scene, "i2m_task_name", text="")
            col.separator()
            row = col.row()
            row.scale_y = 1.5
            row.operator(
                SendImageSubmitRequest.bl_idname, text="Submit Task", icon="PLUS"
            )

        # Task List
        col = layout.box().column(align=True)
        row = col.row()
        row.prop(
            context.scene,
            "i2m_expanded_task_list",
            icon="TRIA_DOWN" if context.scene.i2m_expanded_task_list else "TRIA_RIGHT",
            icon_only=True,
            emboss=False,
        )
        row.label(text="Task List")
        if context.scene.i2m_expanded_task_list:
            col.operator(
                RefreshTaskList.bl_idname, text="Refresh Task List", icon="FILE_REFRESH"
            )

            if not taskList:
                col.label(text="No tasks available.")
                return

            for task in taskList:
                col.separator()
                row = col.row()
                row.label(text=f"Name: {task.get('name', '')}")
                row = col.row()
                row.label(text=f"Status: {task['status']}")
                if task["status"] == "IN_PROGRESS":
                    row.label(text=f"Progress: {str(task['progress'])}")
                elif task["status"] == "FAILED":
                    row.label(
                        text=f"Error: {task.get('error_message', 'Unknown error')}"
                    )

                row = col.row()
                if task["status"] == "SUCCEEDED":
                    download_button = row.operator(
                        DownloadModel.bl_idname, text="Download Model", icon="IMPORT"
                    )
                    download_button.download_url = task["model_urls"]["glb"]

                delete_button = row.operator(
                    DeleteTask.bl_idname, text="Delete Task", icon="TRASH"
                )
                delete_button.task_id = task["id"]


def CreateProperties():
    bpy.types.Scene.i2m_expanded_task_settings = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.i2m_expanded_task_list = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.i2m_image_path = bpy.props.StringProperty(
        name="Image Path",
        description="Path to the image file",
        default="",
        subtype="FILE_PATH",
    )
    bpy.types.Scene.i2m_enable_pbr = bpy.props.BoolProperty(
        name="Enable PBR",
        description="Enable Physically Based Rendering materials",
        default=True,
    )
    bpy.types.Scene.i2m_task_name = bpy.props.StringProperty(
        name="Task Name",
        description="Name of the task",
        default="Meshy_Model",
    )


def RemoveProperties():
    del bpy.types.Scene.i2m_expanded_task_settings
    del bpy.types.Scene.i2m_expanded_task_list
    del bpy.types.Scene.i2m_image_path
    del bpy.types.Scene.i2m_enable_pbr
    del bpy.types.Scene.i2m_task_name


classes = (
    MeshyImageToModel,
    SendImageSubmitRequest,
    RefreshTaskList,
    DownloadModel,
    DeleteTask,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    CreateProperties()


def unregister():
    RemoveProperties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
