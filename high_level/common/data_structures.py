from dataclasses import dataclass
from pyrsistent import PRecord, field, PSet, PMap, PVector
from enum import Enum


@dataclass(frozen=True)
class Hash(str):
    pass


@dataclass(frozen=True)
class Signature:
    pass


@dataclass(frozen=True)
class NodeIdentity(str):
    pass


ValidatorBalances = PMap[NodeIdentity, int]


@dataclass(frozen=True)
class Checkpoint:
    block_hash: Hash
    chkp_slot: int
    block_slot: int


@dataclass(frozen=True)
class VoteMessage:
    slot: int  # Do we need this. We could just use ffg_target.slot
    head_hash: Hash
    ffg_source: Checkpoint
    ffg_target: Checkpoint


@dataclass(frozen=True)
class SignedVoteMessage:
    message: VoteMessage
    signature: Signature
    sender: NodeIdentity


@dataclass(frozen=True)
class BlockBody(object):
    pass


@dataclass(frozen=True)
class Block:
    parent_hash: Hash
    slot: int
    votes: PSet[SignedVoteMessage]
    body: BlockBody


@dataclass(frozen=True)
class ProposeMessage:
    block: Block
    proposer_view: PVector[SignedVoteMessage]


@dataclass(frozen=True)
class SignedProposeMessage:
    message: ProposeMessage
    signature: Signature


@dataclass(frozen=True)
class NodePhase(Enum):
    PROPOSE = 0
    VOTE = 1
    CONFIRM = 2
    MERGE = 3


@dataclass(frozen=True)
class Configuration():
    delta: int
    genesis: Block
    eta: int
    k: int


class NodeState(PRecord):
    configuration: Configuration = field(type=Configuration)
    identity: NodeIdentity = field(type=NodeIdentity)
    current_slot: int = field(type=int)
    current_phase: NodePhase = field(type=NodePhase)
    view_blocks: PMap[Hash, Block] = field()  # Using field(type=dict[Hash,Block]) raises a max stack depth rec. error in execution. Same for sets below
    view_votes: PSet[SignedVoteMessage] = field()
    buffer_votes: PSet[SignedVoteMessage] = field()
    buffer_blocks: PMap[Hash, Block] = field()
    s_cand: PSet[Block] = field()
    chava: Block = field()


@dataclass(frozen=True)
class NewNodeStateAndMessagesToTx:
    state: NodeState
    proposeMessagesToTx: PSet[SignedProposeMessage]
    voteMessagesToTx: PSet[SignedVoteMessage]
