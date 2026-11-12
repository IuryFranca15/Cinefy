# Cinefy — sua filmografia tem trilha sonora

Aplicação pessoal em **Python + Streamlit** que cruza o histórico do Letterboxd com o perfil musical do Spotify. A interface segue uma estética Frutiger Aero: vidro translúcido, gradientes azul/ciano/verde e cartões leves.

## Cinefy v3 — o que mudou

Esta versão mantém a filmografia local e as integrações da v2, com correções de consistência e melhorias de análise:

- Importação do Letterboxd independente da ordem em que os CSVs são selecionados; datas, tags e sinalizadores são mesclados de forma consistente.
- Comparação de gêneros com normalização entre português e inglês (por exemplo, `Ação`/`Action`, `Terror`/`Horror` e `Ficção científica`/`Science Fiction`).
- Compatibilidade de recomendação limitada a 0–100%, com desempate pela maior nota do Letterboxd.
- Métricas de áudio ausentes não são mais substituídas por 50%; o Cinefy exibe indisponibilidade e calcula a compatibilidade apenas com métricas observadas.
- Busca na biblioteca por filme, diretor e gênero, com filtros por situação e década.
- Gravação dos filmes em lotes transacionais no SQLite/PostgreSQL e cache de 24 horas nas consultas de busca/detalhes do TMDB.
- `analyzer.py` agora inspeciona também `.streamlit/secrets.toml` e sinaliza possíveis credenciais sem imprimir seus valores.
- Testes automatizados ampliados para importação, recomendações, auditoria e persistência.

## O que a aplicação oferece

- Importação dos arquivos `diary.csv`, `ratings.csv` e `watchlist.csv` exportados pelo Letterboxd.
- Biblioteca de filmes com notas, datas, tags, gêneros, diretores, sinopses e pôsteres.
- Correspondência de títulos com TMDB: seleção automática apenas quando a confiança é alta e revisão manual para remakes/títulos ambíguos.
- Edição de gêneros e diretores.
- Exportação da biblioteca em CSV e backup de filmes + sincronizações em JSON.
- OAuth 2.0 do Spotify, Top Tracks e Top Artists.
- Métricas de energia, valência, dançabilidade e andamento quando disponibilizadas pelo Spotify.
- Histórico de sincronizações musicais.
- Dashboard, Director's Cut, Mood Mirror e recomendação inversa da watchlist.
- Banco SQLite local ou PostgreSQL/Supabase.
- Auditoria estática do projeto pelo `analyzer.py`.

> As recomendações e comparações entre gêneros musicais e cinematográficos são heurísticas recreativas, não avaliações objetivas.

## 1. Requisitos

- Windows 10/11, macOS ou Linux.
- Python **3.11 ou superior**.
- Conta Spotify e aplicativo no [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
- Conta Letterboxd com acesso à exportação de dados.
- Token de leitura da API do [TMDB](https://www.themoviedb.org/), para enriquecer os filmes.

## 2. Instalação no Windows (PowerShell)

Extraia o ZIP e abra o PowerShell dentro da pasta `Cinefy_v3` (a mesma que contém `app.py`).

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .streamlit\secrets.toml)) { Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml }
```

O pacote pessoal pode já conter seu `.streamlit/secrets.toml`. **Não o sobrescreva** se as credenciais já estiverem configuradas. Confira os valores apenas localmente e depois execute:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

O navegador abrirá em `http://localhost:8501`. Para encerrar, pressione `Ctrl + C` no terminal.

**Se o ambiente virtual já existir:** não é necessário criá-lo novamente. Execute apenas o `pip install` e o comando do Streamlit acima.

### macOS / Linux

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
test -f .streamlit/secrets.toml || cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

## 3. Configurar o Spotify

1. Entre em https://developer.spotify.com/dashboard e crie um aplicativo.
2. Copie o **Client ID** e o **Client Secret**.
3. Em Redirect URIs, adicione exatamente `http://localhost:8501`.
4. Em `.streamlit/secrets.toml`, preencha:

```toml
[spotify]
client_id = "SEU_CLIENT_ID"
client_secret = "SEU_CLIENT_SECRET"
redirect_uri = "http://localhost:8501"
```

5. Inicie o Cinefy, abra a aba **Spotify** e clique em **Conectar minha conta Spotify**.
6. Autorize o acesso e clique em **Sincronizar meu perfil musical**.

Permissões solicitadas:
- `user-top-read`: ler Top Artists e Top Tracks.
- `playlist-modify-private`: criar playlists privadas.

**Atenção:** as políticas do Spotify para aplicativos em Development Mode, incluindo Premium, usuários permitidos e limites, podem mudar. Confira as regras atuais no painel oficial. A sessão OAuth desta versão é mantida na sessão Streamlit; uma nova sessão pode exigir reconexão.

## 4. Configurar o TMDB

1. Crie uma conta em https://www.themoviedb.org/.
2. Acesse **Configurações → API** e solicite/consulte as credenciais.
3. Copie o **API Read Access Token** (o token longo, não a chave curta).
4. Configure:

```toml
[tmdb]
bearer_token = "SEU_API_READ_ACCESS_TOKEN"
api_key = ""
```

O Bearer token é recomendado. Nunca publique o arquivo `secrets.toml` nem envie credenciais ao GitHub.

### Enriquecer os filmes

1. Exporte os dados do Letterboxd.
2. Extraia o ZIP exportado.
3. Na aba **Letterboxd** do Cinefy, selecione `diary.csv`, `ratings.csv` e `watchlist.csv` (os arquivos disponíveis).
4. Clique em **Importar histórico**.
5. Na seção de enriquecimento TMDB, processe os filmes em lotes.
6. Revise manualmente as correspondências ambíguas antes de confirmar.

O Cinefy não depende de scraping nem de uma API privada do Letterboxd. O CSV não contém todos os metadados cinematográficos; por isso o TMDB é usado para buscar gêneros, diretores, sinopses e imagens.

**Crédito TMDB:** Este produto utiliza a API do TMDB, mas não é endossado nem certificado pelo TMDB. Dados e imagens cinematográficas fornecidos por TMDB. Consulte os [termos e diretrizes do TMDB](https://www.themoviedb.org/documentation/api/terms-of-use).

## 5. Banco de dados e backup

Por padrão, o Cinefy cria `cinefy.db` na pasta do projeto. Esse banco local contém sua biblioteca e histórico musical.

- Faça cópias periódicas do arquivo `cinefy.db` com o aplicativo fechado.
- Nesta distribuição pessoal, o banco `cinefy.db` e `.streamlit/secrets.toml` são mantidos para facilitar a continuidade do seu ambiente. Não publique nem compartilhe esse ZIP.
- Use **Baixar backup completo (JSON)** na aba Letterboxd para exportar os dados da aplicação.
- O CSV exporta a biblioteca de filmes; o JSON inclui filmes e snapshots musicais.

### PostgreSQL / Supabase (opcional)

1. Crie um projeto Supabase.
2. Copie a connection string PostgreSQL em **Project Settings → Database → Connection string**.
3. Configure no `secrets.toml`:

```toml
[database]
url = "postgresql://USUARIO:SENHA@HOST:5432/postgres?sslmode=require"
```

Use uma credencial de banco apropriada e mantenha-a privada. O Cinefy usa SQLAlchemy e o driver `psycopg`.

## 6. Auditoria do projeto (`analyzer.py`)

O analisador não executa os arquivos auditados. Ele faz verificações estáticas:

- Sintaxe Python (AST).
- Funções aparentemente vazias (`pass`/`...`).
- Uso de `eval()` e `exec()`.
- Possíveis credenciais literais.
- Validade de arquivos JSON e TOML.
- Presença de arquivos básicos do projeto e regras importantes do `.gitignore`.
- Inspeciona `.streamlit/secrets.toml` para identificar possíveis credenciais literais sem exibir seu conteúdo no relatório.
- Ignora `.venv`, `.git`, caches, `node_modules`, `build` e `dist`.

Comando simples:

```powershell
.\.venv\Scripts\python.exe analyzer.py
```

Como este ZIP pessoal preserva seu `.streamlit/secrets.toml`, o analisador deve exibir avisos `POSSIBLE_CREDENTIAL` para os valores de credenciais. Isso é intencional: os valores não aparecem no relatório. Não publique o TOML nem o ZIP. Os avisos não indicam erro de sintaxe nem impedem a execução normal do Cinefy.

Relatório JSON:

```powershell
.\.venv\Scripts\python.exe analyzer.py --format json
```

Auditoria estrita (código de saída diferente de zero também para avisos):

```powershell
.\.venv\Scripts\python.exe analyzer.py --strict
```

O analisador aponta riscos potenciais; não substitui revisão humana, testes automatizados, ferramentas de segurança ou auditoria de dependências.

## 7. Testes

Instale as dependências de desenvolvimento e rode:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

## 8. Estrutura de pastas

```text
cinefy/
├── app.py                     # Interface Streamlit
├── analyzer.py                # Auditoria estática do projeto
├── cinefy.db                  # Banco local (se incluído no pacote)
├── cinefy/
│   ├── analytics.py           # Métricas e recomendações
│   ├── database.py            # Persistência SQLite/PostgreSQL
│   ├── letterboxd.py          # Leitura e normalização dos CSVs
│   ├── spotify_client.py      # OAuth e integração Spotify
│   └── tmdb_client.py         # Busca e metadados TMDB
├── tests/
│   ├── test_analytics.py
│   ├── test_database.py
│   ├── test_letterboxd.py
│   ├── test_tmdb_client.py
│   └── test_analyzer.py
├── .streamlit/
│   ├── config.toml
│   ├── secrets.toml            # credenciais locais preservadas neste pacote pessoal
│   └── secrets.toml.example
├── requirements.txt
├── run_windows.bat
└── README.md
```

## 9. Publicar (opcional)

Para publicar no Streamlit Community Cloud, envie o código a um repositório privado no GitHub e configure os Secrets no painel do Streamlit. Atualize também o Redirect URI no Spotify para a URL pública do app.

Se usar PostgreSQL/Supabase, configure a connection string nos Secrets. **Não publique o banco SQLite, `.env` ou `secrets.toml`.** A senha simples opcional do app (`[app] password`) protege apenas o acesso casual; não é um sistema completo de autenticação multiusuário.

## 10. Limitações conhecidas

- A disponibilidade de Audio Features depende das permissões e políticas atuais do Spotify.
- A integração Spotify pode exigir nova autorização ao iniciar outra sessão.
- A correspondência entre música e cinema é estimada por regras heurísticas.
- O cache de metadados TMDB é mantido em memória pelo Streamlit durante 24 horas; uma nova execução limpa esse cache.
- Títulos ambíguos no TMDB precisam de confirmação manual.
- SQLite é indicado para uso local; para uso remoto persistente, configure PostgreSQL.
