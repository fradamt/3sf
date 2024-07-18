from pyrsistent import PSet

from .data_structures import *
from .formal_verification_annotations import *
from .pythonic_code_generic import *
from .helpers import *
from .stubs import *


def get_set_FFG_targets(votes: PSet[SignedVoteMessage]) -> PSet[Checkpoint]:
    """
    It extracts a set of ffg targets from a set of `votes`.
    """
    return pset_map_to_pset(
        lambda vote: vote.message.ffg_target,
        votes
    )


def valid_FFG_vote(vote: SignedVoteMessage, node_state: CommonNodeState) -> bool:
    """
    A FFG vote is valid if:
    - the sender is a validator;
    - `vote.message.ffg_source.block_hash` is an ancestor of `vote.message.ffg_target.block_hash`;
    - the checkpoint slot of `vote.message.ffg_source` is strictly less than checkpoint slot of `vote.message.ffg_target`;
    - the block associated with `vote.message.ffg_source.block_hash` has a slot number that matches the slot number specified in the same vote message;
    - the block associated with `vote.message.ffg_target.block_hash` has a slot number that matches the slot number specified in the same vote message;
    - the block hash associated the source exists within a validator's view of blocks; and
    - the block hash associated the target exists within a validator's view of blocks.
    """
    return (
        verify_vote_signature(vote) and
        is_validator(
            vote.sender,
            get_validator_set_for_slot(get_block_from_hash(vote.message.head_hash, node_state), vote.message.slot, node_state)) and
        is_ancestor_descendant_relationship(
            get_block_from_hash(vote.message.ffg_source.block_hash, node_state),
            get_block_from_hash(vote.message.ffg_target.block_hash, node_state),
            node_state) and
        vote.message.ffg_source.chkp_slot < vote.message.ffg_target.chkp_slot and
        has_block_hash(vote.message.ffg_source.block_hash, node_state) and
        get_block_from_hash(vote.message.ffg_source.block_hash, node_state).slot == vote.message.ffg_source.block_slot and
        has_block_hash(vote.message.ffg_target.block_hash, node_state) and
        get_block_from_hash(vote.message.ffg_target.block_hash, node_state).slot == vote.message.ffg_target.block_slot
    )


def is_FFG_vote_in_support_of_checkpoint_justification(vote: SignedVoteMessage, checkpoint: Checkpoint, node_state: CommonNodeState) -> bool:
    """
    It determines whether a given `vote` supports the justification of a specified `checkpoint`.
    """
    return (
        valid_FFG_vote(vote, node_state) and
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


def filter_out_FFG_votes_not_in_FFG_support_of_checkpoint_justification(votes: PSet[SignedVoteMessage], checkpoint: Checkpoint, node_state: CommonNodeState) -> PSet[SignedVoteMessage]:
    """
    It filters out ffg votes that do not support the justification of a specified `checkpoint`.
    """
    return pset_filter(lambda vote: is_FFG_vote_in_support_of_checkpoint_justification(vote, checkpoint, node_state), votes)


def get_validators_in_FFG_support_of_checkpoint_justification(votes: PSet[SignedVoteMessage], checkpoint: Checkpoint, node_state: CommonNodeState) -> PSet[NodeIdentity]:
    """
    It identifies and returns the set of validators that have cast `votes` in support of the justification of a specified `checkpoint`.
    """
    return pset_map_to_pset(
        lambda vote: vote.sender,
        filter_out_FFG_votes_not_in_FFG_support_of_checkpoint_justification(votes, checkpoint, node_state)
    )


def is_justified_checkpoint(checkpoint: Checkpoint, node_state: CommonNodeState) -> bool:
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

        FFG_support_weight = validator_set_weight(get_validators_in_FFG_support_of_checkpoint_justification(node_state.view_votes, checkpoint, node_state), validatorBalances)
        tot_validator_set_weight = validator_set_weight(pmap_keys(validatorBalances), validatorBalances)

        return FFG_support_weight * 3 >= tot_validator_set_weight * 2


def filter_out_non_justified_checkpoint(checkpoints: PSet[Checkpoint], node_state: CommonNodeState) -> PSet[Checkpoint]:
    """
    It filters out `checkpoints` that are not justified.
    """
    return pset_filter(lambda checkpoint: is_justified_checkpoint(checkpoint, node_state), checkpoints)


def get_justified_checkpoints(node_state: CommonNodeState) -> PSet[Checkpoint]:
    """
    It retrieves all the justified checkpoints from a `note_state`. First it extracts all ffg target checkpoints from
    the set of votes in the `node_state`. Then it filter out these checkpoints to keep only those that are justified.
    The `genesis_checkpoint` is automatically considered justified.
    """
    return pset_add(
        filter_out_non_justified_checkpoint(get_set_FFG_targets(node_state.view_votes), node_state),
        genesis_checkpoint(node_state)
    )


def get_greatest_justified_checkpoint(node_state: CommonNodeState) -> Checkpoint:
    """
    It retrieves the greatest justified checkpoint from a `node_state`.
    """
    return pset_max(
        get_justified_checkpoints(node_state),
        lambda c: (c.chkp_slot, c.block_slot)
    )


def is_FFG_vote_linking_to_a_checkpoint_in_next_slot(vote: SignedVoteMessage, checkpoint: Checkpoint, node_state: CommonNodeState) -> bool:
    """
    It evaluates whether a given `vote` represents a link from a specified `checkpoint` to a checkpoint in the immediately following slot.
    """
    return (
        valid_FFG_vote(vote, node_state) and
        vote.message.ffg_source == checkpoint and
        vote.message.ffg_target.chkp_slot == checkpoint.chkp_slot + 1
    )


def filter_out_FFG_vote_not_linking_to_a_checkpoint_in_next_slot(checkpoint: Checkpoint, node_state: CommonNodeState) -> PSet[SignedVoteMessage]:
    """
    It filters and retains only those votes from a `node_state` that are linking to a `checkpoint` in the next slot.
    """
    return pset_filter(lambda vote: is_FFG_vote_linking_to_a_checkpoint_in_next_slot(vote, checkpoint, node_state), node_state.view_votes)


def get_validators_in_FFG_votes_linking_to_a_checkpoint_in_next_slot(checkpoint: Checkpoint, node_state: CommonNodeState) -> PSet[NodeIdentity]:
    """
    It retrieves the identities of validators who have cast ffg votes that support linking a specified `checkpoint` to its immediate successor.
    """
    return pset_map_to_pset(
        lambda vote: vote.sender,
        filter_out_FFG_vote_not_linking_to_a_checkpoint_in_next_slot(checkpoint, node_state)
    )


def is_finalized_checkpoint(checkpoint: Checkpoint, node_state: CommonNodeState) -> bool:
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


def filter_out_non_finalized_checkpoint(checkpoints: PSet[Checkpoint], node_state: CommonNodeState) -> PSet[Checkpoint]:
    """
    It filters out non finalized `checkpoints` from a `node_state`.
    """
    return pset_filter(lambda checkpoint: is_finalized_checkpoint(checkpoint, node_state), checkpoints)


def get_finalized_checkpoints(node_state: CommonNodeState) -> PSet[Checkpoint]:
    """
    It retrieves from `node_state` all the checkpoints that have been finalized.
    """
    return pset_add(
        filter_out_non_finalized_checkpoint(get_set_FFG_targets(node_state.view_votes), node_state),
        genesis_checkpoint(node_state)
    )


def get_greatest_finalized_checkpoint(node_state: CommonNodeState) -> Checkpoint:
    """
    It returns the greatest finalized checkpoint from a `node_state`.
    """
    return pset_max(
        get_finalized_checkpoints(node_state),
        lambda c: c.chkp_slot
    )


def are_equivocating_votes(vote1: SignedVoteMessage, vote2: SignedVoteMessage) -> bool:
    return (
        verify_vote_signature(vote1) and
        verify_vote_signature(vote2) and
        vote1.sender == vote2.sender and
        vote1 != vote2 and
        vote1.message.ffg_target.chkp_slot == vote2.message.ffg_target.chkp_slot
    )


def does_first_vote_surround_second_vote(vote1: SignedVoteMessage, vote2: SignedVoteMessage) -> bool:
    return (
        verify_vote_signature(vote1) and
        verify_vote_signature(vote2) and
        vote1.sender == vote2.sender and
        (vote1.message.ffg_source.chkp_slot, vote1.message.ffg_source.block_slot) < (vote2.message.ffg_source.chkp_slot, vote2.message.ffg_source.block_slot) and
        vote2.message.ffg_target.chkp_slot < vote1.message.ffg_target.chkp_slot
    )


def is_slashable_offence(vote1: SignedVoteMessage, vote2: SignedVoteMessage) -> bool:
    return (
        are_equivocating_votes(vote1, vote2) or
        does_first_vote_surround_second_vote(vote1, vote2) or
        does_first_vote_surround_second_vote(vote2, vote1)
    )


def is_slashable_node(node: NodeIdentity, vote1: SignedVoteMessage, vote2: SignedVoteMessage) -> bool:
    return (
        node == vote1.sender and
        is_slashable_offence(vote1, vote2)
    )


def get_slashabe_nodes(vote_view: PSet[SignedVoteMessage]) -> PSet[NodeIdentity]:
    return pset_map_to_pset(lambda vote: vote.sender,
                            pset_filter(lambda vote1: not pset_is_empty(pset_filter(lambda vote2: is_slashable_offence(vote1, vote2), vote_view)), vote_view))
