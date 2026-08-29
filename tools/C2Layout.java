// Split the mapped c2_x image into LE objects and mark CRT entry.
// @category Caesar2
// @menupath Analysis.Caesar2.Apply c2_x layout

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;

public class C2Layout extends GhidraScript {

	private static final long TEXT_VA = 0x10000L;
	private static final long TEXT_END = 0x8B9C0L;
	private static final long DATA_VA = 0x90000L;
	private static final long ENTRY_VA = 0x72500L;

	@Override
	public void run() throws Exception {
		Memory memory = currentProgram.getMemory();
		splitAt(memory, TEXT_END);
		splitAt(memory, DATA_VA);
		setBlock(memory, TEXT_VA, ".text", true, false, true);
		MemoryBlock hole = memory.getBlock(toAddr(TEXT_END));
		MemoryBlock data = setBlock(memory, DATA_VA, ".data", true, true, false);
		if (hole != null && data != null && hole.getStart().getOffset() == TEXT_END
				&& hole.getEnd().getOffset() < DATA_VA) {
			try {
				hole.setName(".hole");
				hole.setPermissions(false, false, false);
				memory.removeBlock(hole, monitor);
				println("c2 layout: removed unmapped hole 0x8B9C0-0x90000");
			}
			catch (Exception exc) {
				println("c2 layout: hole kept (" + exc.getMessage() + ")");
			}
		}

		Address entry = toAddr(ENTRY_VA);
		currentProgram.getSymbolTable().addExternalEntryPoint(entry);
		Function fn = getFunctionAt(entry);
		if (fn == null) {
			createFunction(entry, "start");
		}
		else {
			fn.setName("start", SourceType.USER_DEFINED);
		}
		createLabel(entry, "start", true, SourceType.USER_DEFINED);
		setPlateComment(entry, "Watcom CRT startup (LE CS:EIP). Not main. Walk toward 0x10010.");
		createBookmark(entry, "C2", "CRT entry start — find main from here");
		println("c2 layout: .text RX, .data RW, entry 0x72500 = start");
	}

	private void splitAt(Memory memory, long va) throws Exception {
		Address addr = toAddr(va);
		MemoryBlock block = memory.getBlock(addr);
		if (block == null || block.getStart().equals(addr)) {
			return;
		}
		memory.split(block, addr);
	}

	private MemoryBlock setBlock(Memory memory, long va, String name, boolean r, boolean w,
			boolean x) {
		MemoryBlock block = memory.getBlock(toAddr(va));
		if (block == null) {
			println("c2 layout: missing block at 0x" + Long.toHexString(va));
			return null;
		}
		try {
			block.setName(name);
		}
		catch (Exception ignored) {
			// keep existing name
		}
		block.setPermissions(r, w, x);
		return block;
	}
}
