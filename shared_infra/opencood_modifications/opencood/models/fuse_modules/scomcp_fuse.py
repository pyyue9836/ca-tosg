#self+ SComCP fuse module: cross-attention selector + Transformer-CA JSCC codec (Gan2026 TVT reproduction)
"""
SComCP fusion module (faithful reproduction of Gan et al., IEEE TVT 2026,
"SComCP: Task-Oriented Semantic Communication for Collaborative Perception").

This reuses the whole importance-map-JSCC pipeline already implemented in
``importance_map_jscc_fuse.py`` (complex AWGN/Rayleigh/OFDM channels, power
normalization, spatial masking, multi-scale attention fusion, paper-CR
diagnostics, perfect-comm / LDPC-QAM eval controls) and only swaps in the two
modules that SComCP actually changes over the baseline [35]:

  1. Importance-aware feature selection network  (paper Sec. III-B, eq. 11-15):
        I_j   = Conv_gen(M_j)                          # importance map (eq. 11)
        M'_j  = Conv_dow(M_j + lambda * CrossAtten(I_j, M_j))   # (eq. 12)
        I'_j  = SpatialAtten(I_j)                       # (eq. 13)
        P_keep= SoftMax(M'_j  ⊙  I'_j)                  # (eq. 14)
        Omega = 1[P_keep > tau]                         # (eq. 15)
     -> replaces the plain Conv ``ImportanceMapGenerator`` of the baseline.

  2. Transformer + Channel-Attention semantic codec  (paper Sec. III-C, eq.16-20):
        Embedding -> [Transformer module, CA module] x L -> Conv -> power norm
        -> channel -> [Transformer, CA] x L -> Conv -> reconstruction
     -> replaces the pure-Conv ``SemanticEncoderDecoder`` of the baseline.

DESIGN NOTES (deviations are explicit, so the gap to the paper is auditable):
  * The paper operates the codec on the K *selected* tokens F_j in R^{K x C}.
    We honor that: the codec gathers only the kept spatial tokens per CAV row
    (using the importance mask), runs the Transformer/CA stack over those K
    tokens (C as the per-token feature dim), then scatters back. This keeps the
    Transformer cost ~ O(K^2) with K ~ cr * H * W (a few tokens), matching the
    paper's K x C formulation instead of running attention over the full BEV.
  * CrossAtten over the dense BEV would be O((H*W)^2); we use a context-pooled
    cross-attention (queries = importance pixels, keys/values = an adaptive-pool
    summary of M_j) so it is tractable on the full feature map. This is the one
    approximation relative to eq. 12 and is flagged here.

The class is a drop-in subclass of ImportanceMapJSCC; everything else
(build_mask, channels, fusion, loss mask, diagnostics) is inherited unchanged.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from opencood.models.fuse_modules.importance_map_jscc_fuse import (
    ImportanceMapJSCC,
    ImportanceMapGenerator,
    build_channel,
)


# --------------------------------------------------------------------------- #
# 1. Importance-aware feature selection network (eq. 11-15)
# --------------------------------------------------------------------------- #
class SpatialAttention(nn.Module):
    """CBAM-style spatial attention applied to refine the importance map (eq. 13)."""
    def __init__(self, kernel_size=7):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size // 2, bias=False)

    def forward(self, feat):
        avg = feat.mean(dim=1, keepdim=True)
        mx, _ = feat.max(dim=1, keepdim=True)
        a = torch.sigmoid(self.conv(torch.cat([avg, mx], dim=1)))
        return a  # [N, 1, H, W] spatial attention weights


class CrossAttentionSelector(nn.Module):
    """
    Importance-aware feature selection network (paper Fig. 3, eq. 11-15).

    Returns a single-channel importance map P in [0, 1] of shape [N, 1, H, W],
    so it is a drop-in replacement for ``ImportanceMapGenerator`` and is consumed
    by the inherited ``build_mask`` (top-k / threshold token selection).
    """
    def __init__(self, in_channels, attn_dim=64, ctx_size=16):
        super().__init__()
        self.in_channels = int(in_channels)
        self.attn_dim = int(attn_dim)
        self.ctx_size = int(ctx_size)

        # eq. 11: Conv_gen -> importance map I_j (classification-branch style).
        self.conv_gen = ImportanceMapGenerator(in_channels)

        # eq. 12: cross-attention CrossAtten(I_j, M_j), context-pooled for the
        # dense BEV.  Q from I_j, K/V from a pooled summary of M_j.
        self.q_proj = nn.Conv2d(1, attn_dim, 1)
        self.k_proj = nn.Conv2d(in_channels, attn_dim, 1)
        self.v_proj = nn.Conv2d(in_channels, in_channels, 1)
        self.lam = nn.Parameter(torch.zeros(1))          # learnable residual gate
        self.conv_dow = nn.Conv2d(in_channels, in_channels, 1)

        # eq. 13: spatial attention on the importance map.
        self.spatial_atten = SpatialAttention(7)

    def forward(self, m_j):
        N, C, H, W = m_j.shape

        # eq. 11
        i_j = self.conv_gen(m_j)                          # [N, 1, H, W]

        # eq. 12 : context-pooled cross-attention
        ctx = F.adaptive_avg_pool2d(m_j, (self.ctx_size, self.ctx_size))  # [N,C,g,g]
        q = self.q_proj(i_j).flatten(2).transpose(1, 2)   # [N, HW, d]
        k = self.k_proj(ctx).flatten(2).transpose(1, 2)   # [N, g*g, d]
        v = self.v_proj(ctx).flatten(2).transpose(1, 2)   # [N, g*g, C]
        attn = torch.softmax(q @ k.transpose(1, 2) / math.sqrt(self.attn_dim), dim=-1)
        cross = (attn @ v).transpose(1, 2).view(N, C, H, W)            # [N, C, H, W]
        m_j_ref = self.conv_dow(m_j + self.lam * cross)               # M'_j

        # eq. 13
        i_j_ref = self.spatial_atten(m_j_ref)             # [N, 1, H, W]  I'_j

        # eq. 14 : P_keep = SoftMax(M'_j ⊙ I'_j) reduced to a per-pixel score.
        # We reduce channels by mean to obtain a single importance score per
        # spatial location, then map to [0, 1]; build_mask handles the eq. 15
        # thresholding / top-k selection.
        scored = (m_j_ref * i_j_ref).mean(dim=1, keepdim=True)        # [N, 1, H, W]
        p_keep = torch.sigmoid(scored)
        return p_keep


# --------------------------------------------------------------------------- #
# 2. Transformer + Channel-Attention semantic codec (eq. 16-20)
# --------------------------------------------------------------------------- #
class CAModule(nn.Module):
    """
    Channel-Attention module (paper Fig. 5, eq. 16-19).
    Input/Output: token features [K, d].  Global context is pooled over the K
    tokens; two linear heads produce a per-channel scale and offset:
        f_{k+1} = Linear(w) * f_k + Linear(w)            (eq. 19)
    """
    def __init__(self, dim):
        super().__init__()
        self.lin_avg = nn.Linear(dim, dim)
        self.lin_max = nn.Linear(dim, dim)
        self.scale = nn.Linear(2 * dim, dim)
        self.offset = nn.Linear(2 * dim, dim)

    def forward(self, f):                                 # f: [K, d]
        if f.shape[0] == 0:
            return f
        s_avg = self.lin_avg(f.mean(dim=0, keepdim=True))         # [1, d] (eq. 16)
        s_max = self.lin_max(f.max(dim=0, keepdim=True).values)   # [1, d] (eq. 17)
        w = torch.cat([s_avg, s_max], dim=-1)                     # [1, 2d] (eq. 18)
        return self.scale(w) * f + self.offset(w)                 # (eq. 19)


class TransformerModule(nn.Module):
    """Standard pre-norm Transformer block over the K selected tokens."""
    def __init__(self, dim, heads=4, mlp_ratio=2.0):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(dim, heads, batch_first=True)
        self.norm2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(
            nn.Linear(dim, int(dim * mlp_ratio)), nn.GELU(),
            nn.Linear(int(dim * mlp_ratio), dim),
        )

    def forward(self, f):                                 # f: [K, d]
        if f.shape[0] == 0:
            return f
        x = f.unsqueeze(0)                                # [1, K, d]
        h = self.norm1(x)
        x = x + self.attn(h, h, h, need_weights=False)[0]
        x = x + self.mlp(self.norm2(x))
        return x.squeeze(0)


class TransformerCACodec(nn.Module):
    """
    Deep-JSCC semantic codec with alternating Transformer + CA modules
    (paper Sec. III-C).  Operates on the K selected tokens per CAV row.

    Interface matches SemanticEncoderDecoder so it is a drop-in replacement:
        forward(x [N, C, H, W], mask [N, 1, H, W]) -> x_rec [N, C, H, W]
        set_snr(snr_db), self.channel
    """
    def __init__(self, in_channels, snr_db=10.0, channel_type='rayleigh',
                 c_complex=64, hidden=128, depth=2, heads=4):
        super().__init__()
        self.in_channels = int(in_channels)
        self.c_complex = int(c_complex)
        self.channel_type = str(channel_type).lower()

        self.embed = nn.Linear(in_channels, hidden)                 # embedding layer
        self.enc_tf = nn.ModuleList([TransformerModule(hidden, heads) for _ in range(depth)])
        self.enc_ca = nn.ModuleList([CAModule(hidden) for _ in range(depth)])
        self.to_symbols = nn.Linear(hidden, 2 * self.c_complex)     # conv -> complex

        self.channel = build_channel(self.channel_type, snr_db)

        self.from_symbols = nn.Linear(2 * self.c_complex, hidden)
        self.dec_tf = nn.ModuleList([TransformerModule(hidden, heads) for _ in range(depth)])
        self.dec_ca = nn.ModuleList([CAModule(hidden) for _ in range(depth)])
        self.head = nn.Linear(hidden, in_channels)                  # zero-pad / restore

    def set_snr(self, snr_db):
        self.channel.snr_db = float(snr_db)

    def _encode_decode_tokens(self, tokens):
        """tokens: [K, C] real -> reconstructed [K, C] real, through the channel."""
        if tokens.shape[0] == 0:
            return tokens
        h = self.embed(tokens)                            # [K, hidden]
        for tf, ca in zip(self.enc_tf, self.enc_ca):
            h = ca(tf(h))
        sym = self.to_symbols(h)                          # [K, 2c]
        c = self.c_complex
        T = torch.complex(sym[:, :c], sym[:, c:])         # [K, c] complex

        # average power constraint E|T|^2 = 1 over the transmitted tokens (eq. 20)
        power = (T.real ** 2 + T.imag ** 2).mean().clamp_min(1e-6)
        T = T / torch.complex(torch.sqrt(power), torch.zeros_like(power))

        T_hat = self.channel(T)                           # complex -> complex
        d = torch.cat([T_hat.real, T_hat.imag], dim=-1)   # [K, 2c]
        h = self.from_symbols(d)
        for tf, ca in zip(self.dec_tf, self.dec_ca):
            h = ca(tf(h))
        return self.head(h)                               # [K, C]

    def forward(self, x, mask=None):
        N, C, H, W = x.shape
        x_rec = torch.zeros_like(x)
        if mask is None:
            mask = torch.ones(N, 1, H, W, device=x.device, dtype=x.dtype)
        flat_mask = (mask.view(N, -1) > 0)
        x_flat = x.view(N, C, -1)
        for n in range(N):
            idx = flat_mask[n].nonzero(as_tuple=False).squeeze(-1)
            if idx.numel() == 0:
                continue
            tokens = x_flat[n][:, idx].transpose(0, 1)    # [K, C]
            rec = self._encode_decode_tokens(tokens)      # [K, C]
            x_rec.view(N, C, -1)[n][:, idx] = rec.transpose(0, 1)
        return x_rec


# --------------------------------------------------------------------------- #
# SComCP fusion = baseline pipeline + the two swapped modules
# --------------------------------------------------------------------------- #
class SComCPFuse(ImportanceMapJSCC):
    """
    Drop-in subclass of ImportanceMapJSCC.  Inherits build_mask, channels,
    multi-scale fusion, loss mask and all eval/diagnostic controls; only the
    importance-map selector and the semantic codec are replaced with the
    SComCP variants.  Configured via the same ``jscc`` args block plus an
    optional ``scomcp`` sub-block.
    """
    def __init__(self, args):
        super().__init__(args)

        scomcp_args = args.get('jscc', {}).get('scomcp', {})
        attn_dim = int(scomcp_args.get('attn_dim', 64))
        ctx_size = int(scomcp_args.get('ctx_size', 16))
        codec_hidden = int(scomcp_args.get('codec_hidden', 128))
        codec_depth = int(scomcp_args.get('codec_depth', 2))
        codec_heads = int(scomcp_args.get('codec_heads', 4))

        # Determine the feature channel count the same way the parent did.
        if self.multi_scale:
            in_channels = args['num_filters'][0]
        else:
            in_channels = args['in_channels']

        # Swap selector (eq. 11-15) and codec (eq. 16-20).
        self.importance_map = CrossAttentionSelector(
            in_channels, attn_dim=attn_dim, ctx_size=ctx_size)
        # Only build the transformer codec for real channels; perfect_comm /
        # ldpc / remote_zero eval controls bypass the codec entirely.
        if not (self.perfect_comm_control or self.ldpc_baseline_control
                or self.remote_zero_control):
            self.semantic_codec = TransformerCACodec(
                in_channels=in_channels, snr_db=self.snr_db,
                channel_type=self.channel_type, c_complex=self.c_complex,
                hidden=codec_hidden, depth=codec_depth, heads=codec_heads)

        # SComCP's selector is always the learned importance source.
        self.importance_source = 'learned'

        print('constructing SComCP fusion (cross-attn selector + transformer-CA codec)')
