from .data_structures import *
from .formal_verification_annotations import *
from .common import is_complete_chain


def block_hash(block: Block) -> Hash:
    ...

def verify_vote_signature(vote: SignedVoteMessage) -> bool:
    ...

def get_block_body(nodeState: NodeState) -> BlockBody:
    ...

def get_proposer(nodeState: NodeState) -> NodeIdentity:
    ...

def get_validator_set_for_slot(block: Block, slot: int, nodeState: NodeState) -> ValidatorBalances: # type: ignore[return]
    Requires(is_complete_chain(block, nodeState))
    ...

def sign_propose_message(propose_message: ProposeMessage, nodeState: NodeState) -> SignedProposeMessage:
    ...

def get_signer_of_vote_message(vote: SignedVoteMessage, nodeState: NodeState) -> NodeIdentity:
    ...

def sign_vote_message(vote_message: VoteMessage, nodeState: NodeState) -> SignedVoteMessage:
    ...