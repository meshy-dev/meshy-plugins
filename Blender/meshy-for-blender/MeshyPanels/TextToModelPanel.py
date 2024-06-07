import json
import bpy
import tempfile
from .Utils import GetApiKey
import requests
import os

T2M_URL = "https://api.meshy.ai/v2/text-to-3d"
taskList = []


# Submit a task
class SubmitTaskToRemote(bpy.types.Operator):
    bl_label = "Submit Task"
    bl_idname = "meshy.t2m_submit_task"

    def execute(self, context):
        if context.scene.t2m_prompt == "" or context.scene.t2m_prompt is None:
            self.report(type={"ERROR"}, message="Prompt cannot be empty!")
            return {"FINISHED"}
        if context.scene.t2m_mode == "preview":
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
            headers = {"Authorization": f"Bearer {GetApiKey()}"}
            response = requests.post(
                T2M_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            self.report({"INFO"}, response.text)
            return {"FINISHED"}
        elif context.scene.t2m_mode == "refine":
            payload = {
                "mode": "refine",
                "preview_task_id": context.scene.t2m_preview_task_id,
            }
            headers = {"Authorization": f"Bearer {GetApiKey()}"}
            return {"FINISHED"}


# Refresh the task list
class RefreshTaskList(bpy.types.Operator):
    bl_label = "Refresh Task List"
    bl_idname = "meshy.t2m_refresh_task_list"

    def refreshOnePage(self, context):
        headers = {"Authorization": f"Bearer {GetApiKey()}"}
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
class AcquireResultsFromRemote(bpy.types.Operator):
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
        headers = {"Authorization": f"Bearer {GetApiKey()}"}
        response = requests.post(
            T2M_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        self.report({"INFO"}, response.text)
        return {"FINISHED"}


# Delete a task
class DeleteTask(bpy.types.Operator):
    bl_label = "Delete Task"
    bl_idname = "t2m.delete_task"
    modelId: bpy.props.StringProperty(name="model id", default="")

    def execute(self, context):
        headers = {"Authorization": f"Bearer {GetApiKey()}"}
        response = requests.delete(
            T2M_URL + f"/{self.modelId}",
            headers=headers,
        )
        response.raise_for_status()
        self.report({"INFO"}, response.text)
        return {"FINISHED"}


# Text to Model panel
class TextToModelPanel(bpy.types.Panel):
    bl_idname = "MESHY_PT_text_to_model"
    bl_label = "Text To Model"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Meshy"

    # Draw the panel UI
    def draw(self, context):
        layout = self.layout
        column = layout.column()
        column.label(text="Mode:")
        column.prop(context.scene, property="t2m_mode", text="")
        if context.scene.t2m_mode == "preview":
            column.label(text="Prompt:")
            column.prop(context.scene, property="t2m_prompt", text="")
            column.label(text="Negative Prompt:")
            column.prop(context.scene, "t2m_negative_prompt", text="")
            column.label(text="Task Name:")
            column.prop(context.scene, "t2m_task_name", text="")
            column.label(text="Art Style:")
            column.prop(context.scene, "t2m_art_style", text="")
            column.prop(context.scene, "t2m_seed", text="Seed")
        elif context.scene.t2m_mode == "refine":
            column.prop(context.scene, "t2m_preview_task_id", text="")
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
        create_col("Mode", "mode")
        create_col("Art Style", "art_style")
        create_col("Status", "status")
        create_col("Progress", "progress")
        col = split.column()
        col.label(text="Refine")
        for task in taskList:
            if task["status"] == "SUCCEEDED" and task["mode"] != "refine":
                refineButton = col.operator(RefineModel.bl_idname, text="Refine")
                refineButton.modelId = task["id"]
                refineButton.taskName = task["name"]
            else:
                col.label(text=" ")
        col = split.column()
        col.label(text="Delete")
        for task in taskList:
            deleteButton = col.operator(DeleteTask.bl_idname, text="Delete")
            deleteButton.modelId = task["id"]


# Create properties shown in the panel
def RegisterProperties():
    bpy.types.Scene.t2m_mode = bpy.props.EnumProperty(
        name="Mode",
        description="Create a preview task, or refine task.",
        items=[("preview", "Preview", ""), ("refine", "Refine", "")],
    )
    bpy.types.Scene.t2m_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="text_to_model_prompt",
        default="",
    )
    bpy.types.Scene.t2m_art_style = bpy.props.EnumProperty(
        name="Art style",
        description="text_to_model_art_style",
        items=[
            ("realistic", "Realistic", ""),
            ("cartoon", "Cartoon", ""),
            ("low-poly", "Low poly", ""),
        ],
    )
    bpy.types.Scene.t2m_negative_prompt = bpy.props.StringProperty(
        name="Negative prompt",
        description="text_to_model_negative_prompt",
        default="",
    )
    bpy.types.Scene.t2m_seed = bpy.props.StringProperty(
        name="Seed",
        description="When you use the same prompt and seed, you will generate the same result.",
        default="",
    )
    bpy.types.Scene.t2m_task_name = bpy.props.StringProperty(
        name="Task name",
        description="text_to_model_task_name",
        default="Meshy_model",
    )


def UnRegisterProperties():
    del bpy.types.Scene.t2m_mode
    del bpy.types.Scene.t2m_prompt
    del bpy.types.Scene.t2m_art_style
    del bpy.types.Scene.t2m_negative_prompt
    del bpy.types.Scene.t2m_task_name


classes = (
    TextToModelPanel,
    SubmitTaskToRemote,
    RefreshTaskList,
    AcquireResultsFromRemote,
    RefineModel,
    DeleteTask,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    RegisterProperties()


def unregister():
    UnRegisterProperties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
