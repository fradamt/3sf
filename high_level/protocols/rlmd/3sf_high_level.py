from ...common.data_structures import *
from ...common.formal_verification_annotations import *
from ...common.pythonic_code_generic import *
from ...common.stubs import *
from .helpers import *

# @Init
# def init() -> NodeState:
#     return NodeState(
#         identity=NodeIdentity(),
#         current_phase = NodePhase.PROPOSE,
#         current_slot=0,
#         blocks=[],
#         configuration=Configuration(
#             delta=10,
#             genesis=Block(
#                 parent_hash="",
#                 body=BlockBody()
#             )
#         )
#     )


@Event
def on_tick(node_state: NodeState, time: int) -> NewNodeStateAndMessagesToTx:
    """
    Manages the transition of the system's state, making changes in both the current slot and the phase.
    Upon initiating a new phase, it activates one of four distinct events based on the phase transition:
    - `on_propose`: Triggered at the start of a new slot, signaling that a designated proposer should submit a new block.
    - `on_vote`: Indicates that validators are now expected to cast their votes in support of a proposed block.
    - `on_confirm`: Calls for validators to update their set of confirmation candidates.
    - `on_merge`: Signals the integration of the current buffer contents into a validator's local view.
    """
    new_slot = get_slot_from_time(time, node_state)
    new_phase = get_phase_from_time(time, node_state)

    if new_slot != node_state.common.current_slot or new_phase != node_state.current_phase:
        node_state = node_state.set(common=node_state.common.set(current_slot=new_slot))
        node_state = node_state.set(current_phase=new_phase)

        if node_state.current_phase == NodePhase.PROPOSE:
            return on_propose(node_state)
        elif node_state.current_phase == NodePhase.VOTE:
            return on_vote(node_state)
        elif node_state.current_phase == NodePhase.CONFIRM:
            return on_confirm(node_state)
        else:
            return on_merge(node_state)
    else:
        return NewNodeStateAndMessagesToTx(
            state=node_state,
            proposeMessagesToTx=pset_get_empty(),
            voteMessagesToTx=pset_get_empty()
        )


def on_propose(node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    """
    A validator acting as a proposer first merges its buffer with its local view using the `execute_view_merge` function.
    This step prepares the validator to propose a new block, generated through `get_new_block`.
    Next, the proposer constructs a new proposal `signed_propose` by signing the block together with its local view.
    Finally, the validator broadcasts such proposal.
    """
    proposer = get_proposer(node_state.common)

    if proposer == node_state.common.identity:
        node_state = execute_view_merge(node_state)

        signed_propose = sign_propose_message(
            ProposeMessage(
                block=get_new_block(node_state),
                proposer_view=get_votes_to_include_in_propose_message_view(node_state)
            ),
            node_state.common
        )

        return NewNodeStateAndMessagesToTx(
            state=node_state,
            proposeMessagesToTx=pset_get_singleton(signed_propose),
            voteMessagesToTx=pset_get_empty()
        )

    else:
        return NewNodeStateAndMessagesToTx(
            state=node_state,
            proposeMessagesToTx=pset_get_empty(),
            voteMessagesToTx=pset_get_empty()
        )


def on_vote(node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    """
    A validator in the role of a voter begins by identifying the current tip of the canonical blockchain using the `get_head` function.
    The validator then filters through its confirmation candidates, removing any that conflict with the `get_head` output, while also
    including the greatest justified checkpoint.
    The candidate block, `bcand`, is determined as the max among the confirmation candidates and the greatest justified checkpoint.
    The validator then considers the k deep prefix from the canonical chain's tip, referred to as `k_deep_block`, and compares it with `bcand`.
    The next step involves updating the validator's available chain, `node_state.chava`, to reflect the max between `bcand` and `k_deep_block`, provided neither are ancestors of `node_state.chava`.
    Finally, the validator casts a vote, specifying the `get_greatest_justified_checkpoint` as the source checkpoint and defining the target checkpoint based on `node_state.chava`, the current slot, and the slot of `chAva`.
    """
    ch = get_head(node_state)
    s_cand = pset_add(
        filter_out_blocks_non_ancestor_of_block(
            ch,
            node_state.s_cand,
            node_state.common
        ),
        get_block_from_hash(get_greatest_justified_checkpoint(node_state.common).block_hash, node_state.common)
    )

    bcand = pset_max(s_cand, lambda b: b.slot)

    k_deep_block = get_block_k_deep(ch, node_state.common.configuration.k, node_state)

    if not (
        is_ancestor_descendant_relationship(bcand, node_state.common.chava, node_state.common) and
        is_ancestor_descendant_relationship(k_deep_block, node_state.common.chava, node_state.common)
    ):
        node_state = node_state.set(
            common=node_state.common.set(chava=pset_max(
                pset_merge(
                    pset_get_singleton(bcand),
                    pset_get_singleton(k_deep_block)
                ),
                lambda b: b.slot
            )
            ))

    signedVoteMessage = sign_vote_message(
        VoteMessage(
            slot=node_state.common.current_slot,
            head_hash=block_hash(get_head(node_state)),
            ffg_source=get_greatest_justified_checkpoint(node_state.common),
            ffg_target=Checkpoint(
                block_hash=block_hash(node_state.common.chava),
                chkp_slot=node_state.common.current_slot,
                block_slot=node_state.common.chava.slot
            )
        ),
        node_state.common
    )

    return NewNodeStateAndMessagesToTx(
        state=node_state,
        proposeMessagesToTx=pset_get_empty(),
        voteMessagesToTx=pset_get_singleton(signedVoteMessage)
    )


def on_confirm(node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    """
    A validator refines its set of confirmation candidates, specifically, the set `s_cand` of blocks that garnered over two-thirds
    of the votes during the NodePhase.VOTE stage.
    """
    return NewNodeStateAndMessagesToTx(
        state=node_state.set(
            s_cand=pset_merge(
                node_state.s_cand,
                filter_out_not_confirmed(
                    get_all_blocks(node_state.common),
                    node_state
                )
            )
        ),
        proposeMessagesToTx=pset_get_empty(),
        voteMessagesToTx=pset_get_empty()
    )


def on_merge(node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    """
    A validator merges its buffer into its local view through `execute_view_merge`.
    """
    return NewNodeStateAndMessagesToTx(
        state=execute_view_merge(node_state),
        proposeMessagesToTx=pset_get_empty(),
        voteMessagesToTx=pset_get_empty()
    )


@Event
def on_received_propose(propose: SignedProposeMessage, node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    """
    A validator merges the proposer's view with its own local view upon receiving a proposal within the timeframe from
    4Δt to 4Δt+Δ, preparing it for the phase NodePhase.VOTE.
    """
    node_state = node_state.set(
        buffer_blocks=pmap_set(
            node_state.buffer_blocks,
            block_hash(propose.message.block),
            propose.message.block)
    )

    if node_state.current_phase == NodePhase.PROPOSE:  # Is this Ok or do we need to also include 4\Delta t + \Delta ?
        node_state = node_state.set(
            common=node_state.common.set(
                view_votes=pset_merge(
                    node_state.common.view_votes,
                    from_pvector_to_pset(propose.message.proposer_view))
            ))

    return NewNodeStateAndMessagesToTx(
        state=node_state,
        proposeMessagesToTx=pset_get_empty(),
        voteMessagesToTx=pset_get_empty()
    )


@Event
def on_block_received(block: Block, node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    """
    A validator, upon receiving a `block` at any moment, adds it to its local buffer `node_state.buffer_blocks`.
    """
    return NewNodeStateAndMessagesToTx(
        state=node_state.set(
            buffer_blocks=pmap_set(
                node_state.buffer_blocks,
                block_hash(block),
                block)
        ),
        proposeMessagesToTx=pset_get_empty(),
        voteMessagesToTx=pset_get_empty()
    )


@Event
def on_vote_received(vote: SignedVoteMessage, node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    """
    A validator, upon receiving a `vote` at any moment, adds it to its local buffer `node_state.buffer_votes`.
    """
    return NewNodeStateAndMessagesToTx(
        state=node_state.set(
            buffer_votes=pset_add(
                node_state.buffer_votes,
                vote
            )
        ),
        proposeMessagesToTx=pset_get_empty(),
        voteMessagesToTx=pset_get_empty()
    )


@View
def finalized_chain(node_state: NodeState) -> PVector[Block]:
    """
    The finalized chain is the chain output by the finalizing component of the protocol.
    """
    return get_blockchain(
        get_block_from_hash(
            get_greatest_finalized_checkpoint(node_state.common).block_hash,
            node_state.common
        ),
        node_state.common
    )


@View
def available_chain(node_state: NodeState) -> PVector[Block]:
    """
    The available chain `node_state.chava` is the chain output by the dynamically available component of the protocol.
    """
    return get_blockchain(
        node_state.common.chava,
        node_state.common
    )
