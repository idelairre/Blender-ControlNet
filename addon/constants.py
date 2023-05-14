import bpy

headers = {
    "User-Agent": "Blender/" + bpy.app.version_string,
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
}

model_list = [
    "none",
    "control_v11e_sd15_ip2p [c4bb465c]",
    "control_v11e_sd15_shuffle [526bfdae]",
    "control_v11f1e_sd15_tile [a371b31b]",
    "control_v11f1p_sd15_depth [cfd03158]",
    "control_v11p_sd15_canny [d14c016b]",
    "control_v11p_sd15_inpaint [ebff9138]",
    "control_v11p_sd15_lineart [43d4be0d]",
    "control_v11p_sd15_mlsd [aca30ff0]",
    "control_v11p_sd15_normalbae [316696f1]",
    "control_v11p_sd15_openpose [cab727d4]",
    "control_v11p_sd15_scribble [d4ba51ff]",
    "control_v11p_sd15_seg [e1f51eb9]",
    "control_v11p_sd15_softedge [a8575a2a]",
    "control_v11p_sd15s2_lineart_anime [3825e83e]"
]

controlnet_models = [
    "none",
    "canny",
    "depth",
    "depth_leres",
    "depth_leres++",
    "hed",
    "hed_safe",
    "mediapipe_face",
    "mlsd",
    "normal_map",
    "openpose",
    "openpose_hand",
    "openpose_face",
    "openpose_faceonly",
    "openpose_full",
    "clip_vision",
    "color",
    "pidinet",
    "pidinet_safe",
    "pidinet_sketch",
    "pidinet_scribble",
    "scribble_xdog",
    "scribble_hed",
    "segmentation",
    "threshold",
    "depth_zoe",
    "normal_bae",
    "oneformer_coco",
    "oneformer_ade20k",
    "lineart",
    "lineart_coarse",
    "lineart_anime",
    "lineart_standard",
    "shuffle",
    "tile_resample",
    "invert",
    "lineart_anime_denoise",
    "reference_only",
    "inpaint"
]

module_details = {
    "canny": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "value": 512,
                "min": 64,
                "max": 2048
            },
            {
                "name": "Canny Low Threshold",
                "value": 100,
                "min": 1,
                "max": 255
            },
            {
                "name": "Canny High Threshold",
                "value": 200,
                "min": 1,
                "max": 255
            }
        ]
    },
    "depth": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            }
        ]
    },
    "depth_leres": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            },
            {
                "name": "Remove Near %",
                "min": 0,
                "max": 100,
                "value": 0,
                "step": 0.1
            },
            {
                "name": "Remove Background %",
                "min": 0,
                "max": 100,
                "value": 0,
                "step": 0.1
            }
        ]
    },
    "depth_leres++": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            },
            {
                "name": "Remove Near %",
                "min": 0,
                "max": 100,
                "value": 0,
                "step": 0.1
            },
            {
                "name": "Remove Background %",
                "min": 0,
                "max": 100,
                "value": 0,
                "step": 0.1
            }
        ]
    },
    "hed": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            }
        ]
    },
    "hed_safe": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            }
        ]
    },
    "mediapipe_face": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "value": 512,
                "min": 64,
                "max": 2048
            },
            {
                "name": "Max Faces",
                "value": 1,
                "min": 1,
                "max": 10,
                "step": 1
            },
            {
                "name": "Min Face Confidence",
                "value": 0.5,
                "min": 0.01,
                "max": 1,
                "step": 0.01
            }
        ]
    },
    "mlsd": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            },
            {
                "name": "MLSD Value Threshold",
                "min": 0.01,
                "max": 2,
                "value": 0.1,
                "step": 0.01
            },
            {
                "name": "MLSD Distance Threshold",
                "min": 0.01,
                "max": 20,
                "value": 0.1,
                "step": 0.01
            }
        ]
    },
    "normal_map": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            },
            {
                "name": "Normal Background Threshold",
                "min": 0,
                "max": 1,
                "value": 0.4,
                "step": 0.01
            }
        ]
    },
    "openpose": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            }
        ]
    },
    "openpose_full": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            }
        ]
    },
    "color": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "value": 512,
                "min": 64,
                "max": 2048
            }
        ]
    },
    "scribble_xdog": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "value": 512,
                "min": 64,
                "max": 2048
            },
            {
                "name": "XDoG Threshold",
                "min": 1,
                "max": 64,
                "value": 32
            }
        ]
    },
    "scribble_hed": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            }
        ]
    },
    "segmentation": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "min": 64,
                "max": 2048,
                "value": 512
            }
        ]
    },
    "threshold": {
        "sliders": [
            {
                "name": "Preprocessor Resolution",
                "value": 512,
                "min": 64,
                "max": 2048
            },
            {
                "name": "Binarization Threshold",
                "min": 0,
                "max": 255,
                "value": 127
            }
        ]
    },
    "tile_resample": {
        "sliders": [
            {
                "name": "Down Sampling Rate",
                "value": 1,
                "min": 1,
                "max": 8,
                "step": 0.01
            }
        ]
    },
}
