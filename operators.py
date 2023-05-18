import bpy
import os
import sys
from bpy.app.handlers import persistent

from .utils import create_properties_group, get_asset_path, get_image_data, extract_model_name, get_width, get_height, img_to_base64, transform_to_enum
from .api import ping_api, send_to_api, request_caption, get_model_list, get_module_list, get_upscalers, get_sampler_items, get_module_details



modules = []
models = []
samplers = []
hd_upscalers = []
module_details = []

valid_endpoint = ping_api()

if valid_endpoint:
    modules = get_module_list()
    models = get_model_list()
    hd_upscalers = get_upscalers()
    samplers = get_sampler_items()
    module_details = get_module_details()


class SDBLENDER_OT_interrogate(bpy.types.Operator):
    bl_idname = "sdblender.interrogate"
    bl_label = "Interrogate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bpy.data.images.get('Render Result').has_data

    def execute(self, context):
        scene = context.scene
        interrogator = scene.interrogators.interrogator

        bpy.data.images['Render Result'].save_render(
            get_asset_path('interrogate.png'))
        image_data = get_image_data(get_asset_path('interrogate.png'))

        # Report that the interrogator is starting
        self.report({'INFO'}, "Starting the interrogator...")

        caption = request_caption(image_data, interrogator)

        if caption:
            context.scene.sdblender.prompt = caption

            # Report that the interrogation is finished
            self.report({'INFO'}, "Interrogation finished")
        else:
            self.report({'ERROR'}, "Failed to get caption from the API")

        return {'FINISHED'}


class OverrideSettingsItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    value: bpy.props.IntProperty(name="Value")


class SDBLENDER_Properties(bpy.types.PropertyGroup):
    method: bpy.props.EnumProperty(name="Method", items=[(
        'txt2img', 'Text to Image', ''), ('img2img', 'Image to Image', '')])
    prompt: bpy.props.StringProperty(name="Prompt")
    negative_prompt: bpy.props.StringProperty(
        name="Negative Prompt", default="lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry")
    width: bpy.props.IntProperty(name="Width", get=get_width)
    height: bpy.props.IntProperty(name="Height", get=get_height)
    sampler_name: bpy.props.EnumProperty(
        name="Sampler",
        description="Choose a sampler",
        items=samplers
    )
    sampler_index: bpy.props.IntProperty(name="Sampler Index", default=0)
    batch_size: bpy.props.IntProperty(name="Batch Size", default=1)
    n_iter: bpy.props.IntProperty(name="N Iter", default=1)
    steps: bpy.props.IntProperty(name="Steps", default=20)
    cfg_scale: bpy.props.IntProperty(name="Cfg Scale", default=7)
    seed: bpy.props.IntProperty(name="Seed", default=-1)
    restore_faces: bpy.props.BoolProperty(name="Restore Faces", default=False)
    enable_hr: bpy.props.BoolProperty(name="Enable HR", default=True)
    hr_scale: bpy.props.FloatProperty(name="HR Scale", default=2.0)
    hr_upscaler: bpy.props.EnumProperty(
        name="Upscalers",
        description="Choose an upscaler",
        items=hd_upscalers
    )
    denoising_strength: bpy.props.FloatProperty(
        name="Denoising Strength", default=0.25)
    override_settings_restore_afterwards: bpy.props.BoolProperty(
        name="Override Settings Restore Afterwards")
    override_settings: bpy.props.CollectionProperty(type=OverrideSettingsItem)


class SDBLENDER_Interrogators(bpy.types.PropertyGroup):
    interrogator: bpy.props.EnumProperty(
        name="Interrogator",
        items=[
            ("clip", "Clip", ""),
            ("deepdanbooru", "DeepBooru", "")
        ],
        default="clip"
    )


class SDBLENDER_preferences(bpy.types.AddonPreferences):
    bl_idname = 'Blender-ControlNet'

    address: bpy.props.StringProperty(
        name="Stable Diffusion Address",
        description="Enter the stable diffusion address",
        default="localhost",
    )

    port: bpy.props.IntProperty(
        name="Port",
        description="Enter the port number",
        default=7000,
        min=1,
        max=65535,
    )

    output_folder: bpy.props.StringProperty(
        name="Output Folder",
        description="Select a directory for output files",
        subtype='DIR_PATH',
        default=os.path.join(os.path.expanduser('~'), 'Pictures', 'blender'),
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Blender Stable Diffusion Preferences")
        layout.prop(self, "address")
        layout.prop(self, "port")
        layout.prop(self, "output_folder")


class SDBLENDER_CONTROLNETProperties(bpy.types.PropertyGroup):
    is_using_ai: bpy.props.BoolProperty(name="Use AI", default=True)

    controlnet1: bpy.props.EnumProperty(
        name="Control Net",
        items=transform_to_enum(modules)
    )
    controlnet2: bpy.props.EnumProperty(
        name="Control Net",
        items=transform_to_enum(modules)
    )
    controlnet3: bpy.props.EnumProperty(
        name="Control Net",
        items=transform_to_enum(modules)
    )
    controlnet4: bpy.props.EnumProperty(
        name="Control Net",
        items=transform_to_enum(modules)
    )
    controlnet5: bpy.props.EnumProperty(
        name="Control Net",
        items=transform_to_enum(modules)
    )


class SDBLENDER_PT_Panel(bpy.types.Panel):
    bl_idname = "SDBlender_PT_Panel"
    bl_label = "SD Blender"
    bl_category = "SD Blender"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        sdblender = scene.sdblender
        layout.prop(sdblender, "method")
        layout.prop(sdblender, "prompt")
        layout.prop(sdblender, "negative_prompt")
        layout.prop(sdblender, "sampler_name")
        layout.prop(sdblender, "batch_size")
        layout.prop(sdblender, "steps")
        layout.prop(sdblender, "cfg_scale")
        layout.prop(sdblender, "seed")
        layout.prop(sdblender, "restore_faces")
        if sdblender.method == 'txt2img':
            layout.prop(sdblender, "enable_hr")
            layout.prop(sdblender, "hr_scale")
            layout.prop(sdblender, "hr_upscaler")
            layout.prop(sdblender, "denoising_strength")


class SDBLENDER_PT_ControlNet(bpy.types.Panel):
    bl_label = "Control Net"
    bl_idname = "SDBLENDER_PT_ControlNet"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SD Blender'

    def draw(self, context):
        layout = self.layout

        props = context.scene.controlnet

        layout.prop(props, "is_using_ai")
        layout.prop(props, "controlnet1")
        layout.prop(props, "controlnet2")
        layout.prop(props, "controlnet3")

        def render_options(controlnet_name):
            controlnet_value = getattr(props, controlnet_name)
            if controlnet_value.lower() != "none":
                layout.label(text=controlnet_name.capitalize() + " Options:")
                controlnet_item = getattr(props, controlnet_value.lower())

                for attr_name in dir(controlnet_item):
                    if attr_name.startswith("__") or 'bl_rna' in attr_name or 'rna_type' in attr_name or 'name' in attr_name:
                        continue
                    layout.prop(controlnet_item, attr_name)
                layout.separator()  # add a horizontal rule

        for controlnet in ['controlnet1', 'controlnet2', 'controlnet3']:
            render_options(controlnet)


class SDBLENDER_PT_Interrogate3DView_Panel(bpy.types.Panel):
    bl_label = "Interrogate"
    bl_idname = "SDBLENDER_PT_interrogate"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SD Blender"

    def draw(self, context):
        layout = self.layout
        interrogators = context.scene.interrogators

        layout.prop(interrogators, "interrogator", text="Interrogator")
        layout.operator("sdblender.interrogate")


class SDBLENDER_Options(bpy.types.PropertyGroup):
    generate_on_render: bpy.props.BoolProperty(name="Generate on Render", default=False)


class SDBLENDER_OT_Generate(bpy.types.Operator):
    bl_idname = "render.generate"
    bl_label = "Generate"

    @classmethod
    def poll(cls, context):
        return bpy.data.images.get('Render Result').has_data

    def execute(self, context):
        is_img_ready = bpy.data.images["Render Result"].has_data
        print('sampler_name: ', context.scene.sdblender.sampler_name)

        if is_img_ready:
            image_data = img_to_base64(bpy.data.images["Render Result"])
            send_to_api(image_data=image_data)
        else:
            self.report({'WARNING'}, "Rendered image is not ready.")
        return {'FINISHED'}


class SDBLENDER_PT_Generate(bpy.types.Panel):
    bl_label = "Generate"
    bl_idname = "RENDER_PT_Generate"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SD Blender"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.sdblender_options, "generate_on_render")
        layout.separator()
        layout.operator("render.generate")


def post_render_handler(scene):
    if scene.sdblender_option.generate_on_render:
        bpy.ops.render.generate()


@persistent
def load_handler(dummy):
    bpy.app.handlers.render_post.append(post_render_handler)
    

def register():
    if valid_endpoint:
        classes = create_properties_group(
            modules, models, module_details)
        for cls in classes:
            pointer = bpy.props.PointerProperty(type=cls)
            setattr(SDBLENDER_CONTROLNETProperties,
                    extract_model_name(cls.__name__), pointer)

    bpy.types.Scene.sdblender = bpy.props.PointerProperty(
        type=SDBLENDER_Properties)
    bpy.types.Scene.controlnet = bpy.props.PointerProperty(
        type=SDBLENDER_CONTROLNETProperties)
    bpy.types.Scene.override_settings = bpy.props.CollectionProperty(
        type=OverrideSettingsItem)
    bpy.types.Scene.interrogators = bpy.props.PointerProperty(
        type=SDBLENDER_Interrogators)
    bpy.types.Scene.sdblender_options = bpy.props.PointerProperty(type=SDBLENDER_Options)

    bpy.app.handlers.load_post.append(load_handler)


def unregister():
    del bpy.types.Scene.sdblender
    del bpy.types.Scene.override_settings
    del bpy.types.Scene.controlnet
