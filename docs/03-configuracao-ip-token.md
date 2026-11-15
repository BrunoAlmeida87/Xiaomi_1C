# Como obter o IP e o token do robô (com segurança)

O app **nunca** pede senha ou token pela conversa ou por arquivo de texto.
Segredos ficam no **Gerenciador de Credenciais do Windows** (via `keyring`) e
nunca são devolvidos pela API nem gravados nos logs, que redigem padrões de
token automaticamente.

## Opção A (recomendada): QR code dentro do app

1. Abra o app, vá em **Configurações** e clique em **Gerar QR code**.
2. No celular, abra o **Xiaomi Home**, vá em **Perfil** e toque no ícone de
   leitura de QR (canto superior). Escaneie o código. A senha não passa pelo app.
3. Em **Importar o robô da conta**, clique em **Listar dispositivos** (deixe
   "Todos os servidores" se você não souber a região; contas no Brasil
   costumam ficar em `us` ou `sg`).
4. Na linha do `dreame.vacuum.mc1808`, clique em **Importar**. O app:
   * grava o token no cofre do Windows;
   * grava IP, `did`, `uid` e servidor em `config.json` (dados não sensíveis);
   * **não** altera nada no robô nem na conta.
5. Selecione **Robô real** em "Modo de operação".

A sessão da Cloud também fica no cofre e serve para baixar o mapa. Para revogá-la,
use **Sair** no app. A sessão some também ao trocar a senha da conta Xiaomi.

> O robô continua na sua conta e o Xiaomi Home segue funcionando normalmente.
> O token só muda se o robô for resetado ou reconfigurado no Wi-Fi.

## Opção B: Xiaomi-cloud-tokens-extractor + entrada manual

1. Baixe `token_extractor.exe` da página de releases do
   [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor/releases).
2. Execute e escolha login por QR code.
3. Copie o token do `dreame.vacuum.mc1808` e cole no campo **Token** em
   Configurações (campo de senha, nunca exibido). Ou use no terminal:

```bash
xiaomi1c set-token
```

## IP do robô

* A importação pela Cloud já traz o `localip`.
* No Xiaomi Home: abra o robô e vá em **⋯ → Configurações → Informações de rede**.
* No roteador: veja a lista de clientes DHCP. Recomenda-se **reservar o IP**
  (DHCP estático) do robô para que ele não mude.
* No app: **Procurar na rede** envia um "hello" miIO (somente leitura) e lista
  quem responder na porta UDP 54321.

## Requisitos de rede no Windows

* O PC e o robô precisam estar na **mesma rede/sub-rede**. Wi-Fi de convidados
  e "isolamento de AP" bloqueiam a comunicação.
* O tráfego é **UDP 54321**. Se o Firewall do Windows perguntar, permita o app
  em redes **privadas**.

## Primeiro teste (somente leitura)

```bash
xiaomi1c info --ip 192.168.X.Y
```

```bash
xiaomi1c probe --ip 192.168.X.Y
```

Ou use a aba **Diagnóstico**. Confira se `model` é `dreame.vacuum.mc1808` e
se `fw_ver` é `4.3.3_1122`.
