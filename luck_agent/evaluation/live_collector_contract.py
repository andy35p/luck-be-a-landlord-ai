"""Version-specific observation checks; version strings are not authentication."""
from luck_agent.evaluation.live_board import displayed_ids


def collector_blockers(record):
    state=record.get('state',{})
    version=record.get('collector_version','0.5.0')
    if version == '0.5.0':
        # Original 0.5 did not emit its version. Mixed new fields must not silently
        # downgrade the checks when the envelope loses its version.
        if 'displayed_board' in state:
            return ['collector_version_fields_mismatch']
        return []
    if version != '0.7.0':
        return ['unsupported_collector_version']
    reasons=[]
    try:
        displayed_ids(state)
    except ValueError as error:
        reasons.append('collector_board_' + str(error))
    for collection in ('symbols','items'):
        entries=state.get(collection)
        if not isinstance(entries,list):
            reasons.append('collector_missing_' + collection)
            continue
        if any(not isinstance(entry,dict) or entry.get('modded') is not False
               or entry.get('inherit_effects') is not False for entry in entries):
            reasons.append('collector_unverified_rule_source')
    return sorted(set(reasons))
