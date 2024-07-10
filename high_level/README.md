# High-Level Specification of the 3SF Protocol [WIP]

This folder contains an initial high-level specification of the 3SF protocol.

## Status

The current specification is just a start and therefore is still incomplete.

A list of TODOs and Known Issues is detailed in the file [TODO_and_KNOWN_ISSUES.md](TODO_and_KNOWN_ISSUES.md).

## Intent

This high-level specification aims to specify the external behavior of a node implementing the 3SF protocol.

Intuitively, the external behavior corresponds to the messages that a  node sends and how a selected view of the state of a node (e.g. finalized and available chain) changes in response to a given sequence of input events (messages received and time updates).

This specification is not concerned with computational efficiency at all.
However, every function must be computable within a finite, but potentially unbounded, amount of time.

Computational efficiency is intended to be handled by lower-level specifications _implementing_ this high-level specification.
Intuitively, in the context of this work, a specification $S1$ _implements_ a specification $S2$ iff $S1$ and $S2$ exhibit the same external behaviors [^1].

Note that it is admitted for a specification $S1$ implementing a specification $S2$ to extend the data carried by each message.
In this case, intuitively, a specification $S1$ implements a specification $S2$ if any external behavior specified by specification $S1$, _with the portion of data added to each message by_ $S1$ _being removed_, is also an external behavior of specification $S2$.

A more formal definition is provided below.

## Quick Comparison to the current Ethereum specification

This section provides a quick overview of some of the most significant differences between this specification and the current [Ethereum specification](https://github.com/ethereum/consensus-specs).

1. This specification also encodes the expected behavior of honest nodes which in the Ethereum specification is mainly described through natural language in the Honest Validator Guide. By doing so, this specification eliminates possible ambiguities inherent to natural language. Additionally, it provides a more straightforward path to formal verification as formal verification of many properties requires unambiguous coding of the expected behavior of honest nodes.
2. `NodeState` in this specification is the equivalent of `Store` in the Ethereum specification.
3. As anticipated above and detailed below, this specification is not concerned with computational efficiency.
4. Redundant information in `NodeState` is reduced as much as possible, that is, the value of any field in `NodeState` should not be derivable from the value of the other fields. This strategy is expected to help ensure a correct design, as it reduces the risk of discrepancies between the protocol designers' intended relationships among fields and their actual interrelations. Additionally, formal verification processes, which often require determining and proving the relationships between fields, are facilitated by this approach.
5. As a consequence of the above, there is no concept of block state in this specification.
6. As mentioned in other parts of this document, computational efficiency can be addressed, if required, via lower-level specifications.

## How to Read the Specification

### Directories

- `protocols` contains files specific to various variants of the 3SF protocol for Ethereum.
  - `rlmd` contains files specific to the RLMD-based variant of the 3SF protocol
    - `3sf_high_level.py` is the "entry" point of the RLMD-based specification. It includes all the event handlers and the functions specifying the external view of the state of a node (more on this below).
    - `helpers.py` contains all of the helper functions used by `3sf_high_level.py`.
    - `data_structures.py` contains data structure definitions specific to the RLMD-based version of the 3SF protocol
- `common` contains definitions that are shared by the various variants of the 3SF protocol.
  - `ffg.py` contains the main logic for computing the finalized chain.
  - `helpers.py` contains helper functions shared by the various 3SF protocols.
  - `data_structures.py` contains the definition of data structures shared by the various 3SF protocols.
  - `stubs.pyi` contains functions that have not yet been defined.
  - `formal_verification_annotations.py` includes the definition of all the annotations used to aid the formal verification of this specification.
  - `pythonic_code_generic.py` is reserved for code heavily reliant on Python syntax and semantics. More on this [below](#hard-rules).

### Event Handlers

The dummy decorator `@Event` is used to identify the Python functions that specify the behavior in response to specific external events.

For example, the following Python function specifies how the node should behave when the node receives a Propose message.

```python
@Event
def on_received_propose(propose: SignedProposeMessage, node_state: NodeState) -> NewNodeStateAndMessagesToTx:
    ...
```

In the above, `node_state` corresponds to the current state of a node.
The value returned is a `@dataclass NewNodeStateAndMessagesToTx` instance with the following three fields:

- `state`: the new state of the node in response to receiving the Propose message `propose`
- `proposeMessagesToTx`: the set, possibly empty, of Propose messages that the node must send in response  to receiving the Propose message `propose`
- `voteMessagesToTx`: the set, possibly empty, of Vote messages that the node must send in response to  to receiving the Propose message `propose`

### Initial State

The dummy decorator `@Init` is used to denote the function that returns the initial `NodeState`.

### External View

The dummy decorator `@View` is used the define which portion of the node state is externally visible.
As mentioned above, this spec does not specify how the state of a node evolves, but only how the externally visible state of a node evolves.

For example, the following Python code expresses that the externally visible state of a node corresponds to its finalized chain and available chain as returned by the functions `finalized_chain` and `available_chain` respectively.

```python
@View
def finalized_chain(node_state: NodeState) -> PVector[Block]:
    ...

@View
def available_chain(node_state: NodeState) -> PVector[Block]:
    ...
```

### `Requires` Statements

`Requires` are dummy statements are used to annotate functions with pre-conditions, that is, conditions that are assumed to always be true every time that the function is called.
It is the responsibility of the callers to ensure that this is the case.

For example, the Python code below states that every time that `get_parent(block, node_state)` is called, the caller must ensure that `has_parent(block, node_state) == True` and, hence, the function `get_parent` can assume that this condition is always satisfied any time that it is executed.

```python
def get_parent(block: Block, node_state: NodeState) -> Block:
    Requires(has_parent(block, node_state))
    return get_block_from_hash(block.parent_hash, node_state)
```

By translating the Python spec to a formal language that supports mechanized formal verification, it will be possible to have a mechanical formal proof that every time that `get_parent(block, node_state)` is called, `has_parent(block, node_state) == True`.

## General Rules Used in Writing the Python Code

### Hard Rules

1. Use only immutable data structures. This is very helpful for formal verification purposes as one does not need to be concerned with the problem of [aliasing](https://en.wikipedia.org/wiki/Aliasing_(computing)).
   1. For sets, lists and maps use the types `PSet`, `PVector` and`PMap`, respectively, from the [`pyrsistent`](https://pypi.org/project/pyrsistent/) library.
   2. For composite data structures that never need to be manipulated during any function, use `@dataclass(frozen=True)`.
   3. For the composite data structures that need to be manipulated during the execution of some of the functions, base them off the `PRecord` class from the [`pyrsistent`](https://pypi.org/project/pyrsistent/) library. This is to use `PRecord`s only when strictly necessary because, as of today, MyPy cannot typecheck `PRecord`s, but it can typecheck `@dataclass`es.

2. Reduce the usage of Pythonic code as much as possible. This is to have a spec with very simple semantics and therefore reduce the risk of possible misinterpretations. As a consequence of this principle, the following rules have been followed:
    1. For all the files, except for `data_structures.py` and `pythonic_code_generic.py`, use only the following features of the Python language
       1. Function definitions and function calls
       2. `if` statements
       3. `for` statements
       4. call to the `set` method of `PRecord`s
       5. lambdas
    2. Relegate all of the code that needs features of the Python language outside of those listed above to the file  `pythonic_code_generic.py` except for data structure definitions which are to be placed in the file `data_structures.py`.

### Soft Rules

1. Employ functions effectively to encapsulate the semantics of operations. This is to improve readability. For example, rather than using `node_state.blocks[hash]` throughout the code to retrieve a block with hash `hash`, define and use the function `get_block_from_hash(Hash, NodeState)` which better captures the semantics.

## General Rules Used in Writing this High-Level Specification

1. Add a field to `NodeState` only if it cannot be computed from the others.
2. Use fixed-size types only for message fields. For any other integer type, use `int`. Fixed-size types (except for messages) are for lower-level specifications.

## Formal Semantics

Defined in [FORMAL_SEMANTICS.md](FORMAL_SEMANTICS.md)
