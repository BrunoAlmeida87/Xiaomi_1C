# Roteiro de testes no robô real (progressivo e seguro)

Execute em ordem. Não avance se uma etapa falhar. Anote os resultados
(versão do firmware, o que aconteceu fisicamente).

## Etapa 0: preparação
* Robô na base, carregado, sem obstáculos ao redor.
* Xiaomi Home funcionando no celular, para comparar.
* Siga [`03-configuracao-ip-token.md`](03-configuracao-ip-token.md) (QR code e importação).

## Etapa 1: somente leitura
1. **Diagnóstico → Executar diagnóstico.** Esperado: `model = dreame.vacuum.mc1808`, `fw_ver = 4.3.3_1122`.
2. Compare no **Painel**: bateria, estado e consumíveis devem bater com o Xiaomi Home.
3. Anote qual dos campos 18.3 ou 18.4 traz a área limpa.
4. Anote propriedades "desconhecidas" (linhas destacadas). Elas são candidatas a novas funções.
5. **Mapa → Atualizar mapa.** O mapa deve corresponder ao do Xiaomi Home. Confira se a posição da base e as paredes virtuais existentes aparecem em vermelho contínuo.

## Etapa 2: comandos sem movimento
1. **Localizar.** O robô deve emitir som.
2. **Potência de sucção.** Mude e confira no Xiaomi Home.
3. Ao final de cada etapa, responda "O robô executou fisicamente?" no aviso. Só assim o comando passa a "Comprovado".

## Etapa 3: comandos com movimento (documentados)
1. **Iniciar.** Confirme, observe alguns segundos e use **Parar**.
2. **Voltar à base.**

## Etapa 4: experimentais (habilite em Configurações)
1. **Pausar** durante uma limpeza, depois **Continuar**. O robô retoma ou recomeça?
2. **Zona:** desenhe uma zona pequena (cerca de 1,5 m × 1,5 m) em local livre, perto da base. O robô deve ir até a área e limpar só ela. Teste também a **limpeza por ponto**.
3. **Cômodo:** só se o mapa mostrar cômodos segmentados. Teste um único cômodo.
4. **Fluxo de água:** com o tanque instalado, mude o valor e verifique no Xiaomi Home.

Se o comando for aceito (code 0) e o robô **não** se mover, marque "Não" e
informe. Esse comportamento já foi relatado na comunidade para a limpeza por cômodo.

## O que reportar ao final
* JSON do diagnóstico (aba Diagnóstico). Não contém token.
* Resultado de cada etapa.
* Arquivo do mapa, se quiser ajudar a validar o parser. Ele fica em `%LOCALAPPDATA%\Xiaomi1C\maps\` e contém a planta da sua casa: compartilhe só se estiver confortável.
