# Deploy no EasyPanel

## 1. Suba o código no GitHub

```bash
git init
git add .
git commit -m "DDR RPG bot"
git remote add origin https://github.com/SEU_USUARIO/ddr-rpg-bot.git
git push -u origin main
```

O `.gitignore` já impede que o `.env` (com seus tokens) suba para o repositório.

## 2. Crie o app no EasyPanel

1. **Create Service → App**
2. **Source**: GitHub → selecione o repositório e a branch `main`
3. **Build**: Dockerfile (ele detecta o `Dockerfile` na raiz)
4. **Environment** — adicione as variáveis:
   - `DISCORD_TOKEN` = token do bot (Discord Developer Portal)
   - `OPENROUTER_API_KEY` = chave do OpenRouter
5. **Mounts / Volumes**: monte um volume em `/app/data`
   (é onde fica o `ddr.db` — sem isso o estado do jogo se perde a cada deploy)
6. **Não exponha porta nenhuma** — o bot só faz conexões de saída.
7. Deploy!

## 3. Convide o bot para o servidor

No Discord Developer Portal → OAuth2 → URL Generator:
- Scopes: `bot`, `applications.commands`
- Permissões: `Send Messages`, `Embed Links`, `Read Message History`

Abra a URL gerada e adicione o bot ao seu servidor.

## 4. Primeiro uso

1. Crie dois canais: `#mesa` e `#fichas`
2. `/iniciar mesa:#mesa fichas:#fichas`
3. Cada jogador: `/criar_ficha`
4. `/cena` para abrir a primeira cena — e boa aventura! 🎲

## Atualizações

Todo `git push` na branch `main` pode disparar rebuild automático
(ative o auto-deploy no EasyPanel). O volume em `/app/data` preserva
campanhas, fichas e histórico entre deploys.
