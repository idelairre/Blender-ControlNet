import bpy
import base64
import os
import requests
import json
import time

from .constants import headers
from .utils import copy_file, create_temp_file, get_sd_host, get_controlnet_host, get_preferences, print_dict, get_asset_path, to_dict, transform_to_enum


def ping_api():
    url = get_sd_host().replace("/sdapi/v1/", "")
    response = requests.head(url, headers=headers)

    return response.status_code == 200


def request_caption(image_data, interrogator):
    url = get_sd_host() + "interrogate"
    data = {
        "image": image_data,
        "model": interrogator
    }
    response = requests.post(
        url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        caption = response.json()["caption"]
        return caption
    else:
        print("Error while requesting caption:")
        print(response.content)
        return [('None', 'None', '')]


def get_model_list():
    url = get_controlnet_host() + "model_list"
    response = requests.get(url)

    if response.status_code == 200:
        model_list = response.json()["model_list"]
        return transform_to_enum(model_list)
    else:
        print("Error while requesting model list:")
        print(response.content)
        return [('None', 'None', '')]


def get_module_list():
    url = get_controlnet_host() + "module_list?alias_names=false"
    response = requests.get(url)

    if response.status_code == 200:
        module_list = response.json()["module_list"]
        return module_list
    else:
        print("Error while requesting module list:")
        print(response.content)
        return [('None', 'None', '')]
    
    
def get_module_details():
    url = get_controlnet_host() + "module_list?alias_names=false"
    response = requests.get(url)

    if response.status_code == 200:
        module_list = response.json()["module_detail"]
        return module_list
    else:
        print("Error while requesting module details:")
        print(response.content)
        return [('None', 'None', '')]


def send_to_api2(method=None, params={}, image_data=False, controlnet_params=None):
    if method == 'img2img':
        params['init_images'] = [image_data]

    # Prepare filenames
    timestamp = int(time.time())
    after_output_filename_prefix = f"{timestamp}-2-after"

    # Get the settings from the scene properties
    img_types = []

    # Add selected items to img_types
    for i in range(1, 4):
        img_type = getattr(controlnet_params, f"controlnet{i}")
        if img_type:
            img_types.append(img_type)

    if params.get('alwayson_scripts') is None:
        params['alwayson_scripts'] = {"controlnet": {"args": []}}

    def prepare_cn_units(img_type):
        settings = to_dict(getattr(controlnet_params, img_type))
        settings['module'] = img_type
        return settings

    for img_type in img_types:
        if img_type != 'none':
            print('sending ', img_type, '...')
            cn_units = prepare_cn_units(img_type)

            params['alwayson_scripts']['controlnet']['args'].append(cn_units)
    print_dict(params)
    # Send to API
    output_file = actually_send_to_api(params, after_output_filename_prefix)

    return output_file


def get_model(name):
    return getattr(bpy.context.scene.controlnet, name, None)


def get_models(names):
    return {name: get_model(name) for name in names}


def get_active_models():
    controlnet_props = bpy.context.scene.controlnet
    return [controlnet_props.controlnet1, controlnet_props.controlnet2, controlnet_props.controlnet3]


def prepare_cn_unit(img_type, timestamp, image_data=False):
    settings = to_dict(get_model(img_type))
    filename = f"{timestamp}-1-{img_type}-before.png"

    if not image_data:
        bpy.data.images["Render Result"].save_render(get_asset_path(filename))
        with open(get_asset_path(filename), "rb") as file:
            settings['input_image'] = base64.b64encode(file.read()).decode()
    else:
        settings['input_image'] = image_data

    settings['module'] = img_type
    return settings


def send_to_api(image_data=False):
    timestamp = int(time.time())
    after_output_filename_prefix = f"{timestamp}-2-after"

    params = to_dict(bpy.context.scene.sdblender)
    params.setdefault('alwayson_scripts', {"controlnet": {"args": []}})
    active_models = get_active_models()
    
    method = bpy.context.scene.sdblender.method
    
    if method == 'img2img':
        params['init_images'] = [image_data]

    for img_type in active_models:
        if img_type != 'none':
            print('sending ', img_type, '...')
            cn_units = prepare_cn_unit(img_type, timestamp, image_data)
            params['alwayson_scripts']['controlnet']['args'].append(cn_units)

    output_file = actually_send_to_api(params, after_output_filename_prefix)
    
    print('finished processing...')

    if output_file:
        new_output_file = save_after_image(
            bpy.context.scene, after_output_filename_prefix, output_file)
        output_file = new_output_file if new_output_file else output_file

        try:
            img = bpy.data.images.load(output_file, check_existing=False)
            for window in bpy.data.window_managers["WinMan"].windows:
                for area in window.screen.areas:
                    if area.type == "IMAGE_EDITOR":
                        area.spaces.active.image = img
        except:
            print("Couldn't load the image.")
        return True
    else:
        return False


def actually_send_to_api(params, filename_prefix):
    method = bpy.context.scene.sdblender.method
    # prepare server url
    server_url = get_sd_host() + method

    # send API request
    try:
        response = requests.post(
            server_url, json=params, headers=headers, timeout=1000)
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
    """Handle successful API response.

    Args:
        response: API response object.
        filename_prefix: Prefix for the output file name.

    Returns:
        The path of the output file if successful, None otherwise.
    """

    try:
        # Parse JSON and extract the base64 image
        base64_img = response.json()["images"][0]

        # Create a temporary file for the image
        output_file = create_temp_file(filename_prefix + "-")

        # Decode the base64 image
        img_binary = base64.b64decode(
            base64_img.replace("data:image/png;base64,", ""))

        try:
            # Write the decoded image data to the temporary file
            with open(output_file, "wb") as file:
                file.write(img_binary)
            # Return the path of the output file
            return output_file
        except Exception as e:
            print("Couldn't write to temp file.")
            print(f"Error details: {e}")
            return
    except Exception as e:
        print("Error while parsing response, creating temp file, or decoding base64 image.")
        print(f"Error details: {e}")
        print("Response content:")
        print(response.content)
        return


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
            f"Couldn't save 'after' image to {bpy.path.abspath(full_path_and_filename)}")


def get_upscalers():
    server_url = get_sd_host() + 'upscalers'
    response = requests.get(server_url)

    if response.status_code == 200:
        upscalers = response.json()
        return [(upscaler['name'], upscaler['name'].title().replace('_', ' '), '') for upscaler in upscalers]
    else:
        print(f"Error: {response.status_code}")
        return [('None', 'None', '')]


def get_sampler_items():
    server_url = get_sd_host() + 'samplers'
    response = requests.get(server_url)

    if response.status_code == 200:
        samplers = response.json()
        return [(sampler['name'], sampler['name'], '') for sampler in samplers]
    else:
        print(f"Error: {response.status_code}")
        return [('None', 'None', '')]
