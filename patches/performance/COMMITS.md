# Отдельные коммиты патчей

Эти коммиты публикуют `.patch`/описания/проверки. Они **не накладывают runtime diff на src/**: production остаётся контрольным master `0716b47`. Применять нужный экспорт через `git apply`, а не ожидать ускорения только от checkout/cherry-pick публикации.

| № | Коммит | Патч и подробное описание |
|---|---|---|
| 0004 | [`81790a3`](https://github.com/klaxons1/secretlmaoproject/commit/81790a385098db1434077e88f4b0a40c05c85240) | [описание](0004-discovery-heuristic.md), [экспорт](0004-discovery-heuristic.patch) |
| 0005 | [`16b8797`](https://github.com/klaxons1/secretlmaoproject/commit/16b87978a0d5a9d613825a0e85a35f08478b8cb1) | [описание](0005-diagonal-collision.md), [экспорт](0005-diagonal-collision.patch) |
| 0006 | [`04dbcff`](https://github.com/klaxons1/secretlmaoproject/commit/04dbcffb83aa5c07199c3deb09d3c3bf9df16942) | [описание](0006-movement-cost-table.md), [экспорт](0006-movement-cost-table.patch) |
| 0007 | [`d090d90`](https://github.com/klaxons1/secretlmaoproject/commit/d090d90e018fd54720fcc36908d8bf61063dd480) | [описание](0007-heap-decrease-key.md), [экспорт](0007-heap-decrease-key.patch) |
| 0008 | [`b3f3328`](https://github.com/klaxons1/secretlmaoproject/commit/b3f3328842cf318b204e59183d6a7a9a99b468dd) | [описание](0008-passive-inmate-vision.md), [экспорт](0008-passive-inmate-vision.patch) |
| 0009 | [`10e74d2`](https://github.com/klaxons1/secretlmaoproject/commit/10e74d24e4bb95a61d0f6e6207a914717372c748) | [описание](0009-object-broad-phase.md), [экспорт](0009-object-broad-phase.patch) |
| 0010 | [`903dfba`](https://github.com/klaxons1/secretlmaoproject/commit/903dfba2a1aef577c6ade3f4337dcd9727c1bb22) | [описание](0010-zone-type-index.md), [экспорт](0010-zone-type-index.patch) |
| 0011 | [`16e74f5`](https://github.com/klaxons1/secretlmaoproject/commit/16e74f5dab85e6f5fe1d42021d239ac0ddc8ec14) | [описание](0011-npc-zone-memo.md), [экспорт](0011-npc-zone-memo.patch) |
| 0012 | [`2224bdc`](https://github.com/klaxons1/secretlmaoproject/commit/2224bdc60416e8db5b92c9b0b7a4cdecb850be5d) | [описание](0012-packed-seat-lookup.md), [экспорт](0012-packed-seat-lookup.patch) |
| 0013 | [`4901328`](https://github.com/klaxons1/secretlmaoproject/commit/490132835a1f066b32fdf62c0e34590881369be0) | [описание](0013-facing-only-movement.md), [экспорт](0013-facing-only-movement.patch) |
| 0014 | [`a24d80e`](https://github.com/klaxons1/secretlmaoproject/commit/a24d80e7cbfc018f80c6ffb0755add38205b3cf6) | [описание](0014-tile-row-strides.md), [экспорт](0014-tile-row-strides.patch) |
| 0015 | [`d880ea8`](https://github.com/klaxons1/secretlmaoproject/commit/d880ea8d796d2e367daea934bd42bbd93718739b) | [описание](0015-clip-invisible-tiles.md), [экспорт](0015-clip-invisible-tiles.patch) |
| 0016 | [`2afba15`](https://github.com/klaxons1/secretlmaoproject/commit/2afba158afc049fba81e99bc4afc36d29602ea95) | [описание](0016-release-logging-off.md), [экспорт](0016-release-logging-off.patch) |
| 0017 | [`92f441e`](https://github.com/klaxons1/secretlmaoproject/commit/92f441e3716e9d2391a4f117db7c58919183850a) | [описание](0017-npc-lag-breakdown.md), [экспорт](0017-npc-lag-breakdown.patch) |
| 0018 | [`c39fa61`](https://github.com/klaxons1/secretlmaoproject/commit/c39fa6147e05e1d555468b72c2445ee18e48edb5) | [описание](0018-avoid-identical-failed-fallback.md), [экспорт](0018-avoid-identical-failed-fallback.patch) |
| 0019 | [`34c0912`](https://github.com/klaxons1/secretlmaoproject/commit/34c09120fe88e4354877a749e32291a3ab1bd401) | [описание](0019-cache-heap-priorities.md), [экспорт](0019-cache-heap-priorities.patch) |

Сопутствующие коммиты:

- `9f09f79` — прежние исследования heap/tiles и функциональная проверка 0003 опубликованы как исторический архив; старые timings сохранены.
- `8cd9979` — основной pinned стенд, 3204 интервала, differential/pixel проверки и 32 полные сборки.
- `4abb941` — conservative-пакеты без 0011/0013, memory-альтернатива, четыре полные сборки и дополнительные offline tests.

Общий [каталог и безопасные варианты применения](README.md); [профиль на устройстве](PROFILE-GUIDE.md).
