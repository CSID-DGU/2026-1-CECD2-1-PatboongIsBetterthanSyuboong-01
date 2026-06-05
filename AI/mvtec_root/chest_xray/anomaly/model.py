#!/usr/bin/env python3

"""

모델 정의 모듈

"""



import torch

import torch.nn as nn

import torch.nn.functional as F





class SimpleAE(nn.Module):

    """간단한 Autoencoder 모델"""

    def __init__(self, in_ch: int = 1, latent_ch: int = 256):

        super().__init__()

        self.in_ch = in_ch

        self.latent_ch = latent_ch

        self.enc = nn.Sequential(

            nn.Conv2d(in_ch, 32, 3, 2, 1), nn.BatchNorm2d(32), nn.ReLU(True),

            nn.Dropout2d(p=0.1),

            nn.Conv2d(32, 64, 3, 2, 1), nn.BatchNorm2d(64), nn.ReLU(True),

            nn.Dropout2d(p=0.1),

            nn.Conv2d(64, 128, 3, 2, 1), nn.BatchNorm2d(128), nn.ReLU(True),

            nn.Conv2d(128, 256, 3, 2, 1), nn.BatchNorm2d(256), nn.ReLU(True),

            nn.Conv2d(256, latent_ch, 3, 2, 1), nn.ReLU(True),

        )

        self.dec = nn.Sequential(

            nn.ConvTranspose2d(latent_ch, 256, 4, 2, 1), nn.BatchNorm2d(256), nn.ReLU(True),

            nn.Dropout2d(p=0.1),

            nn.ConvTranspose2d(256, 128, 4, 2, 1), nn.BatchNorm2d(128), nn.ReLU(True),

            nn.Dropout2d(p=0.1),

            nn.ConvTranspose2d(128, 64, 4, 2, 1), nn.BatchNorm2d(64), nn.ReLU(True),

            nn.ConvTranspose2d(64, 32, 4, 2, 1), nn.BatchNorm2d(32), nn.ReLU(True),

            nn.ConvTranspose2d(32, in_ch, 4, 2, 1), nn.Tanh(),

        )

    

    def _initialize_heads(self):

        """Initialize alpha/beta heads with small bias to avoid zero outputs."""

        for head in [self.head_alpha, self.head_beta]:

            if hasattr(head[-2], 'bias') and head[-2].bias is not None:

                nn.init.constant_(head[-2].bias, 0.1)



    def forward(self, x):

        # 입력은 0~1 범위, 디코더에서 -1~1 범위로 정규화

        x_norm = x * 2.0 - 1.0

        z = self.enc(x_norm)

        xrec_norm = self.dec(z)

        xrec = torch.clamp((xrec_norm + 1.0) * 0.5, 0.0, 1.0)

        return xrec, z  # z는 반환하지 않으므로 제외 (선택적)





# ----------- Attention blocks (CBAM-style) -----------



class CAM2D(nn.Module):

    """Channel Attention for images: [B,C,H,W] -> [B,C,H,W]"""

    def __init__(self, in_ch, r=8):

        super().__init__()

        hidden = max(in_ch // r, 4)

        self.mlp = nn.Sequential(

            nn.Linear(in_ch, hidden), nn.ReLU(True),

            nn.Linear(hidden, in_ch)

        )

        self.sigmoid = nn.Sigmoid()



    def forward(self, x):

        b, c, h, w = x.shape

        avg = F.adaptive_avg_pool2d(x, 1).view(b, c)

        mx  = F.adaptive_max_pool2d(x, 1).view(b, c)

        w_avg = self.mlp(avg)

        w_max = self.mlp(mx)

        w = self.sigmoid(w_avg + w_max).view(b, c, 1, 1)

        return x * w, w  # return gate too (for debugging)



class SAM2D(nn.Module):

    """Spatial Attention for images: [B,C,H,W] -> [B,1,H,W] mask"""

    def __init__(self, k=7):

        super().__init__()

        p = k // 2

        self.conv = nn.Conv2d(2, 1, k, padding=p)

        self.sigmoid = nn.Sigmoid()



    def forward(self, x):

        # channel-wise pooling -> concat -> conv

        x_max, _ = torch.max(x, dim=1, keepdim=True)           # [B,1,H,W]

        x_avg = torch.mean(x, dim=1, keepdim=True)             # [B,1,H,W]

        m = torch.cat([x_max, x_avg], dim=1)                   # [B,2,H,W]

        m = self.sigmoid(self.conv(m))                         # [B,1,H,W]

        return x * m, m



class CSAD2D(nn.Module):

    """Channel+Spatial attention fusion -> 1x1 conv to collapse channels"""

    def __init__(self, in_ch, k=7):

        super().__init__()

        self.cam = CAM2D(in_ch)

        self.sam = SAM2D(k)

        self.reduce = nn.Conv2d(in_ch, 1, kernel_size=1)

        self.act = nn.ReLU(inplace=True)



    def forward(self, x):

        x, cam_w = self.cam(x)             # [B,C,H,W]

        x, sam_w = self.sam(x)             # [B,C,H,W]

        x = self.act(self.reduce(x))       # [B,1,H,W]

        return x, cam_w, sam_w             # feature map + gates



# ----------- ADRM (map-wise) -----------



class ADRM2D(nn.Module):

    """Element-wise adaptive remapping with outlier suppression: x -> x + r*(x^2 - x), twice"""

    def __init__(self, outlier_suppression: bool = True, suppression_percentile: float = 99.5):

        super().__init__()

        self.outlier_suppression = outlier_suppression

        self.suppression_percentile = suppression_percentile



    def _suppress_outliers(self, x):

        """Outlier suppression using percentile clipping"""

        if not self.outlier_suppression:

            return x

        

        # 각 배치별로 outlier suppression

        B, C, H, W = x.shape

        x_flat = x.view(B, C, -1)  # [B, C, H*W]

        

        # 상위 percentile로 클리핑하여 outlier 제거

        percentile_val = torch.quantile(x_flat, self.suppression_percentile / 100.0, dim=2, keepdim=True)  # [B, C, 1]

        x_clipped = torch.clamp(x_flat, max=percentile_val)  # 클리핑 적용

        

        return x_clipped.view(B, C, H, W)



    def forward(self, s1, s2, a, b):

        # all tensors [B,1,H,W], a,b in [-1,1], s1,s2 in [0,1]

        # 다중 percentile 클리핑 제거: 입력 단계에서 outlier suppression 제거

        # (다중 클리핑이 동적 범위를 과도하게 축소하는 문제 해결)

        # s1, s2에 대한 초기 outlier suppression 제거

        

        # 비선형 remapping: 입력을 0으로 보내거나 1로 보내기 위해 clamp 추가

        # s^2 - s 는 s * (1 - s)를 사용하여 안정성 향상

        x1 = s1 + a * (s1 * s1 - s1)

        x1 = torch.clamp(x1, min=0.0, max=1.0)  # 입력 범위 유지

        x2 = x1 + b * (x1 * x1 - x1)

        x2 = torch.clamp(x2, min=0.0, max=1.0)  # 입력 범위 유지

        

        y1 = s2 + a * (s2 * s2 - s2)

        y1 = torch.clamp(y1, min=0.0, max=1.0)  # 입력 범위 유지

        y2 = y1 + b * (y1 * y1 - y1)

        y2 = torch.clamp(y2, min=0.0, max=1.0)  # 입력 범위 유지

        

        # 중간 단계에서 outlier suppression 제거 (범위 축소 방지)

        # x2, y2에 대한 중간 outlier suppression 제거

        

        # Robust fusion: 두 브랜치 결합하여 robust한 최종 스코어

        # x2와 y2의 outlier를 고려한 안정적인 결합

        score = x2 * y2  # 기본 결합

        

        # 최종 score에만 outlier suppression 적용 (한 번만)

        # 필요시 outlier_suppression=True로 설정하여 활성화 가능

        score = self._suppress_outliers(score)

        

        # 입력 범위를 [0, 1]로 유지하여 0으로 수렴 방지

        score = torch.clamp(score, min=0.0, max=1.0)

        

        r = torch.cat([a, b], dim=1)  # [B,2,H,W]

        return score, r





class DualBranchFusion(nn.Module):

    """Re-calibrate ADRM output with learnable gating between two branches"""

    def __init__(self, in_ch=3):

        super().__init__()

        self.body = nn.Sequential(

            nn.Conv2d(in_ch, 32, kernel_size=3, padding=1),

            nn.ReLU(inplace=True),

            nn.Conv2d(32, 32, kernel_size=3, padding=1),

            nn.ReLU(inplace=True)

        )

        self.delta_head = nn.Conv2d(32, 1, kernel_size=1)

        self.gate_head = nn.Conv2d(32, 1, kernel_size=1)

        self.tanh = nn.Tanh()

        self.sigmoid = nn.Sigmoid()



    def forward(self, s_recon, s_feat, score):

        stacked = torch.cat([s_recon, s_feat, score], dim=1)

        feat = self.body(stacked)

        delta = self.tanh(self.delta_head(feat))

        gate = self.sigmoid(self.gate_head(feat))

        refined = torch.clamp(score + delta, 0.0, 1.0)

        average_branch = 0.5 * (s_recon + s_feat)

        fused = gate * refined + (1.0 - gate) * average_branch

        return fused.clamp(0.0, 1.0), gate



# ----------- Dual-detector 2D anomaly model -----------



class ImageAnomalyDual(nn.Module):

    """

    Branch-1: reconstruction score (per-pixel) from AE

    Branch-2: feature-attention score from latent map (CSAD2D)

    ADRM2D: adaptive non-linear remapping with learned alpha/beta maps

    """

    def __init__(self, in_ch=1, latent_ch=256, use_fusion=False):

        super().__init__()

        self.ae = SimpleAE(in_ch=in_ch, latent_ch=latent_ch)

        self.att = CSAD2D(in_ch=latent_ch, k=7)

        # heads for producing scores and r1/r2 on latent grid

        self.head_score = nn.Sequential(

            nn.Conv2d(1, 1, kernel_size=1), nn.Sigmoid()  # s2 on latent grid

        )

        self.head_alpha = nn.Sequential(

            nn.Conv2d(latent_ch, 16, 1), nn.ReLU(True),

            nn.Conv2d(16, 1, 1), nn.Tanh()               # alpha in [-1,1]

        )

        self.head_beta = nn.Sequential(

            nn.Conv2d(latent_ch, 16, 1), nn.ReLU(True),

            nn.Conv2d(16, 1, 1), nn.Tanh()               # beta in [-1,1]

        )

        

        # Alpha/Beta head 초기화: 0이 되지 않도록 작은 값으로 초기화

        self._initialize_heads()

        # ADRM2D: outlier suppression을 기본적으로 비활성화 (다중 클리핑으로 인한 범위 축소 방지)

        # 필요시 최종 score에만 한 번 적용하도록 수정됨

        self.adrm = ADRM2D(outlier_suppression=False, suppression_percentile=99.5)

        self.use_fusion = use_fusion

        if use_fusion:

            self.fusion = DualBranchFusion(in_ch=3)

        else:

            self.fusion = None

    



    def _initialize_heads(self):

        """Initialize alpha/beta heads with small bias to avoid zero outputs."""

        # 마지막 conv layer의 bias를 작은 값으로 초기화

        # Tanh 출력이 0에 가까워지지 않도록

        for head in [self.head_alpha, self.head_beta]:

            if hasattr(head[-2], 'bias') and head[-2].bias is not None:

                nn.init.constant_(head[-2].bias, 0.1)  # 작은 값으로 초기화



    def forward(self, x, return_intermediate=False):

        """

        x: [B,1,H,W] (normalize to 0..1)

        Returns:

          xrec: reconstruction

          score: final anomaly map [B,1,H,W]

          s_recon: recon-branch map (0..1)

          s_feat: feature-branch map (0..1), upsampled

          r: [B,2,H,W] alpha/beta maps (upsampled)

          (optionally cam/sam)

        """

        B, _, H, W = x.shape



        xrec, z = self.ae(x)                             # z:[B,C,h,w], h=H/16



        # --- Branch-1: reconstruction anomaly map (pixel-wise) ---

        # raw absolute error (선형 스케일 사용, exp로 눌러버리지 않음)

        err = torch.abs(x - xrec)                        # [B,1,H,W]

        # 선형/온도 스케일로 펴기: err * scale을 0~1로 클램프

        # scale=5.0은 경험적 값, 필요시 learnable로 변경 가능

        recon_scale = 5.0

        s_recon = torch.clamp(err * recon_scale, 0.0, 1.0)  # [B,1,H,W], higher->more anomalous



        # --- Branch-2: attention over latent + score on latent grid ---

        z_map, cam_w, sam_w = self.att(z)                # z_map:[B,1,h,w]

        s_feat_lat = self.head_score(z_map)              # [B,1,h,w]



        # alpha/beta predicted from full latent feature tensor

        alpha_lat = self.head_alpha(z)                   # [B,1,h,w]

        beta_lat  = self.head_beta(z)                    # [B,1,h,w]



        # upsample latent maps to image size

        s_feat = F.interpolate(s_feat_lat, size=(H, W), mode='bilinear', align_corners=False)

        alpha  = F.interpolate(alpha_lat,  size=(H, W), mode='bilinear', align_corners=False)

        beta   = F.interpolate(beta_lat,   size=(H, W), mode='bilinear', align_corners=False)



        # --- ADRM on image grid ---

        score, r = self.adrm(s_recon.clamp(0,1), s_feat.clamp(0,1), alpha, beta)  # score:[B,1,H,W]

        

        # ADRM 출력은 그대로 사용 (per-image min-max 제거)

        

        # Fusion 모듈 사용 여부에 따라 선택

        if self.use_fusion and self.fusion is not None:

            score, fusion_gate = self.fusion(s_recon, s_feat, score)

        else:

            fusion_gate = None



        if return_intermediate:

            # also return latent gates for debugging/visualization

            cam_up = F.interpolate(cam_w, size=(H, W), mode='nearest')  # [B,C,H,W]

            sam_up = F.interpolate(sam_w, size=(H, W), mode='bilinear', align_corners=False)  # [B,1,H,W]

            result = {

                "xrec": xrec, "score": score, "s_recon": s_recon, "s_feat": s_feat,

                "alpha": alpha, "beta": beta, "r": r, "cam_w_up": cam_up, "sam_w_up": sam_up

            }

            if fusion_gate is not None:

                result["fusion_gate"] = fusion_gate

            return result

        else:

            return xrec, score, s_recon, s_feat, r



