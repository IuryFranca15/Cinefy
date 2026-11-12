# Cinefy — sua filmografia tem trilha sonora

Aplicação pessoal em **Python + Streamlit** que cruza o histórico do Letterboxd com o perfil musical do Spotify e enriquece os filmes com dados do TMDB. A interface segue uma estética Frutiger Aero: vidro translúcido, gradientes azul/ciano/verde, reflexos especulares e ícones 3D.

- **Mood Mirror:** compara o humor da sua música com os gêneros dos filmes que você assiste.
- **Director's Cut:** cria no Spotify uma playlist privada com a atmosfera de um filme.
- **Recomendação inversa:** sugere filmes da sua watchlist a partir do que você escuta.

> As comparações entre música e cinema são heurísticas recreativas, não avaliações objetivas.

## Sumário

1. [Requisitos](#1-requisitos)
2. [Instalação](#2-instalação)
3. [Conectar o Spotify](#3-conectar-o-spotify)
4. [Conectar o TMDB](#4-conectar-o-tmdb)
5. [Configurar credenciais (`secrets.toml` ou variáveis de ambiente)](#5-configurar-credenciais)
6. [Exportar seus dados do Letterboxd](#6-exportar-seus-dados-do-letterboxd)
7. [Usar o Cinefy](#7-usar-o-cinefy)
8. [Banco de dados e backup](#8-banco-de-dados-e-backup)
9. [Auditoria e testes](#9-auditoria-e-testes)
10. [Estrutura de pastas](#10-estrutura-de-pastas)
11. [Publicar (opcional)](#11-publicar-opcional)
12. [Limitações conhecidas](#12-limitações-conhecidas)

## 1. Requisitos

- Windows 10/11, macOS ou Linux.
- Python **3.11 ou superior**.
- Conta no Spotify e um aplicativo criado no [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
- Conta no Letterboxd (a exportação de dados é gratuita).
- Conta no [TMDB](https://www.themoviedb.org/) para obter o token de leitura da API.

## 2. Instalação

### macOS / Linux

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
mkdir -p .streamlit
test -f .streamlit/secrets.toml || cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .streamlit\secrets.toml)) { Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml }
.\.venv\Scripts\python.exe -m streamlit run app.py
```

No Windows também dá para dar dois cliques em `run_windows.bat`, que cria o ambiente virtual na primeira vez e abre o app. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` antes.

**Abra o app em `http://127.0.0.1:8501`** (não em `localhost`). Esse é o endereço que você vai cadastrar no Spotify; usar o mesmo nos dois lados evita erros de redirecionamento. Para encerrar, pressione `Ctrl + C` no terminal.

> O `secrets.toml` ainda está com valores de exemplo logo após a cópia. Preencha-o nas próximas seções antes de usar as integrações.

## 3. Conectar o Spotify

O Cinefy usa o OAuth 2.0 do Spotify para ler seus **Top Tracks** e **Top Artists** e para criar playlists privadas.

1. Entre em <https://developer.spotify.com/dashboard> com sua conta Spotify e clique em **Create app**.
2. Preencha **App name** e **App description** (qualquer texto, por exemplo "Cinefy pessoal").
3. Em **Redirect URIs**, adicione exatamente:

   ```text
   http://127.0.0.1:8501
   ```

   O Spotify **não aceita mais `localhost`**. Em HTTP, só valem endereços de loopback como `127.0.0.1` ou `[::1]`; qualquer outro endereço precisa de HTTPS. O valor tem de ser idêntico ao `redirect_uri` do `secrets.toml`, inclusive porta e ausência de barra final.
4. Em **Which API/SDKs are you planning to use?**, marque **Web API**, aceite os termos e clique em **Save**.
5. Abra **Settings** do aplicativo e copie o **Client ID**. Clique em **View client secret** e copie o **Client Secret**.
6. Se o aplicativo estiver em *Development Mode*, abra **User Management** e adicione o nome e o e-mail da conta Spotify que vai usar o Cinefy. Só usuários cadastrados conseguem autorizar o app.
7. Cole os valores no `secrets.toml` (veja a [seção 5](#5-configurar-credenciais)).
8. Inicie o Cinefy, abra a aba **Spotify**, clique em **Conectar minha conta Spotify**, autorize e depois use **Sincronizar meu perfil musical**.

Permissões solicitadas:

| Escopo | Para quê |
| --- | --- |
| `user-top-read` | Ler Top Artists e Top Tracks. |
| `playlist-modify-private` | Criar playlists privadas no Director's Cut. |

### Atenção: métricas de áudio

O Spotify **descontinuou o endpoint `audio-features`** para aplicativos criados depois de 27/11/2024. Nesses aplicativos, energia, valência, dançabilidade e andamento **não estão disponíveis** e a API responde 403.

O que acontece no Cinefy:

- A sincronização continua funcionando (faixas, artistas e gêneros).
- O app avisa que as métricas não foram liberadas e **não inventa valores**.
- O Mood Mirror e a compatibilidade por humor mostram "indisponível"; o ranking do Director's Cut mantém a ordem original das faixas.
- A recomendação inversa ainda funciona pelos **gêneros dos artistas**.

As regras do Spotify mudam com frequência (limites de usuários, exigência de Premium no Development Mode, recursos descontinuados). Confira as condições atuais no painel e na [documentação oficial](https://developer.spotify.com/documentation/web-api).

## 4. Conectar o TMDB

O CSV do Letterboxd não traz gêneros, diretores, sinopses nem pôsteres. O Cinefy busca esses dados no TMDB.

1. Crie uma conta em <https://www.themoviedb.org/> e confirme o e-mail.
2. Acesse **Configurações → API** (<https://www.themoviedb.org/settings/api>) e solicite uma chave para uso pessoal.
3. Copie o **API Read Access Token**. É o token longo (começa com `eyJ…`), **não** a "API Key" curta.
4. Cole no `secrets.toml`, na seção `[tmdb]`, campo `bearer_token`.

Se preferir a chave curta, preencha `api_key` e deixe `bearer_token` vazio. O token é recomendado.

**Crédito TMDB:** este produto utiliza a API do TMDB, mas não é endossado nem certificado pelo TMDB. Dados e imagens cinematográficas fornecidos por TMDB. Consulte os [termos de uso](https://www.themoviedb.org/documentation/api/terms-of-use).

## 5. Configurar credenciais

O Cinefy lê as credenciais do `st.secrets` (arquivo `.streamlit/secrets.toml`) e, se um valor faltar, de variáveis de ambiente.

### Opção A: `.streamlit/secrets.toml` (recomendada)

```toml
[spotify]
client_id = "SEU_CLIENT_ID"
client_secret = "SEU_CLIENT_SECRET"
redirect_uri = "http://127.0.0.1:8501"

[tmdb]
bearer_token = "SEU_API_READ_ACCESS_TOKEN"
api_key = ""                # opcional; use só se não tiver o bearer_token

[database]
url = ""                    # vazio = SQLite local (cinefy.db)

[app]
password = ""               # opcional; protege o acesso casual ao app
```

O arquivo fica em `.streamlit/secrets.toml`, dentro da pasta do projeto, ao lado de `config.toml`. Ele já está no `.gitignore`.

### Opção B: variáveis de ambiente

| Variável | Equivale a |
| --- | --- |
| `SPOTIFY_CLIENT_ID` | `[spotify] client_id` |
| `SPOTIFY_CLIENT_SECRET` | `[spotify] client_secret` |
| `SPOTIFY_REDIRECT_URI` | `[spotify] redirect_uri` (padrão `http://127.0.0.1:8501`) |
| `TMDB_BEARER_TOKEN` | `[tmdb] bearer_token` |
| `TMDB_API_KEY` | `[tmdb] api_key` |
| `DATABASE_URL` | `[database] url` |
| `CINEFY_APP_PASSWORD` | `[app] password` |

```bash
export SPOTIFY_CLIENT_ID="..."
export SPOTIFY_CLIENT_SECRET="..."
export TMDB_BEARER_TOKEN="..."
streamlit run app.py
```

```powershell
$env:SPOTIFY_CLIENT_ID = "..."
$env:SPOTIFY_CLIENT_SECRET = "..."
$env:TMDB_BEARER_TOKEN = "..."
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Segurança das credenciais

- **Nunca** envie `secrets.toml`, `.env` ou `cinefy.db` ao GitHub. Os três estão no `.gitignore`.
- Se uma credencial já foi publicada, considere-a comprometida: gere um novo Client Secret no painel do Spotify e um novo token no TMDB, e atualize o `secrets.toml`.
- O `[app] password` é só uma barreira simples contra acesso casual. Não é um sistema de autenticação multiusuário.

## 6. Exportar seus dados do Letterboxd

O Cinefy **não faz scraping** nem usa API privada do Letterboxd. Ele importa os CSVs que o próprio Letterboxd exporta.

1. Entre em <https://letterboxd.com> pelo navegador (no computador).
2. Abra **Settings** (Configurações) → aba **Import & Export** → **Export Your Data**.
3. O Letterboxd gera e baixa um arquivo **ZIP** com seus dados.
4. **Extraia o ZIP**. Dentro dele, os arquivos usados pelo Cinefy são:

   | Arquivo | O que contém | O que o Cinefy aproveita |
   | --- | --- | --- |
   | `diary.csv` | Filmes registrados no diário | Data assistida (`Watched Date`), nota, *rewatch* e tags |
   | `ratings.csv` | Todas as suas notas | Nota (`Rating`); prevalece sobre a nota do diário |
   | `watchlist.csv` | Filmes que você quer ver | Marca o filme como "na watchlist" |

   Todos têm as colunas `Name` e `Year`, além de `Letterboxd URI`, usada como identificador único do filme. Os demais arquivos do ZIP (`watched.csv`, `reviews.csv`, `lists/` etc.) não são lidos.
5. No Cinefy, abra a aba **Letterboxd**, selecione os CSVs disponíveis e clique em **Importar histórico**.

Dicas:

- Você pode selecionar os três arquivos de uma vez, **em qualquer ordem**; o resultado é o mesmo.
- Não precisa ter os três. Só o `watchlist.csv` já habilita a Recomendação inversa, e só o `diary.csv` já alimenta o Mood Mirror (ambos dependem dos gêneros, que vêm do enriquecimento com o TMDB).
- Importar de novo é seguro: filmes existentes são atualizados sem apagar gêneros, diretores nem pôsteres já obtidos.
- Um filme que está só em `watched.csv` (assistido sem nota nem diário) **não** entra no Cinefy.

## 7. Usar o Cinefy

1. **Letterboxd:** importe os CSVs e, em *Enriquecimento automático com TMDB*, processe os filmes em lotes. O Cinefy só escolhe sozinho quando a confiança é alta.
2. **Conferir correspondências:** para remakes e títulos ambíguos, escolha a versão certa na lista de candidatos e confirme.
3. **Biblioteca:** busque por filme, diretor ou gênero; filtre por situação e década; edite gêneros e diretores na tabela e clique em **Salvar gêneros e diretores** (só as linhas alteradas são gravadas).
4. **Spotify:** conecte a conta e sincronize o perfil musical (4 semanas, 6 meses ou 1 ano).
5. **Mood Mirror, Director's Cut e Recomendação inversa** usam os dados já importados.
6. **Exportação:** o CSV traz a biblioteca de filmes; o backup JSON inclui também os snapshots musicais.

## 8. Banco de dados e backup

Por padrão o Cinefy cria `cinefy.db` (SQLite) na pasta do projeto. Ele contém sua biblioteca e seu histórico musical, por isso **não deve ser versionado nem compartilhado**.

- Copie o arquivo `cinefy.db` periodicamente, com o aplicativo fechado.
- Use **Baixar backup completo (JSON)** na aba Letterboxd para exportar os dados.

### PostgreSQL / Supabase (opcional)

1. Crie um projeto no Supabase.
2. Copie a connection string em **Project Settings → Database → Connection string**.
3. Configure:

```toml
[database]
url = "postgresql://USUARIO:SENHA@HOST:5432/postgres?sslmode=require"
```

O Cinefy usa SQLAlchemy com o driver `psycopg`. Se o banco estiver indisponível, o app mostra uma mensagem de erro em vez de quebrar.

## 9. Auditoria e testes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q          # testes automatizados
python analyzer.py           # auditoria estática do projeto
python analyzer.py --strict  # falha também em avisos
python analyzer.py --format json
```

O `analyzer.py` não executa o código auditado. Ele verifica sintaxe Python, funções vazias, `eval()`/`exec()`, possíveis credenciais literais (em `.py`, `.toml`, `.json`, incluindo `.streamlit/`, sem imprimir os valores), validade de JSON/TOML e regras importantes do `.gitignore`. Não substitui revisão humana nem auditoria de dependências.

Os testes cobrem importação do Letterboxd, análises e recomendações, persistência, cliente do TMDB, fluxo OAuth do Spotify (estado assinado, falhas de rede) e uma verificação de fumaça que renderiza todas as páginas do app com um banco temporário.

## 10. Estrutura de pastas

```text
Cinefy/
├── app.py                      # Interface Streamlit
├── analyzer.py                 # Auditoria estática do projeto
├── cinefy/
│   ├── analytics.py            # Métricas, humor e recomendações
│   ├── database.py             # Persistência SQLite/PostgreSQL
│   ├── helpers.py              # Funções puras da interface
│   ├── letterboxd.py           # Leitura e normalização dos CSVs
│   ├── spotify_client.py       # OAuth (estado assinado) e API do Spotify
│   ├── tmdb_client.py          # Busca e metadados do TMDB
│   └── ui.py                   # Tema Frutiger Aero, ícones e componentes
├── tests/
├── .streamlit/
│   ├── config.toml             # Tema base do Streamlit
│   ├── secrets.toml.example    # Modelo de credenciais (copie para secrets.toml)
│   └── secrets.toml            # Suas credenciais locais (não versionado)
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── run_windows.bat
└── README.md
```

## 11. Publicar (opcional)

Para usar o Streamlit Community Cloud, envie o código a um repositório **privado** e cadastre o conteúdo do `secrets.toml` no painel **Secrets** do Streamlit. Atualize o Redirect URI no Spotify para a URL pública do app (HTTPS), por exemplo `https://seu-cinefy.streamlit.app`, e o mesmo valor em `[spotify] redirect_uri`.

Na nuvem, o disco é temporário: configure PostgreSQL/Supabase em `[database]` para não perder a biblioteca. Defina também `[app] password`.

## 12. Limitações conhecidas

- A disponibilidade das métricas de áudio depende das políticas atuais do Spotify (veja a [seção 3](#atenção-métricas-de-áudio)).
- A sessão do Spotify fica na sessão do Streamlit; abrir outra sessão pode exigir nova conexão.
- A correspondência entre música e cinema é estimada por regras heurísticas.
- O cache de metadados do TMDB fica em memória por 24 horas.
- Títulos ambíguos no TMDB precisam de confirmação manual.
- SQLite é indicado para uso local; para uso remoto persistente, configure PostgreSQL.
