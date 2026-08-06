"""
runtime/machine — Python machine code layer for the Sovereign engine.

Provides low-level Python ↔ binary bridges:

  bytecode_assembler  — CPython 3.12 opcode assembler
  marshal_codec       — .pyc marshal format read/write
  ctypes_bridge       — C interop: structs, arenas, function bindings
  binary_ir           — SOVEREIGN_IR binary intermediate representation
  vm_executor         — Sovereign stack-based virtual machine
  machine_code_gen    — x86-64 machine code generator

HyperKittyConstraintDSL v1.0 — entropy <= 0.20 constraint enforced at runtime.
"""

from .bytecode_assembler import (
    Opcode,
    Instruction,
    Label,
    BytecodeAssembler,
    InstructionBuffer,
    AssemblerError,
    AssemblerContext,
    FunctionBuilder,
    ConstantFolder,
    PeepholeOptimizer,
    BytecodeVerifier,
    make_assembler,
    assemble_expr,
    describe_code_object,
)

from .marshal_codec import (
    MAGIC_NUMBER,
    PYC_HEADER_SIZE,
    TYPE_NULL,
    TYPE_NONE,
    TYPE_FALSE,
    TYPE_TRUE,
    TYPE_INT,
    TYPE_INT64,
    TYPE_FLOAT,
    TYPE_COMPLEX,
    TYPE_STRING,
    TYPE_UNICODE,
    TYPE_TUPLE,
    TYPE_LIST,
    TYPE_DICT,
    TYPE_CODE,
    TYPE_REF,
    TYPE_SHORT_ASCII,
    TYPE_SHORT_ASCII_INTERNED,
    MarshalReader,
    MarshalWriter,
    MarshalError,
    PycFile,
    CodeObjectSerializer,
    MarshalDiff,
    marshal_dumps,
    marshal_loads,
    marshal_roundtrip,
)

from .ctypes_bridge import (
    Platform,
    Endian,
    CTypeInfo,
    C_TYPES,
    StructField,
    CStructBuilder,
    MemoryArena,
    FunctionBinding,
    CTypesBridgeError,
    TypedMemoryView,
    PackedArray,
    CURRENT_PLATFORM,
    CURRENT_ENDIAN,
    PTR_SIZE,
    IPC_MAGIC,
    IPC_HEADER_SIZE,
    encode_ipc_header,
    decode_ipc_header,
    encode_dispatch_packet,
    decode_dispatch_packet,
    encode_rex as ctypes_encode_rex,
)

from .binary_ir import (
    IR_MAGIC,
    IR_VERSION,
    IR_HEADER_SIZE,
    IR_NODE_SIZE,
    IR_EDGE_SIZE,
    IRNodeType,
    IREdgeType,
    IRNode,
    IREdge,
    IRGraph,
    IRError,
    IRBuilder,
    BinaryIREncoder,
    BinaryIRDecoder,
    ASTParseToBinaryIR,
    IRDiff,
    IRSerializer,
    SymbolTable,
)

from .vm_executor import (
    VMOpcode,
    VMInstruction,
    VMStack,
    VMRegisters,
    VMMemory,
    SovereignVM,
    VMAssembler,
    VMError,
    VMEntropyViolation,
    WORMLog,
    WORMEntry,
    DispatchTable,
    CallFrame,
    nand_op,
    nand_not,
    nand_and,
    nand_or,
    nand_xor,
    make_program,
    push as vm_push,
    halt as vm_halt,
    commit as vm_commit,
)

from .machine_code_gen import (
    Register,
    Reg32,
    Condition,
    CodeBuffer,
    CodeGenError,
    X86Encoder,
    IRToMachineCode,
    encode_rex,
    encode_modrm,
    encode_sib,
    simple_disasm,
)

__all__ = [
    # bytecode_assembler
    "Opcode", "Instruction", "Label", "BytecodeAssembler", "InstructionBuffer",
    "AssemblerError", "AssemblerContext", "FunctionBuilder",
    "ConstantFolder", "PeepholeOptimizer", "BytecodeVerifier",
    "make_assembler", "assemble_expr", "describe_code_object",

    # marshal_codec
    "MAGIC_NUMBER", "PYC_HEADER_SIZE",
    "TYPE_NULL", "TYPE_NONE", "TYPE_FALSE", "TYPE_TRUE",
    "TYPE_INT", "TYPE_INT64", "TYPE_FLOAT", "TYPE_COMPLEX",
    "TYPE_STRING", "TYPE_UNICODE", "TYPE_TUPLE", "TYPE_LIST",
    "TYPE_DICT", "TYPE_CODE", "TYPE_REF",
    "TYPE_SHORT_ASCII", "TYPE_SHORT_ASCII_INTERNED",
    "MarshalReader", "MarshalWriter", "MarshalError",
    "PycFile", "CodeObjectSerializer", "MarshalDiff",
    "marshal_dumps", "marshal_loads", "marshal_roundtrip",

    # ctypes_bridge
    "Platform", "Endian", "CTypeInfo", "C_TYPES",
    "StructField", "CStructBuilder", "MemoryArena",
    "FunctionBinding", "CTypesBridgeError",
    "TypedMemoryView", "PackedArray",
    "CURRENT_PLATFORM", "CURRENT_ENDIAN", "PTR_SIZE",
    "IPC_MAGIC", "IPC_HEADER_SIZE",
    "encode_ipc_header", "decode_ipc_header",
    "encode_dispatch_packet", "decode_dispatch_packet",

    # binary_ir
    "IR_MAGIC", "IR_VERSION", "IR_HEADER_SIZE",
    "IR_NODE_SIZE", "IR_EDGE_SIZE",
    "IRNodeType", "IREdgeType",
    "IRNode", "IREdge", "IRGraph", "IRError",
    "IRBuilder", "BinaryIREncoder", "BinaryIRDecoder",
    "ASTParseToBinaryIR", "IRDiff", "IRSerializer", "SymbolTable",

    # vm_executor
    "VMOpcode", "VMInstruction", "VMStack", "VMRegisters", "VMMemory",
    "SovereignVM", "VMAssembler", "VMError", "VMEntropyViolation",
    "WORMLog", "WORMEntry", "DispatchTable", "CallFrame",
    "nand_op", "nand_not", "nand_and", "nand_or", "nand_xor",
    "make_program", "vm_push", "vm_halt", "vm_commit",

    # machine_code_gen
    "Register", "Reg32", "Condition",
    "CodeBuffer", "CodeGenError",
    "X86Encoder", "IRToMachineCode",
    "encode_rex", "encode_modrm", "encode_sib",
    "simple_disasm",
]

__version__ = "1.0.0"
__author__  = "Sovereign Engine — Agent A (Cognition)"
__dsl__     = "HyperKittyConstraintDSL v1.0"
