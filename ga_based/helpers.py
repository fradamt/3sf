from pyrsistent import PSet, PMap, PVector

from data_structures import *
from formal_verification_annotations import *
from pythonic_code_generic import *
from stubs import *


def get_slot(node_state: NodeState) -> int:
    """
    It calculates the current slot number. 
    """
    return get_slot_from_time(node_state.time, node_state)


def get_phase(node_state: NodeState) -> int:
    """
    It calculates the current phase number. 
    """
    return get_phase_from_time(node_state.time, node_state)

def get_slot_from_time(time: int, node_state: NodeState) -> int:
    """
    It calculates the slot number based on a given `time` and the node's configuration settings. 
    """
    return time // (4 * node_state.configuration.delta)


def get_phase_from_time(time: int, node_state: NodeState) -> NodePhase:
    """
    It calculates the phase within a slot based on a given `time` and the node's configuration settings. 
    """
    time_in_slot = time % (4 * node_state.configuration.delta)

    if time_in_slot >= 3 * node_state.configuration.delta:
        return NodePhase.MERGE
    elif time_in_slot >= 2 * node_state.configuration.delta:
        return NodePhase.CONFIRM
    elif time_in_slot >= node_state.configuration.delta:
        return NodePhase.VOTE
    else:
        return NodePhase.PROPOSE



def genesis_checkpoint(node_state: NodeState) -> Checkpoint:
    """
    It defines the genesis block.
    """
    return Checkpoint(
        block_hash=block_hash(node_state.configuration.genesis),
        chkp_slot=0,
        block_slot=0
    )


def has_block_hash(block_hash: Hash, node_state: NodeState) -> bool:
    """
    It checks if a given `block_hash` is present within a `node_state`.
    """
    return pmap_has(node_state.blocks, block_hash)


def get_block_from_hash(block_hash: Hash, node_state: NodeState) -> Block:
    """
    It retrieves the block associated to a `block_hash`.
    """
    Requires(has_block_hash(block_hash, node_state))
    return pmap_get(node_state.blocks, block_hash)


def has_parent(block: Block, node_state: NodeState) -> bool:
    """
    It checks whether a `block` has a parent.
    """
    return has_block_hash(block.parent_hash, node_state)


def get_parent(block: Block, node_state: NodeState) -> Block:
    """
    It retrieves the parent of a given `block`.
    """
    Requires(has_parent(block, node_state))
    return get_block_from_hash(block.parent_hash, node_state)


def get_all_blocks(node_state: NodeState) -> PSet[Block]:
    """
    It retrieves all the blocks in a `node_state`.
    """
    return pmap_values(node_state.blocks)


def is_validator(node: NodeIdentity, validatorBalances: ValidatorBalances) -> bool:
    """
    It checks whether a `node` is a validator.
    """
    return pmap_has(validatorBalances, node)


def is_complete_chain(block: Block, node_state: NodeState) -> bool:
    """
    It checks if a given `block` is part of a complete chain of blocks that reaches back to the genesis block `node_state.configuration.genesis`
    within a `node_state`.
    """
    if block == node_state.configuration.genesis:
        return True
    elif not has_parent(block, node_state):
        return False
    else:
        return is_complete_chain(get_parent(block, node_state), node_state)


def get_blockchain(block: Block, node_state: NodeState) -> PVector[Block]:
    """
    It constructs a blockchain from a given `block` back to the genesis block, 
    assuming the given `block` is part of a complete chain.
    """
    Requires(is_complete_chain(block, node_state))
    if block == node_state.configuration.genesis:
        return pvector_of_one_element(block)
    else:
        return pvector_concat(
            pvector_of_one_element(block),
            get_blockchain(get_parent(block, node_state), node_state)
        )


def is_ancestor_descendant_relationship(ancestor: Block, descendant: Block, node_state: NodeState) -> bool:
    """
    It determines whether there is an ancestor-descendant relationship between two blocks.
    """
    if ancestor == descendant:
        return True
    elif descendant == node_state.configuration.genesis:
        return False
    else:
        return (
            has_parent(descendant, node_state) and
            is_ancestor_descendant_relationship(
                ancestor,
                get_parent(descendant, node_state),
                node_state
            )
        )


def validator_set_weight(validators: PSet[NodeIdentity], validatorBalances: ValidatorBalances) -> int:
    """
    It calculates the total weight (or sum of `validatorBalances`) of a specified set of `validators` within a blockchain.
    """
    return pset_sum(
        pset_map(
            lambda v: pmap_get(validatorBalances, v),
            pset_intersection(
                pmap_keys(validatorBalances),
                validators
            )
        )
    )


def get_set_FFG_targets(votes: PSet[SignedVoteMessage]) -> PSet[Checkpoint]:
    """
    It extracts a set of ffg targets from a set of `votes`.
    """
    return pset_map(
        lambda vote: vote.message.ffg_target,
        votes
    )


def is_FFG_vote_in_support_of_checkpoint_justification(vote: SignedVoteMessage, checkpoint: Checkpoint, node_state: NodeState) -> bool:
    """
    It determines whether a given `vote` supports the justification of a specified `checkpoint`.
    """
    return (
        valid_vote(vote, node_state) and
        vote.message.ffg_target.chkp_slot == checkpoint.chkp_slot and
        is_ancestor_descendant_relationship(
            get_block_from_hash(checkpoint.block_hash, node_state),
            get_block_from_hash(vote.message.ffg_target.block_hash, node_state),
            node_state) and
        is_ancestor_descendant_relationship(
            get_block_from_hash(vote.message.ffg_source.block_hash, node_state),
            get_block_from_hash(checkpoint.block_hash, node_state),
            node_state) and
        is_justified_checkpoint(vote.message.ffg_source, node_state)
    )


def filter_out_FFG_votes_not_in_FFG_support_of_checkpoint_justification(votes: PSet[SignedVoteMessage], checkpoint: Checkpoint, node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filters out ffg votes that do not support the justification of a specified `checkpoint`.
    """
    return pset_filter(lambda vote: is_FFG_vote_in_support_of_checkpoint_justification(vote, checkpoint, node_state), votes)


def get_validators_in_FFG_support_of_checkpoint_justification(votes: PSet[SignedVoteMessage], checkpoint: Checkpoint, node_state: NodeState) -> PSet[NodeIdentity]:
    """
    It identifies and returns the set of validators that have cast `votes` in support of the justification of a specified `checkpoint`.
    """
    return pset_map(
        lambda vote: vote.sender,
        filter_out_FFG_votes_not_in_FFG_support_of_checkpoint_justification(votes, checkpoint, node_state)
    )


def is_justified_checkpoint(checkpoint: Checkpoint, node_state: NodeState) -> bool:
    """
    It checks whether a `checkpoint` if justified, specifically a `checkpoint` is justified if at least 
    two-thirds of the total validator set weight is in support. This is evaluated by checking if 
    `FFG_support_weight * 3 >= tot_validator_set_weight * 2`.
    """

    if checkpoint == genesis_checkpoint(node_state):
        return True
    else:
        if not has_block_hash(checkpoint.block_hash, node_state) or not is_complete_chain(get_block_from_hash(checkpoint.block_hash, node_state), node_state):
            return False

        validatorBalances = get_validator_set_for_slot(get_block_from_hash(checkpoint.block_hash, node_state), checkpoint.block_slot, node_state)

        FFG_support_weight = validator_set_weight(get_validators_in_FFG_support_of_checkpoint_justification(node_state.votes, checkpoint, node_state), validatorBalances)
        tot_validator_set_weight = validator_set_weight(pmap_keys(validatorBalances), validatorBalances)

        return FFG_support_weight * 3 >= tot_validator_set_weight * 2


def filter_out_non_justified_checkpoint(checkpoints: PSet[Checkpoint], node_state: NodeState) -> PSet[Checkpoint]:
    """
    It filters out `checkpoints` that are not justified.
    """
    return pset_filter(lambda checkpoint: is_justified_checkpoint(checkpoint, node_state), checkpoints)


def get_justified_checkpoints(node_state: NodeState) -> PSet[Checkpoint]:
    """
    It retrieves all the justified checkpoints from a `note_state`. First it extracts all ffg target checkpoints from 
    the set of votes in the `node_state`. Then it filter out these checkpoints to keep only those that are justified.
    The `genesis_checkpoint` is automatically considered justified.
    """
    return pset_add(
        filter_out_non_justified_checkpoint(get_set_FFG_targets(node_state.votes), node_state),
        genesis_checkpoint(node_state)
    )


def get_greatest_justified_checkpoint(node_state: NodeState) -> Checkpoint:
    """
    It retrieves the greatest justified checkpoint from a `node_state`.
    """
    return pset_max(
        get_justified_checkpoints(node_state),
        lambda c: (c.chkp_slot, c.block_slot)
    )


def is_FFG_vote_linking_to_a_checkpoint_in_next_slot(vote: SignedVoteMessage, checkpoint: Checkpoint, node_state: NodeState) -> bool:
    """
    It evaluates whether a given `vote` represents a link from a specified `checkpoint` to a checkpoint in the immediately following slot.
    """
    return (
        valid_vote(vote, node_state) and
        vote.message.ffg_source == checkpoint and
        vote.message.ffg_target.chkp_slot == checkpoint.chkp_slot + 1
    )


def filter_out_FFG_vote_not_linking_to_a_checkpoint_in_next_slot(checkpoint: Checkpoint, node_state: NodeState) -> PSet[SignedVoteMessage]:  
    """
    It filters and retains only those votes from a `node_state` that are linking to a `checkpoint` in the next slot.
    """
    return pset_filter(lambda vote: is_FFG_vote_linking_to_a_checkpoint_in_next_slot(vote, checkpoint, node_state), node_state.votes)


def get_validators_in_FFG_votes_linking_to_a_checkpoint_in_next_slot(checkpoint: Checkpoint, node_state) -> PSet[NodeIdentity]:
    """
    It retrieves the identities of validators who have cast ffg votes that support linking a specified `checkpoint` to its immediate successor.
    """
    return pset_map(
        lambda vote: vote.sender,
        filter_out_FFG_vote_not_linking_to_a_checkpoint_in_next_slot(checkpoint, node_state)
    )


def is_finalized_checkpoint(checkpoint: Checkpoint, node_state: NodeState) -> bool:
    """
    It evaluates whether a given `checkpoint` has been finalized. A `checkpoint` is considered finalized if it is justified and 
    if at least two-thirds of the total validator set's weight supports the transition from this `checkpoint` to the next. Specifically, it first checks if the `checkpoint` is justified using 
    `is_justified_checkpoint(checkpoint, node_state)`. Then it retrieves the set of validators and their balances for the slot associated with the `checkpoint`. 
    This is done through `get_validator_set_for_slot`. Then it calculates the total weight (stake) of validators who have cast votes 
    linking the `checkpoint` to the next slot, using `get_validators_in_FFG_votes_linking_to_a_checkpoint_in_next_slot` to identify these validators
    and `validator_set_weight` to sum their stakes. Finally it checks if `FFG_support_weight * 3 >= tot_validator_set_weight * 2` to finalize `checkpoint`.
    """
    if not is_justified_checkpoint(checkpoint, node_state):
        return False

    validatorBalances = get_validator_set_for_slot(get_block_from_hash(checkpoint.block_hash, node_state), checkpoint.block_slot, node_state)
    FFG_support_weight = validator_set_weight(get_validators_in_FFG_votes_linking_to_a_checkpoint_in_next_slot(checkpoint, node_state), validatorBalances)
    tot_validator_set_weight = validator_set_weight(pmap_keys(validatorBalances), validatorBalances)

    return FFG_support_weight * 3 >= tot_validator_set_weight * 2


def filter_out_non_finalized_checkpoint(checkpoints: PSet[Checkpoint], node_state: NodeState) -> PSet[Checkpoint]:
    """
    It filters out non finalized `checkpoints` from a `node_state`.
    """
    return pset_filter(lambda checkpoint: is_finalized_checkpoint(checkpoint, node_state), checkpoints)


def get_finalized_checkpoints(node_state: NodeState) -> PSet[Checkpoint]:
    """
    It retrieves from `node_state` all the checkpoints that have been finalized.
    """
    return pset_add(
        filter_out_non_finalized_checkpoint(get_set_FFG_targets(node_state.votes), node_state),
        genesis_checkpoint(node_state)
    )


def get_greatest_finalized_checkpoint(node_state: NodeState) -> Checkpoint:
    """
    It returns the greatest finalized checkpoint from a `node_state`.
    """
    return pset_max(
        get_finalized_checkpoints(node_state),
        lambda c: c.chkp_slot
    )


def filter_out_blocks_non_ancestor_of_block(block: Block, blocks: PSet[Block], node_state: NodeState) -> PSet[Block]:
    """
    It filters a set of `blocks`, retaining only those that are ancestors of a specified `block`.
    """
    return pset_filter(
        lambda b: is_ancestor_descendant_relationship(b, block, node_state),
        blocks
    )


def filter_out_head_votes_non_descendant_of_block(block: Block, votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filters a set of `votes`, retaining only those that are for blocks which are descendants of a specified `block`.
    """
    return pset_filter(
        lambda vote:
            has_block_hash(vote.message.head_hash, node_state) and
            is_ancestor_descendant_relationship(
                block,
                get_block_from_hash(vote.message.head_hash, node_state),
                node_state
            ),
        votes
    )


def is_head_vote_for_block_in_blockchain(vote: SignedVoteMessage, blockchainHead: Block, node_state: NodeState) -> bool:
    """
    It evaluates whether a given `vote` is for a block that is part of the blockchain ending at a specified "head" block (`blockchainHead`).
    """
    return (
        has_block_hash(vote.message.head_hash, node_state) and
        is_ancestor_descendant_relationship(
            get_block_from_hash(vote.message.head_hash, node_state),
            blockchainHead,
            node_state)
    )


def filter_out_head_votes_not_for_blocks_in_blockchain(votes: PSet[SignedVoteMessage], blockchainHead: Block, node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filter through a set of `votes`, retaining only those that are for blocks within the blockchain leading up to a specified `blockchainHead`.
    """
    return pset_filter(
        lambda vote: is_head_vote_for_block_in_blockchain(vote, blockchainHead, node_state),
        votes
    )


def filter_out_head_votes_for_blocks_in_blockchain(votes: PSet[SignedVoteMessage], blockchainHead: Block, node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filter through a set of `votes`, excluding those that are for blocks within the blockchain leading up to and including a specified `blockchainHead`. 
    """
    return pset_filter(
        lambda vote: not is_head_vote_for_block_in_blockchain(vote, blockchainHead, node_state),
        votes
    )

def is_head_vote_received_timely(vote: SignedVoteMessage, node_state: NodeState) -> bool:
    """
    It evaluates whether a given `vote` was received before the MERGE phase of the previous slot
    """

    receival_time = pmap_get(node_state.vote_receival_times, vote)
    current_slot = get_slot(node_state)
    return receival_time <= 4 * node_state.configuration.delta * current_slot - node_state.configuration.delta


def filter_out_late_received_head_votes(votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filter through a set of `votes`, retaining only those that are for blocks within the blockchain leading up to a specified `blockchainHead`.
    """
    return pset_filter(
        lambda vote: is_head_vote_received_timely(vote, node_state),
        votes
    )



def is_head_vote_expired(vote: SignedVoteMessage, node_state: NodeState) -> bool:
    """
    A vote is expired if it was cast in a slot older than `get_slot(node_state)` - `node_state.configuration.eta`.
    """
    return vote.message.slot + node_state.configuration.eta < get_slot(node_state)


def filter_out_expired_head_votes(votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filters out from `votes` all the expired votes.
    """
    return pset_filter(
        lambda vote: is_head_vote_expired(vote, node_state),
        votes
    )


def filter_out_non_LMD_head_votes(votes: PSet[SignedVoteMessage]) -> PSet[SignedVoteMessage]:
    lmd: PMap[NodeIdentity, SignedVoteMessage] = pmap_get_empty()

    for vote in votes:
        if not pmap_has(lmd, vote.sender) or vote.message.slot > pmap_get(lmd, vote.sender).message.slot:
            lmd = pmap_set(lmd, vote.sender, vote)

    return pmap_values(lmd)


def is_equivocating_head_vote(vote: SignedVoteMessage, node_state: NodeState) -> bool:
    """
    It checks if the given `vote` is part of an equivocation by comparing it against all other `vote`s from the same sender 
    for the same slot but with different block hashes. If such a `vote` exists, the validator is considered to have equivocated, 
    violating the protocol's rules.
    """
    return not pset_is_empty(
        pset_filter(
            lambda vote_check:
                vote_check.message.slot == vote.message.slot and
                vote_check.sender == vote.sender and
                vote_check.message.head_hash != vote.message.head_hash,
            node_state.votes
        )
    )


def filter_out_head_equivocating_votes(votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    """ 
    It filters out from `votes` all the equivocating votes. 
    """
    return pset_filter(
        lambda vote: not is_equivocating_head_vote(vote, node_state),
        votes
    )


def valid_vote(vote: SignedVoteMessage, node_state: NodeState) -> bool:
    """
    A vote is valid if:
    - it has a valid signature;
    - the block hash associated with the voted head block exists within a validator's view of blocks;
    - the head block associated with the vote is part of a complete chain that leads back to the genesis block within a validator's state;
    - the sender is a validator;
    - `vote.message.ffg_source.block_hash` is an ancestor of `vote.message.ffg_target.block_hash`;
    - `vote.message.ffg_target.block_hash` is an ancestor of `vote.message.head_hash`;
    - the checkpoint slot of `vote.message.ffg_source` is strictly less than checkpoint slot of `vote.message.ffg_target`;   
    - the block associated with `vote.message.ffg_source.block_hash` has a slot number that matches the slot number specified in the same vote message;
    - the block associated with `vote.message.ffg_target.block_hash` has a slot number that matches the slot number specified in the same vote message;
    - the block hash associated the source exists within a validator's view of blocks; and
    - the block hash associated the target exists within a validator's view of blocks.
    """
    return (
        verify_vote_signature(vote) and
        has_block_hash(vote.message.head_hash, node_state) and
        is_complete_chain(get_block_from_hash(vote.message.head_hash, node_state), node_state) and
        is_validator(
            vote.sender,
            get_validator_set_for_slot(get_block_from_hash(vote.message.head_hash, node_state), vote.message.slot, node_state)) and
        is_ancestor_descendant_relationship(
            get_block_from_hash(vote.message.ffg_source.block_hash, node_state),
            get_block_from_hash(vote.message.ffg_target.block_hash, node_state),
            node_state) and
        is_ancestor_descendant_relationship(
            get_block_from_hash(vote.message.ffg_target.block_hash, node_state),
            get_block_from_hash(vote.message.head_hash, node_state),
            node_state) and
        vote.message.ffg_source.chkp_slot < vote.message.ffg_target.chkp_slot and
        has_block_hash(vote.message.ffg_source.block_hash, node_state) and
        get_block_from_hash(vote.message.ffg_source.block_hash, node_state).slot == vote.message.ffg_source.block_slot and
        has_block_hash(vote.message.ffg_target.block_hash, node_state) and
        get_block_from_hash(vote.message.ffg_target.block_hash, node_state).slot == vote.message.ffg_target.block_slot
    )


def filter_out_invalid_votes(votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    return pset_filter(
        lambda vote: valid_vote(vote, node_state),
        votes
    )


def get_votes_included_in_blockchain(block: Block, node_state: NodeState) -> PSet[SignedVoteMessage]:
    if block == node_state.configuration.genesis or not has_block_hash(block.parent_hash, node_state):
        return block.votes
    else:
        return pset_merge(block.votes, get_votes_included_in_blockchain(get_block_from_hash(block.parent_hash, node_state), node_state))


def get_votes_included_in_blocks(blocks: PSet[Block]) -> PSet[SignedVoteMessage]:
    return pset_merge_flatten(
        pset_map(
            lambda b: b.votes,
            blocks
        )
    )


def votes_to_include_in_proposed_block(node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    The votes to include in a proposed block are all those with a head vote for a block in the chain
    of the proposed block that have not already been included in such a chain
    """
    head_block = get_head(node_state)
    votes_for_blocks_in_canonical_chain = filter_out_head_votes_not_for_blocks_in_blockchain(
        filter_out_invalid_votes(node_state.votes, node_state),
        head_block,
        node_state
    )

    return pset_difference(
        votes_for_blocks_in_canonical_chain,
        get_votes_included_in_blockchain(head_block, node_state)
    )


def get_new_block(node_state: NodeState) -> Block:
    head_block = get_head(node_state, is_proposer=True)
    return Block(
        parent_hash=block_hash(head_block),
        body=get_block_body(node_state),
        slot=get_slot(node_state),
        votes=votes_to_include_in_proposed_block(node_state)
    )


def get_votes_to_include_in_propose_message_view(node_state: NodeState) -> PVector[SignedVoteMessage]:
    """
    The votes to include in the view shared via a Propose message are all valid, non-expired head votes
    for a block descendant of the greatest justified checkpoint but that are not in the chain of the proposed block
    (as those in the chain of the proposed block are already included in the proposed block itself via, see `votes_to_include_in_proposed_block`)
    """
    head_block = get_head(node_state)
    return from_set_to_pvector(
        filter_out_head_votes_for_blocks_in_blockchain(
            filter_out_head_votes_non_descendant_of_block(
                get_block_from_hash(get_greatest_justified_checkpoint(node_state).block_hash, node_state),
                filter_out_expired_head_votes(
                    filter_out_invalid_votes(node_state.votes, node_state),
                    node_state
                ),
                node_state
            ),
            head_block,
            node_state
        )
    )


def get_GHOST_weight(block: Block, votes: PSet[SignedVoteMessage], node_state: NodeState, validatorBalances: ValidatorBalances) -> int:
    """
    The GHOST weight of a `block` is determined by the total stake supporting the branch that ends with this `block` as its tip. 
    Validators vote with associated stakes, and the collective stake behind these votes establishes the block's GHOST weight.
    """    
    return pset_sum(
        pset_map(
            lambda vote: validatorBalances[vote.sender],
            pset_filter(
                lambda vote:
                    has_block_hash(vote.message.head_hash, node_state) and  # Perhaps not needed
                    is_ancestor_descendant_relationship(
                        block,
                        get_block_from_hash(vote.message.head_hash, node_state),
                        node_state) and
                    is_validator(vote.sender, validatorBalances),
                votes
            )
        )
    )


def get_children(block: Block, node_state: NodeState) -> PSet[Block]:
    """
    Returns all the children of a given `block`.
    """ 
    return pset_filter(
        lambda b: b.parent_hash == block_hash(block),
        get_all_blocks(node_state)
    )


def find_head_from(block: Block, votes: PSet[SignedVoteMessage], node_state: NodeState, validatorBalances: ValidatorBalances, total_vote_weight: int) -> Block:
    """
    For a given `block`, it uses `get_GHOST_weight` to determine the chain's tip with the largest associated total stake.    
    """ 

    children_with_majority_support = pset_filter(
        get_children(block, node_state),
        lambda child: get_GHOST_weight(child, votes, node_state, validatorBalances) > total_vote_weight // 2
    )

    if len(children_with_majority_support) == 0:
        return block
    else:
        return find_head_from(pset_pick_element(children_with_majority_support), votes, node_state, validatorBalances)



def get_head(node_state: NodeState, is_proposal: bool=False) -> Block:
    """
    It defines the fork-choice function. It starts from the greatest justified checkpoint, it considers 
    the latest (non equivocating) votes cast by validators that are not older than `get_slot(node_state)` - `node_state.configuration.eta` slots,
    and it outputs the head of the canonical chain with the largest associated total stake among such `relevant_votes`.
    """

    relevant_votes: PSet[SignedVoteMessage] = filter_out_non_LMD_head_votes(
        filter_out_expired_head_votes(
            filter_out_head_equivocating_votes(
                filter_out_invalid_votes(
                    node_state.votes,
                    node_state
                ),
                node_state
            ),
            node_state
        ),
        node_state,
    )

    if not is_proposal:
        relevant_votes = filter_out_late_received_head_votes(relevant_votes, node_state)

    validatorBalances = get_validator_set_for_slot(
        node_state.highest_candidate_block,
        get_slot(node_state),
        node_state
    )

    total_vote_weight = pset_sum(
        pset_map(
            lambda v: pmap_get(validatorBalances, v),
            pset_intersection(
                pmap_keys(validatorBalances),
                pset_map(lambda vote: vote.sender, relevant_votes)
            )
        )
    )

    return find_head_from(
        node_state.highest_candidate_block,
        relevant_votes,
        node_state,
        validatorBalances,
        total_vote_weight,
    )


def execute_view_merge(node_state: NodeState) -> NodeState:
    """
    It merges a validator's buffer with its local view, specifically merging the buffer of blocks `node_state.buffer_blocks` 
    into the local view of blocks `node_state.blocks` and the buffer of votes `node_state.buffer_votes` into the 
    local view of votes `node_state.votes`.
    """ 
    node_state = node_state.set(blocks=pmap_merge(node_state.blocks, node_state.buffer_blocks))
    node_state = node_state.set(view_vote=pset_merge(
        pset_merge(
            node_state.votes,
            node_state.buffer_votes
        ),
        get_votes_included_in_blocks(get_all_blocks(node_state)))
    )
    node_state = node_state.set(buffer_vote=pset_get_empty())
    node_state = node_state.set(buffer_blocks=pmap_get_empty())
    return node_state


def get_block_k_deep(blockHead: Block, k: int, node_state: NodeState) -> Block:
    """
    It identifies the block that is `k` blocks back from the tip of the canonical chain, or the genesis block `node_state.configuration.genesis`.
    """ 
    Requires(is_complete_chain(blockHead, node_state))
    if k <= 0 or blockHead == node_state.configuration.genesis:
        return blockHead
    else:
        return get_block_k_deep(get_parent(blockHead, node_state), k - 1, node_state)


def is_confirmed(block: Block, node_state: NodeState) -> bool:
    head_block = get_head(node_state)

    validatorBalances = get_validator_set_for_slot(
        get_block_from_hash(get_greatest_justified_checkpoint(node_state).block_hash, node_state),
        get_slot(node_state),
        node_state
    )

    tot_validator_set_weight = validator_set_weight(pmap_keys(validatorBalances), validatorBalances)

    return (
        is_ancestor_descendant_relationship(block, head_block, node_state) and
        get_GHOST_weight(block, node_state.votes, node_state, validatorBalances) * 3 >= tot_validator_set_weight * 2
    )


def filter_out_not_confirmed(blocks: PSet[Block], node_state: NodeState) -> PSet[Block]:
    return pset_filter(
        lambda block: is_confirmed(block, node_state),
        blocks
    )


def is_recent_quorum_for_block(votes: PSet[SignedVoteMessage], block: Block, node_state: NodeState) -> bool:
    previous_slot = get_slot(node_state) - 1
    votes_from_previous_slot = pset_filter(lambda vote: vote.message.slot == previous_slot, votes)
    validatorBalances = get_validator_set_for_slot(
        get_greatest_justified_block(node_state),
        get_slot(node_state),
        node_state
    )
    tot_validator_set_weight = validator_set_weight(pmap_keys(validatorBalances), validatorBalances)
    get_GHOST_weight(block, votes_from_previous_slot, node_state, validatorBalances) * 3 >= tot_validator_set_weight * 2



def get_greatest_justified_block(node_state: NodeState) -> Block:
    return get_block_from_hash(node_state.greatest_justified_checkpoint.block_hash, node_state)

def get_highest_candidate_block(node_state: NodeState) -> Block:
    greatest_justified_block = get_greatest_justified_block(node_state)
    descendants_of_greatest_justified = filter_out_blocks_non_ancestor_of_block(greatest_justified_block, get_all_blocks(node_state), node_state)
    candidate_blocks = pset_filter(lambda block: is_recent_quorum_for_block(node_state.votes, block, node_state), descendants_of_greatest_justified)
    if len(candidate_blocks) > 0:
        return pset_max(candidate_blocks, lambda b: b.slot)
    else:
        return greatest_justified_block


def update_justified_and_candidate(node_state: NodeState) -> NodeState:
    node_state = node_state.set(
            greatest_justified_checkpoint=get_greatest_justified_checkpoint(node_state),
    )
    # Important to set them sequentially because get_highest_candidate_block makes use of node_state.greatest_justified_checkpoint
    node_state = node_state.set(
            highest_candidate_block=get_highest_candidate_block(node_state)
    )

    return node_state

def is_greater_checkpoint(checkpoint1: Checkpoint, checkpoint2: Checkpoint):
    checkpoint_order_function = lambda c: (c.chkp_slot, c.block_slot)
    return checkpoint_order_function(checkpoint1) > checkpoint_order_function(checkpoint2)