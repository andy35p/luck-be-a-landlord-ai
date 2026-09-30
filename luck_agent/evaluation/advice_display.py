"""Atomic display-only sidecar. No game command channel."""
import json
import os
import time
from pathlib import Path

NAMES = {'coin': '硬币', 'pearl': '珍珠', 'cherry': '樱桃', 'flower': '花',
         'cat': '猫', 'mouse': '老鼠', 'cheese': '奶酪', 'milk': '牛奶', 'goldfish': '金鱼',
         'sapphire': '蓝宝石', 'sand_dollar': '沙钱'}


def display_message(result):
    if result.get('status') == 'ready':
        action = result['action']
        return '建议：跳过' if action['action_type'] == 1 else '建议：选择'+NAMES.get(action['target_id'], action['target_id'])
    reasons = result.get('reasons', [])
    if any('unsupported' in r or 'special_effect' in r for r in reasons):
        return '暂不建议：当前符号或物品尚未支持'
    if any('input_context' in r for r in reasons): return '建议已暂停'
    if any(r in ('feed_stalled', 'expired') for r in reasons): return '建议助手已离线'
    return '等待可支持的选牌状态'


def publish(path, result, identity=None, wall_clock=time.time):
    path = Path(path)
    payload = {'schema': 2, 'created_at': wall_clock(), 'session_id': None, 'sequence': None,
               'state_revision': None,
               'status': result.get('status', 'unavailable'), 'message': display_message(result)}
    payload.update(identity or {})
    # Identity from result takes precedence; unavailable results use last consumed envelope.
    for key in ('session_id', 'sequence', 'state_revision'):
        if key in result: payload[key] = result[key]
    temp = path.with_suffix(path.suffix+'.tmp')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=True), encoding='utf-8')
        os.replace(temp, path)
    except PermissionError:
        # Godot's Windows read handle can briefly prevent replacement. Never
        # truncate the live file; the next poll republishes newly checked state.
        return None
    return payload
