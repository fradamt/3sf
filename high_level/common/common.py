from pyrsistent import PSet, PMap, PVector

from .data_structures import *
from .formal_verification_annotations import *
from .pythonic_code_generic import *
from .stubs import *

def genesis_checkpoint(node_state: CommonNodeState) -> Checkpoint:
    """
    It defines the genesis block.
    """
    return Checkpoint(
        block_hash=block_hash(node_state.configuration.genesis),
        chkp_slot=0,
        block_slot=0
    )


def has_block_hash(block_hash: Hash, node_state: CommonNodeState) -> bool:
    """
    It checks if a given `block_hash` is present within a `node_state`.
    """
    return pmap_has(node_state.view_blocks, block_hash)


def get_block_from_hash(block_hash: Hash, node_state: CommonNodeState) -> Block:
    """
    It retrieves the block associated to a `block_hash`.
    """
    Requires(has_block_hash(block_hash, node_state))
    return pmap_get(node_state.view_blocks, block_hash)


def has_parent(block: Block, node_state: CommonNodeState) -> bool:
    """
    It checks whether a `block` has a parent.
    """
    return has_block_hash(block.parent_hash, node_state)

def get_parent(block: Block, node_state: CommonNodeState) -> Block:
    """
    It retrieves the parent of a given `block`.
    """
    Requires(has_parent(block, node_state))
    return get_block_from_hash(block.parent_hash, node_state)


def get_all_blocks(node_state: CommonNodeState) -> PSet[Block]:
    """
    It retrieves all the blocks in a `node_state`.
    """
    return pmap_values(node_state.view_blocks)

def is_complete_chain(block: Block, node_state: CommonNodeState) -> bool:
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
    
def is_validator(node: NodeIdentity, validatorBalances: ValidatorBalances) -> bool:
    """
    It checks whether a `node` is a validator.
    """
    return pmap_has(validatorBalances, node)


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
    
def get_blockchain(block: Block, node_state: CommonNodeState) -> PVector[Block]:
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