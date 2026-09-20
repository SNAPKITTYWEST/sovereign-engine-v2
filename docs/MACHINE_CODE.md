# Machine runtime guide

The Python VM, CPython bytecode utilities, x86 code generator, and native assembly are separate execution layers.

| Source | Responsibility |
|---|---|
| [vm_executor.py](../src/runtime/machine/vm_executor.py) | Stack VM, opcodes, assembler, debugger, in-memory WORM log |
| [binary_ir.py](../src/runtime/machine/binary_ir.py) | Binary intermediate representation |
| [bytecode_assembler.py](../src/runtime/machine/bytecode_assembler.py) | CPython bytecode assembly; version-sensitive |
| [marshal_codec.py](../src/runtime/machine/marshal_codec.py) | Python marshal/code-object encoding |
| [machine_code_gen.py](../src/runtime/machine/machine_code_gen.py) | x86-64 generation utilities |
| [ctypes_bridge.py](../src/runtime/machine/ctypes_bridge.py) | Native interop |
| [native/asm/](../native/asm/) | NASM runtime and kernel sources |
| [native/dispatcher/](../native/dispatcher/) | C IPC dispatcher and Makefile |

## Local example: stack arithmetic

Run this from a file in the repository root:

```python
from src.runtime.machine.vm_executor import SovereignVM, VMInstruction, VMOpcode

program = [
    VMInstruction(VMOpcode.PUSH, 2),
    VMInstruction(VMOpcode.PUSH, 3),
    VMInstruction(VMOpcode.ADD),
    VMInstruction(VMOpcode.HALT),
]
vm = SovereignVM(program)
result = vm.run(max_steps=10)
assert result == 5
print(result)
```

`run(max_steps=...)` returns the top of the stack and raises `VMError` when the step budget is exhausted. `get_stack()`, `get_registers()`, and `stats()` expose inspection data.

This example executes Python VM instructions. It does not compile or execute NASM, CUDA, or generated x86 machine code.

## Validation

[tests/stress_test_no_drift.py](../tests/stress_test_no_drift.py) exercises deterministic VM and routing operations. Read its assertions and backend selection before interpreting its output. A repeated arithmetic result is not evidence of deterministic external model inference.

Native builds require their own assembler/compiler, OS/ABI compatibility, and tests. Inspect [build.sh](../native/asm/build.sh) and the [dispatcher Makefile](../native/dispatcher/Makefile) before running them. CPython bytecode formats depend on the interpreter version; success under one version does not establish portability.
