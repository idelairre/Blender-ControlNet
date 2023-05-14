from bpy.app.handlers import persistent
import bpy
import os
import shutil
import time
import tempfile
import base64
import requests
import json
import cv2

import bpy
import cv2
import os

headers = {
    "User-Agent": "Blender/" + bpy.app.version_string,
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
}

def get_sd_host():
    return "http://" + get_preferences().address + ':' + str(get_preferences().port) + "/sdapi/v1/"

# Access addon preferences
def get_preferences():
    preferences = bpy.context.preferences.addons['sd_blender'].preferences
    return preferences

def generate_openpose_map(render):
    # Set the path for the temporary image file
    path_to_tmp_image = bpy.path.abspath("//tmp.png")
    model_folder = get_preferences().openpose_models_folder

    # Set up OpenPose
    params = {"model_folder": model_folder, "image_path": bpy.data.images["Render Result"].filepath_raw}
    op_wrapper = op.WrapperPython()
    op_wrapper.configure(params)
    op_wrapper.start()

    # Load the image and process it with OpenPose
    datum = op.Datum()
    image_to_process = cv2.imread(params["image_path"])
    datum.cvInputData = image_to_process
    op_wrapper.emplaceAndPop([datum])

    # Save the skeleton map to a specific file
    bone_map_filename = f"bone{str(bpy.context.scene.frame_current).zfill(4)}.png"
    bone_map_filepath = bpy.path.abspath("//" + bone_map_filename)
    cv2.imwrite(bone_map_filepath, datum.cvOutputData)

    # Delete the temporary image file
    if os.path.exists(path_to_tmp_image):
        os.remove(path_to_tmp_image)

def create_compositor_nodes(scene):
    scene.use_nodes = True
    nodes = scene.node_tree.nodes
    links = scene.node_tree.links

    # clear all nodes to start clean
    for node in nodes:
        nodes.remove(node)

    # create input render layer node
    render_layer_node = nodes.new('CompositorNodeRLayers')
    
    for scene in bpy.data.scenes:
        for view_layer in scene.view_layers:
            view_layer.use_pass_z = True

    # create output file node
    output_node = nodes.new('CompositorNodeOutputFile')
    output_node.base_path = get_preferences().output_folder
    output_node.file_slots.new("depth")
    output_node.file_slots.new("seg")

    # create normalize node
    normalize_node = nodes.new('CompositorNodeNormalize')

    # create mix node
    mix_node = nodes.new('CompositorNodeMixRGB')
    mix_node.blend_type = 'MIX'
    mix_node.inputs[1].default_value = (0, 0, 0, 1)  # color1 set to black
    mix_node.inputs[2].default_value = (1, 1, 1, 1)  # color2 set to white

    # link nodes together
    links.new(render_layer_node.outputs[0], output_node.inputs['seg'])
    links.new(render_layer_node.outputs['Depth'], normalize_node.inputs[0])
    links.new(normalize_node.outputs[0], mix_node.inputs[0])
    links.new(mix_node.outputs[0], output_node.inputs['depth'])
    
def check_compositor_and_create_nodes(context):
    scene = context.scene
    if not scene.use_nodes:
        create_compositor_nodes(scene)
        
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


def send_to_api(scene):
    # prepare filenames
    frame_num = f"{bpy.context.scene.frame_current}".zfill(4)
    timestamp = int(time.time())
    after_output_filename_prefix = f"{timestamp}-2-after"

    # get the settings from the scene properties
    params = to_dict(bpy.context.scene.sdblender)
    img_types = ["canny", "depth", "bone", "seg"]
    
    if params.get('alwayson_scripts') is None:
        params['alwayson_scripts'] = { "controlnet": {"args": []} }
    
    def check_and_rename(img_type):
        comp_output_filename = f"{img_type}{frame_num}.png"
        before_output_filename = f"{timestamp}-1-{img_type}-before.png"
        if img_type != "bone" and img_type == "seg":
            if not os.path.exists(get_asset_path(comp_output_filename)):
                print(f"Couldn't find the {img_type} image at {get_asset_path(comp_output_filename)}.")
            else:
                os.rename(
                    get_asset_path(comp_output_filename),
                    get_asset_path(before_output_filename)
                )
        return before_output_filename

    def prepare_cn_units(img_type, filename):
        settings = to_dict(bpy.context.scene.controlnet).get(img_type)
        # if img_type == "depth" or img_type == "seg":
        #     with open(get_asset_path(filename), "rb") as file:
        #         settings["input_image"] = base64.b64encode(file.read()).decode()
        # else:
        # save the render to a file to use as the input image
        bpy.data.images["Render Result"].save_render(get_asset_path(filename))
        with open(get_asset_path(filename), "rb") as file:
            settings["input_image"] = base64.b64encode(file.read()).decode()
            settings["module"] = "canny" if img_type == "canny" else "openpose_full"
        return settings
    
    for img_type in img_types:
        if to_dict(bpy.context.scene.controlnet).get(f"is_send_{img_type}"):
            print('sending ', img_type, '...')
            filename = check_and_rename(img_type)
            cn_units = prepare_cn_units(img_type, filename)
                
            params['alwayson_scripts']['controlnet']['args'].append(cn_units)
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
        response = requests.post(server_url, json=params, headers=headers, timeout=1000)
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
        img_binary = base64.b64decode(base64_img.replace("data:image/png;base64,", ""))
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

def handle_api_error(response):
    if response.status_code == 404:
        try:
            response_obj = response.json()
            detail = response_obj.get("detail")
            if detail == "Not Found":
                print(f"It looks like the Automatic1111 server is running, but it's not in API mode. Full server response: {json.dumps(response_obj)}")
            elif detail == "Sampler not found":
                print(f"The sampler you selected is not available. Full server response: {json.dumps(response_obj)}")
            else:
                print(f"An error occurred in the Automatic1111 server. Full server response: {json.dumps(response_obj)}")
        except:
            print("It looks like the Automatic1111 server is running, but it's not in API mode.")
    else:
        print(response.content)
        print("An error occurred in the Automatic1111 server.")

def create_temp_file(prefix, suffix=".png"):
    return tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix).name


def save_after_image(scene, filename_prefix, img_file):
    filename = f"{filename_prefix}.png"
    full_path_and_filename = os.path.join(
        os.path.abspath(bpy.path.abspath(get_preferences().output_folder)), filename
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
    asset = os.path.join(get_absolute_path(get_preferences().output_folder), filename)
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

bpy.app.handlers.render_complete.clear()
bpy.app.handlers.render_complete.append(render_complete_handler)

class SDBLENDER_Properties_Canny(bpy.types.PropertyGroup):
    model: bpy.props.StringProperty(name="Model", default="control_v11p_sd15_canny [d14c016b]")
    # mask: bpy.props.StringProperty(name="Mask", default="")
    weight: bpy.props.FloatProperty(name="Weight", default=1.2)
    resize_mode: bpy.props.StringProperty(name="Resize Mode", default="Scale to Fit (Inner Fit)")
    lowvram: bpy.props.BoolProperty(name="Low VRAM", default=False)
    processor_res: bpy.props.IntProperty(name="Processor Resolution", default=64)
    threshold_a: bpy.props.IntProperty(name="Threshold A", default=64)
    threshold_b: bpy.props.IntProperty(name="Threshold B", default=64)
    guidance: bpy.props.IntProperty(name="Guidance", default=1)
    guidance_start: bpy.props.FloatProperty(name="Guidance Start", default=0.19)
    guidance_end: bpy.props.FloatProperty(name="Guidance End", default=1)
        
class SDBLENDER_Properties_Depth(bpy.types.PropertyGroup):
    model: bpy.props.StringProperty(name="Model", default="control_v11f1p_sd15_depth [cfd03158]")
    # mask: bpy.props.StringProperty(name="Mask", default="")
    weight: bpy.props.FloatProperty(name="Weight", default=1.2)
    resize_mode: bpy.props.StringProperty(name="Resize Mode", default="Scale to Fit (Inner Fit)")
    lowvram: bpy.props.BoolProperty(name="Low VRAM", default=False)
    processor_res: bpy.props.IntProperty(name="Processor Resolution", default=64)
    threshold_a: bpy.props.IntProperty(name="Threshold A", default=64)
    threshold_b: bpy.props.IntProperty(name="Threshold B", default=64)
    guidance: bpy.props.IntProperty(name="Guidance", default=1)
    guidance_start: bpy.props.FloatProperty(name="Guidance Start", default=0.19)
    guidance_end: bpy.props.FloatProperty(name="Guidance End", default=1)
    
class SDBLENDER_Properties_Bone(bpy.types.PropertyGroup):
    model: bpy.props.StringProperty(name="Model", default="control_v11p_sd15_openpose [cab727d4]")
    # mask: bpy.props.StringProperty(name="Mask", default="")
    weight: bpy.props.FloatProperty(name="Weight", default=1.2)
    resize_mode: bpy.props.StringProperty(name="Resize Mode", default="Scale to Fit (Inner Fit)")
    lowvram: bpy.props.BoolProperty(name="Low VRAM", default=False)
    processor_res: bpy.props.IntProperty(name="Processor Resolution", default=512)
    guidance: bpy.props.IntProperty(name="Guidance", default=1)
    guidance_start: bpy.props.FloatProperty(name="Guidance Start", default=0.00)
    guidance_end: bpy.props.FloatProperty(name="Guidance End", default=1)
    
class SDBLENDER_Properties_Segmentation(bpy.types.PropertyGroup):
    model: bpy.props.StringProperty(name="Model", default="control_v11p_sd15_seg [e1f51eb9]")
    # mask: bpy.props.StringProperty(name="Mask", default="")
    weight: bpy.props.FloatProperty(name="Weight", default=1.2)
    resize_mode: bpy.props.StringProperty(name="Resize Mode", default="Scale to Fit (Inner Fit)")
    lowvram: bpy.props.BoolProperty(name="Low VRAM", default=False)
    processor_res: bpy.props.IntProperty(name="Processor Resolution", default=64)
    threshold_a: bpy.props.IntProperty(name="Threshold A", default=64)
    threshold_b: bpy.props.IntProperty(name="Threshold B", default=64)
    guidance: bpy.props.IntProperty(name="Guidance", default=1)
    guidance_start: bpy.props.FloatProperty(name="Guidance Start", default=0.19)
    guidance_end: bpy.props.FloatProperty(name="Guidance End", default=1)

def get_sampler_items(self, context):
    samplers_k_diffusion = [
        ('Euler a', 'sample_euler_ancestral', ['k_euler_a', 'k_euler_ancestral'], {}),
        ('Euler', 'sample_euler', ['k_euler'], {}),
        ('LMS', 'sample_lms', ['k_lms'], {}),
        ('Heun', 'sample_heun', ['k_heun'], {}),
        ('DPM2', 'sample_dpm_2', ['k_dpm_2'], {'discard_next_to_last_sigma': True}),
        ('DPM2 a', 'sample_dpm_2_ancestral', ['k_dpm_2_a'], {'discard_next_to_last_sigma': True}),
        ('DPM++ 2S a', 'sample_dpmpp_2s_ancestral', ['k_dpmpp_2s_a'], {}),
        ('DPM++ 2M', 'sample_dpmpp_2m', ['k_dpmpp_2m'], {}),
        ('DPM++ SDE', 'sample_dpmpp_sde', ['k_dpmpp_sde'], {}),
        ('DPM fast', 'sample_dpm_fast', ['k_dpm_fast'], {}),
        ('DPM adaptive', 'sample_dpm_adaptive', ['k_dpm_ad'], {}),
        ('LMS Karras', 'sample_lms', ['k_lms_ka'], {'scheduler': 'karras'}),
        ('DPM2 Karras', 'sample_dpm_2', ['k_dpm_2_ka'], {'scheduler': 'karras', 'discard_next_to_last_sigma': True}),
        ('DPM2 a Karras', 'sample_dpm_2_ancestral', ['k_dpm_2_a_ka'], {'scheduler': 'karras', 'discard_next_to_last_sigma': True}),
        ('DPM++ 2S a Karras', 'sample_dpmpp_2s_ancestral', ['k_dpmpp_2s_a_ka'], {'scheduler': 'karras'}),
        ('DPM++ 2M Karras', 'sample_dpmpp_2m', ['k_dpmpp_2m_ka'], {'scheduler': 'karras'}),
        ('DPM++ SDE Karras', 'sample_dpmpp_sde', ['k_dpmpp_sde_ka'], {'scheduler': 'karras'}),
    ]
    items = [(s[0], s[0], "") for s in samplers_k_diffusion]
    return items
    
class OverrideSettingsItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    value: bpy.props.IntProperty(name="Value")
    
class SDBLENDER_Properties(bpy.types.PropertyGroup):
    prompt: bpy.props.StringProperty(name="Prompt")
    negative_prompt: bpy.props.StringProperty(name="Negative Prompt", default="lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry")
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
        items=[('None', 'None', ''), ('Lanczos', 'Lanczos', ''), ('Nearest', 'Nearest', ''), ('ESRGAN_4x', 'ESRGAN_4x', ''), ('LDSR', 'LDSR', ''), ('R-ESRGAN 4x+', 'R-ESRGAN 4x+', ''), ('R-ESRGAN 4x+ Anime6B', 'R-ESRGAN 4x+ Anime6B', ''), ('ScuNET', 'ScuNET', ''), ('ScuNET PSNR', 'ScuNET PSNR', ''), ('SwinIR_4x', 'SwinIR_4x', '')]
    )
    denoising_strength: bpy.props.FloatProperty(name="Denoising Strength", default=0.25)
    hr_second_pass_steps: bpy.props.IntProperty(name="HR Second Pass Steps")
    hr_resize_x: bpy.props.IntProperty(name="HR Resize X", min=0, max=2048)
    hr_resize_y: bpy.props.IntProperty(name="HR Resize Y", min=0, max=2048)
    firstphase_width: bpy.props.IntProperty(name="Firstphase Width")
    firstphase_height: bpy.props.IntProperty(name="Firstphase Height")
    override_settings_restore_afterwards: bpy.props.BoolProperty(name="Override Settings Restore Afterwards")
    override_settings: bpy.props.CollectionProperty(type=OverrideSettingsItem)
    
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

    openpose_models_folder: bpy.props.StringProperty(
        name="OpenPose Models Directory",
        description="Select the directory containing OpenPose models",
        subtype='DIR_PATH',
        default=os.path.normpath("C:\\Users\\Owner\\Documents\\GitHub\\openpose\\models\\")
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Blender Stable Diffusion Preferences")
        layout.prop(self, "address")
        layout.prop(self, "port")
        layout.prop(self, "output_folder")
        layout.prop(self, "openpose_models_folder")  # add this line


class SDBLENDER_CONTROLNETProperties(bpy.types.PropertyGroup):
    is_using_ai: bpy.props.BoolProperty(name="Use AI", default=True)
    is_send_canny: bpy.props.BoolProperty(name="Send Canny", default=False)
    is_send_depth: bpy.props.BoolProperty(name="Send Depth", default=True)
    is_send_bone: bpy.props.BoolProperty(name="Send Bone", default=False)
    is_send_seg: bpy.props.BoolProperty(name="Send Segmentation", default=True)
    dropdown: bpy.props.EnumProperty(
        name="AI Options",
        items=[
            ('CANNY', "Canny", ""),
            ('DEPTH', "Depth", ""),
            ('BONE', "Bone", ""),
            ('SEG', "Segmentation", "")
        ],
        default='CANNY'
    )
    canny: bpy.props.PointerProperty(type=SDBLENDER_Properties_Canny)
    depth: bpy.props.PointerProperty(type=SDBLENDER_Properties_Depth)
    bone: bpy.props.PointerProperty(type=SDBLENDER_Properties_Bone)
    seg: bpy.props.PointerProperty(type=SDBLENDER_Properties_Segmentation)

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
        layout.prop(sdblender, "width")
        layout.prop(sdblender, "height")
        layout.prop(sdblender, "sampler_index")
        layout.prop(sdblender, "sampler_name")
        layout.prop(sdblender, "batch_size")
        layout.prop(sdblender, "n_iter")
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
    bl_category = 'SD Blender'  # Change to your preferred category

    def draw(self, context):
        layout = self.layout

        props = context.scene.controlnet

        layout.prop(props, "is_using_ai")
        layout.prop(props, "is_send_canny")
        layout.prop(props, "is_send_depth")
        layout.prop(props, "is_send_bone")
        layout.prop(props, "is_send_seg")
        layout.prop(props, "dropdown")
        
        dropdown_item = getattr(props, props.dropdown.lower())

        for attr_name in dir(dropdown_item):
            if attr_name.startswith("__") or 'bl_rna' in attr_name or 'rna_type' in attr_name or 'name' in attr_name:
                continue
            layout.prop(dropdown_item, attr_name)

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
        layout.operator("scene.setup_compositor_nodes")
        
class SDBLENDER_SetupCompositor_Operator(bpy.types.Operator):
    bl_idname = "scene.setup_compositor_nodes"
    bl_label = "Setup Compositor Nodes"

    def execute(self, context):
        check_compositor_and_create_nodes(context)
        return {'FINISHED'}
    
class SDBLENDER_RenderFlagProperty(bpy.types.PropertyGroup):
    flag: bpy.props.BoolProperty(name="Render Flag", default=False)

def register():
    bpy.types.Scene.sdblender = bpy.props.PointerProperty(type=SDBLENDER_Properties)  # Point to the property group
    bpy.types.Scene.controlnet = bpy.props.PointerProperty(type=SDBLENDER_CONTROLNETProperties)
    bpy.types.Scene.override_settings = bpy.props.CollectionProperty(type=OverrideSettingsItem)
    bpy.types.Scene.render_flag = bpy.props.PointerProperty(type=SDBLENDER_RenderFlagProperty)
    
def unregister():
    del bpy.types.Scene.sdblender
    del bpy.types.Scene.override_settings
    del bpy.types.Scene.controlnet
    del bpy.types.Scene.render_flag