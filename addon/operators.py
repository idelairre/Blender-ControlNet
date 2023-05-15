from bpy.app.handlers import persistent
import bpy
import os
import shutil
import time
import tempfile
import base64
import requests
import json

from . import constants
from . import utils


def get_sd_host():
    return "http://" + get_preferences().address + ':' + str(get_preferences().port) + "/sdapi/v1/"


def get_preferences():
    preferences = bpy.context.preferences.addons['sd_blender'].preferences
    return preferences


@persistent
def render_complete_handler(scene, context):
    is_img_ready = bpy.data.images["Render Result"].has_data

    if is_img_ready:
        # Fetch the 'is_using_ai' property from the current scene
        is_using_ai = bpy.context.scene.controlnet.is_using_ai
        if is_using_ai:
            send_to_api(bpy.context.scene)
    else:
        print("Rendered image is not ready.")


def to_dict(obj):
    if isinstance(obj, bpy.types.PropertyGroup):
        result = {}
        for prop in obj.__annotations__.keys():
            attr = getattr(obj, prop)
            if isinstance(attr, bpy.types.PropertyGroup):
                result[prop] = to_dict(attr)
            elif isinstance(attr, (list, tuple)):
                result[prop] = [to_dict(i) for i in attr]
            elif isinstance(attr, bpy.types.bpy_prop_collection):
                result[prop] = [to_dict(i) for i in attr]
            else:
                result[prop] = attr
        return result
    elif isinstance(obj, (list, tuple, bpy.types.bpy_prop_collection)):
        return [to_dict(i) for i in obj]
    else:
        return obj


def print_dict(d):
    def transform(d):
        if isinstance(d, dict):
            return {k: "<INPUT_IMAGE>" if k == "input_image" else transform(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [transform(v) for v in d]
        else:
            return d

    transformed = transform(d)
    print(json.dumps(transformed, indent=3))


def request_caption(image_data, interrogator):
    url = get_sd_host() + "interrogate"
    data = {
        "image": image_data,
        "model": interrogator
    }
    response = requests.post(url, headers=constants.headers, data=json.dumps(data))

    if response.status_code == 200:
        caption = response.json()["caption"]
        return caption
    else:
        print("Error while requesting caption:")
        print(response.content)
        return None


def send_to_api(scene):
    models = {
        "none": bpy.context.scene.controlnet.none,
        "canny": bpy.context.scene.controlnet.canny,
        "depth": bpy.context.scene.controlnet.depth,
        "depth_leres": bpy.context.scene.controlnet.depth_leres,
        "depth_leres++": bpy.context.scene.controlnet.depth_leres_plusplus,
        "hed": bpy.context.scene.controlnet.hed,
        "hed_safe": bpy.context.scene.controlnet.hed_safe,
        "mediapipe_face": bpy.context.scene.controlnet.mediapipe_face,
        "mlsd": bpy.context.scene.controlnet.mlsd,
        "normal_map": bpy.context.scene.controlnet.normal_map,
        "openpose": bpy.context.scene.controlnet.openpose,
        "openpose_hand": bpy.context.scene.controlnet.openpose_hand,
        "openpose_face": bpy.context.scene.controlnet.openpose_face,
        "openpose_faceonly": bpy.context.scene.controlnet.openpose_faceonly,
        "openpose_full": bpy.context.scene.controlnet.openpose_full,
        "clip_vision": bpy.context.scene.controlnet.clip_vision,
        "color": bpy.context.scene.controlnet.color,
        "pidinet": bpy.context.scene.controlnet.pidinet,
        "pidinet_safe": bpy.context.scene.controlnet.pidinet_safe,
        "pidinet_sketch": bpy.context.scene.controlnet.pidinet_sketch,
        "pidinet_scribble": bpy.context.scene.controlnet.pidinet_scribble,
        "scribble_xdog": bpy.context.scene.controlnet.scribble_xdog,
        "scribble_hed": bpy.context.scene.controlnet.scribble_hed,
        "segmentation": bpy.context.scene.controlnet.segmentation,
        "threshold": bpy.context.scene.controlnet.threshold,
        "depth_zoe": bpy.context.scene.controlnet.depth_zoe,
        "normal_bae": bpy.context.scene.controlnet.normal_bae,
        "oneformer_coco": bpy.context.scene.controlnet.oneformer_coco,
        "oneformer_ade20k": bpy.context.scene.controlnet.oneformer_ade20k,
        "lineart": bpy.context.scene.controlnet.lineart,
        "lineart_coarse": bpy.context.scene.controlnet.lineart_coarse,
        "lineart_anime": bpy.context.scene.controlnet.lineart_anime,
        "lineart_standard": bpy.context.scene.controlnet.lineart_standard,
        "shuffle": bpy.context.scene.controlnet.shuffle,
        "tile_resample": bpy.context.scene.controlnet.tile_resample,
        "invert": bpy.context.scene.controlnet.invert,
        "lineart_anime_denoise": bpy.context.scene.controlnet.lineart_anime_denoise,
        "reference_only": bpy.context.scene.controlnet.reference_only,
        "inpaint": bpy.context.scene.controlnet.inpaint
    }

    # prepare filenames
    frame_num = f"{bpy.context.scene.frame_current}".zfill(4)
    timestamp = int(time.time())
    after_output_filename_prefix = f"{timestamp}-2-after"

    # get the settings from the scene properties
    params = to_dict(bpy.context.scene.sdblender)
    img_types = []

    # get the controlnet properties
    controlnet_props = bpy.context.scene.controlnet

    # add selected items to img_types
    if controlnet_props.controlnet1:
        img_types.append(controlnet_props.controlnet1)
    if controlnet_props.controlnet2:
        img_types.append(controlnet_props.controlnet2)
    if controlnet_props.controlnet3:
        img_types.append(controlnet_props.controlnet3)

    if params.get('alwayson_scripts') is None:
        params['alwayson_scripts'] = {"controlnet": {"args": []}}

    def check_and_rename(img_type):
        before_output_filename = f"{timestamp}-1-{img_type}-before.png"
        return before_output_filename

    def prepare_cn_units(img_type, filename):
        settings = to_dict(models.get(img_type))
        print(settings)
        bpy.data.images["Render Result"].save_render(get_asset_path(filename))
        with open(get_asset_path(filename), "rb") as file:
            settings['input_image'] = base64.b64encode(file.read()).decode()
            settings['module'] = img_type
            print_dict(settings)
        return settings

    for img_type in img_types:
        if img_type != 'none':
            print('sending ', img_type, '...')
            filename = check_and_rename(img_type)
            cn_units = prepare_cn_units(img_type, filename)

            params['alwayson_scripts']['controlnet']['args'].append(cn_units)
            print_dict(params)
    # send to API
    output_file = actually_send_to_api(params, after_output_filename_prefix)

    # if we got a successful image created, load it into the scene
    if output_file:
        new_output_file = None

        # save the after image
        new_output_file = save_after_image(
            scene, after_output_filename_prefix, output_file
        )

        # if we saved a new output image, use it
        if new_output_file:
            output_file = new_output_file

        try:
            img = bpy.data.images.load(output_file, check_existing=False)
            for window in bpy.data.window_managers["WinMan"].windows:
                for area in window.screen.areas:
                    if area.type == "IMAGE_EDITOR":
                        area.spaces.active.image = img
            # NOTE: clean up temporary files heres
        except:
            print("Couldn't load the image.")
        return True  # or False depending on your conditions
    else:
        return False


def actually_send_to_api(params, filename_prefix):
    # prepare server url
    server_url = get_sd_host() + "txt2img"

    # send API request
    try:
        response = requests.post(
            server_url, json=params, headers=constants.headers, timeout=1000)
    except requests.exceptions.ConnectionError:
        print(f"The Automatic1111 server couldn't be found.")
    except requests.exceptions.MissingSchema:
        print(f"The url for your Automatic1111 server is invalid.")
    except requests.exceptions.ReadTimeout:
        print("The Automatic1111 server timed out.")

    # handle the response
    if response.status_code == 200:
        return handle_api_success(response, filename_prefix)
    else:
        return handle_api_error(response)


def handle_api_success(response, filename_prefix):
    # Attempt to parse JSON and get base64 image
    try:
        base64_img = response.json()["images"][0]
        output_file = create_temp_file(filename_prefix + "-")
        img_binary = base64.b64decode(
            base64_img.replace("data:image/png;base64,", ""))
    except:
        print("Error while parsing response, creating temp file or decoding base64 image.")
        print("Response content: ")
        print(response.content)
        return

    # Attempt to write to the file
    try:
        with open(output_file, "wb") as file:
            file.write(img_binary)
    except:
        print("Couldn't write to temp file.")
        return

    return output_file


def get_image_data(file_path):
    with open(file_path, "rb") as image_file:
        image_data = image_file.read()
        encoded_image_data = base64.b64encode(image_data).decode("utf-8")
    return encoded_image_data


def handle_api_error(response):
    if response.status_code == 404:
        try:
            response_obj = response.json()
            detail = response_obj.get("detail")
            if detail == "Not Found":
                print(
                    f"It looks like the Automatic1111 server is running, but it's not in API mode. Full server response: {json.dumps(response_obj)}")
            elif detail == "Sampler not found":
                print(
                    f"The sampler you selected is not available. Full server response: {json.dumps(response_obj)}")
            else:
                print(
                    f"An error occurred in the Automatic1111 server. Full server response: {json.dumps(response_obj)}")
        except:
            print(
                "It looks like the Automatic1111 server is running, but it's not in API mode.")
    else:
        print(response.content)
        print("An error occurred in the Automatic1111 server.")


def create_temp_file(prefix, suffix=".png"):
    return tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix).name


def save_after_image(scene, filename_prefix, img_file):
    filename = f"{filename_prefix}.png"
    full_path_and_filename = os.path.join(
        os.path.abspath(bpy.path.abspath(
            get_preferences().output_folder)), filename
    )
    try:
        copy_file(img_file, full_path_and_filename)
        return full_path_and_filename
    except:
        print(
            f"Couldn't save 'after' image to {bpy.path.abspath(full_path_and_filename)}"
        )


def get_absolute_path(path):
    return os.path.abspath(bpy.path.abspath(path))


def get_asset_path(filename):
    asset = os.path.join(get_absolute_path(
        get_preferences().output_folder), filename)
    return asset


def get_output_width(scene):
    return round(scene.render.resolution_x * scene.render.resolution_percentage / 100)


def get_output_height(scene):
    return round(scene.render.resolution_y * scene.render.resolution_percentage / 100)


def copy_file(src, dest):
    shutil.copy2(src, dest)


def get_width(self):
    return get_output_width(bpy.context.scene)


def get_height(self):
    return get_output_height(bpy.context.scene)


def reset_render_complete_handler():
    handler_list = bpy.app.handlers.render_complete
    if render_complete_handler in handler_list:
        handler_list.remove(render_complete_handler)


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

        bpy.data.images['Render Result'].save_render(get_asset_path('interrogate.png'))
        image_data = get_image_data(get_asset_path('interrogate.png'))
        caption = request_caption(image_data, interrogator)

        if caption:
            context.scene.sdblender.prompt = caption
        else:
            self.report({'ERROR'}, "Failed to get caption from the API")

        return {'FINISHED'}


def get_sampler_items(self, context):
    samplers_k_diffusion = [
        ('Euler a', 'sample_euler_ancestral', [
         'k_euler_a', 'k_euler_ancestral'], {}),
        ('Euler', 'sample_euler', ['k_euler'], {}),
        ('LMS', 'sample_lms', ['k_lms'], {}),
        ('Heun', 'sample_heun', ['k_heun'], {}),
        ('DPM2', 'sample_dpm_2', ['k_dpm_2'], {
         'discard_next_to_last_sigma': True}),
        ('DPM2 a', 'sample_dpm_2_ancestral', [
         'k_dpm_2_a'], {'discard_next_to_last_sigma': True}),
        ('DPM++ 2S a', 'sample_dpmpp_2s_ancestral', ['k_dpmpp_2s_a'], {}),
        ('DPM++ 2M', 'sample_dpmpp_2m', ['k_dpmpp_2m'], {}),
        ('DPM++ SDE', 'sample_dpmpp_sde', ['k_dpmpp_sde'], {}),
        ('DPM fast', 'sample_dpm_fast', ['k_dpm_fast'], {}),
        ('DPM adaptive', 'sample_dpm_adaptive', ['k_dpm_ad'], {}),
        ('LMS Karras', 'sample_lms', ['k_lms_ka'], {'scheduler': 'karras'}),
        ('DPM2 Karras', 'sample_dpm_2', ['k_dpm_2_ka'], {
         'scheduler': 'karras', 'discard_next_to_last_sigma': True}),
        ('DPM2 a Karras', 'sample_dpm_2_ancestral', ['k_dpm_2_a_ka'], {
         'scheduler': 'karras', 'discard_next_to_last_sigma': True}),
        ('DPM++ 2S a Karras', 'sample_dpmpp_2s_ancestral',
         ['k_dpmpp_2s_a_ka'], {'scheduler': 'karras'}),
        ('DPM++ 2M Karras', 'sample_dpmpp_2m',
         ['k_dpmpp_2m_ka'], {'scheduler': 'karras'}),
        ('DPM++ SDE Karras', 'sample_dpmpp_sde',
         ['k_dpmpp_sde_ka'], {'scheduler': 'karras'}),
    ]
    items = [(s[0], s[0], "") for s in samplers_k_diffusion]
    return items


def get_modules(self, context):
    cn_preprocessor_modules = [
        ("none", "None", ""),
        ("canny", "Canny", ""),
        ("depth", "Depth", ""),
        ("depth_leres", "Depth LeRes", ""),
        ("depth_leresplusplus", "Depth LeRes++", ""),
        ("hed", "Hed", ""),
        ("hed_safe", "Hed Safe", ""),
        ("mediapipe_face", "MediaPipe Face", ""),
        ("mlsd", "Mlsd", ""),
        ("normal_map", "Normal Map", ""),
        ("openpose", "OpenPose", ""),
        ("openpose_hand", "OpenPose Hand", ""),
        ("openpose_face", "OpenPose Face", ""),
        ("openpose_faceonly", "OpenPose Face Only", ""),
        ("openpose_full", "OpenPose Full", ""),
        ("clip_vision", "Clip Vision", ""),
        ("color", "Color", ""),
        ("pidinet", "Pidinet", ""),
        ("pidinet_safe", "Pidinet Safe", ""),
        ("pidinet_sketch", "Pidinet Sketch", ""),
        ("pidinet_scribble", "Pidinet Scribble", ""),
        ("scribble_xdog", "Scribble Xdog", ""),
        ("scribble_hed", "Scribble Hed", ""),
        ("segmentation", "Segmentation", ""),
        ("threshold", "Threshold", ""),
        ("depth_zoe", "Depth Zoe", ""),
        ("normal_bae", "Normal Bae", ""),
        ("oneformer_coco", "Oneformer Coco", ""),
        ("oneformer_ade20k", "Oneformer Ade20k", ""),
        ("lineart", "Lineart", ""),
        ("lineart_coarse", "Lineart Coarse", ""),
        ("lineart_anime", "Lineart Anime", ""),
        ("lineart_standard", "Lineart Standard", ""),
        ("shuffle", "Shuffle", ""),
        ("tile_resample", "Tile Resample", ""),
        ("invert", "Invert", ""),
        ("lineart_anime_denoise", "Lineart Anime Denoise", ""),
        ("reference_only", "Reference Only", ""),
        ("inpaint", "Inpaint", "")
    ]
    return cn_preprocessor_modules


class OverrideSettingsItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    value: bpy.props.IntProperty(name="Value")


class SDBLENDER_Properties(bpy.types.PropertyGroup):
    prompt: bpy.props.StringProperty(name="Prompt")
    negative_prompt: bpy.props.StringProperty(
        name="Negative Prompt", default="lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry")
    width: bpy.props.IntProperty(name="Width", get=get_width)
    height: bpy.props.IntProperty(name="Height", get=get_height)
    sampler_name: bpy.props.EnumProperty(
        name="Sampler",
        description="Choose a sampler",
        items=get_sampler_items
    )
    sampler_index: bpy.props.IntProperty(name="Sampler Index", default=0)
    batch_size: bpy.props.IntProperty(name="Batch Size", default=1)
    n_iter: bpy.props.IntProperty(name="N Iter", default=1)
    steps: bpy.props.IntProperty(name="Steps", default=20)
    cfg_scale: bpy.props.IntProperty(name="Cfg Scale", default=7)
    seed: bpy.props.IntProperty(name="Seed", default=-1)
    subseed: bpy.props.IntProperty(name="Subseed")
    subseed_strength: bpy.props.FloatProperty(name="Subseed Strength")
    restore_faces: bpy.props.BoolProperty(name="Restore Faces", default=False)
    enable_hr: bpy.props.BoolProperty(name="Enable HR", default=True)
    hr_scale: bpy.props.FloatProperty(name="HR Scale", default=2.0)
    hr_upscaler: bpy.props.EnumProperty(
        name="Upscalers",
        description="Choose an upscaler",
        items=[('None', 'None', ''), ('Lanczos', 'Lanczos', ''), ('Nearest', 'Nearest', ''), ('ESRGAN_4x', 'ESRGAN_4x', ''), ('LDSR', 'LDSR', ''), ('R-ESRGAN 4x+',
                                                                                                                                                    'R-ESRGAN 4x+', ''), ('R-ESRGAN 4x+ Anime6B', 'R-ESRGAN 4x+ Anime6B', ''), ('ScuNET', 'ScuNET', ''), ('ScuNET PSNR', 'ScuNET PSNR', ''), ('SwinIR_4x', 'SwinIR_4x', '')]
    )
    denoising_strength: bpy.props.FloatProperty(
        name="Denoising Strength", default=0.25)
    hr_second_pass_steps: bpy.props.IntProperty(name="HR Second Pass Steps")
    hr_resize_x: bpy.props.IntProperty(name="HR Resize X", min=0, max=2048)
    hr_resize_y: bpy.props.IntProperty(name="HR Resize Y", min=0, max=2048)
    firstphase_width: bpy.props.IntProperty(name="Firstphase Width")
    firstphase_height: bpy.props.IntProperty(name="Firstphase Height")
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
    bl_idname = 'sd_blender'

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
        name="Control Net 1",
        items=get_modules
    )
    controlnet2: bpy.props.EnumProperty(
        name="Control Net 2",
        items=get_modules
    )
    controlnet3: bpy.props.EnumProperty(
        name="Control Net 3",
        items=get_modules
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

        layout.prop(sdblender, "prompt")
        layout.prop(sdblender, "negative_prompt")
        # layout.prop(sdblender, "width")
        # layout.prop(sdblender, "height")
        # layout.prop(sdblender, "sampler_index")
        layout.prop(sdblender, "sampler_name")
        layout.prop(sdblender, "batch_size")
        # layout.prop(sdblender, "n_iter")
        layout.prop(sdblender, "steps")
        layout.prop(sdblender, "cfg_scale")
        layout.prop(sdblender, "seed")
        layout.prop(sdblender, "subseed")
        layout.prop(sdblender, "subseed_strength")
        layout.prop(sdblender, "restore_faces")
        layout.prop(sdblender, "enable_hr")
        layout.prop(sdblender, "hr_scale")
        layout.prop(sdblender, "hr_upscaler")
        layout.prop(sdblender, "denoising_strength")
        layout.prop(sdblender, "hr_second_pass_steps")
        layout.prop(sdblender, "hr_resize_x")
        layout.prop(sdblender, "hr_resize_y")
        layout.prop(sdblender, "firstphase_width")
        layout.prop(sdblender, "firstphase_height")
        layout.prop(sdblender, "override_settings_restore_afterwards")


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


class SDBLENDER_Preferences_Panel(bpy.types.Panel):
    bl_label = "Preferences"
    bl_idname = "SDBLENDER_PT_preferences"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SD Blender"

    def draw(self, context):
        layout = self.layout

        addon_prefs = context.preferences.addons['sd_blender'].preferences

        layout.label(text="Address: " + addon_prefs.address)
        layout.label(text="Port: " + str(addon_prefs.port))
        layout.label(text="Output Folder: " + addon_prefs.output_folder)


class SDBLENDER_Interrogate_Panel(bpy.types.Panel):
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


def register():
    classes = utils.create_properties_group(
        constants.controlnet_models, constants.module_details)
    for cls in classes:
        pointer = bpy.props.PointerProperty(type=cls)
        setattr(SDBLENDER_CONTROLNETProperties,
                utils.extract_model_name(cls.__name__), pointer)

    bpy.types.Scene.sdblender = bpy.props.PointerProperty(
        type=SDBLENDER_Properties)  # Point to the property group
    bpy.types.Scene.controlnet = bpy.props.PointerProperty(
        type=SDBLENDER_CONTROLNETProperties)
    bpy.types.Scene.override_settings = bpy.props.CollectionProperty(
        type=OverrideSettingsItem)
    bpy.types.Scene.interrogators = bpy.props.PointerProperty(
        type=SDBLENDER_Interrogators)

    bpy.app.handlers.render_complete.clear()
    bpy.app.handlers.render_complete.append(render_complete_handler)


def unregister():
    del bpy.types.Scene.sdblender
    del bpy.types.Scene.override_settings
    del bpy.types.Scene.controlnet

    reset_render_complete_handler()
