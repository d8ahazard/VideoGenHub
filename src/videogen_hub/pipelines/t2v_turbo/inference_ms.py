# Adapted from https://github.com/luosiallen/latent-consistency-model
from __future__ import annotations

import os
import random

import numpy as np

from .pipeline.t2v_turbo_ms_pipeline import T2VTurboMSPipeline
from .scheduler.t2v_turbo_scheduler import T2VTurboScheduler
from .utils.common_utils import set_torch_2_attn

try:
    import intel_extension_for_pytorch as ipex
except:
    pass

from transformers import CLIPTokenizer, CLIPTextModel
from .model_scope.unet_3d_condition import UNet3DConditionModel

from .utils.lora import collapse_lora, monkeypatch_remove_lora
from .utils.lora_handler import LoraHandler

import torch
from diffusers.models import AutoencoderKL

DESCRIPTION = """# T2V-Turbo 🚀
We provide T2V-Turbo (MS) distilled from [ModelScopeT2V](https://huggingface.co/ali-vilab/text-to-video-ms-1.7b/) with the reward feedback from [HPSv2.1](https://github.com/tgxs002/HPSv2/tree/master) and [ViCLIP](https://huggingface.co/OpenGVLab/ViCLIP).

You can download the the models from [here](https://huggingface.co/jiachenli-ucsb/T2V-Turbo-MS). Check out our [Project page](https://t2v-turbo.github.io) 😄
"""
if torch.cuda.is_available():
    DESCRIPTION += "\n<p>Running on CUDA 😀</p>"
elif hasattr(torch, "xpu") and torch.xpu.is_available():
    DESCRIPTION += "\n<p>Running on XPU 🤓</p>"
else:
    DESCRIPTION += "\n<p>Running on CPU 🥶 This demo does not work on CPU.</p>"

MAX_SEED = np.iinfo(np.int32).max
CACHE_EXAMPLES = torch.cuda.is_available() and os.getenv("CACHE_EXAMPLES") == "1"
USE_TORCH_COMPILE = os.getenv("USE_TORCH_COMPILE") == "1"

"""
Operation System Options:
    If you are using MacOS, please set the following (device="mps") ;
    If you are using Linux & Windows with Nvidia GPU, please set the device="cuda";
    If you are using Linux & Windows with Intel Arc GPU, please set the device="xpu";
"""
# device = "mps"    # MacOS
# device = "xpu"    # Intel Arc GPU
device = "cuda"  # Linux & Windows

"""
   DTYPE Options:
      To reduce GPU memory you can set "DTYPE=torch.float16",
      but image quality might be compromised
"""
DTYPE = (
    torch.float16
)  # torch.float16 works as well, but pictures seem to be a bit worse


def randomize_seed_fn(seed: int, randomize_seed: bool) -> int:
    if randomize_seed:
        seed = random.randint(0, MAX_SEED)
    return seed


class T2VTurboMSPipeline1:
    def __init__(self, device, unet_dir, base_model_dir):
        pretrained_model_path = base_model_dir
        tokenizer = CLIPTokenizer.from_pretrained(
            pretrained_model_path, subfolder="tokenizer"
        )
        text_encoder = CLIPTextModel.from_pretrained(
            pretrained_model_path, subfolder="text_encoder"
        )
        vae = AutoencoderKL.from_pretrained(pretrained_model_path, subfolder="vae")
        teacher_unet = UNet3DConditionModel.from_pretrained(
            pretrained_model_path, subfolder="unet"
        )

        time_cond_proj_dim = 256
        unet = UNet3DConditionModel.from_config(
            teacher_unet.config, time_cond_proj_dim=time_cond_proj_dim
        )
        # load teacher_unet weights into unet
        unet.load_state_dict(teacher_unet.state_dict(), strict=False)
        del teacher_unet
        set_torch_2_attn(unet)
        use_unet_lora = True
        lora_manager = LoraHandler(
            version="cloneofsimo",
            use_unet_lora=use_unet_lora,
            save_for_webui=True,
        )
        lora_manager.add_lora_to_model(
            use_unet_lora,
            unet,
            lora_manager.unet_replace_modules,
            lora_path=unet_dir,
            dropout=0.1,
            r=32,
        )
        collapse_lora(unet, lora_manager.unet_replace_modules)
        monkeypatch_remove_lora(unet)
        unet.eval()

        noise_scheduler = T2VTurboScheduler()
        self.pipeline = T2VTurboMSPipeline(
            unet=unet,
            vae=vae,
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            scheduler=noise_scheduler,
        )
        self.pipeline.to(device)

    def inference(
            self,
            prompt: str,
            height: int = 320,
            width: int = 512,
            seed: int = 0,
            guidance_scale: float = 7.5,
            num_inference_steps: int = 4,
            num_frames: int = 16,
            fps: int = 16,
            randomize_seed: bool = False,
            param_dtype="torch.float16"
    ):
        seed = randomize_seed_fn(seed, randomize_seed)
        torch.manual_seed(seed)
        self.pipeline.to(
            torch_device=device,
            torch_dtype=torch.float16 if param_dtype == "torch.float16" else torch.float32,
        )

        result = self.pipeline(
            prompt=prompt,
            height=height,
            width=width,
            frames=num_frames,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            num_videos_per_prompt=1,
        )

        return result
