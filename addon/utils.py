import bpy
import re

from . import constants


def transform_to_enum(model_list):
    return [(model, model, "") for model in model_list]


def create_properties_group(controlnet_models, module_details):
    classes = []

    for model in controlnet_models:
        if 'depth_leres++' == model:
            model = 'depth_leres_plusplus'
            
        attrs = {
            "__annotations__": {
                "model": bpy.props.EnumProperty(
                    name="Model",
                    items=transform_to_enum(constants.model_list),
                    default=constants.model_list[0] if constants.model_list else None,
                ),
                "weight": bpy.props.FloatProperty(name="Weight", default=1.2),
                "resize_mode": bpy.props.StringProperty(name="Resize Mode", default="Crop and Resize"),
                "lowvram": bpy.props.BoolProperty(name="Low VRAM", default=False),
                "processor_res": bpy.props.IntProperty(name="Processor Resolution", default=512),
                "guidance": bpy.props.IntProperty(name="Guidance", default=1),
                "guidance_start": bpy.props.FloatProperty(name="Guidance Start", default=0.00),
                "guidance_end": bpy.props.FloatProperty(name="Guidance End", default=1),

            },
        }

        if model in module_details:
            for slider in module_details[model]['sliders']:
                # convert the property name to an identifier
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
