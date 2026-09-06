# Forum / Oracle / Empire strings (C2.ENG + HELP.ENG + picker)

Same method as `walker_quotes.md`. No full `C2.ENG` / `HELP.ENG` dump here.

**Lookup:** `FUN_00026f16` `0x26F16` / wrap `0x27071` — `EAX` = official slot **+ 1**, `EDX` = extra NULs. Buffer `c2_eng_buf` `0xB831C`.

HELP.ENG is a sibling (`Helpfile`, not the 146-slot table). Flavor records are **58 B** (`0x3A`); first `u32` = file offset of the C-string. Blit `0x57B48` seeks `topic * 58 + 8`.

---

## 1. Oracle advice — `[31]` + skip

Kind **1** draws the four columns (`EAX=0x20`, `EDX=1…4` = Empire / Peace / Prosperity / Culture). Prompt with no click: **`[31]+7`**.

Click a column: `0x3D843` hit-test `esi=0…3` → `0x343C3` → picker **`0x57450`** (`EAX` = column). Writes **`[0x102558]`** = advice id **1…16**, then kind-A draw **`0x5F033`**:

```
EDX = [0x102558] + 7
EAX = 0x20          ; official [31]
call 0x27071
```

City-only (`[0x9CE81] != 0`): if id **< 9** (Empire / Peace) force id **17** → skip **24** (`You cannot get promoted when playing in city-only mode…`). Prosperity / Culture still use 9…16.

| Id | Skip | Rating | When (`0x57450`) |
|---:|---:|---|---|
| 1 | 8 | Empire | `[0x102564] != 0` — already at cap for city size |
| 2 | 9 | Empire | else `[0x102A4C] < 80` — low Imperial Favor (same dword ROME uses for the quote) |
| 3 | 10 | Empire | else `[0x102714] == 0` — no provincial road / town links |
| 4 | 11 | Empire | else — develop province (camps, roads, industry) |
| 5 | 12 | Peace | `[0x102540] != 0` — at cap |
| 6 | 13 | Peace | else — invading armies |
| — | 14 | Peace | **never written** — file stub `Peace rating - tip3` |
| — | 15 | Peace | **never written** — file stub `Peace rating - tip4` |
| 9 | 16 | Prosperity | `[0x10257C] != 0` — at cap |
| 10 | 17 | Prosperity | else `[0x1025D8] < 0` — not turning a profit |
| 11 | 18 | Prosperity | else `[0x1025AC] < 10` — housing income low |
| 12 | 19 | Prosperity | else — grow population |
| 13 | 20 | Culture | `[0x102550] != 0` — at cap |
| 14 | 21 | Culture | else `[0x102580]` is min of `{580, 56C, 54C}` — entertainment |
| 15 | 22 | Culture | else `[0x10256C]` is min — temples |
| 16 | 23 | Culture | else — hospitals / schools / gardens / plazas |
| 17 | 24 | (city-only) | forced when `[0x9CE81]` and id &lt; 9 |

ACHEA23 Empire click = **+11** (id 4): not at cap, favor ≥ 80, `[0x102714] != 0`.

### Pack (file order from `[31]`)

| + | Text (file spelling) |
|---:|---|
| 0 | `Your Ratings` |
| 1–4 | `Empire` / `Peace` / `Prosperity` / `Culture` |
| 5 | `Average rating: ` |
| 6 | `(Need` |
| 7 | `Select any of the ratings above to receive advice on improving them.` |
| 8 | `Youe EMPIRE rating is as high as it can be for your city's current size.` (typo *Youe*) |
| 9 | `Your EMPIRE rating is limited by your low Imperial Favor.  When the Emperor talks, you should listen!` |
| 10 | `To improve your EMPIRE rating, build a larger provincial road network.  Link your city to border towns.  Build trading posts and ports, and link them as well.` |
| 11 | `Your EMPIRE rating depends on developing your province.  Pacify barbarian camps, connect towns to your city with roads, and build sources of industry.` |
| 12 | `You have the maximum possible PEACE rating for your city's current size.` |
| 13 | `To increase your PEACE rating, deal swiftly with invading armies, and definitely keep them out of your city. ` |
| 14 | `Peace rating - tip3` |
| 15 | `Peace rating - tip4` |
| 16 | `You have the maximum possible PROSPERITY rating for your city's current size.` |
| 17 | `Your PROSPERITY rating is hampered by a lack of profits.  You must turn a profit, and do so regularly.` |
| 18 | `Your PROSPERITY rating is limited because housing income is low.  Improve your city's housing to increase your income tax.` |
| 19 | `To improve your PROSPERITY rating, increase your city's population.` |
| 20 | `Your CULTURE rating is as high as it can be for your city's current size.` |
| 21 | `Your CULTURE rating suffers because your people want more shows and spectacles.  They want to be entertained. ` |
| 22 | `Your CULTURE rating suffers from a citywide spiritual crisis. Priests are complaining that there are too few places of worship.` |
| 23 | `Your CULTURE rating suffers because of inadequate city services.  Try building more utilities like hospitals and schooling, or improve the overall cleanliness of the city with gardens and plazas.` |
| 24 | `You cannot get promoted when playing in city-only mode. Get ADVICE on your city's Prosperity or Culture ratings by clicking on their boxes. ` |

---

## 2. Empire map — 44 provinces

Hit-test `0x33C3D`: `ecx = 0…0x2B` (44). On hit: `[0x102DE0] = ecx + 1` (**skip** into `[5]`, **1…44**). Chunk **223** pid is **skip − 1** (Achea **15** → `[5]+16`).

### Names — `[5]` (`EAX=6`)

`EDX = [0x102DE0]`. `[5]+0` is a spare `Latium`; the map never uses skip 0. After **+44** the same run continues into Trade Route / Local Waters / `[6] Romans` (Industry / sea-lane LUT, not the empire-map hit list).

| + | Name | + | Name |
|---:|---|---:|---|
| 0 | Latium *(unused skip)* | 23 | Africa Proconsularis |
| 1 | Latium | 24 | Syria |
| 2 | Campania | 25 | Caria |
| 3 | Cisalpine Gaul | 26 | Lycia and Pamphylia |
| 4 | Sicilia | 27 | Bithynia and Pontus |
| 5 | Corsica and Sardinia | 28 | Cappadocia |
| 6 | Gallia Narbonensis | 29 | Thracia |
| 7 | Carthage | 30 | Dacia |
| 8 | Hispania Tarraconensis | 31 | Pannonia |
| 9 | Baetica | 32 | Germania Superior |
| 10 | Lusitania | 33 | Germania Inferior |
| 11 | Aquitania | 34 | Cyprus |
| 12 | Mauretania | 35 | Armenia |
| 13 | Illyricum | 36 | Mesopotamia |
| 14 | Gallia Lugdunensis | 37 | Hibernia |
| 15 | Macedonia | 38 | Caledonia |
| 16 | Achaea | 39 | Germania Exterior |
| 17 | Creta | 40 | Noricum Exterior |
| 18 | Belgica | 41 | Pannonia Exterior |
| 19 | Aegyptus | 42 | Dacia Exterior |
| 20 | Cyrenaica | 43 | Asia Exterior |
| 21 | Judea | 44 | Armenia Exterior |
| 22 | Britannia | 45–47 | Trade Route *(not map hits)* |
| | | 48 | Local Waters |

### Status line — `[47]` (`EAX=0x30`) — `0x5C621`

`edx = [0xD7B30 + skip*4]` (conquer year / sentinel). Init writes Latium skip **1** = **`0x1869E`**.

| `edx` | EDX skip | String |
|---|---:|---|
| `0` | 9 | `As yet unconquered.` — unless `skip-1 == [0x1025CC]` (your current pid) → `EAX=0x4D` `EDX=6` |
| `0x1869E` (99998) | 5 | `Home of our beloved Emperor.` |
| `0x1869F` (99999) | 6 | `Conquered by Pompous Maximus.` |
| other (year) | 7 then 8 | `You conquered this region (in ` + number + `years).` |

Also `[47]+0…4` = career-pick chrome (`Select a Highlighted Province` … `Unknown Province`), not the tooltip.

### Flavor — HELP.ENG, indexed by the same skip

`[0x102468] = [0x102DE0] + 0x47C` (1148) then `0x57B48`. The 44 flavor C-strings sit in topics **1150…1193** (file order). That is **`skip + 1149`** if you count the dummy record after `Helpfile`; the sequential pack below is **one string per `[5]+1…+44`**.

Latium (**+1**) is the short line immediately before the 43-long pack: `All roads lead here...`

| `[5]+` | Flavor (HELP.ENG) |
|---:|---|
| 1 | `All roads lead here...` |
| 2 | `Thanks to our recent campaigns, the people of this province have been "Romanized."  They should be placid and welcoming.` |
| 3 | `This province is fairly quiet, but beware of occasional incursions of the Gauls to the north.` |
| 4 | `There is a slight barbarian presence in this province, but it is a prime trading area with access to the spice routes.` |
| 5 | `Your mission is to manage the small island of Sardinia, to the west of Rome.  One of the outlying villages has not been tamed, so rule with caution.` |
| 6 | `This province contains a village of those rebellious Gauls; however, they should be fairly peaceable for their lot.` |
| 7 | `This region's once-great cities have been razed.  Rebuild this province to even greater splendor, but beware a fierce and unruly populace.` |
| 8 | `This rich agricultural area is suitable for grapes and wheat, and its ports should be a prime source of fish for the Empire.` |
| 9 | `This province allows enemies to reach the Empire from the south.  Taming it would limit their incursions, but the people here seem displeased with our presence.` |
| 10 | `Surveys report the soil here to be rich with ores and gems, and the seas a prime source of fish.` |
| 11 | `The Gauls may have an important presence here, but they are more -- civilized -- than most of their kind.  Resources are plentiful here.` |
| 12 | `As a southern province, this area would give us access to the ivory and spice trading routes.` |
| 13 | `Mineral resources are not plentiful here, but the people recognize our right to rule more than most of these barbarous lands.` |
| 14 | `The further north we expand, the fiercer the Gauls become.  However, this region features some of the richest farmland the Empire has ever seen.` |
| 15 | `This province is suited for cattle and wheat.  Beware the Greeks to the south.` |
| 16 | `The Greeks' constant squabbling have made it easy for us to conquer them.  However, that same contentious behavior will make them more difficult for you to rule.` |
| 17 | `This island is small, yet rich in farmland and minerals.  However, the populace may be troublesome.` |
| 18 | `There is a significant barbarian presence in these lands, but they seem more passive than most.  The true threat must lie further north.` |
| 19 | `With the capacity for wheat farming in this province, this may be the Empire's new breadbasket.  However, its inhabitants are less than welcoming.` |
| 20 | `This region is rich in gems and other minerals, but among the mountains lie many dangerous nomadic tribes.` |
| 21 | `Discontent is high in this area, which will make exploiting its resources difficult.` |
| 22 | `This remote and rather rustic island offers some worthwhile exports, but will have to remain well-defended to keep its rebellious populace at bay.` |
| 23 | `Minerals are less prevalent here, and unrest will likely be a problem.  Exercise caution when governing here.` |
| 24 | `This province is poised to become the most prosperous one in this region, with plenty of farming and mineral resources.` |
| 25 | `This region looks promising, but the further east we expand, the more powerful our enemies seem to become.` |
| 26 | `This province contains some villages that may cause trouble, but overall it seems fairly quiet.` |
| 27 | `This province suffers from a lack of good farmland, and is threatened by harassment from the north.` |
| 28 | `The people here are prone to rebellion, and have settled in many of the outlying towns.  You must pacify the province, if you expect to keep peace in your city.` |
| 29 | `This culture seems ripe for assimilation into our Empire, but the threat of attack from the north looms over it.` |
| 30 | `The soil is quite fertile here, but the barbarian population is significant.  Expect trouble.` |
| 31 | `The people here are strong, but seem willing to join the Empire.  Beware invasions from the north.` |
| 32 | `This northern province contains a large barbarian presence, but its resources seem worth the danger.` |
| 33 | `Farmland seems plentiful here, but the barbarians are also plentiful and unwilling to join the Empire.` |
| 34 | `Resources are scarce on this small island, and the people look to be difficult to manage.  Maintain vigilance.` |
| 35 | `Surveys show little in the way of resources, and resistance to the Empire is strong here.` |
| 36 | `This region is a dangerous mix of excellent mineral resources and rebellious villages.  Exploit the trade routes, and defend your capital city.` |
| 37 | `This tiny empire may be good for little else but fish and frustration.  Emperor, its inhabitants will bring you nothing but trouble.` |
| 38 | `Are you sure this a good idea?  Shouldn't we just wall off the northern border of Britannia and be done with it?` |
| 39 | `We've beaten back those upstart barbarians, and these lands are bereft of minerals.  Perhaps it's best to leave sleeping dogs lie?` |
| 40 | `Many barbarians have resettled in this area, thanks to our previous campaigns.  Expanding into these lands would only give them a chance at revenge -- in my humble opinion.` |
| 41 | `Aside from imported silks, is there anything to be gained from this conquest but bloodshed?` |
| 42 | `Our scouts in Dacia indicate that this area would be extremely difficult to tame, though its silk trade and fishing waters are tempting.` |
| 43 | `Farming is difficult here, and our enemies are plentiful.  Are this land's meager benefits worth provoking them further?` |
| 44 | `This land is barren, and the Huns who travel across it are nearly a match for our own troops!  I beg you to reconsider!` |

No second conquered/unconquered flavor pack — status is `[47]` only; flavor does not change with the conquer flag. Same Germania Superior line as `C31.wav` (`REVERSE.md`). Next HELP string is `AVE  IMPERATOR!` (history book), not a 45th province.

---

## 3. Other Forum packs (already pinned)

| Pack | Slot | Count | Use |
|---|---|---:|---|
| 12 buttons | `[28]+0…11` | 12 | CLEAR FORUM … EMPIRE MAP |
| Treasurer labels | `[28]+12…28` | 17 | Treasury / ACCOUNTS / tribute lines |
| ROME request | `[37]+20` / `+21` | 2 | `The Emperor currently requests nothing.` / prefix `The Emperor currently requests ` |
| ROME favor quotes | `[37]+3…14` | 12 | `"He's after your head!"` … `"He regards you as family!"` |
| Empire chrome | `[33]+0…3` | 4 | `The Empire` / `Select province…` / `Roman empire circa ` / `Right Click to Return to Forum` |

---

## VAs

| VA | What |
|---|---|
| `0x57450` | Oracle advice id → `[0x102558]` |
| `0x343C3` | column click (`EAX` 0…3) → picker + `[0x117A96]=1` |
| `0x5F033` | draw `[31] + id + 7` |
| `0x33C3D` | empire-map hit → `[0x102DE0] = ecx+1` |
| `0x5C621` | tooltip: name `[5]`, status `[47]`, flavor `0x57B48` |
| `0xD7B30` | 44× i32 conquer year / sentinel (index = skip) |
| `0x1025CC` | current province pid (Achea **15**) |
| `0x57B48` | HELP record `topic*58+8` |
