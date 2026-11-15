# Arquitetura recomendada e plano de implementação

## Visão geral

```
┌──────────────────────── Windows (um único processo) ────────────────────────┐
│  Janela nativa (pywebview → WebView2/Edge)                                  │
│      └─ Frontend React + TypeScript (Canvas do mapa, painéis, diagnóstico)  │
│              │  HTTP REST + WebSocket (127.0.0.1 somente)                   │
│  Backend Python (FastAPI)                                                   │
│   ├─ services/core.py   polling c/ reconexão, sessões, mapas, eventos       │
│   ├─ robot/             miIO (UDP/AES) · MIoT · spec do 1C · travas         │
│   │     └─ simulator.py robô fictício no mesmo nível siid/piid/aiid         │
│   ├─ cloud/             login QR, API RC4, token, download do mapa          │
│   ├─ maps/              parser do formato Dreame + sistema de coordenadas   │
│   ├─ storage/db.py      SQLite: histórico, mapas, regiões, auditoria        │
│   └─ secrets_store.py   Gerenciador de Credenciais do Windows (keyring)     │
└─────────────────────────────────────────────────────────────────────────────┘
        │ UDP 54321 (LAN)                          │ HTTPS (só mapa / importação)
     Robô 1C                                     Xiaomi Cloud
```

## Decisões técnicas

| Decisão | Motivo |
|---|---|
| **Protocolo miIO próprio** em vez de depender do python-miio | O python-miio 0.5.12 (2022) puxa `netifaces`, que costuma não ter wheel para Windows em Python novo. Com código próprio controlamos os logs (o token nunca aparece) e os testes. A compatibilidade foi validada contra um vetor gerado pelo python-miio. |
| **pywebview + PyInstaller** em vez de Electron/Tauri | Um único runtime (Python), sem Node nem Rust no PC final. O WebView2 já vem no Windows 10/11 e o executável fica bem menor que o do Electron. O Tauri continua viável no futuro, com o backend como *sidecar*. |
| **Simulador no nível bruto** (siid/piid/aiid) | O mesmo executor de comandos e o mesmo parser de mapa rodam com e sem robô. Todo dado simulado sai marcado como `simulated: true`, e a interface mostra faixas "SIMULADO". |
| **Base de conhecimento com nível de evidência** (`robot/spec_1c.py`) | Cada propriedade e cada comando trazem fontes e nível de evidência. A interface não apresenta como funcional algo que não foi comprovado. |
| **Travas no backend**, não só na interface | `confirm=true` é exigido para movimentos e alterações. Experimentais exigem a opção habilitada. Comandos não implementados nunca são enviados. Tudo fica auditado. |
| **API só em localhost**, com cabeçalho obrigatório | Protege contra CSRF de sites abertos no navegador e contra DNS rebinding. |
| **Cloud mínima** | Usada apenas para importar o token e baixar o mapa. Status e comandos são 100% locais. |

## Plano por fases

| Fase | Situação |
|---|---|
| 1. Investigação e compatibilidade | ✅ Pesquisa feita ([01](01-pesquisa-compatibilidade.md)). Falta a confirmação no seu robô (diagnóstico). |
| 2. Comunicação local | ✅ Implementada: descoberta, IP, token no cofre, handshake, leitura, comandos com confirmação, reconexão com backoff, CLI de diagnóstico. **Pendente:** primeiro contato com o robô real. |
| 3. Recuperação do mapa | ✅ Implementada: login por QR, download, parser, armazenamento de cópias locais, coordenadas documentadas ([04](04-mapa-e-coordenadas.md)). **Pendente:** validar com o mapa real do seu 1C. |
| 4. Interface gráfica | ✅ Base pronta: painel, mapa interativo (zoom/pan, robô, base, trajetória, cômodos, restrições), histórico, compatibilidade, diagnóstico, configurações. |
| 5. Controle espacial | 🧪 Ponto, zona e cômodo implementados como **experimentais**, desabilitados por padrão, aguardando teste físico. |
| 6. Edição de mapa e barreiras | Leitura ✅. Rascunhos ✅ (só na interface). Gravação ⛔ até identificar o comando (ver §6 da pesquisa). |
| 7. Recursos avançados | A fazer: agendamentos e automações, perfis de limpeza, estatísticas avançadas, backup/exportação de mapas, MQTT/Home Assistant, API externa autenticada. |

## Estrutura do repositório

```
backend/            Python (FastAPI) + testes (pytest)
  xiaomi1c/robot/   miio_protocol, transport, device, spec_1c, commands, status, simulator
  xiaomi1c/cloud/   crypto (RC4/assinaturas), client (QR login, devices, map)
  xiaomi1c/maps/    dreame_format (parser/encoder)
  xiaomi1c/api/     app.py (REST + WebSocket)
frontend/           React + TypeScript (Vite)
docs/               pesquisa, arquitetura, configuração, mapa, segurança, testes
packaging/          scripts de build para Windows
```
