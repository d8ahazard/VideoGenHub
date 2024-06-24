from videogen_hub.base.base_infer_model import BaseInferModel


class BaseT2vInferModel(BaseInferModel):
    def infer_one_video(
            self,
            prompt: str = None,
            negative_prompt: str = None,
            size: list = None,
            seconds: int = 2,
            fps: int = 8,
            seed: int = 42,
    ):
        pass
