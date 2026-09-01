# Host — `walkers_tick` no Python

Space/T no `python -m app` corre um pulso de `walkers_tick` `0x459D0`, não o `++walk_frame` falso. Detalhe do EXE: `ghidra_walkers_tick.md`.

## Como tentar (10 linhas)

1. `python -m app` (ou `--sav` no `.SAV` que quiseres; boot pega FELIPE01 / primeiro da pasta).
2. Tecla **3** — mapa iso + pessoas (SavChunk 8 / LTLMEN).
3. **Space** ou **T** — um tick. Segura Space: o repeat do Windows avança vários.
4. HUD: `moved=` (mudou x/y) · `frames=` (só `walk_frame`) · `live=` · `freed=`.
5. Um passo de tile costuma levar **16–32** ticks (timer `0x9673E`/`0x96735` + frame 0…15).
6. Sem `city_sim_phase`: casas/fogo/economia/batalha não evoluem.
7. Sem `actors26_tick`: ninguém spawna do mapa de província.
8. Cidade e província partilham `view_frame`; forum não faz este tick — `findings/view_modes.md`.

## O que o host faz

Tipo 1–7 → estado 0–12. Roam/path → `walker_step` `0x488DC` (unlink/relink +7/+8, facing 0–7). Coverage OR em +10 (0x0C / 0xC0 / 0x30). Sprite `walker_set_sprite` `0x479B8` (câmara 0). Life cap a cada 64 ticks.

## Stub / ainda falso

- Estado **9** (`0x46619`): anda se já tiver dest; **não** chama `0x4A716` / `0x4A76D` / `0x4A397` / `0x4A57F`. Estado 8 **não** entra em 9.
- Path bloqueado (`can_step==0`): sidestep, sem `0x2B54A` / `0x2BA63`.
- `FUN_0004a7ff` scores de casa — skip.
- Rally `[0x10262C]`/`[0x102628]` (chunks 20/21) **não** lido; estados 5/11/12 mantêm dest do SAV.
- `walker_set_sprite_t7` `0x47A95` = mesmo nibble que `0x479B8`.
- Tipos sem pad à volta: estado 2 → free (como o EXE).
