# Immigrant / occupy — pin (1.1A)

**Veredito:** Caesar II **não** tem walker imigrante nem occupy de tenda. População entra no **stamp** (`id` 0x82–0xA1, origem `+5&0xF==0`) via LUT `0x96967` = C2MODEL `[215:247]`. `FUN_00041dd4` `0x41DD4` é **fogo + rioter tipo 7**, vivo em City Only **e** Career. O “imigrante ocupa tenda” em `city_only.md` §3 é mito de C3 / Julius.

`city_sim_phase` `0x3F925`: único `CALL 0x41DD4` (slots `0x9E–0xA1`, EAX=20 filas). Sem gate `[0x9CE81]`. Score `+11&0xF` > 15 → `walker_spawn_retry` EAX=7 `0x4219B`, `next_state=0x0B`, `FUN_00058c87` EAX=`0x57`. C2.ENG `[66]+6` ` - Rioter`; overlay `[52]+4` `Unrest` (crime / riot). Sem string `immigrant` / `occupy` / `vacant`. Censo: `0x445AF` zera `[0x1028FC]`, soma LUT; `0x43F88` copia → `[0x1028E8]`; `0x441C3` → `[0x102AB0]`. Host `recount_population` já faz isto. **Não implementar occupy.** Rioter tipo 7 já corre em City Only (`unrest_spawn_rows`); menu **Disasters → Riot** força o overflow.
