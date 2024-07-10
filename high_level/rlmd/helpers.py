from pyrsistent import PSet, PMap, PVector

from .rlmd_data_structures import *
from ..common.formal_verification_annotations import *
from ..common.pythonic_code_generic import *
from ..common.common import *
from ..common.bft import *
from ..common.stubs import *


def get_slot_from_time(time: int, node_state: NodeState) -> int:
    """
    It calculates the slot number based on a given `time` and the node's configuration settings.
    """
    return time // (4 * node_state.common.configuration.delta)


def get_phase_from_time(time: int, node_state: NodeState) -> NodePhase:
    """
    It calculates the phase within a slot based on a given `time` and the node's configuration settings.
    """
    time_in_slot = time % (4 * node_state.common.configuration.delta)

    if time_in_slot >= 3 * node_state.common.configuration.delta:
        return NodePhase.MERGE
    elif time_in_slot >= 2 * node_state.common.configuration.delta:
        return NodePhase.CONFIRM
    elif time_in_slot >= node_state.common.configuration.delta:
        return NodePhase.VOTE
    else:
        return NodePhase.PROPOSE


def filter_out_GHOST_votes_non_descendant_of_block(block: Block, votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filters a set of `votes`, retaining only those that are for blocks which are descendants of a specified `block`.
    """
    return pset_filter(
        lambda vote:
            has_block_hash(vote.message.head_hash, node_state.common) and
            is_ancestor_descendant_relationship(
                block,
                get_block_from_hash(vote.message.head_hash, node_state.common.common),
                node_state.common
            ),
        votes
    )


def is_GHOST_vote_for_block_in_blockchain(vote: SignedVoteMessage, blockchainHead: Block, node_state: NodeState) -> bool:
    """
    It evaluates whether a given `vote` is for a block that is part of the blockchain ending at a specified "head" block (`blockchainHead`).
    """
    return (
        has_block_hash(vote.message.head_hash, node_state.common) and
        is_ancestor_descendant_relationship(
            get_block_from_hash(vote.message.head_hash, node_state.common.common),
            blockchainHead,
            node_state.common)
    )


def filter_out_GHOST_votes_not_for_blocks_in_blockchain(votes: PSet[SignedVoteMessage], blockchainHead: Block, node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filter through a set of `votes`, retaining only those that are for blocks within the blockchain leading up to a specified `blockchainHead`.
    """
    return pset_filter(
        lambda vote: is_GHOST_vote_for_block_in_blockchain(vote, blockchainHead, node_state),
        votes
    )


def filter_out_GHOST_votes_for_blocks_in_blockchain(votes: PSet[SignedVoteMessage], blockchainHead: Block, node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filter through a set of `votes`, excluding those that are for blocks within the blockchain leading up to and including a specified `blockchainHead`.
    """
    return pset_filter(
        lambda vote: not is_GHOST_vote_for_block_in_blockchain(vote, blockchainHead, node_state),
        votes
    )


def is_GHOST_vote_expired(vote: SignedVoteMessage, node_state: NodeState) -> bool:
    """
    A vote is expired if it was cast in a slot older than `node_state.current_slot` - `node_state.configuration.eta`.
    """
    return vote.message.slot + node_state.configuration.eta < node_state.current_slot


def filter_out_expired_GHOST_votes(votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filters out from `votes` all the expired votes.
    """
    return pset_filter(
        lambda vote: is_GHOST_vote_expired(vote, node_state),
        votes
    )


def filter_out_non_LMD_GHOST_votes(votes: PSet[SignedVoteMessage]) -> PSet[SignedVoteMessage]:
    lmd: PMap[NodeIdentity, SignedVoteMessage] = pmap_get_empty()

    for vote in votes:
        if not pmap_has(lmd, vote.sender) or vote.message.slot > pmap_get(lmd, vote.sender).message.slot:
            lmd = pmap_set(lmd, vote.sender, vote)

    return pmap_values(lmd)


def is_equivocating_GHOST_vote(vote: SignedVoteMessage, node_state: NodeState) -> bool:
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
            node_state.view_votes
        )
    )


def filter_out_GHOST_equivocating_votes(votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    It filters out from `votes` all the equivocating votes.
    """
    return pset_filter(
        lambda vote: not is_equivocating_GHOST_vote(vote, node_state),
        votes
    )


def valid_vote(vote: SignedVoteMessage, node_state: NodeState) -> bool:
    """
    A vote is valid if:
    - it has a valid signature;
    - it is a valid FFG vote
    - the block hash associated with the voted head block exists within a validator's view of blocks;
    - the head block associated with the vote is part of a complete chain that leads back to the genesis block within a validator's state;
    - the sender is a validator;
    - `vote.message.ffg_source.block_hash` is an ancestor of `vote.message.ffg_target.block_hash`;
    """
    return (
        verify_vote_signature(vote) and
        valid_FFG_vote(vote, node_state.common) and
        has_block_hash(vote.message.head_hash, node_state.common) and
        is_complete_chain(get_block_from_hash(vote.message.head_hash, node_state.common), node_state.common.common) and
        is_validator(
            vote.sender,
            get_validator_set_for_slot(get_block_from_hash(vote.message.head_hash, node_state.common), vote.message.slot, node_state.common.common)) and
        is_ancestor_descendant_relationship(
            get_block_from_hash(vote.message.ffg_target.block_hash, node_state.common.common),
            get_block_from_hash(vote.message.head_hash, node_state.common.common),
            node_state.common)
    )


def filter_out_invalid_votes(votes: PSet[SignedVoteMessage], node_state: NodeState) -> PSet[SignedVoteMessage]:
    return pset_filter(
        lambda vote: valid_vote(vote, node_state),
        votes
    )


def get_votes_included_in_blockchain(block: Block, node_state: NodeState) -> PSet[SignedVoteMessage]:
    if block == node_state.common.configuration.genesis or not has_block_hash(block.parent_hash, node_state.common):
        return block.votes
    else:
        return pset_merge(block.votes, get_votes_included_in_blockchain(get_block_from_hash(block.parent_hash, node_state.common), node_state))


def get_votes_included_in_blocks(blocks: PSet[Block]) -> PSet[SignedVoteMessage]:
    return pset_merge_flatten(
        pset_map(
            lambda b: b.votes,
            blocks
        )
    )


def votes_to_include_in_proposed_block(node_state: NodeState) -> PSet[SignedVoteMessage]:
    """
    The votes to include in a proposed block are all those with a GHOST vote for a block in the chain
    of the proposed block that have not already been included in such a chain
    """
    head_block = get_head(node_state)
    votes_for_blocks_in_canonical_chain = filter_out_GHOST_votes_not_for_blocks_in_blockchain(
        filter_out_invalid_votes(node_state.view_votes, node_state),
        head_block,
        node_state
    )

    return pset_difference(
        votes_for_blocks_in_canonical_chain,
        get_votes_included_in_blockchain(head_block, node_state)
    )


def get_new_block(node_state: NodeState) -> Block:
    head_block = get_head(node_state)
    return Block(
        parent_hash=block_hash(head_block),
        body=get_block_body(node_state.common),
        slot=node_state.current_slot,
        votes=votes_to_include_in_proposed_block(node_state)
    )


def get_votes_to_include_in_propose_message_view(node_state: NodeState) -> PVector[SignedVoteMessage]:
    """
    The votes to include in the view shared via a Propose message are all valid, non-expired GHOST votes
    for a block descendant of the greatest justified checkpoint but that are not in the chain of the proposed block
    (as those in the chain of the proposed block are already included in the proposed block itself via, see `votes_to_include_in_proposed_block`)
    """
    head_block = get_head(node_state)
    return from_set_to_pvector(
        filter_out_GHOST_votes_for_blocks_in_blockchain(
            filter_out_GHOST_votes_non_descendant_of_block(
                get_block_from_hash(get_greatest_justified_checkpoint(node_state.common).block_hash, node_state.common.common),
                filter_out_expired_GHOST_votes(
                    filter_out_invalid_votes(node_state.view_votes, node_state),
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
                    has_block_hash(vote.message.head_hash, node_state.common) and  # Perhaps not needed
                    is_ancestor_descendant_relationship(
                        block,
                        get_block_from_hash(vote.message.head_hash, node_state.common),
                        node_state.common) and
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
        get_all_blocks(node_state.common)
    )


def find_head_from(block: Block, votes: PSet[SignedVoteMessage], node_state: NodeState, validatorBalances: ValidatorBalances) -> Block:
    """
    For a given `block`, it uses `get_GHOST_weight` to determine the chain's tip with the largest associated total stake.
    """
    children = get_children(block, node_state)

    if len(children) == 0:
        return block
    else:
        best_child = pset_max(
            children,
            lambda child: get_GHOST_weight(child, votes, node_state, validatorBalances)
        )

        return find_head_from(best_child, votes, node_state, validatorBalances)


def get_head(node_state: NodeState) -> Block:
    """
    It defines the fork-choice function. It starts from the greatest justified checkpoint, it considers
    the latest (non equivocating) votes cast by validators that are not older than `node_state.current_slot` - `node_state.configuration.eta` slots,
    and it outputs the head of the canonical chain with the largest associated total stake among such `relevant_votes`.
    """
    relevant_votes: PSet[SignedVoteMessage] = filter_out_GHOST_votes_non_descendant_of_block(  # Do we really need this given that we start find_head from GJ?
        get_block_from_hash(get_greatest_justified_checkpoint(node_state.common).block_hash, node_state.common.common),
        filter_out_non_LMD_GHOST_votes(
            filter_out_expired_GHOST_votes(
                filter_out_GHOST_equivocating_votes(
                    filter_out_invalid_votes(
                        node_state.view_votes,
                        node_state
                    ),
                    node_state
                ),
                node_state
            )
        ),
        node_state
    )

    validatorBalances = get_validator_set_for_slot(
        get_block_from_hash(get_greatest_justified_checkpoint(node_state.common).block_hash, node_state.common),
        node_state.current_slot,
        node_state.common
    )

    return find_head_from(
        get_block_from_hash(get_greatest_justified_checkpoint(node_state.common).block_hash, node_state.common),
        relevant_votes,
        node_state,
        validatorBalances
    )


def execute_view_merge(node_state: NodeState) -> NodeState:
    """
    It merges a validator's buffer with its local view, specifically merging the buffer of blocks `node_state.buffer_blocks`
    into the local view of blocks `node_state.view_blocks` and the buffer of votes `node_state.buffer_votes` into the
    local view of votes `node_state.view_votes`.
    """
    node_state = node_state.set(common=node_state.common.set(view_blocks=pmap_merge(node_state.view_blocks, node_state.buffer_blocks)))
    node_state = node_state.set(view_vote=pset_merge(
        pset_merge(
            node_state.view_votes,
            node_state.buffer_votes
        ),
        get_votes_included_in_blocks(get_all_blocks(node_state.common)))
    )
    node_state = node_state.set(buffer_vote=pset_get_empty())
    node_state = node_state.set(buffer_blocks=pmap_get_empty())
    return node_state


def get_block_k_deep(blockHead: Block, k: int, node_state: NodeState) -> Block:
    """
    It identifies the block that is `k` blocks back from the tip of the canonical chain, or the genesis block `node_state.configuration.genesis`.
    """
    Requires(is_complete_chain(blockHead, node_state.common))
    if k <= 0 or blockHead == node_state.configuration.genesis:
        return blockHead
    else:
        return get_block_k_deep(get_parent(blockHead, node_state.common), k - 1, node_state)


def is_confirmed(block: Block, node_state: NodeState) -> bool:
    head_block = get_head(node_state)

    validatorBalances = get_validator_set_for_slot(
        get_block_from_hash(get_greatest_justified_checkpoint(node_state.common).block_hash, node_state.common),
        node_state.current_slot,
        node_state.common
    )

    tot_validator_set_weight = validator_set_weight(pmap_keys(validatorBalances), validatorBalances)

    return (
        is_ancestor_descendant_relationship(block, head_block, node_state.common) and
        get_GHOST_weight(block, node_state.view_votes, node_state, validatorBalances) * 3 >= tot_validator_set_weight * 2
    )


def filter_out_not_confirmed(blocks: PSet[Block], node_state: NodeState) -> PSet[Block]:
    return pset_filter(
        lambda block: is_confirmed(block, node_state),
        blocks
    )
