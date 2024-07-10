from dataclasses import dataclass
from pyrsistent import PRecord, field, PSet, PMap, PVector
from enum import Enum
from ..common.data_structures import *

class NodeState(PRecord):
    common: CommonNodeState
    current_phase: NodePhase = field(type=NodePhase)
    buffer_votes: PSet[SignedVoteMessage] = field()
    buffer_blocks: PMap[Hash, Block] = field()


@dataclass(frozen=True)
class NewNodeStateAndMessagesToTx:
    state: NodeState
    proposeMessagesToTx: PSet[SignedProposeMessage]
    voteMessagesToTx: PSet[SignedVoteMessage]