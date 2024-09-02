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
        self.name = json_data["name"] if json_data["name"].strip() else "Untitled"
        self.id = json_data["id"]
        self.author = json_data.get("author", "Unknown")
        self.thumbnail_url = json_data["thumbnailUrl"]
        self.model_url = json_data.get("modelUrl", "")
        self.thumbnail_path = ""


class MeshyApi:
    def __init__(self):
        self.models = OrderedDict()
        self.headers = {}
        self.page_num = 1
        self.has_next_page = False
        self.thumbnail_dir = bpy.utils.user_resource(
            "SCRIPTS", path="meshy_thumbnails", create=True
        )

    def fetch_model_data(self, page_num=1, search_query=""):
        base_url = "https://api.meshy.ai/public/showcases"
        params = {
            "pageNum": page_num,
            "pageSize": 24,
            "search": search_query,
            "sortBy": "-public_popularity",
        }

        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            self.models.clear()
            for model_data in data["result"]:
                model = MeshyModel(model_data)
                self.models[model.id] = model
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
    is_loading: BoolProperty(
        name="Is Loading", default=False
    )  # 新增的属性，用于显示加载状态


class MeshySearchOperator(Operator):
    bl_idname = "wm.meshy_search"
    bl_label = "Search Meshy Library"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        props.is_loading = True  # 设置为加载中状态
        bpy.context.window.cursor_set("WAIT")  # 更改鼠标指针为加载状态

        search_thread = threading.Thread(target=self.search_in_thread, args=(context,))
        search_thread.start()
        return {"FINISHED"}

    def search_in_thread(self, context):
        props = context.window_manager.meshy_browser
        api = MeshyApi()
        user_input = props.user_input

        # 执行搜索并更新模型数据
        api.fetch_model_data(page_num=api.page_num, search_query=user_input)

        # 在主线程中更新 Blender 数据
        def update_results():
            props.search_results.clear()
            for model_id, model in api.models.items():
                props.search_results[model_id] = model
            props.has_next_page = api.has_next_page
            props.page_num = api.page_num

            props.is_loading = False  # 加载完成，更新状态
            bpy.context.window.cursor_set("DEFAULT")  # 恢复默认鼠标指针

            # 加载缩略图
            bpy.ops.wm.meshy_load_thumbnails("INVOKE_DEFAULT")

        # 将更新操作放入Blender主线程中
        bpy.app.timers.register(update_results, first_interval=0.1)


class MeshyNextPageOperator(Operator):
    bl_idname = "wm.meshy_next_page"
    bl_label = "Next Page"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        props.is_loading = True  # 设置为加载中状态
        bpy.context.window.cursor_set("WAIT")  # 更改鼠标指针为加载状态

        next_page_thread = threading.Thread(
            target=self.next_page_in_thread, args=(context,)
        )
        next_page_thread.start()
        return {"FINISHED"}

    def next_page_in_thread(self, context):
        props = context.window_manager.meshy_browser
        api = MeshyApi()
        api.fetch_model_data(page_num=props.page_num + 1, search_query=props.user_input)

        def update_results():
            props.search_results.clear()
            for model_id, model in api.models.items():
                props.search_results[model_id] = model
            props.has_next_page = api.has_next_page
            props.page_num = api.page_num

            props.is_loading = False  # 加载完成，更新状态
            bpy.context.window.cursor_set("DEFAULT")  # 恢复默认鼠标指针

            # 加载缩略图
            bpy.ops.wm.meshy_load_thumbnails("INVOKE_DEFAULT")

        bpy.app.timers.register(update_results, first_interval=0.1)


class MeshyPrevPageOperator(Operator):
    bl_idname = "wm.meshy_prev_page"
    bl_label = "Previous Page"

    def execute(self, context):
        props = context.window_manager.meshy_browser
        props.is_loading = True  # 设置为加载中状态
        bpy.context.window.cursor_set("WAIT")  # 更改鼠标指针为加载状态

        prev_page_thread = threading.Thread(
            target=self.prev_page_in_thread, args=(context,)
        )
        prev_page_thread.start()
        return {"FINISHED"}

    def prev_page_in_thread(self, context):
        props = context.window_manager.meshy_browser
        api = MeshyApi()
        api.fetch_model_data(page_num=props.page_num - 1, search_query=props.user_input)

        def update_results():
            props.search_results.clear()
            for model_id, model in api.models.items():
                props.search_results[model_id] = model
            props.has_next_page = api.has_next_page
            props.page_num = api.page_num

            props.is_loading = False  # 加载完成，更新状态
            bpy.context.window.cursor_set("DEFAULT")  # 恢复默认鼠标指针

            # 加载缩略图
            bpy.ops.wm.meshy_load_thumbnails("INVOKE_DEFAULT")

        bpy.app.timers.register(update_results, first_interval=0.1)


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
    bl_label = "Import Model"

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

        layout.prop(props, "user_input", text="Search")
        layout.operator("wm.meshy_search", text="Search")

        if props.is_loading:
            layout.label(text="Loading... Please wait.", icon="INFO")

        if props.search_results:
            layout.template_icon_view(
                context.window_manager, "meshy_results", show_labels=True
            )

        if not preview_collection["meshy"] and not props.is_loading:
            layout.label(text="No results found")

        # 翻页按钮（同一行，独立控制）
        row = layout.row()

        # 前一页按钮
        subrow = row.row()
        subrow.enabled = props.page_num > 1
        subrow.operator("wm.meshy_prev_page", text="Prev Page", icon="TRIA_LEFT")

        # 下一页按钮
        subrow = row.row()
        subrow.enabled = props.has_next_page
        subrow.operator("wm.meshy_next_page", text="Next Page", icon="TRIA_RIGHT")

        if props.search_results:
            selected_model_name = context.window_manager.meshy_results
            if selected_model_name in props.search_results:
                selected_model = props.search_results[selected_model_name]

                layout.separator()

                layout.label(
                    text=f"Model Name: {selected_model.name}", icon="OBJECT_DATAMODE"
                )

                layout.label(text=f"Author: {selected_model.author}", icon="USER")

                row = layout.row()
                row.scale_y = 1.5
                row.operator(
                    "wm.meshy_download_model",
                    text="Import Model",
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

    api = MeshyApi()
    if os.path.exists(api.thumbnail_dir):
        shutil.rmtree(api.thumbnail_dir)

    if "meshy" in preview_collection:
        bpy.utils.previews.remove(preview_collection["meshy"])


if __name__ == "__main__":
    register()
