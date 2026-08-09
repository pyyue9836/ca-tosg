#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 submit-B step f: PROTOCOL sec 8 anomaly checklist over the deployment outputs.

Reads results/p2_deploy/* + FROZEN_MANIFEST.json + the grids, tests every pre-registered sec-8
expectation, writes results/p2_deploy/anomaly_report.txt, and -- per the binding handling rules --
FUSES (exit 1) if ANY expectation is unmet, reporting the numbers as-is with a diagnosed root cause
(no artefact hand-wave, no data adjustment, no retrain, no touching delta).

Run:  /path/to/env/python paper1/code/p2_dataprep/anomaly_check.py
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
DEPLOY = os.path.join(P1, 'results/p2_deploy')
MANIFEST = os.path.join(P1, 'results/p2_dataprep/FROZEN_MANIFEST.json')
REPORT = os.path.join(DEPLOY, 'anomaly_report.txt')


def main():
    man = json.load(open(MANIFEST))
    act = pd.read_csv(os.path.join(DEPLOY, 'headline_action_dist.csv'))
    summ = pd.read_csv(os.path.join(DEPLOY, 'replay_summary.csv'))
    checks = []                                                   # (id, expectation, met, detail)

    def add(cid, exp, met, detail):
        checks.append((cid, exp, bool(met), detail))

    # 1. plumbing: manifest present + schema + each budget frozen_validate_payload <= B_max
    ok_pay = all(bd['frozen_validate_payload'] <= float(b) for b, bd in man['budgets'].items())
    add('S8-plumbing', 'manifest present, schema catosg-frozen-manifest/1, frozen payload <= B_max',
        man.get('schema') == 'catosg-frozen-manifest/1' and ok_pay,
        f'schema={man.get("schema")}; frozen_pay={[round(bd["frozen_validate_payload"],4) for bd in man["budgets"].values()]}')

    # 5. no C256 in any deployed action-distribution curve (S = {E,L,F})
    add('S8-noC256', 'no deployed action-distribution curve contains C256',
        not any(c.startswith('rf_C256') or c == 'C256' for c in act.columns), 'action set is {E,L,F}')

    # 7. one frozen model/lambda*/tau* per budget (structural: eval reads manifest only)
    add('S8-onefrozen', 'test/Culver produced with exactly one frozen model + lambda*/tau* from the manifest',
        all('model_sha256' in bd and 'tau_star' in bd for bd in man['budgets'].values()),
        '3 sha256 + tau* recorded; eval_p2_deploy sources params from the manifest only')

    # per split x budget structural expectations (on the deterministic grid action dist)
    ray_collapse = []                                            # (split,budget,or_E_ray,rf_E_ray)
    for (split, budget), g in act.groupby(['split', 'budget']):
        ray = g[g.channel == 'rayleigh']; awgn = g[g.channel == 'awgn']
        low = awgn[awgn.snr_db <= 8]
        # 2. Rayleigh F ~= 0
        add(f'S8-rayF~0[{split},B{budget}]', 'Rayleigh: F fraction ~= 0',
            ray.rf_F.mean() < 0.01, f'mean rf_F(rayleigh)={ray.rf_F.mean():.4f}')
        # 3. AWGN low-SNR (<=8) E/L-dominated
        add(f'S8-awgnlowEL[{split},B{budget}]', 'AWGN low SNR (<=8 dB): E/L-dominated (F small)',
            low.rf_F.mean() < 0.05, f'mean rf_F(awgn,snr<=8)={low.rf_F.mean():.4f}')
        # 4. high-SNR F rises (AWGN 20 dB > 0 dB)
        f0 = float(awgn[awgn.snr_db == 0].rf_F.mean()); f20 = float(awgn[awgn.snr_db == 20].rf_F.mean())
        add(f'S8-Frises[{split},B{budget}]', 'high SNR: F share increases with SNR (AWGN 20>0 dB)',
            f20 >= f0, f'rf_F(awgn) 0dB={f0:.4f} -> 20dB={f20:.4f}')
        # 8 (E-related, sec-8 #2 for the SELECTOR): on Rayleigh both E and L should show; UNMET if the
        #    selector collapses E (rf_E<0.01) while the oracle uses it (or_E>0.05).
        orE = float(ray.or_E.mean()); rfE = float(ray.rf_E.mean())
        met = not (orE > 0.05 and rfE < 0.01)
        add(f'S8-selE[{split},B{budget}]',
            'Rayleigh: selector shows both E and L, tracking the oracle (not an E-collapse)',
            met, f'oracle_E(rayleigh)={orE:.4f} vs selector_E(rayleigh)={rfE:.4f}')
        if not met:
            ray_collapse.append((split, budget, orE, rfE))

    unmet = [c for c in checks if not c[2]]
    with open(REPORT, 'w') as f:
        f.write('CA-TOSG P2 submit-B step f -- PROTOCOL sec 8 anomaly checklist\n' + '=' * 72 + '\n')
        f.write(f'{len(checks)} expectations tested; {len(unmet)} UNMET.\n\n')
        for cid, exp, met, detail in checks:
            f.write(f'[{"PASS" if met else "FAIL"}] {cid}: {exp}\n        {detail}\n')
        if unmet:
            f.write('\n' + '=' * 72 + '\nHANDLING RULE 1 -> FUSED. Reported as-is; no retrain, no data '
                    'adjustment, no delta change.\n')
            if ray_collapse:
                f.write('\nROOT CAUSE (E-collapse, diagnosed -- not an artefact hand-wave):\n'
                        '  The frozen selectors almost never predict E, while the oracle uses E '
                        'substantially on test/Culver (esp. under Rayleigh, where F is infeasible and the '
                        'choice is E-vs-L). Cause: the selectors were fit on the VALIDATE grid, whose '
                        'oracle E base-rate is only 0.77%, and R9\'s frozen walk selected class_weight=None '
                        'models (the cw=balanced candidates were walked past for exceeding the frozen '
                        'payload budget). So E is under-represented in training and the selector collapses '
                        'it at deployment, costing F1 on the ego-favourable frames.\n')
                for s, b, oe, re_ in ray_collapse:
                    f.write(f'    {s} B{b}: oracle_E(rayleigh)={oe:.4f}  selector_E(rayleigh)={re_:.4f}\n')
                f.write('  This is a real selector limitation, not a plumbing bug. Resolution requires a '
                        'NEW pre-registered decision (e.g. permit cw=balanced under a revised budget rule, '
                        'or re-weight E in training) -- NOT taken here.\n')
        else:
            f.write('\nAll sec-8 expectations met.\n')

    print(f'sec-8 checklist: {len(checks)} tested, {len(unmet)} UNMET -> {REPORT}')
    for cid, exp, met, detail in checks:
        if not met:
            print(f'  FAIL {cid}: {detail}')
    if unmet:
        raise SystemExit(f'P2-B FUSE (PROTOCOL sec 8): {len(unmet)} expectation(s) unmet '
                         '(see results/p2_deploy/anomaly_report.txt). Halted per handling rule 1.')
    print('all sec-8 expectations met.')


if __name__ == '__main__':
    main()
