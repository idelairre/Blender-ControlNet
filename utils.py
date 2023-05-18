import base64
import bpy
import re
import json
import shutil
import os
import tempfile
import sys
from types import SimpleNamespace


def transform_to_enum(model_list):
    enum_list = []
    for model in model_list:
        if isinstance(model, tuple):
            enum_list.append(model)
        else:
            display_name = model.replace('_', ' ').title()
            if model == 'depth_leres++':
                display_name = "Depth Leres++"
                enum_list.append(('depth_leres_plusplus', display_name, ""))
            else:
                enum_list.append((model, display_name, ""))
    return enum_list


def create_properties_group(controlnet_modules, models, module_details):
    classes = []

    for model in controlnet_modules:
        if 'depth_leres++' == model:
            model = 'depth_leres_plusplus'
        if 'none' == model:
            continue

        attrs = {
            "__annotations__": {
                "model": bpy.props.EnumProperty(
                    name="Model",
                    items=transform_to_enum(models),
                    default=transform_to_enum(
                        models)[0][0] if models else 'none',
                ),
                "weight": bpy.props.FloatProperty(name="Weight", default=1.2),
                "resize_mode": bpy.props.StringProperty(name="Resize Mode", default="Crop and Resize"),
                "lowvram": bpy.props.BoolProperty(name="Low VRAM", default=False),
                # "processor_res": bpy.props.IntProperty(name="Processor Resolution", default=512),
                "guidance": bpy.props.IntProperty(name="Guidance", default=1),
                "guidance_start": bpy.props.FloatProperty(name="Guidance Start", default=0.00),
                "guidance_end": bpy.props.FloatProperty(name="Guidance End", default=1),

            },
        }

        if model in module_details:
            for slider in module_details[model]['sliders']:
                # convert the property name to an identifier
                if slider and slider.get('name'):
                    prop_name = slider['name'].replace(' ', '_').lower()

                    if "step" in slider and slider["step"] < 1:
                        attrs["__annotations__"][prop_name] = bpy.props.FloatProperty(
                            name=slider['name'],
                            default=slider['value'],
                            min=slider['min'],
                            max=slider['max'],
                            step=slider['step']
                        )
                    else:
                        attrs["__annotations__"][prop_name] = bpy.props.IntProperty(
                            name=slider['name'],
                            default=int(slider['value']),
                            min=int(slider['min']),
                            max=int(slider['max']),
                        )

        # Create the class and add it to the dictionary with its name as the key
        cls_name = "SDBLENDER_Properties_" + model
        cls = type(cls_name, (bpy.types.PropertyGroup,), attrs)
        bpy.utils.register_class(cls)
        classes.append(cls)

    return classes


def extract_model_name(class_name):
    # Remove the prefix and convert to lowercase
    model_name = re.sub(r'^SDBLENDER_Properties_', '',
                        class_name, flags=re.IGNORECASE)
    return model_name.lower()


def get_sd_host():
    return "http://" + get_preferences().address + ':' + str(get_preferences().port) + "/sdapi/v1/"


def get_controlnet_host():
    return get_sd_host().replace("/sdapi/v1/", "") + "/controlnet/"


def get_preferences():
    try:
        preferences = bpy.context.preferences.addons["Stable Diffusion ControlNet"].preferences

        if preferences:
            return preferences
    except KeyError:
        # we have a problem
        preferences = {"address": "localhost",
                       "port": 7000, "output_folder": "C://tmp"}
        p = SimpleNamespace(**preferences)
        return p


def to_dict(obj):
    if isinstance(obj, bpy.types.PropertyGroup):
        result = {}
        for prop in obj.__annotations__.keys():
            attr = getattr(obj, prop)
            if isinstance(attr, bpy.types.PropertyGroup):
                result[prop] = to_dict(attr)
            elif isinstance(attr, (list, tuple)):
                result[prop] = [to_dict(i) for i in attr]
            elif isinstance(attr, bpy.
                            types.bpy_prop_collection):
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


def get_image_data(file_path):
    with open(file_path, "rb") as image_file:
        image_data = image_file.read()
        encoded_image_data = base64.b64encode(image_data).decode("utf-8")
    return encoded_image_data


def create_temp_file(prefix, suffix=".png"):
    return tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix).name


def safe_base64_decode(base64_string):
    padding_needed = 4 - len(base64_string) % 4
    if padding_needed != 4:
        base64_string += '=' * padding_needed
    return base64.b64decode(base64_string)


def node_to_dict(self):
    node_dict = {}

    # Iterate over all input sockets
    for socket in self.inputs:
        if socket.is_linked:
            # If the socket is linked, we only store the fact that it is linked
            # We don't store the data it's linked to, because that could create a circular dependency
            node_dict[socket.name] = "linked"
        else:
            # If the socket is not linked, we can store its default value
            node_dict[socket.name] = socket.default_value

    # Iterate over all properties of the node
    for prop_name in dir(self):
        if prop_name.startswith('__') or prop_name in ('rna_type', 'bl_rna', 'inputs', 'outputs'):
            continue

        # Get the property value
        prop_value = getattr(self, prop_name)

        # Check if the property is a socket
        if isinstance(prop_value, bpy.types.NodeSocket):
            continue

        # Add the property to the dictionary
        node_dict[prop_name] = prop_value

    return node_dict


def img_to_base64(img):
    width, height = img.size
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    temp_file_name = temp_file.name
    temp_file.close()

    # Save the image to the temporary file
    img.save_render(temp_file_name)

    # Read the temporary file and encode it as base64
    with open(temp_file_name, "rb") as file:
        image_data = file.read()
    os.remove(temp_file_name)

    return base64.b64encode(image_data).decode('utf-8')
