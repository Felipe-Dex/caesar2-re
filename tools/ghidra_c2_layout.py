# Split the mapped c2_x image into LE objects and mark CRT entry.
# @category Caesar2
# @runtime PyGhidra
# @menupath Analysis.Caesar2.Apply c2_x layout
#
# Pre-analysis script for the raw image from tools/ps_le.py --write-image.
# Base 0x10000, obj1 RX 0x7B9C0, hole, obj2 RW 0x89260, EIP 0x72500.

from ghidra.program.model.symbol import SourceType

TEXT_VA = 0x10000
TEXT_END = 0x8B9C0
DATA_VA = 0x90000
ENTRY_VA = 0x72500


def _split_at(memory, va):
    addr = toAddr(va)
    block = memory.getBlock(addr)
    if block is None:
        return
    if block.getStart().equals(addr):
        return
    memory.split(block, addr)


def _set_block(memory, va, name, r, w, x):
    block = memory.getBlock(toAddr(va))
    if block is None:
        println("c2 layout: missing block at %s" % hex(va))
        return None
    try:
        block.setName(name)
    except Exception:
        pass
    block.setPermissions(r, w, x)
    return block


memory = currentProgram.getMemory()
_split_at(memory, TEXT_END)
_split_at(memory, DATA_VA)

_set_block(memory, TEXT_VA, ".text", True, False, True)
hole = memory.getBlock(toAddr(TEXT_END))
data = _set_block(memory, DATA_VA, ".data", True, True, False)

# Unmap the LE gap 0x8B9C0–0x90000 (zeros in the linear image, not resident).
if hole is not None and data is not None:
    if hole.getStart().getOffset() == TEXT_END and hole.getEnd().getOffset() < DATA_VA:
        try:
            hole.setName(".hole")
            hole.setPermissions(False, False, False)
            memory.removeBlock(hole, monitor)
            println("c2 layout: removed unmapped hole 0x8B9C0-0x90000")
        except Exception as exc:
            println("c2 layout: hole kept (%s)" % exc)

entry = toAddr(ENTRY_VA)
currentProgram.getSymbolTable().addExternalEntryPoint(entry)
fn = getFunctionAt(entry)
if fn is None:
    createFunction(entry, "start")
else:
    fn.setName("start", SourceType.USER_DEFINED)
createLabel(entry, "start", True, SourceType.USER_DEFINED)
setPlateComment(entry, "Watcom CRT startup (LE CS:EIP). Not main. Walk toward 0x10010.")
createBookmark(entry, "C2", "CRT entry start — find main from here")
println("c2 layout: .text RX, .data RW, entry 0x72500 = start")
