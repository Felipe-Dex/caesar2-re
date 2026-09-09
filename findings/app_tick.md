# Host — `walkers_tick` no Python

Space/T no `python -m app` corre um pulso de `walkers_tick` `0x459D0`, não o `++walk_frame` falso. Detalhe do EXE: `ghidra_walkers_tick.md`.

## Como tentar (10 linhas)

1. `python -m app` (ou `--sav` no `.SAV` que quiseres; boot pega FELIPE01 / primeiro da pasta).
2. Tecla **3** — mapa iso + pessoas (SavChunk 8 / LTLMEN).
3. **Space** ou **T** — um tick. Segura Space: o repeat do Windows avança vários.
4. HUD: `moved=` (mudou x/y) · `frames=` (só `walk_frame`) · `live=` · `freed=`.
5. Um passo de tile costuma levar **16–32** ticks (timer `0x9673E`/`0x96735` + frame 0…15).
6. `city_sim_phase` agora corre **um** slot por Space (depois walkers). Casas só mudam nos slots `1…0x50`. Como testar: `findings/app_sim_phase.md`.
7. Sem `actors26_tick`: ninguém spawna do mapa de província.
8. Cidade e província partilham `view_frame`; forum não faz este tick — `findings/view_modes.md`.

## O que o host faz

Tipo 1–7 → estado 0–12. Roam/path → `walker_step` `0x488DC` (unlink/relink +7/+8, facing 0–7). Coverage OR em +10 (0x0C / 0xC0 / 0x30). Sprite `walker_set_sprite` `0x479B8` (câmara 0). Life cap a cada 64 ticks.

## Stub / ainda falso

- Estado **9** (`0x46619`): vigile fire seek. `0x4A397` (sector 8×8 id&lt;8 + bit7) → `0x4A57F` dest; `0x4A716` extingue no tile; `0x4A76D` mantém o alvo. Estado 8 entra em 9 quando o sector tem fogo.
- Path bloqueado (`can_step==0`): sidestep, sem `0x2B54A` / `0x2BA63`.
- `FUN_0004a7ff` scores de casa — skip.
- Rally `[0x10262C]`/`[0x102628]`: City Only type 3 lê o pico de `+15` (`0x40695`) no spawn `0x536E2`. Estados 5/11/12 seguem esse dest.
- `walker_set_sprite_t7` `0x47A95` = mesmo nibble que `0x479B8`.
- Tipos sem pad à volta: estado 2 → free (como o EXE).
