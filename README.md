# 🎲 Bot de Rolagem — WUX: A Senda dos Mil Reinos

Bot de Discord que rola pools de d6 com as regras do WUX:

> **5–6 = Êxito ✦** · **6 explode** (rola outro, em cadeia) · **1 = Dissonância**

Ele faz as explosões sozinho e devolve **êxitos** e **dissonâncias** automaticamente.

---

## Comandos

**Barra (recomendado — não exige intent privilegiada):**

| Comando | Faz |
|---|---|
| `/rolar dados:8` | rola 8d6 |
| `/rolar dados:8 modificador:2` | 8 +2 = 10d6 (postura, etc.) |
| `/rolar dados:8 exitos_bonus:1` | soma **+1 êxito automático** (Supressão de Reino) |
| `/rolar dados:8 dificuldade:3` | mostra **passou/falhou** e **margem** |
| `/rolar dados:8 volatil:true` | ação Volátil — **destaca as Dissonâncias** |
| `/rolar dados:8 rotulo:"Golpe do Arado"` | nomeia a rolagem |

**Prefixo (aceita expressões):**

| Comando | Faz |
|---|---|
| `!r 8` | rola 8d6 |
| `!r 8+2 Golpe do Arado` | 8 **+2 dados** = 10d6, com rótulo |
| `!r 8+2-1` | soma e subtrai dados |
| `!r 8+1e` | rola 8d6 e soma **+1 êxito automático** ao resultado |
| `!rv 8 Técnica volátil` | rolagem de ação **Volátil** |
| `!ajuda` | resumo dos comandos |

> O `!r`/`!rv` precisa da **Message Content Intent** ligada (passo 3). O `/rolar` não precisa.

---

## Instalação (uma vez)

```bash
cd "discord-bot"
python3 -m pip install --user -r requirements.txt
```

### 1. Criar o app e o bot
1. Vá ao [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Aba **Bot** → **Reset Token** → copie o token.
3. Cole no arquivo `.env` (copie de `.env.example`):
   ```
   DISCORD_TOKEN=seu_token_aqui
   ```

> ⚠️ **Segurança:** nunca compartilhe o token. Se ele vazar, clique em **Reset Token** — o antigo morre na hora.

### 2. Convidar o bot para o servidor
Aba **OAuth2 → URL Generator**:
- **Scopes:** marque `bot` **e** `applications.commands`
- **Bot Permissions:** `Send Messages`, `Embed Links`, `Read Message History`
- Abra a URL gerada e escolha o servidor.

### 3. (Só para `!r`/`!rv`) ligar a intent
Aba **Bot** → **Privileged Gateway Intents** → ligue **Message Content Intent**.
(Se você só usar `/rolar`, pode deixar desligada — mas o código pede essa intent; veja a nota abaixo.)

---

## Rodar

```bash
cd "discord-bot"
python3 bot.py
```

Quando aparecer `✓ Logado como ...`, está no ar. Os comandos de barra podem levar **alguns minutos** para aparecer na primeira sincronização global.

> **Se você NÃO quiser ligar a Message Content Intent:** abra `bot.py` e troque
> `intents.message_content = True` por `False`. Aí só os comandos `/rolar` funcionam (os `!r` deixam de ler o texto).

---

## Estrutura

| Arquivo | O quê |
|---|---|
| `dados.py` | motor de rolagem puro (regras WUX) — testável sem Discord |
| `bot.py` | o bot (comandos, embeds) |
| `test_dados.py` | testes do motor (`python3 test_dados.py`) |
| `.env` | seu token (não versionar) |
| `requirements.txt` | dependências |

---

## Manter rodando (opcional)

No Mac, a forma simples é deixar o terminal aberto com `python3 bot.py`. Para rodar
de fundo:

```bash
nohup python3 bot.py > bot.log 2>&1 &
```

Para parar: `pkill -f bot.py`.
