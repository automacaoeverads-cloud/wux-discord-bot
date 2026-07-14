# DDR — RPG de mesa narrado por IA no Discord

Bot que mestra RPG de mesa em um canal do Discord, com fichas atualizadas
automaticamente em outro canal. Usa múltiplos agentes de IA via
[OpenRouter](https://openrouter.ai), coordenados por código determinístico
para evitar alucinações.

## Arquitetura anti-alucinação

```
Jogador usa /acao
      │
      ▼
┌─────────────────── ORQUESTRADOR (código, não IA) ───────────────────┐
│                                                                     │
│  1. ÁRBITRO (qwen) ─── decide SE rola dado, atributo e CD (JSON)    │
│  2. CÓDIGO ──────────── rola o d20; resultado vira fato imutável    │
│  3. NARRADOR (deepseek) escreve a prosa a partir do fato            │
│  4. ESCRIBA (qwen) ──── extrai deltas de ficha (JSON validado)      │
│  5. CÓDIGO ──────────── aplica deltas no SQLite com limites         │
│  6. CRONISTA (qwen) ─── compacta o histórico quando cresce          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
      │
      ▼
Narração no canal da mesa + ficha atualizada no canal de fichas
```

Princípios:
- **SQLite é a fonte única da verdade** — a IA nunca "lembra" estado, sempre recebe do banco.
- **Dados rolados por código** — a IA nunca decide o resultado de um teste.
- **Cada agente faz uma coisa só** e retorna JSON validado com defaults seguros.
- **Narrador recebe o resultado como fato** e não pode contradizê-lo.

## Sistema de regras

- 4 atributos: **Força, Agilidade, Mente, Presença** (-1 a +3, soma máx. 5)
- Teste: **d20 + atributo vs CD** (fácil 10, médio 14, difícil 18)
- 20 natural = crítico, 1 natural = desastre
- HP = 10 + 2×Força

## Comandos

| Comando | O que faz |
|---|---|
| `/iniciar mesa fichas` | Configura os canais da campanha |
| `/criar_ficha` | Cria seu personagem |
| `/ficha` | Mostra sua ficha (privado) |
| `/apagar_ficha` | Apaga seu personagem |
| `/cena descricao` | Abre uma nova cena |
| `/acao descricao` | Declara o que seu personagem faz |
| `/historia` | Resumo da campanha até aqui |

## Rodando local

```bash
cp .env.example .env   # preencha DISCORD_TOKEN e OPENROUTER_API_KEY
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Deploy

Veja [DEPLOY-EASYPANEL.md](DEPLOY-EASYPANEL.md).
