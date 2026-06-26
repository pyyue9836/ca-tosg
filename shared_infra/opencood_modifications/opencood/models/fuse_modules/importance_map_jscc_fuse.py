#self+ ImportanceMapJSCC fuse module: importance mask selector + CNN JSCC codec + AWGN/Rayleigh/OFDM channel models
"""
Importance Map + JSCC fusion module for cooperative perception.

Paper-level pipeline (Sheng et al., WCSP 2023, "Semantic Communication for
Cooperative Perception Based on the Importance Map"):

    C_i = P(F_i)                      # importance map in [0, 1]
    M_i = F_i ⊙ C_i                   # importance-masked feature (sparse)
    T_i = Psi_s(M_i)                  # semantic encoder -> COMPLEX symbol stream
    T'_i = channel(T_i)               # AWGN / Rayleigh / OFDM multipath
    R_i = Psi_d(T'_i)                 # semantic decoder -> reconstructed feature
    D_i = chi(R_i, F'_ego)            # self-attention fusion
    Y_i = Gamma(D_i)                  # detection head

Design notes (this rewrite):
  * The semantic codec produces a *complex* symbol tensor with an average-power
    constraint, matching the paper's JSCC formulation, and the channel operates
    directly on the complex symbols.
  * Spatial token selection (importance mask) is DECOUPLED from the channel-use
    compression rate.  Spatial sparsity follows a where2comm-style confidence
    threshold (so cooperation can approach the upper bound), while the ~1e-2
    channel-use compression comes from the encoder mapping C=64 feature channels
    to c_complex complex symbols.  The two combine into an effective payload CR
    of  rho_spatial * c_complex / 64, which is reported honestly.
  * SNR can be randomized per training step (DeepJSCC practice) so a single
    per-channel model degrades gracefully across SNR instead of being flat.
The separate-coding (LDPC + QAM) baseline is NOT implemented here; it lives on
the where2comm perception host (see where2comm_fuse.py link-erasure), so that at
high SNR it can recover the full upper bound and exhibit a true waterfall cliff.
"""

import math
import random

import torch
import torch.nn as nn
import torch.nn.functional as F

from opencood.models.fuse_modules.self_attn import ScaledDotProductAttention


# --------------------------------------------------------------------------- #
# Fusion / importance-map building blocks
# --------------------------------------------------------------------------- #
class AttentionFusion(nn.Module):
    def __init__(self, feature_dim):
        super(AttentionFusion, self).__init__()
        self.att = ScaledDotProductAttention(feature_dim)

    def forward(self, x):
        cav_num, C, H, W = x.shape
        x = x.view(cav_num, C, -1).permute(2, 0, 1)
        x = self.att(x, x, x)
        x = x.permute(1, 2, 0).view(cav_num, C, H, W)[0]
        return x


class ImportanceMapGenerator(nn.Module):
    """
    Learned spatial importance map C = P(F) in [0, 1].
    Input:  [N, C, H, W]
    Output: [N, 1, H, W]
    """
    def __init__(self, in_channels, hidden_channels=None):
        super(ImportanceMapGenerator, self).__init__()
        if hidden_channels is None:
            hidden_channels = max(in_channels // 4, 16)
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(hidden_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_channels, 1, kernel_size=1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)


# --------------------------------------------------------------------------- #
# Complex-symbol wireless channels.  Every channel takes a complex tensor
# T [N, c_complex, H, W] (average power ~1) and returns a complex tensor of the
# same shape.  snr_db is a mutable float attribute so it can be swept / randomized.
# --------------------------------------------------------------------------- #
class NoiseFreeChannel(nn.Module):
    """Perfect channel (identity).  T'_i = T_i.  The JSCC ceiling."""
    def __init__(self, snr_db=60.0, noise_during_eval=True):
        super(NoiseFreeChannel, self).__init__()
        self.snr_db = float(snr_db)
        self.noise_during_eval = bool(noise_during_eval)

    def forward(self, T):
        return T


class ComplexAWGNChannel(nn.Module):
    """y = T + n,  n ~ CN(0, N0),  N0 = 1 / snr_linear  (power-normalized T)."""
    def __init__(self, snr_db=10.0, noise_during_eval=True):
        super(ComplexAWGNChannel, self).__init__()
        self.snr_db = float(snr_db)
        self.noise_during_eval = bool(noise_during_eval)
        self.last_noise_power = None

    def forward(self, T):
        if (not self.training) and (not self.noise_during_eval):
            return T
        snr_linear = 10.0 ** (self.snr_db / 10.0)
        n0 = 1.0 / snr_linear
        std = math.sqrt(n0 / 2.0)
        noise = torch.complex(torch.randn_like(T.real) * std,
                              torch.randn_like(T.imag) * std)
        self.last_noise_power = float(n0)
        return T + noise


class ComplexRayleighChannel(nn.Module):
    """
    y = h * T + n,  h ~ CN(0, 1)  (E|h|^2 = 1),  n ~ CN(0, N0).
    Perfect-CSI equalization with a small Tikhonov term for deep-fade stability:
        T_hat = conj(h) * y / (|h|^2 + eps)   (eps -> 0 gives true ZF y/h).
    """
    def __init__(self, snr_db=10.0, noise_during_eval=True, eps=1e-2):
        super(ComplexRayleighChannel, self).__init__()
        self.snr_db = float(snr_db)
        self.noise_during_eval = bool(noise_during_eval)
        self.eps = float(eps)
        self.last_h_abs_mean = None

    def forward(self, T):
        if (not self.training) and (not self.noise_during_eval):
            return T
        snr_linear = 10.0 ** (self.snr_db / 10.0)
        n0 = 1.0 / snr_linear
        std = math.sqrt(n0 / 2.0)

        h = torch.complex(torch.randn_like(T.real),
                          torch.randn_like(T.imag)) / math.sqrt(2.0)
        noise = torch.complex(torch.randn_like(T.real) * std,
                              torch.randn_like(T.imag) * std)
        y = h * T + noise
        h_abs2 = (h.real ** 2 + h.imag ** 2)
        T_hat = torch.conj(h) * y / (h_abs2 + self.eps)
        self.last_h_abs_mean = float(h_abs2.sqrt().mean().detach().cpu().item())
        return T_hat


class ComplexOFDMChannel(nn.Module):
    """
    Time-varying multipath OFDM channel (paper eq. 2-3):
        y_{i,k} = h_{i,k} x_{i,k} + n,
        h_{i,k} = sum_m a_m(i) exp(-j 2 pi k tau_m / K).
    Pilot-based channel estimation + perfect-CSI-style ZF equalization.
    Operates directly on the complex symbol tensor.
    """
    def __init__(self, snr_db=10.0, n_subcarriers=64, n_taps=4, max_delay=8,
                 noise_during_eval=True, eps=1e-2):
        super(ComplexOFDMChannel, self).__init__()
        self.snr_db = float(snr_db)
        self.n_subcarriers = int(n_subcarriers)
        self.n_taps = int(n_taps)
        self.max_delay = int(max_delay)
        self.noise_during_eval = bool(noise_during_eval)
        self.eps = float(eps)
        self.last_h_abs_mean = None

    def _channel_response(self, device, dtype, N, n_symbols, K):
        delays = torch.arange(self.n_taps, device=device, dtype=dtype)
        delays = torch.clamp(delays, 0, max(self.max_delay, 1))
        pdp = torch.exp(-delays / max(float(self.n_taps), 1.0))
        pdp = pdp / torch.sum(pdp)
        ar = torch.randn(N, n_symbols, self.n_taps, device=device, dtype=dtype)
        ai = torch.randn(N, n_symbols, self.n_taps, device=device, dtype=dtype)
        taps = torch.complex(ar, ai) * torch.sqrt(pdp.view(1, 1, -1) / 2.0)
        k = torch.arange(K, device=device, dtype=dtype).view(1, 1, 1, K)
        tau = delays.view(1, 1, self.n_taps, 1)
        phase = -2.0 * math.pi * k * tau / float(K)
        exp_term = torch.complex(torch.cos(phase), torch.sin(phase))
        H_f = torch.sum(taps.unsqueeze(-1) * exp_term, dim=2)  # [N, n_symbols, K]
        return H_f

    def forward(self, T):
        if (not self.training) and (not self.noise_during_eval):
            return T
        N, C, H, W = T.shape
        device, rdtype = T.device, T.real.dtype
        x = T.reshape(N, -1)
        K = self.n_subcarriers
        pad_len = (K - (x.shape[1] % K)) % K
        if pad_len > 0:
            x = torch.cat([x, torch.zeros(N, pad_len, device=device, dtype=x.dtype)], dim=1)
        n_symbols = x.shape[1] // K
        X = x.view(N, n_symbols, K)

        H_f = self._channel_response(device, rdtype, N, n_symbols, K)

        snr_linear = 10.0 ** (self.snr_db / 10.0)
        n0 = 1.0 / snr_linear
        std = math.sqrt(n0 / 2.0)
        noise_data = torch.complex(torch.randn_like(X.real) * std,
                                   torch.randn_like(X.real) * std)
        noise_pilot = torch.complex(torch.randn_like(X.real) * std,
                                    torch.randn_like(X.real) * std)

        # Pilot estimation (all-ones pilot) then ZF equalization.
        H_hat = H_f + noise_pilot
        Y = H_f * X + noise_data
        H_abs2 = (H_hat.real ** 2 + H_hat.imag ** 2)
        X_hat = torch.conj(H_hat) * Y / (H_abs2 + self.eps)

        x_hat = X_hat.reshape(N, -1)
        if pad_len > 0:
            x_hat = x_hat[:, :-pad_len]
        self.last_h_abs_mean = float(torch.abs(H_f).mean().detach().cpu().item())
        return x_hat.view(N, C, H, W)


def build_channel(channel_type, snr_db):
    """Dispatch channel_type -> complex channel module."""
    ct = str(channel_type).lower()
    if ct == 'awgn':
        return ComplexAWGNChannel(snr_db=snr_db)
    if ct == 'rayleigh':
        return ComplexRayleighChannel(snr_db=snr_db)
    if ct in ['ofdm', 'ofdm_multipath', 'multipath_ofdm']:
        return ComplexOFDMChannel(snr_db=snr_db)
    # Diagnostic / non-JSCC control types do not use the codec channel; give a
    # no-op so construction never fails.
    return NoiseFreeChannel(snr_db=snr_db)


# --------------------------------------------------------------------------- #
# Complex-symbol semantic encoder/decoder (DeepJSCC autoencoder)
# --------------------------------------------------------------------------- #
class SemanticEncoderDecoder(nn.Module):
    """
    Psi_s: real feature [N, C, H, W] -> complex symbols T [N, c_complex, H, W]
    channel(T)
    Psi_d: complex symbols -> reconstructed real feature [N, C, H, W]

    Power normalization enforces E[|T|^2] = 1 over the *transmitted* tokens
    (computed per sample over the kept mask) so the SNR definition is correct
    once the importance mask is sparse.
    """
    def __init__(self, in_channels, latent_dim=64, snr_db=10.0,
                 channel_type='awgn', c_complex=16, hidden=128):
        super(SemanticEncoderDecoder, self).__init__()
        self.channel_type = str(channel_type).lower()
        self.c_complex = int(c_complex)
        self.in_channels = int(in_channels)

        self.encoder = nn.Sequential(
            nn.Conv2d(in_channels, hidden, kernel_size=1, bias=False),
            nn.BatchNorm2d(hidden), nn.PReLU(),
            nn.Conv2d(hidden, hidden, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(hidden), nn.PReLU(),
            nn.Conv2d(hidden, 2 * self.c_complex, kernel_size=1),
        )
        self.channel = build_channel(self.channel_type, snr_db)
        self.decoder = nn.Sequential(
            nn.Conv2d(2 * self.c_complex, hidden, kernel_size=1, bias=False),
            nn.BatchNorm2d(hidden), nn.PReLU(),
            nn.Conv2d(hidden, hidden, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(hidden), nn.PReLU(),
            nn.Conv2d(hidden, in_channels, kernel_size=1),
        )

    def set_snr(self, snr_db):
        self.channel.snr_db = float(snr_db)

    def forward(self, x, mask=None):
        c = self.c_complex
        e = self.encoder(x)                                  # [N, 2c, H, W]
        T = torch.complex(e[:, :c], e[:, c:])                # [N, c, H, W] complex

        # Average-power constraint E|T|^2 = 1, per sample over kept tokens.
        power_map = (T.real ** 2 + T.imag ** 2)              # [N, c, H, W]
        if mask is not None:
            m = (mask > 0).to(power_map.dtype)               # [N, 1, H, W]
            denom = m.sum(dim=(1, 2, 3), keepdim=True) * c + 1e-6
            power = (power_map * m).sum(dim=(1, 2, 3), keepdim=True) / denom
        else:
            power = power_map.mean(dim=(1, 2, 3), keepdim=True)
        power = power.clamp_min(1e-6)
        scale = torch.sqrt(power)
        T = T / torch.complex(scale, torch.zeros_like(scale))

        T_hat = self.channel(T)                              # complex -> complex
        d = torch.cat([T_hat.real, T_hat.imag], dim=1)       # [N, 2c, H, W]
        x_rec = self.decoder(d)
        return x_rec


# --------------------------------------------------------------------------- #
# Importance-map JSCC fusion
# --------------------------------------------------------------------------- #
class ImportanceMapJSCC(nn.Module):
    def __init__(self, args):
        super(ImportanceMapJSCC, self).__init__()

        self.fully = args.get('fully', False)
        self.multi_scale = args.get('multi_scale', True)

        jscc_args = args.get('jscc', {})
        self.cr = float(jscc_args.get('cr', 0.005))
        self.snr_db = float(jscc_args.get('snr_db', 10.0))
        self.latent_dim = int(jscc_args.get('latent_dim', 64))
        self.c_complex = int(jscc_args.get('c_complex', 16))
        self.channel_type = str(jscc_args.get('channel_type', 'awgn')).lower()
        self.importance_source = str(jscc_args.get('importance_source', 'psm')).lower()
        if bool(jscc_args.get('use_psm_importance', False)):
            self.importance_source = 'psm'

        # Spatial masking mode: 'threshold' (where2comm-style, decoupled from CR)
        # or 'topk' (strict paper CR on spatial tokens).
        self.mask_mode = str(jscc_args.get('mask_mode', 'threshold')).lower()
        self.comm_threshold = float(jscc_args.get('comm_threshold', 0.01))

        # Per-step SNR randomization range for training (DeepJSCC). If both None,
        # the fixed snr_db is used.
        self.train_snr_low = jscc_args.get('train_snr_low', None)
        self.train_snr_high = jscc_args.get('train_snr_high', None)
        if self.train_snr_low is not None:
            self.train_snr_low = float(self.train_snr_low)
        if self.train_snr_high is not None:
            self.train_snr_high = float(self.train_snr_high)

        # Diagnostic controls.
        self.identity_channel_control = self.channel_type in [
            'identity', 'no_channel', 'bypass_codec']
        # Paper "upper bound" = perfect communication: the CR-masked remote feature
        # M is delivered to fusion with an ideal link AND no codec distortion
        # (R = M exactly). This isolates the perception+masking ceiling that the
        # JSCC curve approaches as SNR -> inf; the residual JSCC gap is codec loss.
        self.perfect_comm_control = self.channel_type in [
            'perfect_comm', 'perfect', 'upper_bound']
        self.remote_zero_control = self.channel_type in ['remote_zero', 'drop_remote', 'zero']

        # Separate-coding (LDPC + QAM) baseline hosted on THIS perception net
        # (eval only): replace the analog codec with 8-bit quantization of M
        # + per-token block erasure at the calibrated BLER(snr). Valid because
        # the trained codec is near-lossless (Psi_d(perfect) ~= M), so feeding
        # quantized M to the same fusion matches the JSCC ceiling at high SNR
        # and cliffs at low SNR -- the paper's separate-coding behaviour, on a
        # single shared perception ceiling.
        self.ldpc_baseline_control = self.channel_type in [
            'ldpc16qam', 'ldpc_16qam', 'ldpc256qam', 'ldpc_256qam']
        self.ldpc_qam_order = 16 if self.channel_type in ['ldpc16qam', 'ldpc_16qam'] else 256
        # The digital baseline cliffs at low SNR (BLER->1, remote tokens erased ->
        # ego-only) and converges to the perception upper bound at high SNR
        # (BLER->0, quantized feature delivered losslessly) -- the paper's
        # separate-coding waterfall. The two QAM orders differ only in the
        # waterfall position (256QAM needs higher SNR), encoded in the BLER table.
        self._bler_xs = None
        self._bler_ys = None
        if self.ldpc_baseline_control:
            self._load_bler_table(jscc_args.get(
                'bler_csv',
                'experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv'))

        # Diagnostic / reporting attributes consumed by the model wrapper.
        self.last_rec_loss = None
        self.last_paper_cr_target = None
        self.last_paper_cr_actual = None
        self.last_paper_k = None
        self.last_paper_hw = None
        self.last_importance_score = None
        self.last_importance_mask = None
        self.last_com_including_ego = None
        self.last_remote_payload_cr_actual = None
        self.last_remote_payload_tokens = None
        self.last_remote_payload_total_tokens = None
        self.last_importance_source = None
        self._loss_mask = None

        if self.fully:
            print('constructing a fully connected importance-map JSCC graph')
        else:
            print('constructing a partially connected importance-map JSCC graph')

        if self.multi_scale:
            layer_nums = args['layer_nums']
            num_filters = args['num_filters']
            self.num_levels = len(layer_nums)
            self.fuse_modules = nn.ModuleList()
            for idx in range(self.num_levels):
                self.fuse_modules.append(AttentionFusion(num_filters[idx]))
            first_channels = num_filters[0]
            self.importance_map = ImportanceMapGenerator(first_channels)
            self.semantic_codec = SemanticEncoderDecoder(
                in_channels=first_channels, latent_dim=self.latent_dim,
                snr_db=self.snr_db, channel_type=self.channel_type,
                c_complex=self.c_complex)
        else:
            in_channels = args['in_channels']
            self.fuse_modules = AttentionFusion(in_channels)
            self.importance_map = ImportanceMapGenerator(in_channels)
            self.semantic_codec = SemanticEncoderDecoder(
                in_channels=in_channels, latent_dim=self.latent_dim,
                snr_db=self.snr_db, channel_type=self.channel_type,
                c_complex=self.c_complex)

        # Fixed Gaussian smoothing kernel for confidence maps (mirror where2comm).
        self.register_buffer('gauss_kernel', self._make_gauss_kernel(5, 1.0))

    @staticmethod
    def _make_gauss_kernel(k_size, sigma):
        center = k_size // 2
        ax = torch.arange(k_size).float() - center
        xx, yy = torch.meshgrid(ax, ax, indexing='ij')
        kernel = torch.exp(-(xx ** 2 + yy ** 2) / (2.0 * sigma ** 2))
        kernel = kernel / kernel.sum()
        return kernel.view(1, 1, k_size, k_size)

    def set_snr(self, snr_db):
        self.snr_db = float(snr_db)
        self.semantic_codec.set_snr(snr_db)

    def _load_bler_table(self, csv_path):
        import csv as _csv
        qam = self.ldpc_qam_order
        xs, ys = [], []
        with open(csv_path) as f:
            for row in _csv.DictReader(f):
                if int(float(row['qam'])) == qam:
                    xs.append(float(row['snr_db']))
                    ys.append(float(row['bler']))
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        self._bler_xs = [xs[i] for i in order]
        self._bler_ys = [ys[i] for i in order]

    def _bler(self):
        xs, ys = self._bler_xs, self._bler_ys
        snr = self.snr_db
        if snr <= xs[0]:
            return ys[0]
        if snr >= xs[-1]:
            return ys[-1]
        for i in range(len(xs) - 1):
            if xs[i] <= snr <= xs[i + 1]:
                t = (snr - xs[i]) / (xs[i + 1] - xs[i])
                return ys[i] + t * (ys[i + 1] - ys[i])
        return ys[-1]

    def _separate_coding(self, x_masked, x_original, record_len, num_bits=8, clip=4.0):
        """8-bit uniform quantization of M + per-token block erasure at BLER(snr)."""
        self.last_rec_loss = x_masked.new_zeros(())
        bler = self._bler()
        qmax = (1 << num_bits) - 1
        xc = torch.clamp(x_masked, -clip, clip)
        q = torch.round((xc + clip) / (2.0 * clip) * qmax)
        x = q / qmax * (2.0 * clip) - clip          # dequantized M
        start = 0
        for length in record_len.tolist():
            length = int(length)
            if length > 1:
                rf = x[start + 1:start + length]
                shp = (rf.shape[0], 1, rf.shape[2], rf.shape[3])
                # block erasure at BLER(snr): a failed block -> token zeroed.
                # At high SNR BLER->0 the quantized feature is delivered losslessly,
                # so the digital baseline converges to the perception upper bound
                # (waterfall behaviour), matching the paper. No artificial
                # equal-bandwidth token dropping.
                fail = (torch.rand(shp, device=x.device) < bler).float()
                x[start + 1:start + length] = rf * (1.0 - fail)
            x[start] = x_original[start]             # ego local feature, lossless
            start += length
        return x

    def regroup(self, x, record_len):
        cum_sum_len = torch.cumsum(record_len, dim=0)
        split_x = torch.tensor_split(x, cum_sum_len[:-1].cpu())
        return split_x

    def make_importance_maps(self, x, psm_single=None):
        learned_maps = self.importance_map(x)
        if self.importance_source in ['learned', 'paper', 'map']:
            importance_maps = learned_maps
        elif self.importance_source in ['psm', 'where2comm']:
            if psm_single is None:
                raise ValueError('psm importance requested but psm_single is None')
            importance_maps = torch.sigmoid(psm_single).amax(dim=1, keepdim=True)
            if importance_maps.shape[-2:] != x.shape[-2:]:
                importance_maps = F.interpolate(importance_maps, size=x.shape[-2:],
                                                mode='bilinear', align_corners=False)
        elif self.importance_source in ['hybrid', 'learned_psm', 'psm_learned']:
            if psm_single is None:
                importance_maps = learned_maps
            else:
                psm_maps = torch.sigmoid(psm_single).amax(dim=1, keepdim=True)
                if psm_maps.shape[-2:] != x.shape[-2:]:
                    psm_maps = F.interpolate(psm_maps, size=x.shape[-2:],
                                             mode='bilinear', align_corners=False)
                importance_maps = learned_maps * psm_maps
        else:
            raise ValueError(f"Unsupported importance_source: {self.importance_source}")
        self.last_importance_source = self.importance_source
        return importance_maps

    def _smooth(self, maps):
        return F.conv2d(maps, self.gauss_kernel, padding=self.gauss_kernel.shape[-1] // 2)

    def build_mask(self, importance_maps, record_len):
        """
        Spatial token selection for the importance-map channel.

        train  : straight-through top-k around the target CR so learned importance
                 maps receive gradients while the forward payload is sparse.
        eval   : strict top-k CR (mask_mode='topk') or threshold diagnostics.

        Returns (mask, communication_rate). Side effect: stores self._loss_mask
        (remote kept tokens only, ego rows zeroed) for the reconstruction loss,
        plus paper-CR diagnostics.
        """
        N, _, H, W = importance_maps.shape
        smoothed = self._smooth(importance_maps)

        if self.training:
            mask_flat = torch.zeros(N, H * W, device=importance_maps.device,
                                    dtype=importance_maps.dtype)
            flat = smoothed.view(N, H * W)
            lo = max(1, int(H * W * self.cr * 0.5))
            hi = max(lo + 1, int(H * W * self.cr * 2.0))
            for n in range(N):
                k = random.randint(lo, hi)
                _, idx = torch.topk(flat[n], k=k, sorted=False)
                mask_flat[n, idx] = 1.0
            hard_mask = mask_flat.view(N, 1, H, W)
            soft_map = smoothed.clamp(0.0, 1.0)
            paper_mask = hard_mask + soft_map - soft_map.detach()
        elif self.mask_mode == 'topk':
            k = max(1, int(H * W * self.cr))
            _, indices = torch.topk(smoothed.view(N, -1), k=k, dim=1, sorted=False)
            mask_flat = torch.zeros(N, H * W, device=importance_maps.device,
                                    dtype=importance_maps.dtype)
            mask_flat.scatter_(1, indices, 1.0)
            paper_mask = mask_flat.view(N, 1, H, W)
        else:  # threshold
            paper_mask = (smoothed > self.comm_threshold).to(importance_maps.dtype)

        paper_cr_actual = paper_mask.mean()

        # Feature-multiply mask: ego rows kept full (local information).
        mask = paper_mask.clone()
        # Reconstruction-loss mask: remote kept tokens only (ego rows zeroed).
        loss_mask = paper_mask.clone()
        start = 0
        for length in record_len.tolist():
            mask[start] = 1.0
            loss_mask[start] = 0.0
            start += int(length)
        com_including_ego = mask.mean()

        # Remote payload statistics.
        remote_masks = []
        start = 0
        for length in record_len.tolist():
            cav_num = int(length)
            if cav_num > 1:
                remote_masks.append(paper_mask[start + 1:start + cav_num])
            start += cav_num
        if remote_masks:
            remote_mask = torch.cat(remote_masks, dim=0)
            remote_payload_cr = remote_mask.mean()
            remote_payload_tokens = remote_mask.sum()
            remote_payload_total_tokens = torch.tensor(
                float(remote_mask.numel()), device=importance_maps.device,
                dtype=importance_maps.dtype)
        else:
            remote_payload_cr = paper_cr_actual.new_tensor(0.0)
            remote_payload_tokens = paper_cr_actual.new_tensor(0.0)
            remote_payload_total_tokens = paper_cr_actual.new_tensor(0.0)

        self.last_paper_cr_target = float(self.cr)
        self.last_paper_cr_actual = paper_cr_actual.detach()
        self.last_paper_k = int(paper_mask.sum().item() / max(N, 1))
        self.last_paper_hw = int(H * W)
        self.last_importance_score = importance_maps.detach()
        self.last_importance_mask = paper_mask.detach()
        self.last_com_including_ego = com_including_ego.detach()
        self.last_remote_payload_cr_actual = remote_payload_cr.detach()
        self.last_remote_payload_tokens = remote_payload_tokens.detach()
        self.last_remote_payload_total_tokens = remote_payload_total_tokens.detach()
        self._loss_mask = loss_mask

        return mask, paper_cr_actual

    def apply_jscc_to_non_ego(self, x_masked, x_original, record_len, mask):
        """Run the semantic codec on the masked feature, restore ego rows."""
        # Per-step SNR randomization during training.
        if self.training and (self.train_snr_low is not None) \
                and (self.train_snr_high is not None):
            snr = random.uniform(self.train_snr_low, self.train_snr_high)
            self.semantic_codec.set_snr(snr)

        # Perfect-communication upper bound: deliver M losslessly (R = M, no codec,
        # no channel), restore ego rows. This is the paper's "upper bound".
        if self.perfect_comm_control:
            self.last_rec_loss = x_masked.new_zeros(())
            x_out = x_masked.clone()
            start = 0
            for length in record_len.tolist():
                x_out[start] = x_original[start]
                start += int(length)
            return x_out

        # Separate-coding (LDPC+QAM) baseline on this perception net.
        if self.ldpc_baseline_control:
            return self._separate_coding(x_masked, x_original, record_len)

        # Ego-only diagnostic: keep ego rows, zero the remote (non-ego) rows.
        if self.remote_zero_control:
            self.last_rec_loss = x_masked.new_zeros(())
            x_out = torch.zeros_like(x_original)
            start = 0
            for length in record_len.tolist():
                x_out[start] = x_original[start]
                start += int(length)
            return x_out

        x_rec = self.semantic_codec(x_masked, mask=mask)

        # Reconstruction loss over remote kept tokens only.
        loss_mask = self._loss_mask
        if loss_mask is not None and loss_mask.sum() > 0:
            C = x_rec.shape[1]
            diff2 = (x_rec - x_masked.detach()) ** 2 * loss_mask
            self.last_rec_loss = diff2.sum() / (loss_mask.sum() * C + 1e-6)
        else:
            self.last_rec_loss = F.mse_loss(x_rec, x_masked.detach())

        x_out = x_rec.clone()
        start = 0
        for length in record_len.tolist():
            x_out[start] = x_original[start]
            start += int(length)
        return x_out

    def _communicate(self, x, psm_single, record_len):
        """Importance masking + JSCC codec at backbone block 0."""
        importance_maps = self.make_importance_maps(x, psm_single)
        mask, communication_rates = self.build_mask(importance_maps, record_len)
        if x.shape[-1] != mask.shape[-1] or x.shape[-2] != mask.shape[-2]:
            mask = F.interpolate(mask, size=(x.shape[-2], x.shape[-1]),
                                 mode='nearest')
        x_original = x
        x_masked = x * mask
        x = self.apply_jscc_to_non_ego(x_masked, x_original, record_len, mask)
        return x, communication_rates

    def forward(self, x, psm_single, record_len, pairwise_t_matrix, backbone=None):
        B = pairwise_t_matrix.shape[0]

        if self.multi_scale:
            ups = []
            for i in range(self.num_levels):
                x = backbone.blocks[i](x)
                if i == 0:
                    if self.fully:
                        communication_rates = torch.tensor(1.0, device=x.device)
                    else:
                        x, communication_rates = self._communicate(x, psm_single, record_len)

                batch_node_features = self.regroup(x, record_len)
                x_fuse = []
                for b in range(B):
                    neighbor_feature = batch_node_features[b]
                    x_fuse.append(self.fuse_modules[i](neighbor_feature))
                x_fuse = torch.stack(x_fuse)

                if len(backbone.deblocks) > 0:
                    ups.append(backbone.deblocks[i](x_fuse))
                else:
                    ups.append(x_fuse)

            if len(ups) > 1:
                x_fuse = torch.cat(ups, dim=1)
            else:
                x_fuse = ups[0]
            if len(backbone.deblocks) > self.num_levels:
                x_fuse = backbone.deblocks[-1](x_fuse)
        else:
            if self.fully:
                communication_rates = torch.tensor(1.0, device=x.device)
            else:
                x, communication_rates = self._communicate(x, psm_single, record_len)
            batch_node_features = self.regroup(x, record_len)
            x_fuse = []
            for b in range(B):
                neighbor_feature = batch_node_features[b]
                x_fuse.append(self.fuse_modules(neighbor_feature))
            x_fuse = torch.stack(x_fuse)

        return x_fuse, communication_rates
