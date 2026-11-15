# Xiaomi 1C Control

Aplicativo próprio para Windows que controla, monitora e gerencia o **Xiaomi
Robot Vacuum-Mop 1C** (STYTJ01ZHM, `dreame.vacuum.mc1808`). A prioridade é a
comunicação **local** (miIO/MIoT pela rede Wi-Fi). A Xiaomi Cloud é usada
somente para importar o token e baixar o mapa. O firmware original e o Xiaomi
Home são preservados.

> **Estado atual:** fundação completa e testada com o **simulador**. Nenhuma
> função foi ainda comprovada no robô real. Siga o
> [roteiro de testes](docs/06-roteiro-de-testes.md).

## Documentação

| Documento | Conteúdo |
|---|---|
| [01 — Pesquisa e compatibilidade](docs/01-pesquisa-compatibilidade.md) | Protocolos, bibliotecas, matriz de funcionalidades com nível de evidência e fontes |
| [02 — Arquitetura e plano](docs/02-arquitetura-e-plano.md) | Decisões técnicas e status por fase |
| [03 — IP e token](docs/03-configuracao-ip-token.md) | Como obter com segurança (QR code, sem senha) |
| [04 — Mapa e coordenadas](docs/04-mapa-e-coordenadas.md) | Formato binário, coordenadas, níveis de edição |
| [05 — Segurança](docs/05-seguranca.md) | Travas implementadas |
| [06 — Roteiro de testes](docs/06-roteiro-de-testes.md) | Validação progressiva no robô real |

## O que já funciona

* Protocolo miIO próprio (AES/UDP), MIoT, descoberta na rede e reconexão automática.
* Painel: estado, bateria, erros (28 códigos), sucção, água, volume, totais, consumíveis e todas as propriedades lidas.
* Comandos com **confirmação obrigatória** para movimentos. Experimentais desabilitados por padrão. Auditoria.
* Login na Xiaomi Cloud por **QR code**: token guardado no **Gerenciador de Credenciais do Windows**.
* Mapa: download, parser do formato Dreame, backup local, canvas interativo (zoom/pan, robô, base, trajetória, cômodos, paredes e zonas existentes).
* Seleção de ponto, zonas e cômodos; regiões e sequências salvas (envio marcado como **experimental**).
* Rascunhos de paredes e zonas proibidas, marcados como **não enviados**: o firmware não tem comando conhecido para gravá-los.
* Histórico local (SQLite) e sessões de limpeza derivadas das mudanças de estado.
* Matriz de compatibilidade viva e diagnóstico somente-leitura (varredura siid × piid).
* Modo **simulador** para usar a interface sem o robô.

## Executar no Windows

**Mais simples:** baixe `Xiaomi1C-portatil.zip` (gerado por `python packaging/make_portable.py`), extraia e dê dois cliques em `Iniciar.bat`. Só exige o Python 3.11+ instalado: a interface já vem compilada.

Para desenvolvimento:

Requisitos: Python 3.11+ e Node.js 20+.

```powershell
.\packaging\setup_windows.ps1
```

```powershell
.\packaging\run_windows.ps1
```

Para gerar um executável portátil: `.\packaging\build_windows.ps1`.

## Desenvolvimento

```bash
python -m venv .venv && .venv/bin/pip install -e "backend[dev]"
```

```bash
.venv/bin/python -m pytest backend/tests
```

```bash
.venv/bin/python -m xiaomi1c serve
```

```bash
cd frontend && npm install && npm run dev
```

No desenvolvimento, o Vite (porta 5173) encaminha `/api` e `/ws` para o backend (porta 8765).

### CLI de diagnóstico

```bash
xiaomi1c discover
```

```bash
xiaomi1c set-token
```

```bash
xiaomi1c info --ip 192.168.1.50
```

```bash
xiaomi1c probe --ip 192.168.1.50
```

## Dados locais

`%LOCALAPPDATA%\Xiaomi1C\` contém: `config.json` (sem segredos), `xiaomi1c.db`,
`maps\` (cópias dos mapas) e `logs\`. Os segredos ficam no cofre do Windows,
nunca nessa pasta.

## Créditos e referências

Projeto baseado na pesquisa pública de: python-miio, Xiaomi Cloud Map Extractor e
Xiaomi-cloud-tokens-extractor (PiotrMachowski), Piotras1/dreame-vacuum-1808-1c,
Tasshack/dreame-vacuum e al-one/hass-xiaomi-miot. Detalhes em [docs/01](docs/01-pesquisa-compatibilidade.md).
