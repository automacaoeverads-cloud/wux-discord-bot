# DDR — RPG de mesa narrado por IA no Discord

Bot que mestra um RPG de **fantasia medieval** direto no Discord. Os jogadores
**conversam livremente no canal da mesa** como seus personagens; quando querem a
resposta do Mestre, alguém usa `/narrar` — o bot lê tudo que foi dito desde a
última narração, separa por personagem, decide os testes, rola os dados e narra.
Fichas ficam num canal próprio, atualizadas automaticamente.

Usa múltiplos agentes de IA via [OpenRouter](https://openrouter.ai), coordenados
por código determinístico para evitar alucinações.

## O fluxo de jogo

```
/iniciar  ──► cria a categoria 🎲 com #🎭-mesa e #📜-fichas
/criar_ficha ──► ficha publicada em #📜-fichas
/cena     ──► o Narrador abre a cena em #🎭-mesa

jogadores digitam à vontade em #🎭-mesa (RP livre)
  · mensagens com //, ( ou [ no início = fora do jogo (ignoradas)

/narrar   ──► o bot coleta o que cada personagem disse/fez e responde
```

## Arquitetura anti-alucinação

```
/narrar
      │  código coleta o chat desde a última narração e separa por personagem
      ▼
┌─────────────────── ORQUESTRADOR (código, não IA) ───────────────────┐
│                                                                     │
│  1. ÁRBITRO ─────────── decide QUEM rola dado, atributo e CD (JSON) │
│  2. CÓDIGO ──────────── rola os d20; resultados viram fatos         │
│  3. NARRADOR ────────── escreve a prosa a partir dos fatos          │
│  4. ESCRIBA ─────────── extrai deltas de ficha por personagem       │
│  5. CÓDIGO ──────────── aplica deltas no SQLite com limites         │
│  6. CRONISTA ────────── compacta o histórico quando cresce          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
      │
      ▼
Narração + testes + fichas atualizadas
```

Princípios:
- **SQLite é a fonte única da verdade** — a IA nunca "lembra" estado, sempre recebe do banco.
- **Dados rolados por código** — a IA nunca decide o resultado de um teste.
- **Cada agente faz uma coisa só** e retorna JSON validado com defaults seguros.
- **Narrador recebe os resultados como fatos** e não pode contradizê-los.
- **O Mestre nunca controla os PJs** e **NPCs não são oniscientes** (ver abaixo).

## Convenções de escrita na mesa

O `parsing.py` separa cada mensagem antes de qualquer IA ver:

| Você escreve | É lido como | Quem percebe |
|---|---|---|
| `**abro a porta**` | **AÇÃO** | NPCs **veem** |
| `-- Tem alguém aí?` | **FALA** | NPCs **ouvem** (só quem está perto) |
| `"não confio nele"` | **PENSAMENTO** | **ninguém** — é privado |

Texto sem marcação = ação.

**Por que isso importa:** o pensamento nunca chega aos NPCs *nem entra no histórico
da campanha* — um NPC não pode "lembrar" de algo que ninguém disse. O Narrador é
instruído a nunca escrever ações/falas/emoções dos PJs, e a só deixar um NPC saber
o que ele viu ou ouviu.

Modelos padrão (troque via env, sem mexer no código):

| Env | Agentes | Padrão | Por quê |
|---|---|---|---|
| `MODEL_NARRATOR` | Narrador | `deepseek/deepseek-v4-pro` | escreve a prosa da mesa — vale o modelo bom |
| `MODEL_UTILITY` | Árbitro, Escriba, Cronista | `deepseek/deepseek-v4-flash` | só JSON estruturado e resumos — rápido e barato |

> **Nota sobre modelos de raciocínio.** Modelos que "pensam" antes de responder
> (ex.: `tencent/hy3`) gastam o orçamento de tokens no raciocínio e devolvem
> conteúdo vazio (`finish_reason=length`). O `llm.py` já soma um colchão
> (`REASONING_HEADROOM`, padrão 3000) e dobra o orçamento ao detectar isso — mas
> se um modelo desses continuar falhando, prefira um modelo não-raciocinante.

## Sistema de regras

- Cenário: fantasia medieval clássica
- 4 atributos: **Força, Agilidade, Mente, Presença** (-1 a +3 na criação, soma máx. 5)
- **Raça** dá +1 num atributo (pode chegar a +4); **classe** define HP e MP
- Teste: **d20 + atributo vs CD** (fácil 10, médio 14, difícil 18)
- 20 natural = crítico, 1 natural = desastre
- **HP** = 10 + 2×Força + bônus de raça/classe + 2 por nível
- **MP** = base da classe + Mente + bônus de raça + 1 por nível

**Raças:** Humano, Elfo, Anão, Halfling, Orc, Gnomo, Tiefling
**Classes:** Guerreiro, Ladino, Mago, Clérigo, Patrulheiro, Bardo — cada uma com
**habilidades nos níveis 1, 3 e 5** (árvore em `rules.py`)

### XP e níveis

Tabela progressiva (XP **total** acumulado): N2 100 · N3 250 · N4 450 · N5 700 ·
N6 1000 · N7 1400 · N8 1900 · N9 2500 · N10 3200.

Ao fim de um **combate vencido** ou **missão concluída**, o agente Tesoureiro detecta
o marco e posta uma **sugestão de XP** no canal `💬-off-topic` (escaramuça 20-30,
combate sério 40-60, chefe 70-100...). **Quem concede é o mestre humano**, com
`/xp jogador quantidade` — a IA nunca altera XP sozinha.

*(tudo definido em `rules.py` — o bot publica as tabelas completas no canal `📖-regras`)*

## Comandos

| Comando | O que faz |
|---|---|
| `/iniciar [nome]` | **Cria a mesa inteira**: categoria + `📖-regras`, `🎭-mesa`, `📜-fichas`, `💬-off-topic` (precisa de Gerenciar Canais) |
| `/criar_ficha` | Cria seu personagem (nome, raça, classe, atributos) |
| `/ficha` | Mostra sua ficha (privado) |
| `/apagar_ficha` | Apaga seu personagem |
| `/cena descricao` | Abre uma nova cena |
| `/narrar` | O Mestre lê a mesa desde a última narração e responde |
| `/xp jogador quantidade` | Concede XP (mestre da mesa) |
| `/historia` | Resumo da campanha até aqui |

O `/iniciar` publica automaticamente no `📖-regras` o livro da mesa: sistema, raças,
classes, as convenções de escrita e o que o Mestre pode/não pode fazer.

## Permissões necessárias do bot

- **Gerenciar Canais** (para o `/iniciar` criar a categoria e os canais)
- Ver Canal, Enviar Mensagens, Inserir Links (embeds), **Ler Histórico de Mensagens**
- **Message Content Intent** ligada no Developer Portal (para ler o chat da mesa)

## Rodando local

```bash
cp .env.example .env   # preencha DISCORD_TOKEN e OPENROUTER_API_KEY
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Deploy

Veja [DEPLOY-EASYPANEL.md](DEPLOY-EASYPANEL.md).
