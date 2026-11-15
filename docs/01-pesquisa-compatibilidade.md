# Fase 1 — Pesquisa técnica e matriz de compatibilidade

Equipamento: **Xiaomi Robot Vacuum-Mop 1C**, modelo físico **STYTJ01ZHM**, firmware **4.3.3_1122**.
Data da pesquisa: novembro de 2026.

> **Como ler este documento.** Nenhuma funcionalidade foi, até agora, testada no
> *seu* robô — esta fase foi feita só com código-fonte e relatos públicos. A
> confirmação no seu equipamento é feita pelo próprio aplicativo (aba
> **Diagnóstico** e confirmação física de cada comando; ver
> [`06-roteiro-de-testes.md`](06-roteiro-de-testes.md)).

## 1. Identificação: `dreame.vacuum.mc1808`

| Evidência | Resultado |
|---|---|
| python-miio (`DREAME_1C = "dreame.vacuum.mc1808"`) | Mapeamento MIoT dedicado ao 1C |
| Xiaomi Cloud Map Extractor (README) | "`dreame.vacuum.mc1808` (Xiaomi Mi Mop/Xiaomi Mijia 1C)" |
| Piotras1/dreame-vacuum-1808-1c | Integração feita exclusivamente para "MC1808 / STYTJ01ZHM" |
| URN MIoT (al-one#1506) | `urn:miot-spec-v2:device:vacuum:0000A006:dreame-mc1808:1` |

**Status:** muito provável, **não comprovado**. A confirmação técnica é o campo
`model` da resposta `miIO.info` do seu robô. O app faz essa leitura no
diagnóstico (`model_confirmed`). Atenção: a Valetudo cita várias revisões de
hardware vendidas com o nome "1C" e só suporta a `mc1808`. Por isso a leitura no
equipamento é obrigatória.

## 2. Protocolos locais

* **miIO** (UDP 54321): handshake "hello", depois mensagens JSON cifradas com
  AES-128-CBC, onde a chave é derivada do **token** de 32 caracteres hexadecimais.
  Implementado do zero em `backend/xiaomi1c/robot/miio_protocol.py` e validado
  contra um vetor gerado pelo python-miio.
* **MIoT** sobre miIO: métodos `get_properties`, `set_properties` e `action`
  (siid/piid/aiid). O 1C é um dispositivo MIoT. Os comandos clássicos
  `app_start`/`get_status` do miIO valem para Roborock e **não** se aplicam ao 1C.
* Não há API HTTP local. O mapa **não** é servido localmente pelo firmware
  original (ver §5).

## 3. Bibliotecas e projetos avaliados

| Projeto | Serve para o 1C? | Observações |
|---|---|---|
| [python-miio](https://github.com/rytilahti/python-miio) | **Sim** (status, comandos básicos, ventoinha, consumíveis, movimento manual) | Última versão no PyPI é a 0.5.12 (2022). Puxa `netifaces`, que costuma não ter wheel para Windows em Python novo. Usado como **referência**. O app implementa o protocolo por conta própria. |
| [Piotras1/dreame-vacuum-1808-1c](https://github.com/Piotras1/dreame-vacuum-1808-1c) | **Sim**, feito para o 1C | Traz limpeza por zona (`zone_cleanup`) e por cômodo (`segment_cleanup`), esta última marcada pelo próprio autor como *EXPERIMENTAL / não verificada*. Diverge do python-miio em alguns piids. |
| [Xiaomi Cloud Map Extractor](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Xiaomi-Cloud-Map-Extractor) | **Sim** (mapa via Cloud) | Formato "Dreame". O mapa do 1C é obtido em `/v2/home/get_interim_file_url` com `obj_name = {uid}/{did}/0`. |
| [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor) | **Sim** (token) | Faz login por QR code ou por senha (com captcha e 2FA por e-mail). O fluxo por QR foi reimplementado no app. |
| [Tasshack/dreame-vacuum](https://github.com/Tasshack/dreame-vacuum) | **Não** para o 1C | O código não menciona `mc1808` e usa o layout MIoT dos Dreame novos (siid 2/4/6). Foi útil como referência do formato de paredes virtuais dos modelos novos. |
| [al-one/hass-xiaomi-miot](https://github.com/al-one/hass-xiaomi-miot) | Parcial | Integração genérica MIoT. As issues #279 e #1506 documentam a limpeza por cômodo no 1C. |
| [Valetudo](https://valetudo.cloud/) | Lista a `mc1808` | Exige **root** (UART 3,3 V + placa breakout Dreame, segundo o resumo da busca). Substitui a nuvem e desvincula o robô do Xiaomi Home. **Fora do escopo** pelas regras do projeto (preservar o firmware e o Xiaomi Home). Guias de terceiros dizem que o suporte ao 1C é "apenas ok" e "não recomendado". |

Não foi necessário usar ferramentas de engenharia reversa (REA/RIA) nesta
fase: já existem soluções abertas para status, comandos, token e mapa. A
engenharia reversa fica reservada à lacuna que continua aberta, a **gravação de
paredes virtuais e zonas proibidas** (§6).

## 4. Matriz de funcionalidades

Legenda: ✅ comprovado no seu robô · 📘 documentado para o mc1808 · 🔗 documentado só para modelos relacionados · 🧪 experimental · ⛔ não implementado / sem comando conhecido.
Na data deste documento nada está ✅. O app troca 📘 por ✅ automaticamente, a partir do diagnóstico e da sua confirmação física.

### 4.1 Controle

| Função | MIoT | Nível | Fontes / observações |
|---|---|---|---|
| Iniciar limpeza | action 3.1 | 📘 | python-miio. O piotras1 usa 18.1 com piid1=2 |
| Parar | action 3.2 | 📘 | python-miio, piotras1 |
| Pausar | action 18.2 | 🧪 | O 1C não tem "pause" documentado. O piotras1 usa 18.2 |
| Continuar | action 3.1 | 🧪 | Reenvia o start. É preciso confirmar se o firmware retoma a tarefa |
| Voltar à base | action 2.1 | 📘 | start-charge |
| Localizar (som) | action 17.1 | 📘 | |
| Potência de sucção | set 18.6 (0–3) | 📘 | Silencioso, Padrão, Médio, Forte |
| Fluxo de água | set 18.20 (1–3) | 🧪 | A leitura é documentada. A escrita **não** (TODO no python-miio) |
| Volume / som de teste | set 24.1 / action 24.3 | 📘 | |
| Não perturbe | set 20.1–20.3 | 📘 | |
| Zerar consumíveis | actions 26.1, 27.1, 28.1 | 📘 | |
| Movimento manual | action 21.1 | 🧪 | As fontes divergem (python-miio: piid1=ângulo, piid2=velocidade; piotras1: "start remote") |
| Códigos de erro | prop 3.1 | 📘 | Tabela de 28 códigos (piotras1) |

### 4.2 Monitoramento

| Dado | MIoT | Nível |
|---|---|---|
| Bateria, estado de carga | 2.1, 2.2 | 📘 |
| Estado operacional, modo de trabalho | 3.2, 18.1 | 📘 |
| Tempo e área da limpeza atual | 18.2 e 18.3 **ou** 18.4 | 📘 / 🧪 (as fontes divergem quanto à área; o diagnóstico resolve) |
| Totais (tempo, quantidade, área, 1ª limpeza) | 18.13, 18.14, 18.15, 18.12 | 📘 |
| Escovas e filtro (% e horas) | 26.x, 27.x, 28.x | 📘 |
| Tanque de água instalado | 18.9 | 🧪 (só notify) |
| Firmware, MAC, Wi-Fi | `miIO.info` | 📘 |
| Histórico de limpezas do robô | — | ⛔ via local. O app grava **o próprio histórico** em SQLite a partir das mudanças de estado |
| Estado dos sensores | — | ⛔ não exposto. Erros de sensor aparecem via 3.1 |

### 4.3 Mapa e controle espacial

| Função | Nível | Detalhes |
|---|---|---|
| Baixar mapa da Xiaomi Cloud | 📘 | Map Extractor. O arquivo vem em base64 + zlib (formato descrito em [`04-mapa-e-coordenadas.md`](04-mapa-e-coordenadas.md)) |
| Mapa direto do robô, sem internet | ⛔ | O firmware só envia o mapa para a nuvem. Sem root não há acesso local conhecido. A propriedade 23.1 (`map-view`) será inspecionada pelo diagnóstico |
| Pedir upload do mapa (action 23.1) | 🧪 | Análogo à ação 6.1 dos modelos novos |
| Posição do robô, base, trajetória, paredes e zonas existentes | 📘 | Cabeçalho do mapa e campos `tr`/`vw` |
| Limpeza por zona | 🧪 | `18.1 {piid1:19, piid21:'{"areas":[[x1,y1,x2,y2,rep,1,1]]}'}` (card#406). Não há relato publicado de sucesso no 1C |
| Limpeza por cômodo | 🧪 | `18.1 {piid1:18, piid21:'{"selects":[[id,rep,sucção,3,ordem]]}'}`. Relatos divergentes: funcionou (al-one#279, 2021; card#406, 2024), "sucesso sem movimento" (card#406, nov/2025), erro -1 com JSON não minificado (al-one#1506) |
| Limpeza por ponto | 🧪 (emulada) | Não existe comando no 1C. O app envia uma zona de 1 m × 1 m centrada no ponto clicado |
| Regiões salvas e sequências | ✅ no app | Ficam no SQLite local e são reexecutadas pelos comandos acima |
| Nomes de cômodos | só no app | Não existe comando conhecido para renomear no robô |
| Dividir/unir cômodos, ajustar limites | ⛔ | Sem comando conhecido para o 1C |
| **Gravar** paredes virtuais e zonas proibidas | ⛔ | Ver §6 |
| **Ler** paredes virtuais e zonas proibidas | 📘 | Campo `vw` do mapa da Cloud (`line`, `rect`, `mop`) |
| Alterar o mapa interno de navegação | ⛔ | O firmware original não aceita mapas externos |

## 5. Por que o mapa depende da Cloud

O 1C navega por câmera de teto (VSLAM). O mapa fica na memória do robô e é
enviado ao armazenamento da Xiaomi. O app Xiaomi Home o lê de lá. O Map
Extractor faz o mesmo:

1. sessão autenticada (`userId`, `ssecurity`, `serviceToken`);
2. `POST https://{servidor}.api.io.mi.com/app/v2/home/get_interim_file_url`, com `{"obj_name": "{uid}/{did}/0"}` cifrado em RC4;
3. download da URL temporária devolvida.

Sem root não existe caminho local documentado. Por isso a Cloud é usada
**somente** para o mapa e para importar o token uma única vez. Todos os
comandos e o status continuam locais.

## 6. Paredes virtuais, zonas proibidas e edição de mapa

| Nível de alteração | Situação no 1C com firmware original |
|---|---|
| 1. Representação visual no app | ✅ possível. O app desenha **rascunhos**, marcados como "não enviado" |
| 2. Restrições operacionais (paredes, zonas proibidas, regiões) | Leitura 📘. **Gravação ⛔**: não há comando documentado. Nos Dreame novos é `action 6.2` com `piid4 = '{"vw":{"line":[],"rect":[],"mop":[]}}'` (Tasshack). O equivalente no 1C (siid 23?) é **hipótese não testada** e **não** está implementado |
| 3. Mapa interno de navegação (paredes, passagens) | ⛔ sem root |

**Próximo passo de pesquisa (não invasivo), por ordem de custo:**

1. Ler a especificação completa em `miot-spec.org` (no seu PC) e verificar se o
   siid 23 declara uma ação de "update map" com parâmetro de dados estendidos.
2. Inspecionar o *plugin* do Xiaomi Home para o `mc1808` (bundle JavaScript
   baixado pelo app). Ele contém exatamente o payload que o app oficial envia ao
   salvar paredes virtuais. É aqui que uma ferramenta de engenharia reversa
   (REA/RIA) faz sentido.
3. Só depois disso, com sua autorização, um teste controlado: criar uma parede
   pelo Xiaomi Home, ler o `vw` pelo app, enviar a mesma parede pelo comando
   candidato e confirmar fisicamente que o robô a respeita.

Até lá, a interface **não** apresenta paredes virtuais desenhadas como funcionais.

## 7. Referências

* python-miio: `miio/integrations/vacuum/dreame/dreamevacuum_miot.py` (0.5.12) e `miio/integrations/dreame/vacuum/dreamevacuum_miot.py` (master)
* Piotras1/dreame-vacuum-1808-1c: `custom_components/dreame_mc1808/dreame_client.py`, `vacuum.py`
* Xiaomi Cloud Map Extractor: `dreame/map_data_parser.py`, `dreame/image_handler.py`, `common/vacuum_v2.py`, `common/xiaomi_cloud_connector.py`
* Xiaomi-cloud-tokens-extractor: `token_extractor.py` (`QrCodeXiaomiCloudConnector`)
* Tasshack/dreame-vacuum: `dreame/device.py` (`set_restricted_zone`, `request_map`) e `dreame/types.py`
* [al-one/hass-xiaomi-miot#279](https://github.com/al-one/hass-xiaomi-miot/issues/279), [#1506](https://github.com/al-one/hass-xiaomi-miot/issues/1506)
* [lovelace-xiaomi-vacuum-map-card discussion #406](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card/discussions/406)
* [merdok/homebridge-miot — robotcleaner.md](https://github.com/merdok/homebridge-miot/blob/main/docs/robotcleaner.md)
* [Valetudo — supported robots](https://valetudo.cloud/pages/general/supported-robots.html) (não lido diretamente: domínio bloqueado no ambiente de pesquisa; informações vindas de resumo de busca)
* Relatos de firmware: smartrobotreviews.com (paredes virtuais e zonas adicionadas por atualização; problemas na 3.5.8_1110). Nenhuma fonte cita especificamente a 4.3.3_1122.

**Limitações desta pesquisa:** `miot-spec.org`, `valetudo.cloud` e o fórum do
Home Assistant estavam inacessíveis a partir do ambiente de desenvolvimento. A
especificação MIoT oficial do mc1808 ainda precisa ser baixada e conferida, o que
o diagnóstico faz em parte lendo diretamente o seu robô.
