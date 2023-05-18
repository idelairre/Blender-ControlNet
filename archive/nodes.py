import bpy
import base64
import json

from ..api import send_to_api2, get_sampler_items, get_upscalers, get_module_list
from ..utils import get_width, get_height, transform_to_enum, node_to_dict

import logging

logger = logging.getLogger(__name__)

samplers = get_sampler_items()
upscalers = get_upscalers()
modules = transform_to_enum(get_module_list())


class SDBLENDER_SocketString(bpy.types.NodeSocket):
    bl_idname = 'SDBLENDER_SocketString'
    bl_label = "String Socket"

    # Define a property for the socket value
    string_value: bpy.props.StringProperty()

    # Override draw_color to define its color in the node editor
    def draw_color(self, context, node):
        return (1.0, 0.4, 0.216, 0.5)

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=text)
        else:
            layout.prop(self, "string_value", text=text)


class ControlNetTypeNode(bpy.types.Node):
    bl_idname = 'ControlNetNodeType'
    bl_label = 'ControlNet Node'
    bl_icon = 'URL'

    controlnet: bpy.props.EnumProperty(
        name="Control Net",
        items=modules
    )

    def init(self, context):
        self.inputs.new('NodeSocketColor', 'Input Images')
        self.outputs.new('SDBLENDER_SocketString', 'Output')

    def draw_buttons(self, context, layout):
        props = context.scene.controlnet

        layout.prop(props, "controlnet1")

        def render_options(controlnet_name):
            controlnet_value = getattr(props, controlnet_name)
            if controlnet_value.lower() != "none":
                layout.label(text="ControlNet Options:")
                controlnet_item = getattr(props, controlnet_value.lower())

                for attr_name in dir(controlnet_item):
                    if attr_name.startswith("__") or 'bl_rna' in attr_name or 'rna_type' in attr_name or 'name' in attr_name:
                        continue
                    layout.prop(controlnet_item, attr_name)

        render_options('controlnet1')

    def update_sockets(self):
        # Convert properties to dict
        props_dict = {k: v for k, v in self.__dict__.items()
                      if not k.startswith("_")}

        # If the input is an image, convert it to base64
        if self.inputs['Input Images'].is_linked:
            input_image = self.inputs['Input Images'].links[0].from_node.image
            img_path = bpy.path.abspath(input_image.filepath)
            with open(img_path, "rb") as img_file:
                encoded_string = base64.b64encode(
                    img_file.read()).decode('utf-8')
            props_dict['Input Images'] = encoded_string

        # Convert dict to string
        props_str = json.dumps(props_dict)

        logger.info('props dict: %s', props_dict)
        logger.info('props str: %s', props_str)

        # Set the value of the custom string output
        self.outputs['Output'].string_value = props_str


class SDBlenderNodeTypeNode(bpy.types.Node):
    bl_idname = 'StableDiffusionNodeType'
    bl_label = 'Stable Diffusion Node'
    bl_icon = 'URL'

    prompt: bpy.props.StringProperty(name="Prompt")
    negative_prompt: bpy.props.StringProperty(
        name="Negative Prompt", default="lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry")

    hr_upscaler: bpy.props.EnumProperty(
        name="Upscalers",
        description="Choose an upscaler",
        items=upscalers
    )

    sampler_name: bpy.props.EnumProperty(
        name="Sampler",
        description="Choose a sampler",
        items=samplers
    )

    controlnet1: bpy.props.StringProperty()
    controlnet2: bpy.props.StringProperty()
    controlnet3: bpy.props.StringProperty()

    method: bpy.props.EnumProperty(name="Method", items=[(
        'txt2img', 'Text to Image', ''), ('img2img', 'Image to Image', '')])

    def init(self, context):
        self.inputs.new('NodeSocketColor', 'Input Image')
        self.outputs.new('NodeSocketColor', 'Output Image')
        self.inputs.new('NodeSocketInt',
                        'Width').default_value = get_width(self)
        self.inputs.new('NodeSocketInt',
                        'Height').default_value = get_height(self)
        self.inputs.new('NodeSocketInt', 'Batch Size').default_value = 1
        self.inputs.new('NodeSocketInt', 'Steps').default_value = 20
        self.inputs.new('NodeSocketInt', 'Cfg Scale').default_value = 7
        self.inputs.new('NodeSocketInt', 'Seed').default_value = -1
        self.inputs.new('NodeSocketBool', 'Restore Faces')
        self.inputs.new('NodeSocketBool', 'Enable HR')
        self.inputs.new('NodeSocketFloat', 'HR Scale').default_value = 2.0
        self.inputs.new('NodeSocketFloat',
                        'Denoising Strength').default_value = 0.25
        self.inputs.new('NodeSocketBool',
                        'Override Settings Restore Afterwards')
        self.inputs.new('SDBLENDER_SocketString', 'ControlNet 1')
        self.inputs.new('SDBLENDER_SocketString', 'ControlNet 2')
        self.inputs.new('SDBLENDER_SocketString', 'ControlNet 3')

    def draw_buttons(self, context, layout):
        layout.prop(self, "prompt")
        layout.prop(self, "negative_prompt")
        layout.prop(self, "sampler_name")
        layout.prop(self, "hr_upscaler")
        layout.prop(self, "method")

    def update(self):
        print('called...')
        if self.inputs['Input Image'].is_linked:
            print('is linked')
            from_node = self.inputs['Input Image'].links[0].from_node
            if isinstance(from_node, bpy.types.CompositorNodeRLayers):
                # Save render result as an image file
                image_path = bpy.path.abspath("//render_result.png")
                bpy.context.scene.render.image_settings.file_format = 'PNG'
                bpy.context.scene.render.filepath = image_path
                bpy.ops.render.render(write_still=True)
            elif isinstance(from_node, bpy.types.CompositorNodeImage):
                # Use image from Image node
                image_path = bpy.path.abspath(from_node.image.filepath)
            else:
                raise ValueError(
                    "Unsupported node type connected to 'Input Image'")
            print('valid node...')
            print('image path: ', image_path)
            # Convert image to base64
            with open(image_path, "rb") as f:
                input_image_base64 = base64.b64encode(f.read()).decode("utf-8")

            # Get ControlNet parameters from inputs and parse them into dicts
            controlnet_params = []
            for i in range(1, 4):
                socket_name = 'ControlNet {}'.format(i)
                print(socket_name)
                if self.inputs[socket_name].is_linked:  
                    controlnet_string = self.inputs[socket_name].links[0].from_node.outputs['Output'].string_value
                    print('controlnet string: ', controlnet_string)
                    controlnet_dict = json.loads(controlnet_string)
                    controlnet_params.append(controlnet_dict)
            print('controlnet params: ', controlnet_params)

            # Send to API
            processed_image_path = send_to_api2(method=self.method, params=node_to_dict(self),
                image_data=input_image_base64, controlnet_params=controlnet_params)

            # Load processed_image as a new bpy.types.Image
            processed_image = bpy.data.images.load(processed_image_path)

            # Assign processed_image to the output socket
            self.outputs['Output Image'].image = processed_image
