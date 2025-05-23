SLOTS_PER_HISTORICAL_ROOT = 2**17
FAR_FUTURE_SLOT = Slot(2**64 - 1)
MIN_ATTESTATION_INCLUSION_DELAY = 1
ATTESTATION_REWARD_PERIOD = 8
MIN_SLOTS_TO_INACTIVITY_PENALTY = 128
K_DEEP_CONFIRMATION_PARAMETER = 64
EPOCHS_PER_FFG_STATE = 4192
SLOTS_PER_EPOCH = 32


class Checkpoint(Container):
    root: Root
    chain_slot: Slot
    checkpoint_slot: Slot
    
class AttestationData(Container):
    head: Root
    source: Checkpoint
    target: Checkpoint
    
class Attestation(Container):
    aggregation_bits: Bitlist[VALIDATOR_REGISTRY_LIMIT]
    data: AttestationData
    signature: BLSSignature

class Eth(uint16):
    pass

class FFGState(Container):
    ffg_balances: List[Eth, VALIDATOR_REGISTRY_LIMIT]
    total_active_balance: Eth

class FFGLink(Container):
    source: Checkpoint
    target: Checkpoint

class BeaconState(Container):
    slot: Slot
    block_roots = Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots = Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    justified_checkpoints: List[Checkpoint, SLOTS_PER_HISTORICAL_ROOT]
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    ffg_states: List[FFGState, EPOCHS_PER_FFG_STATE]
    head_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    ffg_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Track which validators voted for which roots in each slot
    # For each slot in the reward period, we have:
    # - A vector of roots that were voted for
    # - A vector of validator sets, where validator_sets[i] contains the validators who voted for roots[i]
    ffg_vote_roots: Vector[List[Root, VALIDATOR_REGISTRY_LIMIT], ATTESTATION_REWARD_PERIOD]
    ffg_voters: Vector[List[List[ValidatorIndex], VALIDATOR_REGISTRY_LIMIT], ATTESTATION_REWARD_PERIOD]
    recent_justifications: Vector[FFGLink, ATTESTATION_REWARD_PERIOD]


def get_block_root(state: BeaconState, slot: Slot) -> Root:
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.block_roots[slot % SLOTS_PER_HISTORICAL_ROOT]

def get_state_root(state: BeaconState, slot: Slot) -> Root:
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.state_roots[slot % SLOTS_PER_HISTORICAL_ROOT]

def get_k_deep_slot(slot: Slot) -> Slot:
    if slot >= K_DEEP_CONFIRMATION_PARAMETER:
        k_deep_slot = slot - K_DEEP_CONFIRMATION_PARAMETER
    else:
        k_deep_slot = GENESIS_SLOT

def get_indexed_attestation(state: BeaconState, attestation: Attestation) -> IndexedAttestation:
    k_deep_slot = get_k_deep_slot(attestation.data.target.checkpoint_slot)
    voting_indices = get_active_validator_indices(state, compute_epoch_at_slot(k_deep_slot))
    assert len(attestation.aggregation_bits) == len(voting_indices)
    indices = set(i for i, bit in zip(voting_indices, attestation.aggregation_bits) if bit)
    return IndexedAttestation(
        attesting_indices=sorted(indices),
        data=attestation.data,
        signature=attestation.signature,
    )
      
def get_finality_delay(state: BeaconState) -> uint64:
    latest_finalizable_slot = GENESIS_SLOT if state.slot < GENESIS_SLOT + 2 else state.slot - 2
    return latest_finalizable_slot - state.finalized_checkpoint.slot


def is_in_inactivity_leak(state: BeaconState) -> bool:
    return get_finality_delay(state) > MIN_SLOTS_TO_INACTIVITY_PENALTY


def get_ffg_state(state: BeaconState, slot: Slot) -> FFGState:
    epoch = compute_epoch_at_slot(slot)
    current_epoch = get_current_epoch(state)
    assert epoch + EPOCHS_PER_FFG_STATE >= current_epoch
    return state.ffg_states[epoch % EPOCHS_PER_FFG_STATE]


def update_justified_and_finalized_checkpoints(
    state: BeaconState,
    source: Checkpoint,
    target: Checkpoint,
) -> bool:
    state.justified_checkpoint = target
    state.justified_checkpoints.append(target)

    if (
        state.finalized_checkpoint.slot < source.checkpoint_slot
        and target.checkpoint_slot == source.checkpoint_slot + 1
        ):
        # Record new finalization
        state.finalized_checkpoint = source
        
        # Remove all checkpoints older than the finalized checkpoint
        state.justified_checkpoints = [
            checkpoint for checkpoint in state.justified_checkpoints 
            if checkpoint.checkpoint_slot >= state.finalized_checkpoint.checkpoint_slot
        ]


def process_attestation(state: BeaconState, attestation: Attestation):
    source = attestation.data.source
    target = attestation.data.target

    # Attestation must be from at least MIN_ATTESTATION_INCLUSION_DELAY slots ago
    assert target.checkpoint_slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot
    # Target chain slot must not be more than k slots behind the voting slot
    assert target.chain_slot + K_DEEP_CONFIRMATION_PARAMETER >= target.checkpoint_slot

    # Source must be justified
    assert source in state.justified_checkpoints
    # Target must be later than source
    assert target.checkpoint_slot > source.checkpoint_slot
    # Target root must match the block root at target chain slot
    assert target.root == get_block_root(state, target.chain_slot)

    # Get and validate the indexed attestation
    indexed_attestation = get_indexed_attestation(state, attestation)
    assert is_valid_indexed_attestation(state, indexed_attestation)

    # Record votes
    vote_index = target.checkpoint_slot % ATTESTATION_REWARD_PERIOD
    ffg_link = FFGLink(source=source, target=target)
    vote_root = hash_tree_root(ffg_link)
    if target.root not in state.ffg_vote_roots[vote_index]:
        state.ffg_vote_roots[vote_index].append(vote_root)
        state.ffg_voters[vote_index].append([])
    root_index = state.ffg_vote_roots[vote_index].index(vote_root)
    for validator_index in indexed_attestation.attesting_indices:
        if validator_index not in state.ffg_voters[vote_index][root_index]:
            state.ffg_voters[vote_index][root_index].append(validator_index)


    ffg_state = get_ffg_state(state, get_k_deep_slot(target.checkpoint_slot))
    justification_balance = sum(
        balance for i, balance in enumerate(ffg_state.ffg_balances)
        if attestation.aggregation_bits[i]
    )
    is_supermajority_link = justification_balance >= 2 * ffg_state.total_active_balance // 3

    if is_supermajority_link and target not in state.justified_checkpoints:
        update_justified_and_finalized_checkpoints(state, source, target)
        if target.checkpoint_slot + ATTESTATION_REWARD_PERIOD >= state.slot:
            state.recent_justifications[target.checkpoint_slot % ATTESTATION_REWARD_PERIOD] = ffg_link
    else:
        # Attestations can only be included outside of the reward period if they justify something new
        assert state.slot <= target.checkpoint_slot + ATTESTATION_REWARD_PERIOD 

    # If we're within the reward period, update participation flags
    if state.slot <= target.checkpoint_slot + ATTESTATION_REWARD_PERIOD:
        # When inactivity leak is not active, FFG votes are rewarded only if they justify something
        # When it is active, they are rewarded also if the source is the latest justified checkpoint 
        # and the target block is the highest of the source block and the k deep block
        safe_target_chain_slot = max(get_k_deep_slot(target.checkpoint_slot), source.chain_slot)
        reward_ffg = target.root in state.justified_checkpoints or (
            is_in_inactivity_leak(state)
            and source == state.justified_checkpoint
            and target.chain_slot == safe_target_chain_slot
        )
        timely_head = target.checkpoint_slot + MIN_ATTESTATION_INCLUSION_DELAY == state.slot
        correct_head = attestation.data.head == get_block_root(state, target.checkpoint_slot)
        reward_head = correct_head and timely_head
        
        for index in indexed_attestation.attesting_indices:
            flag_index = target.checkpoint_slot % ATTESTATION_REWARD_PERIOD
            if reward_ffg and not has_flag(state.ffg_participation[index], flag_index):
                add_flag(state.ffg_participation[index], flag_index)
            if reward_head and not has_flag(state.head_participation[index], flag_index):
                add_flag(state.head_participation[index], flag_index)


    