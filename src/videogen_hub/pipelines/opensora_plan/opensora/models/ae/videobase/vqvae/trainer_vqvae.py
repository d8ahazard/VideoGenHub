import torch.nn.functional as F
from videogen_hub.pipelines.opensora_plan.opensora.models.ae.videobase.trainer_videobase import VideoBaseTrainer


class VQVAETrainer(VideoBaseTrainer):

    def compute_loss(self, model, inputs, return_outputs=False):
        model = model.module
        x = inputs.get("video")
        x = x / 2
        z = model.pre_vq_conv(model.encoder(x))
        vq_output = model.codebook(z)
        x_recon = model.decoder(model.post_vq_conv(vq_output["embeddings"]))
        recon_loss = F.mse_loss(x_recon, x) / 0.06
        commitment_loss = vq_output['commitment_loss']
        loss = recon_loss + commitment_loss
        return loss

