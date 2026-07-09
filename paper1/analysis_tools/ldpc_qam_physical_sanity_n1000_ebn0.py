import numpy as np
import pandas as pd
from pathlib import Path
from scipy.special import logsumexp


def gray_to_binary_int(g):
    b = int(g)
    while g > 0:
        g >>= 1
        b ^= g
    return b


def bits_to_int(bits):
    v = 0
    for bit in bits:
        v = (v << 1) | int(bit)
    return v


def qam_constellation(M):
    m = int(np.sqrt(M))
    assert m * m == M

    bits_per_symbol = int(np.log2(M))
    bits_axis = bits_per_symbol // 2

    const = []
    bit_table = []

    for idx in range(M):
        bits = [(idx >> (bits_per_symbol - 1 - i)) & 1 for i in range(bits_per_symbol)]

        i_gray = bits_to_int(bits[:bits_axis])
        q_gray = bits_to_int(bits[bits_axis:])

        i_bin = gray_to_binary_int(i_gray)
        q_bin = gray_to_binary_int(q_gray)

        i_level = 2 * i_bin - (m - 1)
        q_level = 2 * q_bin - (m - 1)

        const.append(i_level + 1j * q_level)
        bit_table.append(bits)

    const = np.asarray(const, dtype=np.complex64)
    const = const / np.sqrt(np.mean(np.abs(const) ** 2))
    bit_table = np.asarray(bit_table, dtype=np.int8)

    return const, bit_table


def qam_modulate(bits, M):
    const, bit_table = qam_constellation(M)
    bps = int(np.log2(M))

    pad_len = (-len(bits)) % bps

    if pad_len > 0:
        bits = np.concatenate([bits, np.zeros(pad_len, dtype=np.int8)])

    groups = bits.reshape(-1, bps)
    mapper = {tuple(bit_table[i].tolist()): i for i in range(M)}
    indices = np.array([mapper[tuple(g.tolist())] for g in groups], dtype=np.int64)

    return const[indices], pad_len


def qam_demod_llr(y, M, noise_var):
    const, bit_table = qam_constellation(M)
    bps = int(np.log2(M))

    dist = np.abs(y[:, None] - const[None, :]) ** 2
    metric = -dist / max(noise_var, 1e-12)

    llrs = np.zeros((len(y), bps), dtype=np.float32)

    for b in range(bps):
        mask0 = bit_table[:, b] == 0
        mask1 = bit_table[:, b] == 1

        llr0 = logsumexp(metric[:, mask0], axis=1)
        llr1 = logsumexp(metric[:, mask1], axis=1)

        llrs[:, b] = llr0 - llr1

    return llrs.reshape(-1)


def make_systematic_ldpc(K=500, row_weight=3, seed=2026):
    """
    Systematic rate-1/2 LDPC-like sparse parity-check code:
        H = [A | I]
        codeword c = [u | A u]
    For MAP-paper baseline matching:
        K = 500, N = 1000, rate = 1/2.
    """
    rng = np.random.default_rng(seed)

    A = np.zeros((K, K), dtype=np.int8)

    for r in range(K):
        cols = rng.choice(K, size=row_weight, replace=False)
        A[r, cols] = 1

    I = np.eye(K, dtype=np.int8)
    H = np.concatenate([A, I], axis=1)

    return A, H


def ldpc_encode(u, A):
    p = (A @ u) % 2
    c = np.concatenate([u, p]).astype(np.int8)
    return c


def build_graph(H):
    M, N = H.shape
    check_nodes = [np.where(H[m] == 1)[0] for m in range(M)]
    var_nodes = [np.where(H[:, n] == 1)[0] for n in range(N)]
    return check_nodes, var_nodes


def min_sum_decode(llr, H, check_nodes, var_nodes, max_iter=40, alpha=0.8):
    M, N = H.shape

    q_msg = np.zeros((M, N), dtype=np.float32)
    r_msg = np.zeros((M, N), dtype=np.float32)

    for m in range(M):
        ns = check_nodes[m]
        q_msg[m, ns] = llr[ns]

    total = llr.copy().astype(np.float32)

    for _ in range(max_iter):
        for m in range(M):
            ns = check_nodes[m]
            vals = q_msg[m, ns]

            signs = np.sign(vals)
            signs[signs == 0] = 1.0

            abs_vals = np.abs(vals)
            total_sign = np.prod(signs)

            min1_idx = np.argmin(abs_vals)
            min1 = abs_vals[min1_idx]

            tmp = abs_vals.copy()
            tmp[min1_idx] = np.inf
            min2 = np.min(tmp)

            for j, n in enumerate(ns):
                mag = min2 if j == min1_idx else min1
                r_msg[m, n] = alpha * total_sign * signs[j] * mag

        total = llr + np.sum(r_msg, axis=0)
        hard = (total < 0).astype(np.int8)

        syndrome = (H @ hard) % 2

        if np.all(syndrome == 0):
            return hard, True

        for n in range(N):
            ms = var_nodes[n]
            if len(ms) > 0:
                q_msg[ms, n] = total[n] - r_msg[ms, n]

    hard = (total < 0).astype(np.int8)
    syndrome = (H @ hard) % 2

    return hard, bool(np.all(syndrome == 0))


def simulate_ldpc_qam(M_qam, snr_db, num_blocks=20, K=500, row_weight=3, seed=2026):
    rng = np.random.default_rng(seed + int(M_qam) + int((snr_db + 100) * 10))

    A, H = make_systematic_ldpc(K=K, row_weight=row_weight, seed=seed)
    check_nodes, var_nodes = build_graph(H)

    bit_errors = 0
    total_bits = 0
    block_errors = 0
    decode_success = 0

    snr_linear = 10.0 ** (snr_db / 10.0)

    # Coded-modulation SNR scaling.
    # SNR is treated as information-bit normalized SNR.
    # code_rate = 1/2, bits_per_symbol = log2(M_qam).
    noise_var = 1.0 / (snr_linear * 0.5 * np.log2(M_qam))
    noise_std = np.sqrt(noise_var / 2.0)

    for _ in range(num_blocks):
        u = rng.integers(0, 2, size=K, dtype=np.int8)
        c = ldpc_encode(u, A)

        x, pad_len = qam_modulate(c, M_qam)

        noise = noise_std * (
            rng.standard_normal(len(x)) + 1j * rng.standard_normal(len(x))
        )

        y = x + noise
        llr = qam_demod_llr(y, M_qam, noise_var)

        if pad_len > 0:
            llr = llr[:-pad_len]

        decoded_c, ok = min_sum_decode(
            llr[: len(c)],
            H,
            check_nodes,
            var_nodes,
            max_iter=40,
            alpha=0.8,
        )

        decoded_u = decoded_c[:K]

        errors = int(np.sum(decoded_u != u))
        bit_errors += errors
        total_bits += K

        if errors > 0:
            block_errors += 1

        if ok:
            decode_success += 1

    ber = bit_errors / max(total_bits, 1)
    bler = block_errors / max(num_blocks, 1)
    success_rate = decode_success / max(num_blocks, 1)

    return {
        "qam": M_qam,
        "snr_db": snr_db,
        "num_blocks": num_blocks,
        "K": K,
        "N": 2 * K,
        "rate": 0.5,
        "ber": ber,
        "bler": bler,
        "decode_success_rate": success_rate,
    }


def main():
    out_dir = Path("experiment_logs/importance_map_jscc/ldpc_qam_sanity_n1000_ebn0")
    out_dir.mkdir(parents=True, exist_ok=True)

    snrs = [0, 3, 6, 9, 12, 15, 18, 20, 24, 28]
    qams = [16, 256]

    rows = []

    for qam in qams:
        for snr in snrs:
            print("=" * 80)
            print(f"[RUN] LDPC rate=1/2, N=1000, {qam}QAM, SNR={snr} dB")

            row = simulate_ldpc_qam(
                M_qam=qam,
                snr_db=snr,
                num_blocks=20,
                K=500,
                row_weight=3,
                seed=2026,
            )

            rows.append(row)

            print(
                f"[RESULT] {qam}QAM SNR={snr}: "
                f"BER={row['ber']:.6f}, "
                f"BLER={row['bler']:.4f}, "
                f"decode_success={row['decode_success_rate']:.4f}"
            )

            df = pd.DataFrame(rows)
            csv_path = out_dir / "ldpc_qam_sanity_n1000_ebn0_summary.csv"
            df.to_csv(csv_path, index=False)

    df = pd.DataFrame(rows)
    csv_path = out_dir / "ldpc_qam_sanity_n1000_ebn0_summary.csv"
    df.to_csv(csv_path, index=False)

    print("\n[DONE] LDPC-QAM N=1000 EbN0-scaled sanity finished.")
    print("[INFO] Summary:", csv_path)
    print(df)


if __name__ == "__main__":
    main()
