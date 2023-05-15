# Blender-ControlNet

Using Multiple ControlNet in Blender. Now an addon courtesy of me! No more fiddling with variables in a script file, no need for any compositor node setups, just press `render` and it will send the render to your Stable Diffusion WebUI on completion. The result appears in your image viewer just like the original script. 

## Required

- [AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
- [Mikubill/sd-webui-controlnet](https://github.com/Mikubill/sd-webui-controlnet)
- this addon correctly installed
- brain capable of following instructions

## Usage

### 1. Start A1111 in API mode.

First, of course, is to run web ui with `--api` commandline argument

- example in your "webui-user.bat": `set COMMANDLINE_ARGS=--api`

### 2. Install Mikubill/sd-webui-controlnet extension

You have to install the `Mikubill/sd-webui-controlnet` extension in A1111 and download the ControlNet models.  
Please refer to the installation instructions from [Mikubill/sd-webui-controlnet](https://github.com/Mikubill/sd-webui-controlnet).

**Notes**

- In new version of Mikubill/sd-webui-controlnet, you need to enable `Allow other script to control this extension` in settings for API access.
- To enable Multi ControlNet, change `Multi ControlNet: Max models amount (requires restart)` in the settings. Note that you will need to restart the WebUI for changes to take effect.

### 3. Install the addon

Follow these steps to install the add-on in Blender courtesy of GPT-4 with some minor edits:

- **Option 1**: just use the tag release and install the addon like normal following the directions below.

- **Option 2**: *The hard way.* Clone or download the repository as a `.zip`. If you download it as a `.zip` file you will have to extract the `addon` folder then recompress the contents, give it a sensible named like `blender_controlnet` making sure to avoid any dashes, e.g., `-`, in the folder name as this will break Blender.

- Open Blender and go to `Edit > Preferences`

- In the Preferences window, navigate to the `Add-ons` tab.

- Click the `Install` button at the top right corner of the window.

- Browse to the location where you downloaded the `.zip` archive, select it, and click `Install Add-on`

- After the installation is complete, the add-on should appear in the list of installed add-ons. You can search for it by typing its name in the search bar.

- Enable the add-on by clicking the checkbox next to its name.

## The buttons

**IMPORTANT**: Configure the add-on settings, such as the API `server address`, `port`, and `output folder`, by expanding the add-on panel and adjusting the options as needed. **This is not optional!**

There is a little (read: a lot) of technical debt to the original script so I don't know what all these properties do GPT-4 will try it's best to explain the panels.

**SD Blender:**
Your basic Stable Diffusion prompt settings and some other stuff I don't really understand:
- `prompt`:
    A string property representing the prompt text for the AI model.
- `negative_prompt`:
    A string property representing the negative prompt text for the AI model. The default value includes common negative attributes like "lowres", "bad anatomy", "blurry", etc.
- `width`:
    An integer property representing the width of the output image. This property is read-only and is calculated based on the current scene's render settings. **IMPORTANT:** the width and height settings you use to render in Blender WILL crash your Stable Diffusion.
- `height`:
    An integer property representing the height of the output image. This property is read-only and is calculated based on the current scene's render settings.
- `sampler_name`:
    An enumeration property that allows the user to choose a sampler from a list of available samplers.
- `sampler_index`:
    An integer property representing the index of the selected sampler.
- `batch_size`:
    An integer property representing the batch size for processing images.
- `n_iter`:
    An integer property representing the number of iterations for the AI model.
- `steps`:
    An integer property representing the number of steps for the AI model.
- `cfg_scale`:
    An integer property representing the configuration scale for the AI model.
- `seed`:
    An integer property representing the random seed used by the AI model.
- `subseed`:
    An integer property representing the subseed value.
- `subseed_strength`:
    A float property representing the strength of the subseed.
- `restore_faces`:
    A boolean property indicating whether to restore faces in the output image.
- `enable_hr`:
    A boolean property indicating whether to enable high-resolution (HR) processing.
- `hr_scale`:
    A float property representing the scale factor for high-resolution processing.
- `hr_upscaler`:
    An enumeration property that allows the user to choose an upscaler from a list of available upscalers.
- `denoising_strength`:
    A float property representing the strength of denoising applied to the output image.
- `hr_second_pass_steps`:
    An integer property representing the number of steps for the second pass of high-resolution processing.
- `hr_resize_x`:
    An integer property representing the width of the resized high-resolution output image. The value is limited between 0 and 2048.
- `hr_resize_y`:
    An integer property representing the height of the resized high-resolution output image. The value is limited between 0 and 2048.
- `firstphase_width`:
    An integer property representing the width of the first phase output image.
- `firstphase_height`:
    An integer property representing the height of the first phase output image.
- `override_settings_restore_afterwards`:
    A boolean property indicating whether to restore the original settings after processing the image.
- `override_settings`:
    A collection property containing instances of the `OverrideSettingsItem` class, which represents individual settings to be overridden during processing.

**Control Net**: properties for your nets, supports up to three control nets
- `model`:
    An enumeration property that allows the user to choose a ControlNet model from a list of available models.
- `weight`:
    A float property representing the weight parameter for ControlNet. The default value is 1.2.
- `resize_mode`:
    A string property representing the resize mode for the image processing. The default value is "Crop and Resize".
- `lowvram`:
    A boolean property indicating whether to enable the low VRAM mode for ControlNet. The default value is False.
- `processor_res`:
    An integer property representing the processor resolution for ControlNet. The default value is 512.
- `guidance`:
    An integer property representing the guidance value for ControlNet. The default value is 1.
- `guidance_start`:
    A float property representing the guidance start value for ControlNet. The default value is 0.00.
- `guidance_end`:
    A float property representing the guidance end value for ControlNet. The default value is 1.

**Interrogate**: image to text caption for when you don't want to prompt
- Interrogator: `clip` or `deepdanbooru`
- Interrogate: run the `clip` or `deepdanbooru` model you must have rendered at least once otherwise this option will be disabled. The analysis runs on your last render, not your viewport.

## Future plans
- reogranize repo
- figure out what some of these parameters do so we can see if we still need all of them
- tool tips, better help, improved readme
- see if this works with a remote host like a runpod instance
- figure out which preprocessors are compatible with what models so you're not hunting around for the matching model after selecting your preprocessor
- see if we can get this merged back into the main repo