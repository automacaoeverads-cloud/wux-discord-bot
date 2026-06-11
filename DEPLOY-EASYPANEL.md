# 🚀 Deploy no EasyPanel (VPS)

O bot é um **worker** (não expõe porta HTTP) — roda 24/7 num container, buildado a
partir do `Dockerfile`. O token fica nas **variáveis de ambiente do EasyPanel**, nunca
no código.

---

## Pré-requisito: o código num repositório Git

O EasyPanel faz deploy a partir de um repo (GitHub/GitLab ou URL Git pública).
A pasta `discord-bot/` já tem tudo (`Dockerfile`, `.dockerignore`, `requirements.txt`).
O `.env` **não** vai junto (está no `.gitignore`/`.dockerignore`).

---

## Passo a passo no EasyPanel

1. **Projeto** → abra (ou crie) o projeto onde fica o seu n8n etc.
2. **+ Service → App**.
3. **Source:**
   - **GitHub** (conecte a conta e escolha o repo + branch `main`), **ou**
   - **Git** e cole a URL pública do repositório.
4. **Build:** selecione **Dockerfile** (caminho: `Dockerfile`).
   - Se a pasta do bot **não** for a raiz do repo, ajuste o **Build Context / Root** para `discord-bot`.
5. **Environment** (aba de variáveis): adicione
   ```
   DISCORD_TOKEN = (o seu token NOVO, do Reset Token)
   ```
6. **Domains / Ports:** deixe **vazio** — é um worker, não tem porta web.
7. **Deploy.**

Acompanhe a aba **Logs**. Quando aparecer:
```
✓ 1 comando(s) de barra sincronizado(s).
✓ Logado como ArtosBot#8859 ...
  Pronto para rolar os dados dos Mil Reinos.
```
está no ar 24/7. 🎲

---

## Convidar o bot pro servidor (uma vez)

https://discord.com/api/oauth2/authorize?client_id=1284997110759952468&permissions=83968&scope=bot%20applications.commands

Scopes `bot` + `applications.commands`; permissões: Enviar Mensagens, Embed Links,
Ler Histórico.

---

## Importante

- **Um bot, uma instância.** Rodar o mesmo token em dois lugares ao mesmo tempo (ex.: na
  sua máquina **e** no EasyPanel) causa respostas duplicadas/conflito de sessão. Deixe só
  o do EasyPanel ligado.
- **Token novo.** O token antigo foi exposto em chat — gere um novo (Developer Portal →
  Bot → **Reset Token**) e use **esse** no EasyPanel.
- **Atualizar o bot depois:** com GitHub, basta dar `git push` na branch — o EasyPanel
  pode rebuildar automático (ative *Auto Deploy*) ou clique em **Deploy** no painel.
- **Recursos:** o container é leve (~80–120 MB de RAM). Qualquer plano serve.
```
