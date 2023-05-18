import base64
import bpy
import gpu
import bgl
import blf
import threading
import time
import io
import numpy as np
from PIL import Image

from mathutils import Matrix

from .api import send_to_api
from .utils import safe_base64_decode, print_dict

task = None
last_interaction_time = time.time()


class SDBLENDER_BackgroundTask:
    def __init__(self, scene):
        self.done = False
        self.result = None
        self.scene = scene


    def capture_viewport(self):
        scene = bpy.context.scene
        offscreen = gpu.types.GPUOffScreen(scene.render.resolution_x, scene.render.resolution_y)

        view_matrix = Matrix().Identity(4)
        projection_matrix = Matrix().Identity(4)

        offscreen.draw_view3d(
            scene,
            bpy.context.view_layer,
            bpy.context.space_data,
            bpy.context.region,
            view_matrix,
            projection_matrix)

        buffer = bgl.Buffer(
            bgl.GL_BYTE, scene.render.resolution_x * scene.render.resolution_y * 4)
        bgl.glReadPixels(0, 0, scene.render.resolution_x,
                        scene.render.resolution_y, bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, buffer)

        offscreen.free()
        buffer_bytes = bytearray(buffer)

        # Convert the buffer to a numpy array
        image_data = np.array(buffer_bytes).astype('uint8')

        # Reshape the array into the shape of the image
        image_data = image_data.reshape((scene.render.resolution_y, scene.render.resolution_x, 4))

        # Create a PIL Image object from the numpy array
        image = Image.fromarray(image_data, 'RGBA')

        # Save the image to an in-memory file
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG')

        # Get the PNG data from the in-memory file
        image_bytes = image_bytes.getvalue()

        # Encode the image data in base64
        encoded_string = base64.b64encode(image_bytes).decode()

        return encoded_string

    def post_to_api(self):
        # Capture the viewport
        encoded_string = self.capture_viewport()

        # Check if Cycles has finished rendering
        if self.scene.render.engine == 'CYCLES':
            sd_image = send_to_api(image_data=encoded_string)
            self.draw_image_to_viewport(sd_image)
            self.result = "Task result"
            self.done = True
        else:
            self.result = "Render engine is not Cycles. Task not performed."
            self.done = True


    def draw_image_to_viewport(self, sd_image):
        # Decode the base64 encoded image
        sd_image_data = safe_base64_decode(sd_image)

        # Convert the byte data into normalized floats
        sd_image_pixels = [pixel / 255 for pixel in sd_image_data]

        image = bpy.data.images.new(
            name="SDImage", width=self.scene.render.resolution_x, height=self.scene.render.resolution_y)

        # Ensure that the number of pixels matches the expected size
        if len(sd_image_pixels) == len(image.pixels):
            image.pixels = sd_image_pixels
        else:
            self.result = "Received image size does not match expected size."
            
        # Store the texture ID in a persistent variable so it doesn't get lost
        if not hasattr(bpy, "sd_image_tex_id"):
            bpy.sd_image_tex_id = bgl.Buffer(bgl.GL_INT, [1])
            bgl.glGenTextures(1, bpy.sd_image_tex_id)
        tex_id = bpy.sd_image_tex_id[0]

        # Convert sd_image_pixels to a bgl.Buffer
        pixels_list = sd_image_pixels

        # Flip the image vertically
        width = self.scene.render.resolution_x
        height = self.scene.render.resolution_y
        components = 4  # Assuming RGBA image
        flipped_pixels_list = [pixels_list[(y * width + x) * components: (y * width + x + 1) * components] for y in range(height-1, -1, -1) for x in range(width)]
        flattened_flipped_pixels_list = [item for sublist in flipped_pixels_list for item in sublist]
        pixels_buffer = bgl.Buffer(bgl.GL_FLOAT, len(flattened_flipped_pixels_list), flattened_flipped_pixels_list)


        # Bind the image pixels to the texture
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, tex_id)
        bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, width,
                        height, 0, bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, pixels_buffer)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                            bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
                            bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)


    # # Define a draw function to draw the texture on the viewport
    # def draw_callback_px(self, context):
    #     bgl.glEnable(bgl.GL_BLEND)
    #     bgl.glBindTexture(bgl.GL_TEXTURE_2D, tex_id)
    #     bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
    #                         bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
    #     bgl.glTexParameteri(bgl.GL_TEXTURE_2D,
    #                         bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
    #     bgl.glEnable(bgl.GL_TEXTURE_2D)
    #     bgl.glBegin(bgl.GL_QUADS)
    #     bgl.glTexCoord2d(0, 0)
    #     bgl.glVertex2d(0, 0)
    #     bgl.glTexCoord2d(1, 0)
    #     bgl.glVertex2d(100, 0)
    #     bgl.glTexCoord2d(1, 1)
    #     bgl.glVertex2d(100, 100)
    #     bgl.glTexCoord2d(0, 1)
    #     bgl.glVertex2d(0, 100)
    #     bgl.glEnd()
    #     bgl.glDisable(bgl.GL_TEXTURE_2D)
    #     bgl.glFlush()

    #     # Add the draw function to the viewport draw handler
    #     self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(
    #         draw_callback_px, (self.scene,), 'WINDOW', 'POST_PIXEL')

    def remove_draw_handler(self):
        if self.draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(
                self.draw_handler, 'WINDOW')
            self.draw_handler = None


class SDBLENDER_DrawOperator(bpy.types.Operator):
    bl_idname = "sdblender.custom_draw"
    bl_label = "SD Draw (Experimental)"

    def start_task(self, context):
        task = SDBLENDER_BackgroundTask(context.scene)
        task.post_to_api()

    def execute(self, context):
        if context.area.type == 'VIEW_3D' and context.scene.render.engine == 'CYCLES':
            self.start_task(context)
            return {'RUNNING_MODAL'}
        else:
            self.report(
                {'WARNING'}, "View3D not found, cannot run operator or Render engine is not Cycles")
            return {'CANCELLED'}

    def cancel(self, context):
        pass
