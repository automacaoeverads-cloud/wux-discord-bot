from __future__ import annotations

"""Parser das convenções de mesa.

    -- fala          → o personagem FALA em voz alta (NPCs podem ouvir)
    **ação**         → o personagem AGE (NPCs podem ver)
    "pensamento"     → o personagem PENSA (PRIVADO — ninguém ouve, nem o Mestre reage)

Texto sem marcação nenhuma é tratado como AÇÃO (o caso mais comum).

Essa separação é o que impede a onipotência narrativa: o pensamento nunca
chega aos NPCs, e a fala só chega a quem estava presente.
"""

import re

FALA = "fala"
ACAO = "acao"
PENSAMENTO = "pensamento"

LABELS = {
    FALA: "FALA (em voz alta)",
    ACAO: "AÇÃO",
    PENSAMENTO: "PENSAMENTO — PRIVADO, ninguém ouve",
}

# Linha de fala: começa com --, ---, — (travessão) ou –
_SPEECH_LINE = re.compile(r"^\s*(?:-{2,}|[—–])\s*(.+)$")

# Dentro de uma linha: **ação** ou "pensamento" / “pensamento”
_TOKEN = re.compile(r"\*\*(?P<acao>.+?)\*\*|[\"“](?P<pensamento>[^\"”]+)[\"”]")


def parse_rp(text: str) -> list[tuple[str, str]]:
    """Quebra a mensagem em segmentos [(tipo, conteúdo), ...] na ordem em que aparecem."""
    segments: list[tuple[str, str]] = []

    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue

        speech = _SPEECH_LINE.match(line)
        if speech:
            content = speech.group(1).strip()
            if content:
                segments.append((FALA, content))
            continue

        cursor = 0
        for match in _TOKEN.finditer(line):
            plain = line[cursor:match.start()].strip()
            if plain:
                segments.append((ACAO, plain))
            if match.group("acao"):
                segments.append((ACAO, match.group("acao").strip()))
            else:
                segments.append((PENSAMENTO, match.group("pensamento").strip()))
            cursor = match.end()

        tail = line[cursor:].strip()
        if tail:
            segments.append((ACAO, tail))

    return [(kind, content) for kind, content in segments if content]


def format_for_agents(entries: list[tuple[str, str, list[tuple[str, str]]]]) -> str:
    """Monta o roteiro que vai para o Árbitro e o Narrador.

    `entries` = [(nome_do_personagem, descrição_curta, segmentos), ...]
    """
    blocks: list[str] = []
    for name, brief, segments in entries:
        lines = [f"{name} ({brief}):"]
        for kind, content in segments:
            lines.append(f"  [{LABELS[kind]}] {content}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def has_public_content(segments: list[tuple[str, str]]) -> bool:
    """True se houve algo que o mundo pode perceber (fala ou ação)."""
    return any(kind != PENSAMENTO for kind, _ in segments)
