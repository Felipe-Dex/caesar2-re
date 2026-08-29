// Name known c2_x VAs from findings/ps_exe.md after auto-analysis.
// @category Caesar2
// @menupath Analysis.Caesar2.Apply c2_x symbols

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.ArrayDataType;
import ghidra.program.model.data.CategoryPath;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.DWordDataType;
import ghidra.program.model.data.PointerDataType;
import ghidra.program.model.data.StructureDataType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class C2Symbols extends GhidraScript {

	private static final String WATCOM =
			"EAX=arg1, EDX=arg2, EBX=arg3, ECX=arg4; more on stack; ret EAX";

	@Override
	public void run() throws Exception {
		nameFunc(0x72500L, "start",
				"Watcom CRT entry (LE CS:EIP). Not main. Next: walk to c2_early_init 0x10010.");
		nameFunc(0x2444AL, "load_file",
				WATCOM + " path / dest / max / flags?. open/seek/read/close.");
		nameFunc(0x70174L, "sav_write",
				WATCOM + " EAX=path. 500 SavChunk then 4000 B from history.dat.");
		nameFunc(0x7024AL, "sav_read",
				WATCOM + " EAX=path. Inverse of sav_write; trailer -> history.dat.");
		nameFunc(0x10DCAL, "gfx_load_city_assets",
				"GFX cluster: cityfixt.256, fonts, mouse, panels, c2.eng via load_file.");
		nameFunc(0x34D92L, "sav_year_end",
				"Year-end autosave: lastyear.sav when flags [0x9CE85]==0 and [0x9CE87]!=0.");
		nameFunc(0x74300L, "AIL_set_sample_address_dbg",
				"Miles stdcall debug wrapper; real API 0x7EA10. Format string 0x9163A.");
		nameFunc(0x7EA10L, "AIL_set_sample_address",
				"Miles AIL 3.x stdcall (stack args). Called from dbg wrapper 0x74300.");
		nameFunc(0x10010L, "c2_early_init",
				"Early game init: malloc-ish then load_file(resource.cfg).");
		nameFunc(0x2456EL, "load_file_cfg",
				WATCOM + " EAX=path EDX=dst. resource.cfg sibling of load_file.");
		nameFunc(0x706C6L, "load_regions",
				WATCOM + " EAX=index. 3600-byte record x 44. Dest [0xC4D10].");
		nameFunc(0x722ADL, "open_", "Watcom CRT open (stack). Modes 0x200 read, 0x180+0x261 create.");
		nameFunc(0x77B37L, "read_",
				WATCOM + " EAX=fd EDX=buf EBX=len. Used by load_file and sav_read.");
		nameFunc(0x7A995L, "write_",
				WATCOM + " EAX=fd EDX=buf EBX=len. Used by sav_write.");
		nameFunc(0x724FBL, "close_", "Watcom CRT close. EAX=fd.");

		label(0x10FC7L, "load_c2_eng_site");
		eol(0x10FC7L, "ebx=0x9C40 (40000) edx=0xB831C eax=c2.eng  call load_file");
		bookmark(0x10FC7L, "c2.eng load site — dest 0xB831C, max 40000");

		label(0x120A6L, "push_22050_raw_rate");
		eol(0x120A6L, "push 22050 — Miles RAW sample rate (also 0x120FB)");
		bookmark(0x120A6L, "push 22050 Hz (RAW / Miles digital)");

		label(0x120FBL, "push_22050_raw_rate_b");
		eol(0x120FBL, "push 22050 — second Miles RAW rate site");

		label(0x11FF0L, "miles_set_rate_22050");
		bookmark(0x11FF0L, "function around push 22050 — name if prologue is here");

		label(0x9ABC0L, "sav_chunks");
		plate(0x9ABC0L,
				"SavChunk sav_chunks[500] — {void *ptr; u32 size}. First size==0 ends loop.");
		bookmark(0x9ABC0L, "sav table — 500 slots; name each from notes/ps_sav_chunks.tsv");

		label(0xE2FBCL, "city_planes_20x80x80");
		plate(0xE2FBCL,
				"BSS 20 x 6400 = 128000. City map SoA (SAV chunk 13, file off 50395).");
		bookmark(0xE2FBCL, "20 planes BSS — name layers after a 1-house SAV pair");

		label(0xB831CL, "c2_eng_buf");
		plate(0xB831CL, "40000-byte dest of c2.eng (on disk 31876). Indexed UI strings.");
		bookmark(0xB831CL, "c2.eng dest buffer");

		label(0x93694L, "raw_name_bank");
		plate(0x93694L,
				"Packed 8.3 RAW names, 8 bytes each: a01-a30, b01-b30, c01-c44 (104).");
		bookmark(0x93694L, "RAW filename bank — index via shl eax,3 at ~0x135A9");

		label(0xC4D10L, "regions_or_history_ptr");
		plate(0xC4D10L,
				"Pointer: regions.dat dest, later aliased to 4000 B history.dat. Lifetime TBD.");
		bookmark(0xC4D10L, "[0xC4D10] regions vs history alias — confirm lifetime");

		long[] imm1090 = { 0x84294L, 0x85112L, 0x88207L };
		String[] immNames = { "imm_1090_c2model_a", "imm_1090_c2model_b", "imm_1090_c2model_c" };
		for (int i = 0; i < imm1090.length; i++) {
			label(imm1090[i], immNames[i]);
			eol(imm1090[i], "mov r/m32, 1090 — possible C2MODEL int count; filename absent");
			bookmark(imm1090[i], "1090 immediate — C2MODEL loader breadcrumb");
		}

		StructureDataType sav = new StructureDataType(new CategoryPath("/c2_x"), "SavChunk", 0);
		sav.add(PointerDataType.dataType, 4, "ptr", "runtime dest");
		sav.add(DWordDataType.dataType, 4, "size", "bytes");
		DataType savDt = currentProgram.getDataTypeManager().addDataType(sav, null);
		ArrayDataType arr = new ArrayDataType(savDt, 500, 8);
		Address start = toAddr(0x9ABC0L);
		Address end = toAddr(0x9ABC0L + 500 * 8 - 1);
		try {
			clearListing(start, end);
			createData(start, arr);
			println("c2 symbols: SavChunk[500] at 0x9ABC0");
		}
		catch (Exception exc) {
			println("c2 symbols: SavChunk apply skipped (" + exc.getMessage() + ")");
		}
		try {
			createData(toAddr(0xE2FBCL), DWordDataType.dataType);
		}
		catch (Exception ignored) {
			// already typed
		}
		println("c2 symbols: applied load_file/sav_*/gfx/AIL/CRT + data labels");
	}

	private void nameFunc(long va, String name, String note) throws Exception {
		Address addr = toAddr(va);
		Function fn = getFunctionAt(addr);
		if (fn == null) {
			fn = createFunction(addr, name);
		}
		if (fn != null) {
			try {
				fn.setName(name, SourceType.USER_DEFINED);
			}
			catch (Exception ignored) {
				// keep existing
			}
			fn.setComment(note);
		}
		label(va, name);
		plate(va, note);
		bookmark(va, name + " — " + note);
	}

	private void label(long va, String name) throws Exception {
		createLabel(toAddr(va), name, true, SourceType.USER_DEFINED);
	}

	private void plate(long va, String text) throws Exception {
		setPlateComment(toAddr(va), text);
	}

	private void eol(long va, String text) throws Exception {
		setEOLComment(toAddr(va), text);
	}

	private void bookmark(long va, String text) throws Exception {
		createBookmark(toAddr(va), "C2", text);
	}
}
