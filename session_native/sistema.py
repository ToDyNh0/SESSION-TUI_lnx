"""Tudo o que depende do sistema operacional -- versao LINUX.

A versao Windows deste arquivo tem as mesmas funcoes com o mesmo contrato; o
resto do projeto e identico nas duas pastas.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .i18n import t

NOME = "linux"
APP = "session-tui"


def pasta_perfil_padrao() -> Path:
    """$XDG_DATA_HOME/session-tui/profile (normalmente ~/.local/share/...)."""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP / "profile"


def preparar_pasta_privada(pasta: Path) -> None:
    """Pasta 700: historico, anexos e estado nao ficam legiveis por outros usuarios.

    Os arquivos la dentro nascem com o umask (644 em geral), mas sem permissao
    de entrar na pasta ninguem chega neles.
    """
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        if pasta.stat().st_uid == os.getuid():
            os.chmod(pasta, 0o700)
    except OSError:
        pass


def restringir_arquivo(caminho) -> bool:
    try:
        os.chmod(caminho, 0o600)
        return True
    except OSError:
        return False


def abrir_no_sistema(caminho) -> None:
    """Abre no programa padrao (xdg-open), sem deixar ele escrever na TUI."""
    if not shutil.which("xdg-open"):
        raise FileNotFoundError(t("xdg-open not found: install xdg-utils to open files"))
    subprocess.Popen(
        ["xdg-open", str(caminho)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # fechar a TUI nao fecha o visualizador
    )


def copiar_texto(texto: str) -> bool:
    """Copia com wl-copy (Wayland), xclip ou xsel (X11) -- o que existir.

    A saida vai para /dev/null de proposito: xclip e wl-copy ficam rodando em
    segundo plano para "segurar" a selecao, e um pipe aberto travaria aqui.
    """
    candidatos = []
    if os.environ.get("WAYLAND_DISPLAY"):
        candidatos.append(["wl-copy"])
    if os.environ.get("DISPLAY"):
        candidatos += [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for comando in candidatos:
        if not shutil.which(comando[0]):
            continue
        try:
            resultado = subprocess.run(
                comando,
                input=texto.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
            if resultado.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def desescapar_caminho(texto: str) -> str:
    r"""GNOME Terminal, kitty e outros soltam `minha\ foto.png` ao arrastar."""
    return re.sub(r"\\(.)", r"\1", texto)


def dica_area_de_transferencia(erro: str) -> str:
    if "xclip" in erro or "wl-paste" in erro:
        return t("install wl-clipboard (Wayland) or xclip (X11) to paste images -- {error}", error=erro)
    return erro


def configurar_saida() -> None:
    """Nunca morrer por um emoji num terminal com locale estranho."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


# --- verificacao automatica do kill switch (systemd --user ou crontab) ------


def _nome(perfil) -> str:
    chave = str(Path(perfil).resolve()).encode("utf-8")
    return f"{APP}-killswitch-{hashlib.sha1(chave).hexdigest()[:10]}"


def comando_verificacao(perfil) -> list[str]:
    perfil = str(Path(perfil).resolve())
    argumentos = ["killswitch", "check", "--profile", perfil]
    if getattr(sys, "frozen", False):  # executavel do PyInstaller
        return [sys.executable, *argumentos]
    principal = Path(__file__).resolve().parent.parent / "main.py"
    return [sys.executable, str(principal), *argumentos]


def _pasta_systemd() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "systemd" / "user"


def _systemd_disponivel() -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        return (
            subprocess.run(
                ["systemctl", "--user", "show-environment"],
                capture_output=True,
                timeout=10,
                check=False,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def _systemctl(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *argumentos],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )


def _aspas_systemd(argumento: str) -> str:
    """Um argumento de ExecStart= entre aspas, com % e $ escapados."""
    escapado = argumento.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escapado.replace("%", "%%").replace("$", "$$") + '"'


def _ler_crontab() -> list[str] | None:
    """Linhas do crontab do usuario; None se nao houver crontab no sistema."""
    if not shutil.which("crontab"):
        return None
    try:
        resultado = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, errors="replace", timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # sem crontab ainda: "no crontab for <usuario>" e codigo 1
    return resultado.stdout.splitlines() if resultado.returncode == 0 else []


def _gravar_crontab(linhas: list[str]) -> None:
    texto = "\n".join(linhas) + "\n" if linhas else ""
    resultado = subprocess.run(
        ["crontab", "-"], input=texto, capture_output=True, text=True, timeout=10, check=False
    )
    if resultado.returncode != 0:
        raise RuntimeError(t("could not update the crontab: {error}", error=resultado.stderr.strip()))


def instalar_agendamento(perfil) -> str:
    """Timer de usuario do systemd; sem ele, uma linha no crontab.

    Levanta RuntimeError explicando o que agendar quando nao ha nenhum dos dois
    (container, WSL sem systemd...).
    """
    nome = _nome(perfil)
    comando = comando_verificacao(perfil)

    if _systemd_disponivel():
        pasta = _pasta_systemd()
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{nome}.service").write_text(
            "[Unit]\n"
            "Description=Session TUI kill switch check\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"ExecStart={' '.join(_aspas_systemd(a) for a in comando)}\n",
            encoding="utf-8",
        )
        (pasta / f"{nome}.timer").write_text(
            "[Unit]\n"
            "Description=Session TUI kill switch check, every hour\n\n"
            "[Timer]\n"
            "OnCalendar=hourly\n"
            "Persistent=true\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n",
            encoding="utf-8",
        )
        _systemctl("daemon-reload")
        resultado = _systemctl("enable", "--now", f"{nome}.timer")
        if resultado.returncode != 0:
            raise RuntimeError(
                t("could not create the systemd timer: {error}", error=resultado.stderr.strip())
            )
        return t(
            "systemd user timer '{name}', every hour (to run while you are logged out: loginctl enable-linger)",
            name=nome,
        )

    linhas = _ler_crontab()
    if linhas is not None:
        # % e especial no crontab (vira quebra de linha): precisa de \%
        linha_cron = shlex.join(comando).replace("%", "\\%")
        linhas = [linha for linha in linhas if nome not in linha]
        linhas.append(f"0 * * * * {linha_cron} >/dev/null 2>&1 # {nome}")
        _gravar_crontab(linhas)
        return t("crontab entry '{name}', every hour", name=nome)

    raise RuntimeError(
        t(
            "no systemd user session or crontab found; add this to your scheduler to run every hour: {cmd}",
            cmd=shlex.join(comando),
        )
    )


def remover_agendamento(perfil) -> bool:
    nome = _nome(perfil)
    removido = False
    pasta = _pasta_systemd()
    timer = pasta / f"{nome}.timer"
    if timer.exists():
        if shutil.which("systemctl"):
            _systemctl("disable", "--now", f"{nome}.timer")
        for sufixo in (".timer", ".service"):
            (pasta / f"{nome}{sufixo}").unlink(missing_ok=True)
        if shutil.which("systemctl"):
            _systemctl("daemon-reload")
        removido = True
    linhas = _ler_crontab()
    if linhas and any(nome in linha for linha in linhas):
        try:
            _gravar_crontab([linha for linha in linhas if nome not in linha])
            removido = True
        except RuntimeError:
            pass
    return removido


def agendamento_instalado(perfil) -> bool:
    nome = _nome(perfil)
    if (_pasta_systemd() / f"{nome}.timer").exists():
        return True
    linhas = _ler_crontab()
    return bool(linhas and any(nome in linha for linha in linhas))
