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

Modelo padrão de todos os agentes: `deepseek/deepseek-v4-pro` (troque via env
`MODEL_NARRATOR` / `MODEL_UTILITY`).

> **Nota sobre modelos de raciocínio.** Modelos que "pensam" antes de responder
> (ex.: `tencent/hy3`) gastam o orçamento de tokens no raciocínio e devolvem
> conteúdo vazio (`finish_reason=length`). O `llm.py` já soma um colchão
> (`REASONING_HEADROOM`, padrão 3000) e dobra o orçamento ao detectar isso — mas
> se um modelo desses continuar falhando, prefira um modelo não-raciocinante.

## Sistema de regras

- Cenário: fantasia medieval clássica
- 4 atributos: **Força, Agilidade, Mente, Presença** (-1 a +3, soma máx. 5)
- Teste: **d20 + atributo vs CD** (fácil 10, médio 14, difícil 18)
- 20 natural = crítico, 1 natural = desastre
- HP = 10 + 2×Força

## Comandos

| Comando | O que faz |
|---|---|
| `/iniciar [nome]` | **Cria a mesa inteira**: categoria + canais (precisa de Gerenciar Canais) |
| `/criar_ficha` | Cria seu personagem |
| `/ficha` | Mostra sua ficha (privado) |
| `/apagar_ficha` | Apaga seu personagem |
| `/cena descricao` | Abre uma nova cena |
| `/narrar` | O Mestre lê a mesa desde a última narração e responde |
| `/historia` | Resumo da campanha até aqui |

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
