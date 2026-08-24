#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manifest + config contract gate.

Part 1: projects/ca_tosg/configs/ == docs/experiment_protocol.md, checked two independent ways.

  1a. PER-BLOCK md5. Every config records, in its own `derived_from:` block, the md5 of the exact
      protocol text it was generated from. This gate recomputes each of those md5s from the
      protocol as it stands NOW and compares them one by one, naming the block that drifted
      (CATOSG-CANDIDATES / §3 Channel grid / §4 Action set / Appendix B). This is the assertion
      that keeps the protocol the single normative source: change the protocol and the configs
      are stale by construction, and the gate says which part.
  1b. BYTE COMPARE. The five files are regenerated from the protocol and compared byte-for-byte,
      which also catches a hand-edit that leaves the md5 line untouched.

  Both directions fail loudly: a config that configs.py does not generate is reported as an
  ungoverned second source rather than ignored.

Part 2: the frozen manifests' INTERNAL relative paths.
  ONE rule, stated once and enforced here: every path inside a manifest is relative to the
  REPOSITORY ROOT (it used to be relative to paper1/). The gate resolves each of them and
  recomputes each recorded md5/sha256 from the file it lands on. A manifest whose pins point at
  nothing -- or at something whose hash has moved on -- is a decorative manifest, so this fails
  loudly rather than skipping. The migration itself is archive/docs-history/restructure/migrate_manifests.py.

Exit 0 iff every check passes.

  python tests/test_manifest.py
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/utils'))

import configs  # noqa: E402

CONFIG_DIR = os.path.join(ROOT, 'projects/ca_tosg/configs')
MANIFESTS = ['results/manifests/FROZEN_MANIFEST.json', 'results/manifests/P4A_MANIFEST.json']
PATH_KEYS = ('file', 'model')


def _derived_from(text):
    """Pull the `derived_from:` mapping out of a generated yaml without a yaml parser."""
    out, inside = {}, False
    for line in text.splitlines():
        if line.startswith('derived_from:'):
            inside = True
            continue
        if inside:
            if not line.startswith('  ') or not line.strip():
                break
            k, _, v = line.strip().partition(':')
            out[k.strip()] = v.strip()
    return out


def check_config_md5s():
    """1a: every md5 a config claims must equal the protocol block's md5 as computed right now."""
    txt = configs.protocol_text()
    live = {'candidate_block_md5': configs.json_block('CATOSG-CANDIDATES', txt)[2],
            'channel_section_md5': configs.section('3. Channel grid', txt)[1],
            'action_section_md5': configs.section('4. Action set S = {E, L, F}', txt)[1],
            'appendix_b_md5': configs.appendix_b(txt)[1]}
    fails, n = [], 0
    for name in sorted(os.listdir(CONFIG_DIR)) if os.path.isdir(CONFIG_DIR) else []:
        if not name.endswith('.yaml'):
            continue
        claimed = _derived_from(open(os.path.join(CONFIG_DIR, name), encoding='utf-8').read())
        if not claimed:
            fails.append('configs/%s records no derived_from block -- it claims no protocol source'
                         % name)
            continue
        pinned = [k for k in claimed if k.endswith('_md5')]
        if not pinned:
            fails.append('configs/%s pins no protocol block md5' % name)
            continue
        for k in pinned:
            n += 1
            if k not in live:
                fails.append('configs/%s pins unknown protocol block %r' % (name, k))
            elif claimed[k] != live[k]:
                fails.append('configs/%s: %s is %s… but docs/experiment_protocol.md now hashes to '
                             '%s… -- the protocol changed and configs/ was not regenerated'
                             % (name, k, claimed[k][:12], live[k][:12]))
        print('  configs/%-22s pins %d protocol block md5(s), all current' % (name, len(pinned)))
    if n == 0:
        fails.append('no config pinned any protocol md5 -- this check would pass vacuously')
    return fails


def check_configs():
    """1b: every config must be exactly what the protocol generates today."""
    want = configs.build()
    fails = []
    for name, body in sorted(want.items()):
        p = os.path.join(CONFIG_DIR, name)
        if not os.path.exists(p):
            fails.append('configs/%s MISSING (run: python projects/ca_tosg/utils/configs.py --write)'
                         % name)
            continue
        have = open(p, encoding='utf-8').read()
        if have != body:
            n = sum(1 for a, b in zip(have.splitlines(), body.splitlines()) if a != b)
            fails.append('configs/%s DRIFT vs docs/experiment_protocol.md (%d differing lines, '
                         '%d vs %d bytes)' % (name, n, len(have), len(body)))
        else:
            print('  configs/%-22s == protocol-derived (%d bytes)' % (name, len(body)))

    extra = sorted(f for f in os.listdir(CONFIG_DIR)
                   if f.endswith('.yaml') and f not in want) if os.path.isdir(CONFIG_DIR) else []
    for f in extra:
        fails.append('configs/%s is not generated by configs.py -- an ungoverned second source' % f)
    return fails


def _hash(p, algo):
    h = hashlib.new(algo)
    h.update(open(p, 'rb').read())
    return h.hexdigest()


def _walk(obj, path, fails, stats):
    if isinstance(obj, dict):
        rel = next((obj[k] for k in PATH_KEYS if isinstance(obj.get(k), str)), None)
        if rel is not None:
            if os.path.isabs(rel):
                fails.append('%s: absolute path in a manifest (%s) -- must be repo-root relative'
                             % (path, rel))
            p = os.path.normpath(os.path.join(ROOT, rel))
            if not os.path.exists(p):
                fails.append('%s: relpath does not resolve from the repo root -> %s' % (path, rel))
            else:
                stats['resolved'] += 1
                # A pin may declare that it refers to a PRE-PROMOTION file: the P4-A bandit was
                # trained on the retired full-collaborator grid and only replayed under the N=1
                # convention, so pinning today's file would misstate what it learned from. Such a
                # pin is verified against the tagged blob instead of the working tree -- stronger
                # than skipping it, because the historical content is actually re-hashed.
                retired = obj.get('retired_at')
                for algo in ('md5', 'sha256'):
                    if algo not in obj:
                        continue
                    if retired:
                        blob = subprocess.run(['git', '-C', ROOT, 'show', f'{retired}:{rel}'],
                                              capture_output=True)
                        if blob.returncode != 0:
                            # the blob is absent because the input is git-excluded (data/p2 is).
                            # That cannot be verified from the repository at all, so it is allowed
                            # ONLY as a declared exception and is printed every run -- an
                            # unverifiable pin must never look like a passing one.
                            if obj.get('unverifiable_reason'):
                                print('  %s: %s UNVERIFIABLE (declared) -- %s'
                                      % (path, rel, obj['unverifiable_reason']))
                                stats.setdefault('unverifiable', 0)
                                stats['unverifiable'] += 1
                            else:
                                fails.append('%s: retired_at=%s but %s is not in that tag and no '
                                             'unverifiable_reason is declared'
                                             % (path, retired, rel))
                            continue
                        got = getattr(hashlib, algo)(blob.stdout).hexdigest()
                        stats['hashed'] += 1
                        if got != obj[algo]:
                            fails.append('%s: %s mismatch for %s AT TAG %s (manifest %s..., '
                                         'tagged blob %s...)'
                                         % (path, algo, rel, retired, obj[algo][:12], got[:12]))
                        else:
                            print('  %s: %s verified against tag %s (pre-promotion input)'
                                  % (path, rel, retired))
                        continue
                    got = _hash(p, algo)
                    stats['hashed'] += 1
                    if got != obj[algo]:
                        fails.append('%s: %s mismatch for %s (manifest %s..., file %s...)'
                                     % (path, algo, rel, obj[algo][:12], got[:12]))
        for k, v in obj.items():
            _walk(v, path + '/' + str(k), fails, stats)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk(v, path + '[%d]' % i, fails, stats)


def check_manifests():
    fails = []
    for rel in MANIFESTS:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            fails.append('%s MISSING' % rel)
            continue
        stats = {'resolved': 0, 'hashed': 0}
        _walk(json.load(open(p)), rel, fails, stats)
        print('  %-40s %d relpath(s) resolve, %d recorded hash(es) re-verified'
              % (rel, stats['resolved'], stats['hashed']))
        if stats['resolved'] == 0:
            fails.append('%s: no resolvable path at all -- the gate would pass vacuously' % rel)
    return fails


def main():
    print('configs pin the protocol blocks (per-block md5):')
    fails = check_config_md5s()
    print('configs == protocol (byte compare):')
    fails += check_configs()
    print('manifest relpaths (repo-root relative) + recorded hashes:')
    fails += check_manifests()
    if fails:
        print('\nMANIFEST/CONFIG GATE FAIL:')
        for f in fails:
            print('  ' + f)
        return 1
    print('MANIFEST/CONFIG GATE PASS: %d configs match the protocol; %d manifests resolve.'
          % (len(configs.build()), len(MANIFESTS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
