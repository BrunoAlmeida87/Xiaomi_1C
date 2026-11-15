# Formato do mapa e sistema de coordenadas

Implementação: `backend/xiaomi1c/maps/dreame_format.py` (testada em `tests/test_map_format.py`).
Fonte do formato: Xiaomi Cloud Map Extractor, parser "Dreame", que lista o `dreame.vacuum.mc1808`.

## Obtenção

1. A sessão da Xiaomi Cloud é obtida por QR code.
2. `POST /v2/home/get_interim_file_url` com `{"obj_name": "<uid>/<did>/0"}` devolve uma URL temporária.
3. O download traz um texto base64 *URL-safe* com dados compactados em zlib.
4. Cada download é salvo **sem alteração** em `%LOCALAPPDATA%\Xiaomi1C\maps\map_<data>_cloud.b64` e registrado no SQLite. Esse é o backup local.

## Estrutura binária

| Offset | Tipo | Campo |
|---|---|---|
| 0 | int16 LE | índice do mapa |
| 2 | int16 LE | id do quadro |
| 4 | int8 | tipo de quadro (`I`=73 completo, `P`=80 incremental) |
| 5/7/9 | int16 LE | robô: x, y (mm), ângulo (°) |
| 11/13/15 | int16 LE | base: x, y (mm), ângulo (°) |
| 17 | int16 LE | tamanho do pixel (mm), em geral 50 |
| 19/21 | int16 LE | largura e altura (pixels) |
| 23/25 | int16 LE | `left` e `top`: origem da grade (mm) |
| 27 | `largura × altura` bytes | pixels (linha 0 = menor Y) |
| … | JSON UTF-8 | dados adicionais |

Pixels do mapa "regular": `seg = px >> 2` indica o cômodo quando `0 < seg < 62`. Fora disso, `px & 3` vale 0 (fora), 1 (chão) ou 2 (parede).
No mapa salvo aninhado (`rism`, presente quando `ris == 2`): `px >> 7` = parede e `px & 0x7F` = cômodo.

JSON adicional (chaves conhecidas):

| Chave | Conteúdo |
|---|---|
| `tr` | trajetória: `M`/`S` = ponto absoluto, `L` = deslocamento relativo (mm) |
| `vw.line` | paredes virtuais `[x1,y1,x2,y2]` |
| `vw.rect` | zonas proibidas `[x1,y1,x2,y2]` |
| `vw.mop` | zonas sem pano |
| `sa` | segmentos ativos (cômodos em limpeza) |
| `seg_inf` | nomes dos cômodos (base64) |
| `rism`, `ris` | mapa salvo aninhado |

O app guarda a lista de **todas** as chaves recebidas (`extra_keys`) para
documentar campos novos ou desconhecidos do seu firmware.

## Sistema de coordenadas

* Unidade: **milímetros**, no mesmo referencial usado pelos comandos de zona e de ponto.
* `x_mm = left + coluna × pixel_size`
* `y_mm = top + linha × pixel_size`
* O Y do robô cresce "para cima". A interface inverte as linhas ao desenhar (`linha_tela = altura − linha`).
* Clique na tela → mm: `MapView.tsx::toMm`. Um retângulo desenhado vira `[x1,y1,x2,y2]` em mm, que é exatamente o formato de `areas` da limpeza por zona.

## Três níveis de "editar o mapa"

1. **Visual (app):** rascunhos, nomes de cômodos e regiões salvas. Existem só no app e não afetam o robô.
2. **Restrições operacionais (robô):** paredes virtuais e zonas proibidas. O app **lê** as existentes, mas **não grava**, porque não há comando conhecido para o 1C.
3. **Mapa interno de navegação:** impossível com o firmware original.

## Limitações conhecidas

* Quadros incrementais (`P`) não são suportados, assim como no Map Extractor. A Cloud entrega quadros `I`.
* O VSLAM do 1C tende a gerar mapas mais "ruidosos" que os de LiDAR. As coordenadas continuam válidas para os comandos.
* Mapa ao vivo: a Cloud é consultada no máximo a cada 15 s, e só durante a limpeza. A opção vem desligada por padrão.
