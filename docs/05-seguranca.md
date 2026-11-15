# Segurança e preservação do equipamento

| Regra do projeto | Como é garantida |
|---|---|
| Não modificar firmware, não fazer root, não instalar Valetudo, não resetar | Nenhum código faz isso. Não existem comandos de OTA, reset, Wi-Fi ou voz expostos (o `set_voice` do python-miio **não** foi portado). |
| Não remover o robô da conta e preservar o Xiaomi Home | A Cloud é usada só para leitura (lista de dispositivos e mapa). O protocolo local não altera o vínculo com a conta. |
| Priorizar leitura | Modo simulador por padrão. O diagnóstico usa somente `miIO.info` e `get_properties`. |
| Confirmar antes de movimentos e limpezas | O backend recusa comandos com `moves_robot` ou `requires_confirmation` sem `confirm=true`. A interface abre um diálogo informando: real/simulado, nível de evidência, aviso de movimento e o payload exato. |
| Evitar comandos incompatíveis | Comandos são uma lista fechada (`spec_1c.COMMANDS`). Experimentais exigem a opção explícita. "Não implementados" nunca são enviados. Parâmetros são validados (faixas, enums, tamanho mínimo de zona, formato HH:MM). |
| Não expor tokens ou credenciais | Ficam no cofre do Windows (keyring). A API nunca os devolve. Logs com redação automática. `.gitignore` bloqueia `data/`, `*.db`, `.env` e `*.b64`. Sem cofre disponível, os segredos ficam só em memória. |
| Não alterar configurações críticas sem confirmação | Zerar consumíveis, "não perturbe" e fluxo de água exigem confirmação. |
| API local segura | Escuta em 127.0.0.1. `Host` diferente de localhost é rejeitado (DNS rebinding). O cabeçalho `X-Xiaomi1C: 1` é obrigatório em requisições que alteram estado (CSRF). O WebSocket valida `Origin`. |
| Auditoria | Todo comando enviado é registrado (payload, resposta, real/simulado) e aparece na aba Diagnóstico. |
| Não apresentar funções fictícias | Faixas "SIMULADO", selos de evidência em toda a interface. "Comprovado" só aparece depois do diagnóstico ou da sua confirmação física. |
