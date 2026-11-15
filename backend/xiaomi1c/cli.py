"""Linha de comando: diagnóstico não invasivo e servidor.

Exemplos::

    xiaomi1c discover                 # procura dispositivos miIO na rede (hello, sem token)
    xiaomi1c info --ip 192.168.1.50   # miIO.info (modelo, firmware) — token lido do cofre
    xiaomi1c probe --ip 192.168.1.50  # varredura SOMENTE-LEITURA de propriedades
    xiaomi1c set-token                # grava o token no cofre (entrada oculta)
    xiaomi1c serve                    # API + interface em http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from .secrets_store import ROBOT_TOKEN, SecretStore


def _robot(args):
    from .robot.device import RealRobot

    token = SecretStore().get(ROBOT_TOKEN)
    if not token:
        sys.exit("Token não encontrado no cofre. Use 'xiaomi1c set-token' ou importe pela interface (Xiaomi Cloud).")
    return RealRobot(args.ip, token)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="xiaomi1c")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover")
    for name in ("info", "probe", "status"):
        sp = sub.add_parser(name)
        sp.add_argument("--ip", required=True)
    sub.add_parser("set-token")
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=8765)
    sub.add_parser("desktop")
    args = p.parse_args(argv)

    if args.cmd == "discover":
        from .robot.transport import discover

        devs = discover()
        if not devs:
            print("Nenhum dispositivo respondeu. Verifique se o PC está na mesma rede/VLAN do robô.")
        for d in devs:
            print(f"{d.ip}\tdevice_id={d.device_id}")
    elif args.cmd == "set-token":
        tok = getpass.getpass("Token (32 hex, não será exibido): ").strip()
        if len(tok) != 32:
            sys.exit("Token inválido")
        store = SecretStore()
        store.set(ROBOT_TOKEN, tok.lower())
        print("Token salvo no cofre do sistema." if store.persistent else "AVISO: cofre indisponível; token não persistido.")
    elif args.cmd == "info":
        print(json.dumps(_robot(args).info(), indent=2, ensure_ascii=False))
    elif args.cmd == "status":
        from .robot.status import normalize_status

        r = _robot(args)
        st = normalize_status(r.read_props(), False)
        st.pop("properties")
        print(json.dumps(st, indent=2, ensure_ascii=False))
    elif args.cmd == "probe":
        from .robot.status import probe

        res = probe(_robot(args))
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    elif args.cmd == "serve":
        from .server import serve

        serve(port=args.port)
    elif args.cmd == "desktop":
        from .desktop import main as desktop_main

        desktop_main()


if __name__ == "__main__":
    main()
