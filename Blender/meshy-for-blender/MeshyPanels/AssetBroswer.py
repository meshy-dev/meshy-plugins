import bpy
import requests
import os
import threading
import shutil
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.types import Operator, Panel, PropertyGroup
import bpy.utils.previews
from collections import OrderedDict

# 初始化 preview_collection
preview_collection = {"meshy": bpy.utils.previews.new()}
ongoingSearches = set([])


class MeshyModel:
    def __init__(self, json_data):
        # 如果模型的名字为空字符串，则将其设置为 "Untitled"
        self.name = json_data["name"] if json_data["name"].strip() else "Untitled"
        self.id = json_data["id"]
        self.author = json_data.get(
            "author", "Unknown"
        )  # 获取作者名称，若无则为 'Unknown'
        self.thumbnail_url = json_data["thumbnailUrl"]
        self.model_url = json_data.get("modelUrl", "")  # 获取模型的下载链接
        self.thumbnail_path = ""


class MeshyApi:
    def __init__(self):
        self.models = OrderedDict()
        self.headers = {}
        self.page_num = 1  # 当前页码
        self.has_next_page = False  # 是否有下一页
        self.thumbnail_dir = bpy.utils.user_resource(
            "SCRIPTS", path="meshy_thumbnails", create=True
        )

    def fetch_model_data(self, page_num=1, search_query=""):
        """Fetch model data from the Meshy API."""
        base_url = "https://api.meshy.ai/public/showcases"
        params = {"pageNum": page_num, "pageSize": 20, "search": search_query}

        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            self.models.clear()
            for model_data in data["result"]:
                model = MeshyModel(model_data)
                self.models[model.id] = model
            # 检查是否有下一页
            self.has_next_page = len(data["result"]) > 0
            self.page_num = page_num
        else:
            print("Failed to fetch data from Meshy API")
            self.has_next_page = False

    def download_thumbnail(self, model):
        """Download thumbnail to a local path."""
        thumbnail_path = os.path.join(self.thumbnail_dir, f"{model.id}.jpeg")

        response = requests.get(model.thumbnail_url, stream=True)
        if response.status_code == 200:
            with open(thumbnail_path, "wb") as f:
                f.write(response.content)
            model.thumbnail_path = thumbnail_path
        else:
            print(f"Failed to download thumbnail for {model.name}")


class MeshyBrowserProps(PropertyGroup):
    user_input: StringProperty(name="Search", description="Search Query", default="")
    search_results = {}
    page_num: IntProperty(name="Page Number", default=1)
    has_next_page: BoolProperty(name="Has Next Page", default=False)


class MeshySearchOperator(Operator):
    bl_idname = "wm.meshy_search"
    bl_label = "Search Meshy Library"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        api = MeshyApi()
        user_input = props.user_input  # 获取用户输入
        api.fetch_model_data(page_num=api.page_num, search_query=user_input)
        props.search_results.clear()

        for model_id, model in api.models.items():
            props.search_results[model_id] = model

        # 更新状态
        props.has_next_page = api.has_next_page
        props.page_num = api.page_num

        bpy.ops.wm.meshy_load_thumbnails("INVOKE_DEFAULT")
        return {"FINISHED"}


class MeshyNextPageOperator(Operator):
    bl_idname = "wm.meshy_next_page"
    bl_label = "Next Page"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        api = MeshyApi()
        api.fetch_model_data(page_num=props.page_num + 1, search_query=props.user_input)
        props.search_results.clear()

        for model_id, model in api.models.items():
            props.search_results[model_id] = model

        # 更新状态
        props.has_next_page = api.has_next_page
        props.page_num = api.page_num

        bpy.ops.wm.meshy_load_thumbnails("INVOKE_DEFAULT")
        return {"FINISHED"}


class MeshyPrevPageOperator(Operator):
    bl_idname = "wm.meshy_prev_page"
    bl_label = "Previous Page"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        api = MeshyApi()
        api.fetch_model_data(page_num=props.page_num - 1, search_query=props.user_input)
        props.search_results.clear()

        for model_id, model in api.models.items():
            props.search_results[model_id] = model

        # 更新状态
        props.has_next_page = api.has_next_page
        props.page_num = api.page_num

        bpy.ops.wm.meshy_load_thumbnails("INVOKE_DEFAULT")
        return {"FINISHED"}


class MeshyLoadThumbnailsOperator(Operator):
    bl_idname = "wm.meshy_load_thumbnails"
    bl_label = "Load Meshy Thumbnails"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        for model in props.search_results.values():
            threading.Thread(target=self.download_thumbnail, args=(model,)).start()
        return {"FINISHED"}

    def download_thumbnail(self, model):
        api = MeshyApi()
        api.download_thumbnail(model)
        preview_collection["meshy"][model.id] = bpy.utils.previews.new().load(
            model.id, model.thumbnail_path, "IMAGE"
        )


class MeshyDownloadModelOperator(Operator):
    bl_idname = "wm.meshy_download_model"
    bl_label = "Download and Import Model"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        selected_model_name = context.window_manager.meshy_results

        if selected_model_name in props.search_results:
            model = props.search_results[selected_model_name]
            model_path = os.path.join(
                bpy.app.tempdir, f"{model.name}.glb"
            )  # 假设模型为 .glb 格式

            # 下载模型文件
            response = requests.get(model.model_url, stream=True)
            if response.status_code == 200:
                with open(model_path, "wb") as f:
                    f.write(response.content)
                self.import_model(model_path)
                self.report(
                    {"INFO"},
                    f"Model {model.name} downloaded and imported successfully.",
                )
            else:
                self.report({"ERROR"}, f"Failed to download model {model.name}.")
        else:
            self.report({"ERROR"}, "No model selected.")

        return {"FINISHED"}

    def import_model(self, model_path):
        # 使用 Blender 的导入功能导入 .glb 文件
        bpy.ops.import_scene.gltf(filepath=model_path)


class MeshyAssetBrowserPanel(Panel):
    bl_idname = "VIEW3D_PT_meshy_asset_browser"
    bl_label = "Assets Browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Meshy"

    def draw(self, context):
        layout = self.layout
        props = context.window_manager.meshy_browser

        # 添加搜索条
        layout.prop(props, "user_input", text="Search")

        # 搜索按钮
        layout.operator("wm.meshy_search", text="Search")

        # 搜索结果的缩略图视图
        if props.search_results:
            layout.template_icon_view(
                context.window_manager, "meshy_results", show_labels=True
            )

        # 如果没有结果，显示一条提示信息
        if not preview_collection["meshy"]:
            layout.label(text="No results found")

        # 翻页按钮
        row = layout.row()
        row.enabled = props.page_num > 1
        row.operator("wm.meshy_prev_page", text="Previous Page", icon="TRIA_LEFT")

        row = layout.row()
        row.enabled = props.has_next_page
        row.operator("wm.meshy_next_page", text="Next Page", icon="TRIA_RIGHT")

        # 显示选中模型的详细信息
        if props.search_results:
            selected_model_name = context.window_manager.meshy_results
            if selected_model_name in props.search_results:
                selected_model = props.search_results[selected_model_name]

                layout.separator()  # 分隔符

                # 显示模型名称
                layout.label(
                    text=f"Model Name: {selected_model.name}", icon="OBJECT_DATAMODE"
                )

                # 显示作者名称
                layout.label(text=f"Author: {selected_model.author}", icon="USER")

                # 下载模型按钮
                layout.operator(
                    "wm.meshy_download_model",
                    text="Download and Import Model",
                    icon="IMPORT",
                )


def list_meshy_results(self, context):
    props = context.window_manager.meshy_browser
    if not preview_collection.get("meshy"):
        preview_collection["meshy"] = bpy.utils.previews.new()
    items = []
    for i, (model_id, model) in enumerate(props.search_results.items()):
        if model.thumbnail_path:
            items.append(
                (
                    model_id,
                    model.name,
                    "",
                    preview_collection["meshy"][model_id].icon_id,
                    i,
                )
            )
        else:
            items.append((model_id, model.name, "", "QUESTION", i))
    return items


classes = (
    MeshyBrowserProps,
    MeshySearchOperator,
    MeshyNextPageOperator,
    MeshyPrevPageOperator,
    MeshyLoadThumbnailsOperator,
    MeshyDownloadModelOperator,
    MeshyAssetBrowserPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.meshy_browser = PointerProperty(type=MeshyBrowserProps)
    bpy.types.WindowManager.meshy_results = EnumProperty(items=list_meshy_results)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.WindowManager.meshy_browser
    del bpy.types.WindowManager.meshy_results

    # 删除缩略图文件夹
    api = MeshyApi()
    if os.path.exists(api.thumbnail_dir):
        shutil.rmtree(api.thumbnail_dir)  # 删除整个文件夹及其内容

    if "meshy" in preview_collection:
        bpy.utils.previews.remove(preview_collection["meshy"])


if __name__ == "__main__":
    register()
