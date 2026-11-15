"""Monta a pasta portátil para Windows: dist-portable/Xiaomi1C (+ .zip).

Conteúdo: código do backend, interface já compilada (dispensa Node.js),
``Iniciar.bat`` (duplo clique) e ``LEIA-ME.txt``. Na primeira execução o .bat
cria um ambiente Python isolado dentro da própria pasta.

Uso (na raiz do repositório, com o frontend já compilado)::

    python packaging/make_portable.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist-portable"
PKG = OUT / "Xiaomi1C"


def crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


INICIAR_BAT = r"""@echo off
setlocal
chcp 65001 >nul
title Xiaomi 1C Control
cd /d "%~dp0"

set "VENV=%~dp0.venv"
set "VPY=%VENV%\Scripts\python.exe"

if exist "%VPY%" goto run

echo ============================================================
echo  Xiaomi 1C Control - primeira execucao
echo  Preparando o ambiente (precisa de internet, so desta vez).
echo ============================================================
rem Cada candidato e EXECUTADO para confirmar que funciona e e 3.10+.
rem (O lancador "py" pode apontar para um Python desinstalado.)
set "PY="
set "PYTXT="
if exist "%~dp0python.txt" set /p PYTXT=<"%~dp0python.txt"
if defined PYTXT set "PYTXT=%PYTXT:"=%"
if defined PYTXT call :try "%PYTXT%"
if not defined PY call :try python
if not defined PY call :try py -3
if not defined PY call :try python3
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "C:\Python3*" "D:\Python3*" "E:\Python3*") do (
  if not defined PY if exist "%%~D\python.exe" call :try "%%~D\python.exe"
)
if not defined PY goto nopython
echo Usando Python: %PY%

%PY% -m venv "%VENV%"
if errorlevel 1 goto fail
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip
"%VPY%" -m pip install --disable-pip-version-check -e "%~dp0backend"
if errorlevel 1 goto fail

echo Instalando janela nativa (opcional; se falhar, o app abre no navegador)...
"%VPY%" -m pip install --disable-pip-version-check -q "pywebview>=5.0"
if errorlevel 1 echo Aviso: pywebview nao instalado. O app abrira no navegador.

:run
echo Iniciando... (feche esta janela para encerrar o programa)
"%VPY%" -m xiaomi1c desktop
if errorlevel 1 (
  echo.
  echo O programa terminou com erro. Veja os logs em %LOCALAPPDATA%\Xiaomi1C\logs
  pause
)
exit /b 0

:try
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%*"
exit /b 0

:nopython
echo.
echo Nenhum Python 3.10+ FUNCIONAL foi encontrado neste computador.
echo.
echo Diagnostico:
echo  - "python" no PATH:
where python 2>nul || echo      nenhum
echo  - Pythons registrados no lancador "py":
py -0p 2>nul || echo      nenhum
echo.
echo Se algum caminho acima nao existe mais (ex.: E:\python311), o Python foi
echo desinstalado ou a unidade mudou. Solucao:
echo  1. Instale o Python 3.11+ em https://www.python.org/downloads/
echo     marcando "Add python.exe to PATH" e "py launcher".
echo  2. Feche esta janela e execute o Iniciar.bat novamente.
echo.
echo Alternativa: crie um arquivo python.txt nesta pasta contendo o caminho
echo completo do python.exe (ex.: C:\Python312\python.exe).
pause
exit /b 1

:fail
echo.
echo Falha ao preparar o ambiente. Verifique a internet e tente de novo.
echo Se persistir, apague a pasta ".venv" dentro desta pasta e execute novamente.
if exist "%VENV%" rmdir /s /q "%VENV%"
pause
exit /b 1
"""

DIAG_BAT = r"""@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute primeiro o Iniciar.bat.
  pause
  exit /b 1
)
echo Procurando dispositivos Xiaomi na rede (somente leitura)...
".venv\Scripts\python.exe" -m xiaomi1c discover
echo.
pause
"""

LEIA_ME = """XIAOMI 1C CONTROL - versão portátil
====================================

COMO EXECUTAR
1. Instale o Python 3.11 ou superior: https://www.python.org/downloads/
   Durante a instalação, marque "Add python.exe to PATH".
2. Dê dois cliques em  Iniciar.bat
   - Na primeira vez ele prepara o ambiente (1 a 3 minutos, precisa de internet).
   - Nas próximas vezes abre direto.
3. O programa abre em MODO SIMULADOR (dados fictícios, marcados como "SIMULADO").
   Para usar o robô de verdade: aba Configurações > Gerar QR code >
   escaneie com o app Xiaomi Home > Listar dispositivos > Importar >
   modo "Robô real".

Se o Windows exibir "O Windows protegeu o computador" (SmartScreen), clique em
"Mais informações" > "Executar assim mesmo". O .bat é texto simples: você pode
abri-lo no Bloco de Notas para conferir o que ele faz.
Se o Firewall do Windows perguntar, permita o acesso em redes PRIVADAS
(o robô é acessado pela porta UDP 54321 da rede local).

PROBLEMAS COM O PYTHON
- "Unable to create process using 'E:\\python311\\python.exe'..." ou
  "Nenhum Python 3.10+ FUNCIONAL": o Windows ainda tem registro de um Python
  que foi desinstalado/movido. Reinstale o Python 3.11+ (python.org) marcando
  "Add python.exe to PATH" e execute o Iniciar.bat de novo.
- Se o Python estiver instalado num local incomum, crie nesta pasta um arquivo
  python.txt contendo só o caminho completo do python.exe.
- Se a primeira execução falhar no meio, apague a pasta .venv daqui e tente de novo.

OUTROS ARQUIVOS
- Procurar-robo.bat : procura dispositivos Xiaomi na rede (somente leitura).
- docs\\             : pesquisa técnica, segurança e roteiro de testes no robô.

ONDE FICAM OS DADOS
- Configurações, histórico e mapas: %LOCALAPPDATA%\\Xiaomi1C
- Token e sessão Xiaomi: Gerenciador de Credenciais do Windows (nunca em arquivo).

SEGURANÇA
- Nada é enviado ao robô sem você confirmar movimentos e limpezas.
- Funções experimentais vêm desligadas.
- O firmware e o app Xiaomi Home não são alterados.

PARA REMOVER
Apague esta pasta e a pasta %LOCALAPPDATA%\\Xiaomi1C.
"""


def main() -> None:
    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").exists():
        print("Compilando o frontend (npm run build)...")
        subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=True, shell=sys.platform == "win32")

    if OUT.exists():
        shutil.rmtree(OUT)
    PKG.mkdir(parents=True)

    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", "tests", ".pytest_cache")
    shutil.copytree(ROOT / "backend", PKG / "backend", ignore=ignore)
    shutil.copytree(dist, PKG / "frontend" / "dist")
    shutil.copytree(ROOT / "docs", PKG / "docs")

    (PKG / "Iniciar.bat").write_bytes(crlf(INICIAR_BAT))
    (PKG / "Procurar-robo.bat").write_bytes(crlf(DIAG_BAT))
    (PKG / "LEIA-ME.txt").write_bytes(crlf(LEIA_ME))

    zip_path = OUT / "Xiaomi1C-portatil.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(PKG.rglob("*")):
            zf.write(f, f.relative_to(OUT))
    print(f"Pasta: {PKG}\nZip:   {zip_path} ({zip_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
