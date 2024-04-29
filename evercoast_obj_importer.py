import os

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import (StringProperty, BoolProperty)

OBJ_FILTER = ''
OBJ_FILES = []

bl_info = {
    "name": "Evercoast OBJ importer",
    "author": "Evercoast",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "location": "Object Context Menu > Evercoast Import OBJs",
    "description": "Imports all OBJs as a single mesh sequence",
    "warning": "",
    "doc_url": "",
    "category": "",
}


def load_current_obj(frame: int):
    # Very simply, if the current obj isn't loaded, load it again

    if OBJ_FILTER == "":
        return

    if frame >= len(OBJ_FILES):
        frame = len(OBJ_FILES) - 1
    if frame < 0:
        frame = 0

    objs = [obj for obj in bpy.data.objects if obj.name.startswith(OBJ_FILTER)]
    current_obj_file = OBJ_FILES[frame]
    current_obj_name, _ = os.path.splitext(os.path.basename(current_obj_file))
    found = False
    for obj in objs:
        if obj.name == current_obj_name:
            obj.hide_select = False
            obj.hide_set(False)
            found = True
            bpy.context.view_layer.objects.active = obj
        else:
            obj.hide_select = True
            obj.hide_set(True)
            # Ensure a hidden mesh isn't selected
            if obj.select_get():
                obj.select_set(False)

    if found == False:
        bpy.ops.import_scene.obj(filepath=current_obj_file)

        # Get all matching objs, again
        objs = [obj for obj in bpy.data.objects if obj.name.startswith(OBJ_FILTER)]

        new_obj = None
        for o in objs:
            if o.name == current_obj_name:
                new_obj = o

        if new_obj == None:
            print("Failed to find newly loaded OBJ. ERROR")
            return

        new_obj.data.shade_smooth()
        bpy.context.view_layer.objects.active = new_obj

        material = new_obj.material_slots[0].material
        material_input = material.node_tree.nodes.get('Image Texture')
        if not material_input:
            print('creating image texture material node')
            material_input = material.node_tree.nodes.new('ShaderNodeTexImage')
            material_input.image = bpy.data.images.load(current_obj_name.replace('.obj', '.png'))
        material_output = material.node_tree.nodes.get('Material Output')
        bsdf_node = material.node_tree.nodes.get('Principled BSDF')
        emission_node = material.node_tree.nodes.new('ShaderNodeEmission')
        mix_shader_node = material.node_tree.nodes.new("ShaderNodeMixShader")

        # set node locations
        material_input.location = [-245.7530, 613.1129]

        bsdf_node.location = [64.2470, 313.1128]
        emission_node.location = [116.9115, 521.6726]

        mix_shader_node.location = [476.9994, 337.1869]

        material_output.location = [723.6876, 345.8949]

        # link emission shader to material
        material.node_tree.links.new(emission_node.inputs[0], material_input.outputs[0])

        material.node_tree.links.new(mix_shader_node.inputs[1], emission_node.outputs[0])
        material.node_tree.links.new(mix_shader_node.inputs[2], bsdf_node.outputs[0])

        material.node_tree.links.new(material_output.inputs[0], mix_shader_node.outputs[0])


def obj_menu_func(self, context):
    self.layout.separator()
    self.layout.menu("OBJECT_MT_evercoast_obj_submenu", text="Evercoast OBJ")


def parse_obj_sequence(source_file):
    global OBJ_FILES
    global OBJ_FILTER

    def parse_input_path(file_path):
        parts = file_path.split('.')
        if len(parts) >= 3:
            ext = parts[-1]
            if ext == 'obj':
                name = '.'.join(parts[0:-2])
                frame_num = int(parts[-2])
                return frame_num, name

        return -1, ''

    obj_dir = source_file
    if os.path.isfile(source_file):
        # We want to have the directory, not the source file
        obj_dir = os.path.dirname(source_file)

    temp_filter = None
    temp_paths = {}

    for file_path in os.listdir(obj_dir):
        frame_num, file_filter = parse_input_path(file_path)
        if frame_num > 0:
            if temp_filter is None:
                temp_filter = file_filter
            if temp_filter == file_filter:
                temp_paths[frame_num] = file_path

    temp_paths = sorted(temp_paths.items())

    for _, value in temp_paths:
        OBJ_FILES.append(os.path.join(obj_dir, value))
    OBJ_FILTER = temp_filter

    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = len(OBJ_FILES) - 1


def pre_update_handler(scene):
    load_current_obj(scene.frame_current)


def ShowMessageBox(message="", title="Message Box", icon='INFO'):
    def draw(self, context):
        # Incredibly simple and small label
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


class OBJECT_MT_evercoast_obj_submenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_evercoast_obj_submenu"
    bl_label = "Evercoast OBJ"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        layout = self.layout

        # Here is where we add all the submenu options to the UI
        layout.operator("evercoast.import_obj")
        layout.operator("evercoast.export_obj")
        layout.operator("evercoast.purge_obj")


class EVERCOAST_OT_obj_import(bpy.types.Operator, ImportHelper):
    """Import the obj sequence from a folder. Will load on frame change."""
    bl_idname = "evercoast.import_obj"
    bl_label = "Import obj sequence (*.obj)"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(
        default='*.obj',
        options={'HIDDEN'}
    )

    def execute(self, context):
        """Open a .obj file and attempt import"""
        # Parse OBJ paths from source path
        parse_obj_sequence(self.filepath)

        # load first OBJ frame
        load_current_obj(bpy.context.scene.frame_current)
        # Append update handlers. One to load. One to hide the rest
        bpy.app.handlers.frame_change_pre.append(pre_update_handler)

        ShowMessageBox("%d objs available. Starting at frame 0" % bpy.context.scene.frame_end, icon="ERROR")

        return {'FINISHED'}


class EVERCOAST_OT_obj_export(bpy.types.Operator, ImportHelper):
    """Export the loaded objs to a folder. Won't export any frame that isn't loaded."""
    bl_idname = "evercoast.export_obj"
    bl_label = "Export loaded objs (*.obj)"
    bl_options = {'REGISTER', 'UNDO'}

    open_folder: BoolProperty(
        name="Open folder on completion",
        description="Open output folder once export is completed",
        default=False
    )

    def execute(self, context):
        error = False
        output_dir = self.filepath
        if not os.path.isdir(output_dir):
            ShowMessageBox("Please select a directory to export to", icon="ERROR")
            return {'FINISHED'}

        global OBJ_FILTER
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects[:]:
            if obj.name.startswith(OBJ_FILTER):
                print(obj)
                obj.hide_select = False
                obj.hide_set(False)
                obj.select_set(True)
                out_name = "/%s/%s.obj" % (output_dir, obj.name)

                # From testing Blender will ONLY write a texture for a single Principled BSDF shader
                # So we have to relink what we imported, then reset it

                material = obj.material_slots[0].material
                errored = False
                try:
                    material_output = material.node_tree.nodes.get('Material Output')
                except AttributeError as err:
                    print("Failed to get 'Material Output' node.", err)
                    errored = True
                try:
                    bsdf_node = material.node_tree.nodes.get('Principled BSDF')
                except AttributeError as err:
                    print("Failed to get 'Material Output' node.", err)
                    errored = True
                try:
                    mix_shader_node = material.node_tree.nodes.get("Mix Shader")
                except AttributeError as err:
                    print("Failed to get 'Material Output' node.", err)
                    errored = True

                if not errored:
                    material.node_tree.links.new(material_output.inputs[0], bsdf_node.outputs[0])

                    bpy.ops.wm.obj_export(filepath=out_name, export_selected_objects=True, export_materials=True,
                                          export_object_groups=True, export_material_groups=True,
                                          export_vertex_groups=True,
                                          path_mode="COPY")

                    material.node_tree.links.new(material_output.inputs[0], mix_shader_node.outputs[0])
                else:
                    print("Cannot export %s obj. Materials nodes have been edited." % obj.name)

                obj.hide_select = True
                obj.hide_set(True)

        # Set back to current frame visibility of the obj
        load_current_obj(bpy.context.scene.frame_current)
        return {'FINISHED'}


class EVERCOAST_OT_purge_obj(bpy.types.Operator):
    """Delete all evercoast objs and remove the orphaned mesh."""
    bl_idname = "evercoast.purge_obj"
    bl_label = "Purge obj sequence AND orphans"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global OBJ_FILTER
        obj_to_remove = [obj for obj in bpy.data.objects if obj.name.startswith(OBJ_FILTER)]
        [bpy.data.objects.remove(obj, do_unlink=True) for obj in obj_to_remove]

        # Purge orphans, the unlink above won't do this for us
        bpy.types.BlendData.orphans_purge(do_recursive=True)

        # Reset globals
        global OBJ_FILES

        OBJ_FILTER = ''
        OBJ_FILES = []
        return {'FINISHED'}


CLASSES = (
    EVERCOAST_OT_obj_import,
    EVERCOAST_OT_obj_export,
    EVERCOAST_OT_purge_obj,
    OBJECT_MT_evercoast_obj_submenu
)


def register():
    # Called when adding/enabling plugin blender
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object_context_menu.append(obj_menu_func)


def unregister():
    # Called when removing/disabling plugin in blender
    from bpy.utils import unregister_class
    for cls in reversed(CLASSES):
        unregister_class(cls)
    bpy.types.VIEW3D_MT_object_context_menu.remove(obj_menu_func)


if __name__ == "__main__":
    register()
