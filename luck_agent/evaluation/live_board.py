"""Validate explicit captured board membership, never infer it from coordinates."""


def displayed_ids(state):
    """Return row-major instance IDs, or reject missing/ambiguous snapshots.

    Includes empty-symbol instances. Callers still need settled-state checks;
    membership does not establish timer or payout correctness.
    """
    if not isinstance(state, dict): raise ValueError('invalid_state')
    board = state.get('displayed_board')
    if not isinstance(board, dict): raise ValueError('missing_displayed_board')
    width, height = board.get('width'), board.get('height')
    if type(width) is not int or type(height) is not int or (width,height)!=(5,4):
        raise ValueError('unverified_board_dimensions')
    rows = board.get('rows')
    if not isinstance(rows,list) or len(rows)!=height:
        raise ValueError('incomplete_displayed_board')
    ids=[]
    for row in rows:
        if not isinstance(row,list) or len(row)!=width:
            raise ValueError('incomplete_displayed_board')
        for uid in row:
            if not isinstance(uid,str) or not uid: raise ValueError('invalid_displayed_identity')
            ids.append(uid)
    if len(set(ids))!=len(ids): raise ValueError('duplicate_displayed_identity')
    symbols=state.get('symbols')
    if not isinstance(symbols,list): raise ValueError('missing_inventory')
    inventory=set()
    for symbol in symbols:
        uid=symbol.get('instance_id') if isinstance(symbol,dict) else None
        if not isinstance(uid,str) or not uid or uid in inventory:
            raise ValueError('invalid_inventory_identity')
        inventory.add(uid)
    if not set(ids).issubset(inventory): raise ValueError('displayed_symbol_missing_from_inventory')
    return tuple(ids)
