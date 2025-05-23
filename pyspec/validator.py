from .beacon_chain import (
    Checkpoint,
    AttestationData,
    BeaconState,
    get_block_root,
    get_k_deep_slot,
    is_in_inactivity_leak,
)

def generate_attestation_data(head_state: BeaconState, latest_justified_checkpoint: Checkpoint, confirmed_slot: Slot) -> AttestationData:
    source = latest_justified_checkpoint
    safe_target_chain_slot = max(get_k_deep_slot(head_state.slot), source.chain_slot)
    # Revert to safe target slot if the previous slot is not justified or during the inactivity leak
    # Otherwise use the latest confirmed block as target
    if source.checkpoint_slot + 1 < head_state.slot or is_in_inactivity_leak(head_state):
        target_chain_slot = safe_target_chain_slot
    else:
        target_chain_slot = max(safe_target_chain_slot, confirmed_slot)
    target = Checkpoint(
        root=get_block_root(head_state, target_chain_slot),
        chain_slot=target_chain_slot,
        checkpoint_slot=head_state.slot,
    )
    return AttestationData(
        head=hash_tree_root(head_state.latest_block_header),
        source=source,
        target=target,
    )