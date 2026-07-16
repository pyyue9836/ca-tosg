#self+ Structural attribution for the collaboration-harm footnote (supervisor point 4, 2026-07-16).
# Replaces the payload-derived ~89% with a DIRECT count from the deployed selector's predictions (same
# selector as the 0/0/0 C256 count), and TESTS the structural claim: on frames where the selector requests L,
# its realised output is frame-identical to Fixed-L, so the paired (CA-TOSG - Fixed-L) difference arises
# ENTIRELY on the C16-request frames. Stratum = test Easy (top tercile of ego object-level late_f1), under the
# deterministic reliable channel (AWGN, 16 dB), matching a2_difficulty_reliable_v3.csv.
import os, pickle, numpy as np, pandas as pd
P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(P1, 'data'); BLER = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
RF = pickle.load(open(f'{D}/selector_rf.pkl', 'rb')); FEAT = list(RF.feature_names_in_)
_T = pd.read_csv(BLER)
def bler_frame(snr, qam, ch):
    s = _T[(_T.qam == qam) & (_T.channel == ch)].sort_values('esno_db')
    return float(np.interp(snr, s.esno_db, s.bler_frame, left=1.0, right=float(s.bler_frame.iloc[-1])))

d = pd.read_csv(f'{D}/dataset_test_v3.csv')
late, comp, ego = d.late_f1.to_numpy(), d.compressed_f1.to_numpy(), d.ego_f1.to_numpy()
q = np.quantile(late, [1/3, 2/3])
easy = late > q[1]                                   # Easy = top tercile of ego object-level F1 (a2 def)
SNR = 16.0; b16 = bler_frame(SNR, 16, 'awgn')        # reliable channel: deterministic AWGN 16 dB
dd = d.copy(); dd['est_snr_db'] = SNR; dd['channel_is_rayleigh'] = 0
act = np.asarray(RF.predict(dd[FEAT]))               # deployed selector action per frame (deterministic CSI)

# per-frame realised F1: Fixed-L = late (object-level, delivered); CA-TOSG = late if L else eff_C16 at 16 dB
fixedL = late.copy()
catosg = np.where(act == 'L', late, comp * (1 - b16) + ego * b16)
m = easy                                             # restrict to the Easy stratum
n = int(m.sum()); n_c16 = int((act[m] == 'C16').sum()); n_l = int((act[m] == 'L').sum())
# STRUCTURAL TEST: on L-frames within the stratum, CA-TOSG realised == Fixed-L realised (frame-identical)?
L_frames = m & (act == 'L')
l_frame_max_abs_diff = float(np.abs(catosg[L_frames] - fixedL[L_frames]).max()) if L_frames.any() else 0.0
gain = float((catosg[m] - fixedL[m]).mean())
# does the paired difference arise ENTIRELY on C16 frames? (sum of diffs on L-frames == 0)
diff_sum_on_L = float((catosg[L_frames] - fixedL[L_frames]).sum())
diff_sum_on_C16 = float((catosg[m & (act == 'C16')] - fixedL[m & (act == 'C16')]).sum())
print(f"stratum test Easy @ reliable AWGN 16 dB: n={n}  (a2 CSV n=713)  b16(16,awgn)={b16:.4g}")
print(f"selector action share: C16 = {n_c16}/{n} = {n_c16/n:.4f}   L = {n_l}/{n} = {n_l/n:.4f}")
print(f"mean(CA-TOSG - Fixed-L) over stratum = {gain:.4f}   (a2 CSV gain -0.0147)")
print(f"STRUCTURAL: max|CA-TOSG - Fixed-L| on L-frames = {l_frame_max_abs_diff:.2e}  (0 => frame-identical)")
print(f"  paired-diff sum on L-frames = {diff_sum_on_L:.4f} ; on C16-frames = {diff_sum_on_C16:.4f}")
structural = bool(l_frame_max_abs_diff < 1e-9)
print(f"STRUCTURAL CLAIM HOLDS (diff arises entirely on C16 frames) = {structural}")
# EPISTEMIC NOTE (supervisor 2026-07-16): n_C16 + n_L == n implies ZERO C256 on this stratum. That zero is
# the SAME SOURCE as the deployment 0/0/0 C256 count -- both come from this one classifier (selector_rf.pkl,
# class set {L, C16}), so it is an internal consistency check, NOT independent corroboration. Record as
# consistency, not independence.
c256_zero = (n_c16 + n_l == n)
print(f"n_C16+n_L == n ({n_c16}+{n_l}=={n}) -> zero C256 on stratum = {c256_zero}; SAME SOURCE as the "
      f"deployment 0/0/0 (one classifier, class set {sorted(RF.classes_)}) -> consistency, not independent evidence.")
pd.DataFrame([dict(stratum='test_Easy_reliable_awgn16', n=n, n_C16=n_c16, n_L=n_l,
                   frac_C16=round(n_c16/n, 4), mean_gain=round(gain, 4),
                   L_frame_max_abs_diff=l_frame_max_abs_diff, structural_holds=structural,
                   C256_zero_same_source_as_deployment_000=c256_zero)]
             ).to_csv(os.path.join(P1, 'results/harm_stratum_structural.csv'), index=False)
