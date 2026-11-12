from __future__ import annotations

import html
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from cinefy.analytics import (
    build_music_dataframe,
    describe_music_mood,
    get_film_mood_target,
    inverse_recommendations,
    make_mood_mirror_text,
    rank_tracks_for_film,
)
from cinefy.database import (
    get_films,
    get_latest_snapshot,
    get_snapshots,
    init_db,
    save_films,
    save_music_snapshot,
    update_film_metadata,
    update_tmdb_metadata,
)
from cinefy.helpers import changed_metadata_rows, passwords_match, safe_poster_url
from cinefy.letterboxd import parse_letterboxd_uploads
from cinefy.ui import aero_layout, brand_html, card_title, inject_theme, metric_card, orb, page_header, status_pill
from cinefy.tmdb_client import (
    TMDBAbortError,
    find_and_enrich_movie,
    get_movie_details,
    is_tmdb_configured,
    search_movies,
)
from cinefy.spotify_client import (
    SpotifyTemporaryError,
    build_authorize_url,
    create_playlist,
    exchange_code,
    is_spotify_configured,
    make_state,
    refresh_access_token,
    sync_top_music,
    verify_state,
)

st.set_page_config(
    page_title="Cinefy — sua filmografia tem trilha sonora",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


inject_theme()


# ------------------------------- app helpers -------------------------------
def secret_value(section: str, key: str, env_name: str = "") -> str:
    value = ""
    try:
        value = st.secrets.get(section, {}).get(key, "")
    except Exception:
        pass
    if not value and env_name:
        value = os.getenv(env_name, "")
    return str(value or "").strip()


def require_app_password() -> bool:
    password = secret_value("app", "password", "CINEFY_APP_PASSWORD")
    if not password:
        return True
    if st.session_state.get("cinefy_authenticated"):
        return True
    page_header("Cinefy", "Um espaço pessoal para sua música e seu cinema.", "lock")
    typed = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar no Cinefy", width="stretch"):
        if passwords_match(typed, password):
            st.session_state["cinefy_authenticated"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.caption("Configure app.password nos Secrets antes de publicar o aplicativo.")
    return False


def flash(message: str, kind: str = "success") -> None:
    """Guarda uma mensagem para ser exibida depois do próximo st.rerun()."""
    st.session_state.setdefault("_flash", []).append((kind, message))


def show_flash() -> None:
    for kind, message in st.session_state.pop("_flash", []):
        getattr(st, kind if kind in {"success", "info", "warning", "error"} else "info")(message)


def current_token() -> dict[str, Any] | None:
    token = st.session_state.get("spotify_token")
    if not token:
        return None
    try:
        expires_at = float(token.get("expires_at", 0) or 0)
    except (TypeError, ValueError):
        expires_at = 0.0
    if expires_at <= datetime.now(timezone.utc).timestamp() + 60:
        try:
            refreshed = refresh_access_token(token)
        except SpotifyTemporaryError:
            # Falha de rede: mantém a sessão; o token será renovado na próxima tentativa.
            st.session_state["_spotify_refresh_warning"] = True
            return token
        if refreshed:
            st.session_state["spotify_token"] = refreshed
            token = refreshed
        else:
            st.session_state.pop("spotify_token", None)
            return None
    return token


def handle_spotify_callback() -> None:
    params = st.query_params
    code = params.get("code")
    error = params.get("error")
    if error and not code:
        st.query_params.clear()
        flash("A autorização do Spotify foi cancelada ou negada. Você pode tentar conectar novamente." if error == "access_denied"
              else f"O Spotify devolveu um erro de autorização ({error}).", "warning")
        return
    if not code:
        return
    # O redirect do Spotify cria uma sessão nova; por isso o state é validado pela assinatura.
    if not verify_state(str(params.get("state") or "")):
        st.query_params.clear()
        flash("Não foi possível validar o retorno do Spotify (link expirado ou inválido). Tente conectar novamente.", "error")
        return
    try:
        token = exchange_code(str(code))
    except Exception as exc:
        st.query_params.clear()
        flash(f"Falha ao conectar ao Spotify: {exc}", "error")
        return
    st.session_state["spotify_token"] = token
    st.session_state["page"] = "Spotify"
    st.query_params.clear()
    flash("Spotify conectado!")
    st.rerun()


def format_film_option(row: pd.Series) -> str:
    year = row.get("year")
    return f"{row.get('title', 'Filme')} ({int(year)})" if pd.notna(year) and str(year).strip() else str(row.get("title", "Filme"))


def format_percent(value: Any) -> str:
    """Show a dash for unavailable metrics instead of formatting them as zero."""
    try:
        return f"{float(value):.0%}" if value is not None and pd.notna(value) else "—"
    except (TypeError, ValueError):
        return "—"


# ------------------------------- app startup -------------------------------
try:
    init_db()
except Exception as exc:
    st.error(f"Não consegui acessar o banco de dados. Confira a configuração em [database] ou apague a variável DATABASE_URL para usar o SQLite local. Detalhe: {exc}")
    st.stop()
if not require_app_password():
    st.stop()
handle_spotify_callback()

with st.sidebar:
    st.markdown(brand_html(), unsafe_allow_html=True)
    st.caption("A trilha sonora da sua filmografia")
    page = st.radio(
        "Navegação",
        ["Visão geral", "Letterboxd", "Spotify", "Director's Cut", "Mood Mirror", "Recomendação inversa"],
        label_visibility="collapsed",
        key="page",
    )
    st.divider()
    token = current_token()
    st.markdown(status_pill("Spotify conectado" if token else "Spotify desconectado", bool(token)), unsafe_allow_html=True)
    st.caption("Cinefy v3 · Python + Streamlit")

try:
    films_df = get_films()
    latest_snapshot = get_latest_snapshot()
except Exception as exc:
    st.error(f"Não consegui ler seus dados no banco. Detalhe: {exc}")
    st.stop()
music_df = build_music_dataframe(latest_snapshot.get("tracks", [])) if latest_snapshot else pd.DataFrame()
show_flash()
if st.session_state.pop("_spotify_refresh_warning", False):
    st.warning("Não consegui renovar a sessão do Spotify agora (falha de rede). A conexão foi mantida; tente novamente em instantes.")

# -------------------------------- dashboard ---------------------------------
if page == "Visão geral":
    page_header("Sua filmografia tem trilha sonora", "Cruze o que você ouve com o que você assiste — e descubra a estética que existe entre os dois.", "overview")
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Filmes no Cinefy", str(len(films_df)), "Importados do seu Letterboxd", "film")
    with c2:
        metric_card("Faixas no último sync", str(len(music_df)), "Seu Top Tracks do Spotify" if not music_df.empty else "Conecte o Spotify para começar", "headphones")
    with c3:
        watched_count = int((~films_df.get("is_watchlist", pd.Series(dtype=bool)).fillna(False)).sum()) if not films_df.empty else 0
        metric_card("Filmes assistidos", str(watched_count), "Registros do diário e avaliações", "clapper")

    st.subheader("Seu painel estético")
    if music_df.empty and films_df.empty:
        st.markdown("<div class='callout'><b>Seu Cinefy está pronto para receber seus dados.</b><br><span class='muted'>Comece importando o arquivo ZIP/CSV exportado pelo Letterboxd (os CSVs individuais) e conectando sua conta Spotify.</span></div>", unsafe_allow_html=True)
        st.write("")
        a, b = st.columns(2)
        with a:
            st.info("**Primeiro:** vá até Letterboxd e importe `diary.csv`, `ratings.csv` e `watchlist.csv`.")
        with b:
            st.info("**Depois:** conecte seu Spotify na aba Spotify e sincronize suas músicas mais ouvidas.")
    else:
        a, b = st.columns(2)
        with a, st.container(border=True):
            card_title("headphones", "Assinatura sonora")
            if not music_df.empty:
                if music_df[["energy", "valence", "danceability"]].notna().sum().sum() > 0:
                    mood = describe_music_mood(music_df)
                    st.markdown(f"<h3 style='margin:.4rem 0'>{html.escape(mood['headline'])}</h3><p class='muted'>{html.escape(mood['description'])}</p>", unsafe_allow_html=True)
                    if mood.get("energy") is not None:
                        st.progress(float(mood["energy"]))
                    st.caption(f"Energia {format_percent(mood.get('energy'))} · Valência {format_percent(mood.get('valence'))} · Dançabilidade {format_percent(mood.get('danceability'))}")
                else:
                    st.caption("Faixas sincronizadas; o Spotify não disponibilizou as métricas de áudio nesta consulta.")
            else:
                st.caption("Ainda não há dados musicais sincronizados.")
        with b, st.container(border=True):
            card_title("clapper", "Sua filmografia")
            if not films_df.empty:
                genre_counts: dict[str, int] = {}
                for value in films_df.loc[~films_df["is_watchlist"].fillna(False), "genres"].fillna(""):
                    for genre in str(value).split(","):
                        genre = genre.strip()
                        if genre:
                            genre_counts[genre] = genre_counts.get(genre, 0) + 1
                if genre_counts:
                    top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:4]
                    st.markdown(" ".join(f"<span class='aero-pill'>{html.escape(g)} · {n}</span>" for g, n in top_genres), unsafe_allow_html=True)
                else:
                    st.caption("Adicione gêneros aos seus filmes na aba Letterboxd para descobrir sua estética cinematográfica.")
            else:
                st.caption("Importe seu histórico do Letterboxd para começar.")

    chart_columns = {"track_name", "energy", "valence", "danceability", "artist_names"}
    if not music_df.empty and chart_columns.issubset(music_df.columns) and music_df[["energy", "valence"]].notna().any().all():
        st.subheader("O som que mais aparece no seu perfil")
        chart_df = music_df.head(12).copy()
        fig = px.bar(chart_df, x="track_name", y="energy", color="valence", hover_data=["artist_names", "danceability"],
                     labels={"track_name": "Faixa", "energy": "Energia", "valence": "Valência", "artist_names": "Artista"},
                     color_continuous_scale="Tealgrn")
        aero_layout(fig)
        st.plotly_chart(fig, width="stretch")

    if latest_snapshot:
        st.caption(f"Última sincronização do Spotify: {latest_snapshot.get('created_at', 'data não informada')} · período: {latest_snapshot.get('time_range', 'médio prazo')}")

# -------------------------------- Letterboxd --------------------------------
elif page == "Letterboxd":
    page_header("Sua filmografia", "Importe seu histórico e enriqueça cada filme automaticamente com dados cinematográficos do TMDB.", "film")
    st.markdown("<div class='callout'>No Letterboxd, use <b>Settings → Import & Export → Export Your Data</b>. Extraia o arquivo e selecione os CSVs abaixo. O Cinefy reconhece diário, avaliações e watchlist.</div>", unsafe_allow_html=True)
    uploads = st.file_uploader("Selecione os CSVs do Letterboxd", type=["csv"], accept_multiple_files=True, key="lb_uploads")
    if uploads and st.button("Importar histórico", type="primary"):
        try:
            imported = parse_letterboxd_uploads(uploads)
            if imported.empty:
                st.warning("Não encontrei filmes reconhecíveis. Confira se selecionou os CSVs exportados pelo Letterboxd.")
            else:
                save_films(imported.to_dict("records"))
                flash(f"{len(imported)} filmes processados e salvos no Cinefy.")
                st.rerun()
        except Exception as exc:
            st.error(f"Não consegui ler os arquivos: {exc}")

    films_df = get_films()
    if not films_df.empty:
        st.divider()
        st.subheader("Enriquecimento automático com TMDB")
        if not is_tmdb_configured():
            st.warning("Configure o token do TMDB em `.streamlit/secrets.toml` para buscar gêneros, diretores, sinopses e pôsteres automaticamente.")
            st.code('[tmdb]\nbearer_token = "SEU_API_READ_ACCESS_TOKEN"', language="toml")
            st.markdown("Crie uma conta em [themoviedb.org](https://www.themoviedb.org/), acesse **Configurações → API** e copie o **API Read Access Token**. O token fica somente nos Secrets do Streamlit.")
        else:
            has_tmdb = films_df.get("tmdb_id", pd.Series(index=films_df.index, dtype="float64")).notna()
            status = films_df.get("metadata_status", pd.Series(index=films_df.index, dtype="object")).fillna("")
            needs_first_pass = films_df[~has_tmdb & ~status.isin(["needs_review", "not_found"])]
            linked_count = int(has_tmdb.sum())
            needs_review_count = int(status.eq("needs_review").sum())
            not_found_count = int(status.eq("not_found").sum())
            a, b, c = st.columns(3)
            a.metric("Filmes identificados", f"{linked_count}/{len(films_df)}")
            b.metric("Precisam de revisão", needs_review_count)
            c.metric("Sem resultado", not_found_count)
            if not needs_first_pass.empty:
                st.caption(f"{len(needs_first_pass)} filme(s) ainda não foram consultados no TMDB.")
                batch_size = st.selectbox("Quantidade por processamento", [10, 25, 50, 100, "Todos"], index=1, key="tmdb_batch_size")
                to_process = needs_first_pass if batch_size == "Todos" else needs_first_pass.head(int(batch_size))
                if st.button(f"Buscar dados de {len(to_process)} filme(s) no TMDB", type="primary"):
                    progress = st.progress(0, text="Preparando consulta ao TMDB...")
                    success_count = 0
                    review_count = 0
                    not_found_count_run = 0
                    errors: list[str] = []
                    review_candidates = st.session_state.get("tmdb_review_candidates", {})
                    aborted = ""
                    processed = 0
                    for index, (_, film_row) in enumerate(to_process.iterrows(), start=1):
                        try:
                            details, candidates = find_and_enrich_movie(str(film_row["title"]), int(film_row["year"]) if pd.notna(film_row.get("year")) else None)
                            if details:
                                update_tmdb_metadata(str(film_row["film_key"]), details)
                                success_count += 1
                            elif candidates:
                                update_tmdb_metadata(str(film_row["film_key"]), {"metadata_status": "needs_review", "metadata_source": "TMDB"})
                                review_candidates[str(film_row["film_key"])] = candidates
                                review_count += 1
                            else:
                                update_tmdb_metadata(str(film_row["film_key"]), {"metadata_status": "not_found", "metadata_source": "TMDB"})
                                not_found_count_run += 1
                        except TMDBAbortError as exc:
                            # Credencial recusada ou limite de uso: continuar só repetiria o erro.
                            aborted = str(exc)
                            break
                        except Exception as exc:
                            errors.append(f"{film_row['title']}: {exc}")
                        processed = index
                        progress.progress(index / len(to_process))
                    st.session_state["tmdb_review_candidates"] = review_candidates
                    flash(f"Concluído: {success_count} identificado(s), {review_count} para revisão e {not_found_count_run} sem resultado.")
                    if aborted:
                        flash(f"Processamento interrompido após {processed} filme(s): {aborted}", "error")
                    if errors:
                        flash("Algumas consultas falharam: " + " · ".join(errors[:5]), "warning")
                    st.rerun()

            # Manual resolution for ambiguous titles and films not found automatically.
            films_df = get_films()
            unmatched = films_df[films_df["tmdb_id"].isna()] if "tmdb_id" in films_df else films_df
            if not unmatched.empty:
                st.markdown("#### Conferir correspondências")
                st.caption("O Cinefy evita escolher automaticamente quando títulos, remakes ou anos deixam a correspondência incerta. Selecione a versão correta abaixo.")
                # Opções por film_key: dois filmes com o mesmo título/ano não podem se sobrepor.
                base_labels = {str(row["film_key"]): format_film_option(row) for _, row in unmatched.iterrows()}
                label_counts: dict[str, int] = {}
                for text in base_labels.values():
                    label_counts[text] = label_counts.get(text, 0) + 1
                film_labels = {key: (f"{text} · {key.rstrip('/').rsplit('/', 1)[-1][-12:]}" if label_counts[text] > 1 else text)
                               for key, text in base_labels.items()}
                selected_key = st.selectbox("Filme do Letterboxd", list(film_labels.keys()), format_func=lambda key: film_labels.get(key, key), key="tmdb_film_to_review")
                selected_film = unmatched[unmatched["film_key"].astype(str) == selected_key].iloc[0]
                default_year = int(selected_film["year"]) if pd.notna(selected_film.get("year")) else None
                review_store: dict[str, list[dict[str, Any]]] = st.session_state.setdefault("tmdb_review_candidates", {})
                # Os candidatos vivem só na sessão; ao reabrir um filme em revisão, a busca é refeita.
                tried: set[str] = st.session_state.setdefault("tmdb_auto_tried", set())
                if not review_store.get(selected_key) and selected_key not in tried and str(selected_film.get("metadata_status") or "") == "needs_review":
                    tried.add(selected_key)
                    try:
                        review_store[selected_key] = search_movies(str(selected_film["title"]), default_year)[:8]
                    except Exception as exc:
                        st.warning(f"Não consegui recuperar as sugestões do TMDB: {exc}")
                search_col, year_col = st.columns([3, 1])
                with search_col:
                    manual_query = st.text_input("Título para pesquisar no TMDB", value=str(selected_film["title"]), key=f"tmdb_query_{selected_key}")
                with year_col:
                    manual_year = st.number_input("Ano", min_value=1870, max_value=2100, value=default_year or 2000, step=1, key=f"tmdb_year_{selected_key}")
                if st.button("Pesquisar título no TMDB", key=f"tmdb_search_{selected_key}"):
                    try:
                        results = search_movies(manual_query, int(manual_year) if manual_year else None)
                        review_store[selected_key] = results[:10]
                        if not results:
                            st.info("Nenhum resultado encontrado. Tente o título original ou pesquise sem o ano.")
                    except Exception as exc:
                        st.error(f"Falha na pesquisa: {exc}")
                candidates = review_store.get(selected_key, [])
                if candidates:
                    def candidate_label(item: dict[str, Any]) -> str:
                        release = str(item.get("release_date") or "")[:4] or "ano desconhecido"
                        original = item.get("original_title") or item.get("title") or ""
                        score = item.get("_cinefy_score")
                        score_text = f" · compatibilidade {score:.0%}" if isinstance(score, (int, float)) else ""
                        return f"{item.get('title') or original} ({release}) · original: {original} · TMDB #{item.get('id')}{score_text}"
                    candidate_map = {str(item.get("id")): item for item in candidates}
                    chosen_id = st.selectbox("Escolha a correspondência correta", list(candidate_map.keys()),
                                             format_func=lambda cid: candidate_label(candidate_map[cid]), key=f"tmdb_candidate_{selected_key}")
                    chosen = candidate_map[chosen_id]
                    overview_preview = str(chosen.get("overview") or "Sinopse indisponível na pesquisa.")
                    st.caption(overview_preview[:500] + ("…" if len(overview_preview) > 500 else ""))
                    if st.button("Confirmar filme e importar metadados", type="primary", key=f"tmdb_apply_{selected_key}"):
                        try:
                            details = get_movie_details(int(chosen["id"]))
                            update_tmdb_metadata(selected_key, details)
                            review_store.pop(selected_key, None)
                            flash("Dados cinematográficos importados do TMDB.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não consegui importar os detalhes: {exc}")

        films_df = get_films()
        st.divider()
        st.subheader("Biblioteca cinematográfica")
        st.caption("Pesquise e filtre sua coleção antes de editar ou explorar os pôsteres.")
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 1, 1, 1])
        with filter_col1:
            library_search = st.text_input("Buscar filme, diretor ou gênero", key="library_search")
        with filter_col2:
            status_filter = st.selectbox("Situação", ["Todos", "Assistidos", "Watchlist"], key="library_status")
        with filter_col3:
            valid_years = pd.to_numeric(films_df.get("year", pd.Series(dtype=float)), errors="coerce").dropna()
            decades = sorted({(int(year) // 10) * 10 for year in valid_years}, reverse=True)
            decade_options = ["Todas"] + [f"{decade}s" for decade in decades]
            decade_filter = st.selectbox("Década", decade_options, key="library_decade")
        with filter_col4:
            genre_values = set()
            for raw_genres in films_df.get("genres", pd.Series(dtype=str)).dropna():
                genre_values.update(value.strip() for value in str(raw_genres).split(",") if value.strip())
            genre_options = ["Todos"] + sorted(genre_values, key=str.casefold)
            genre_filter = st.selectbox("Gênero", genre_options, key="library_genre")

        library_view = films_df.copy()
        if library_search.strip():
            search_mask = pd.Series(False, index=library_view.index)
            for search_column in ("title", "director", "genres"):
                if search_column in library_view.columns:
                    search_mask |= library_view[search_column].fillna("").astype(str).str.contains(library_search.strip(), case=False, regex=False)
            library_view = library_view[search_mask]
        if status_filter == "Assistidos":
            library_view = library_view[~library_view["is_watchlist"].fillna(False).astype(bool)]
        elif status_filter == "Watchlist":
            library_view = library_view[library_view["is_watchlist"].fillna(False).astype(bool)]
        if decade_filter != "Todas":
            selected_decade = int(decade_filter[:-1])
            years_numeric = pd.to_numeric(library_view["year"], errors="coerce")
            library_view = library_view[years_numeric.between(selected_decade, selected_decade + 9)]
        if genre_filter != "Todos":
            library_view = library_view[library_view["genres"].fillna("").astype(str).apply(
                lambda values: genre_filter.casefold() in {item.strip().casefold() for item in values.split(",")}
            )]
        st.caption(f"{len(library_view)} de {len(films_df)} filmes exibidos")

        editable = library_view[["film_key", "title", "year", "watched_date", "rating", "is_watchlist", "director", "genres", "tags"]].copy()
        editable = editable.rename(columns={
            "film_key": "Chave", "title": "Filme", "year": "Ano", "watched_date": "Data assistido",
            "rating": "Nota", "is_watchlist": "Na watchlist", "director": "Diretor", "genres": "Gêneros", "tags": "Tags"
        })
        # A chave inclui os filtros: o st.data_editor guarda as edições por posição da linha,
        # e trocar o filtro sem trocar a chave aplicaria as edições na linha errada.
        editor_key = "film_editor_" + str(abs(hash((library_search.strip(), status_filter, decade_filter, genre_filter))))
        edited = st.data_editor(
            editable,
            width="stretch",
            hide_index=True,
            disabled=["Chave", "Filme", "Ano", "Data assistido", "Nota", "Na watchlist", "Tags"],
            column_config={
                "Nota": st.column_config.NumberColumn("Nota", min_value=0, max_value=5, step=0.5, format="%.1f"),
                "Na watchlist": st.column_config.CheckboxColumn("Na watchlist"),
                "Diretor": st.column_config.TextColumn("Diretor"),
                "Gêneros": st.column_config.TextColumn("Gêneros", help="Separe por vírgula"),
            },
            key=editor_key,
        )
        if st.button("Salvar gêneros e diretores", type="primary"):
            columns = {"Chave": "film_key", "Diretor": "director", "Gêneros": "genres"}
            updates = changed_metadata_rows(
                editable.rename(columns=columns)[["film_key", "director", "genres"]],
                edited.rename(columns=columns)[["film_key", "director", "genres"]],
            )
            if not updates:
                st.info("Nenhuma alteração para salvar.")
            else:
                update_film_metadata(updates)
                flash(f"Metadados de {len(updates)} filme(s) atualizados manualmente.")
                st.rerun()

        st.subheader("Pôsteres e sinopses")
        enriched_all = library_view[library_view.get("tmdb_id", pd.Series(index=library_view.index, dtype="float64")).notna()]
        poster_limit = st.selectbox("Filmes exibidos", [12, 24, 48, "Todos"], index=0, key="poster_limit")
        enriched = enriched_all if poster_limit == "Todos" else enriched_all.head(int(poster_limit))
        if enriched.empty:
            st.info("Assim que os filmes forem identificados no TMDB, os pôsteres e sinopses aparecerão aqui.")
        else:
            poster_cols = st.columns(4)
            for index, (_, film_row) in enumerate(enriched.iterrows()):
                with poster_cols[index % 4]:
                    poster_url = safe_poster_url(film_row.get("poster_url"))
                    if poster_url:
                        st.image(poster_url, width="stretch")
                    else:
                        st.markdown(f"<div class='glass-card' style='text-align:center;padding:40px 8px'>{orb('film', 'md')}<br><span class='muted'>Pôster indisponível</span></div>", unsafe_allow_html=True)
                    st.markdown(f"**{html.escape(str(film_row['title']))}**")
                    st.caption(f"{html.escape(str(film_row.get('year') or ''))} · {html.escape(str(film_row.get('director') or 'Direção não informada'))}")
                    st.caption(str(film_row.get("genres") or "Gêneros não informados"))
                    overview = str(film_row.get("overview") or "Sinopse indisponível.")
                    st.markdown(f"<div class='muted' style='font-size:.82rem'>{html.escape(overview[:350])}{'…' if len(overview) > 350 else ''}</div>", unsafe_allow_html=True)
                    if film_row.get("tmdb_url"):
                        st.markdown(f"[Ver no TMDB]({html.escape(str(film_row['tmdb_url']))})")
        st.download_button("Exportar filmes em CSV", films_df.to_csv(index=False).encode("utf-8-sig"), "cinefy_filmes.csv", "text/csv")
        snapshots_df = get_snapshots()
        backup_payload = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "application": "Cinefy",
            "films": films_df.where(pd.notna(films_df), None).to_dict("records"),
            "music_snapshots": snapshots_df.where(pd.notna(snapshots_df), None).to_dict("records"),
        }
        st.download_button(
            "Baixar backup completo (JSON)",
            data=json.dumps(backup_payload, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            file_name=f"cinefy_backup_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            help="Inclui filmes e histórico de sincronizações musicais. Guarde em local seguro.",
        )
    else:
        st.info("Nenhum filme importado ainda.")

# ---------------------------------- Spotify ----------------------------------
elif page == "Spotify":
    page_header("Sua identidade sonora", "Conecte o Spotify, sincronize suas faixas e transforme seu gosto musical em dados exploráveis.", "headphones")
    if not is_spotify_configured():
        st.warning("Falta configurar Spotify Client ID e Client Secret. Veja o arquivo README.md e o exemplo em .streamlit/secrets.toml.example.")
    else:
        token = current_token()
        if not token:
            st.markdown("<div class='callout'>O Cinefy só acessa os dados depois da sua autorização. A conexão utiliza OAuth do Spotify.</div>", unsafe_allow_html=True)
            auth_url = build_authorize_url(make_state())
            st.link_button("Conectar minha conta Spotify", auth_url, width="stretch")
            st.caption("Permissões solicitadas: ler Top Artists/Tracks e criar playlists privadas.")
        else:
            st.success("Conexão Spotify autorizada nesta sessão.")
            col1, col2 = st.columns([1, 2])
            with col1:
                time_range = st.selectbox("Janela de análise", ["short_term", "medium_term", "long_term"], index=1,
                                          format_func=lambda x: {"short_term": "Últimas 4 semanas", "medium_term": "Últimos 6 meses", "long_term": "Último ano"}[x])
                if st.button("Sincronizar meu perfil musical", type="primary", width="stretch"):
                    with st.spinner("Buscando suas músicas e calculando a assinatura sonora..."):
                        try:
                            payload = sync_top_music(time_range)
                            save_music_snapshot(payload)
                            flash(f"Sincronização concluída: {len(payload.get('tracks', []))} faixas e {len(payload.get('artists', []))} artistas.")
                            if payload.get("tracks") and not any(t.get("energy") is not None for t in payload["tracks"]):
                                flash("O Spotify não liberou as métricas de áudio (energia, valência, dançabilidade) para este aplicativo. Apps criados depois de 27/11/2024 não têm acesso a esse recurso; o Cinefy não inventa valores no lugar.", "warning")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível sincronizar: {exc}")
                if st.button("Desconectar Spotify", width="stretch"):
                    st.session_state.pop("spotify_token", None)
                    st.rerun()
            with col2:
                st.markdown("<div class='callout'><b>O que é sincronizado?</b><br>Seu Top 50 de faixas, Top 50 de artistas e métricas de áudio disponíveis (energia, valência e dançabilidade). O Cinefy salva um retrato da sincronização para comparar períodos.</div>", unsafe_allow_html=True)

    latest_snapshot = get_latest_snapshot()
    if latest_snapshot:
        st.subheader("Top tracks mais recentes")
        latest_df = build_music_dataframe(latest_snapshot.get("tracks", []))
        if not latest_df.empty:
            show_cols = [c for c in ["track_name", "artist_names", "album_name", "energy", "valence", "danceability"] if c in latest_df.columns]
            st.dataframe(latest_df[show_cols].rename(columns={"track_name":"Faixa", "artist_names":"Artista(s)", "album_name":"Álbum", "energy":"Energia", "valence":"Valência", "danceability":"Dançabilidade"}), width="stretch", hide_index=True,
                         column_config={name: st.column_config.NumberColumn(name, format="percent") for name in ("Energia", "Valência", "Dançabilidade")})
            if latest_df[["energy", "valence", "danceability"]].notna().sum().sum() > 0:
                mood = describe_music_mood(latest_df)
                st.markdown(f"<div class='glass-card'><b>{html.escape(mood['headline'])}</b><p class='muted'>{html.escape(mood['description'])}</p></div>", unsafe_allow_html=True)
            else:
                st.warning("As faixas foram importadas, mas as métricas de áudio não foram disponibilizadas para esta aplicação Spotify.")

# ------------------------------- Director's Cut ------------------------------
elif page == "Director's Cut":
    page_header("Director's Cut", "Uma trilha sonora alternativa feita com as músicas que já fazem parte da sua vida.", "clapper")
    if films_df.empty:
        st.info("Importe seu diário do Letterboxd primeiro.")
    elif music_df.empty:
        st.info("Sincronize o Spotify primeiro para gerar uma playlist com seu repertório musical.")
    else:
        candidates = films_df[~films_df["is_watchlist"].fillna(False)].copy()
        if candidates.empty:
            candidates = films_df.copy()
        candidates = candidates.reset_index(drop=True)
        film_labels_dc = {str(row["film_key"]): format_film_option(row) for _, row in candidates.iterrows()}
        selected_film_key = st.selectbox("Escolha um filme", list(film_labels_dc.keys()), format_func=lambda key: film_labels_dc.get(key, key), key="director_film_key")
        film = candidates[candidates["film_key"].astype(str) == selected_film_key].iloc[0]
        genres = str(film.get("genres") or "").strip()
        director = str(film.get("director") or "").strip()
        film_poster_col, film_info_col = st.columns([1, 3])
        with film_poster_col:
            director_poster = safe_poster_url(film.get("poster_url"))
            if director_poster:
                st.image(director_poster, width="stretch")
        with film_info_col:
            st.markdown(f"<div class='glass-card'><h3 style='margin-top:0'>{html.escape(str(film['title']))}</h3><span class='aero-pill'>{html.escape(str(int(film['year'])) if pd.notna(film.get('year')) else 'Ano não informado')}</span><span class='aero-pill'>{html.escape(genres or 'Gêneros não preenchidos')}</span><p class='muted'>Direção: {html.escape(director or 'não informada')}</p><p>{html.escape(str(film.get('overview') or 'Sinopse ainda não disponível.'))}</p></div>", unsafe_allow_html=True)
        target = get_film_mood_target(genres)
        st.caption(f"Atmosfera estimada: {target['label']} · energia {target['energy']:.0%} · valência {target['valence']:.0%} · dançabilidade {target['danceability']:.0%}")
        ranked = rank_tracks_for_film(music_df, genres)
        st.subheader("Faixas que combinam com esse filme")
        if "match_available" in ranked.columns and not ranked["match_available"].any():
            st.warning("O Spotify não forneceu métricas de áudio para estas faixas. A lista mantém a ordem original e não inventa uma compatibilidade.")
        else:
            st.caption("A compatibilidade considera somente as métricas realmente disponíveis em cada faixa.")
        st.dataframe(ranked[[c for c in ["track_name", "artist_names", "energy", "valence", "danceability", "match_score"] if c in ranked.columns]].head(15).rename(columns={"track_name":"Faixa", "artist_names":"Artista(s)", "energy":"Energia", "valence":"Valência", "danceability":"Dançabilidade", "match_score":"Compatibilidade"}), width="stretch", hide_index=True,
                     column_config={name: st.column_config.NumberColumn(name, format="percent") for name in ("Energia", "Valência", "Dançabilidade", "Compatibilidade")})
        playlist_name = f"Cinefy — {str(film['title'])[:70]}: Director's Cut"
        playlist_key = f"director_playlist_name_{selected_film_key}"  # um nome por filme, sem reaproveitar o do anterior
        st.text_input("Nome da playlist", value=playlist_name, key=playlist_key)
        if st.button("Criar playlist no meu Spotify", type="primary"):
            token = current_token()
            track_uris = ranked.head(30)["uri"].dropna().astype(str).tolist() if "uri" in ranked.columns else []
            if not token:
                st.error("Conecte o Spotify na aba Spotify.")
            elif not track_uris:
                st.warning("Estas faixas não têm o identificador (URI) do Spotify. Sincronize o Spotify novamente para gerar a playlist.")
            else:
                try:
                    playlist = create_playlist(st.session_state[playlist_key],
                                               f"Trilha alternativa gerada pelo Cinefy para {film['title']}. Seleção baseada na atmosfera do filme e no seu perfil musical.", track_uris)
                    st.success("Playlist criada no Spotify!")
                    playlist_url = (playlist.get("external_urls") or {}).get("spotify")
                    if playlist_url:
                        st.link_button("Abrir playlist", playlist_url)
                except Exception as exc:
                    st.error(f"Não consegui criar a playlist. Confira as permissões da conexão Spotify. Detalhe: {exc}")

# -------------------------------- Mood Mirror --------------------------------
elif page == "Mood Mirror":
    page_header("Mood Mirror", "O espelho entre aquilo que você escuta e os mundos que escolhe assistir.", "mirror")
    if music_df.empty:
        st.info("Sincronize seu Spotify para construir o Mood Mirror.")
    elif films_df.empty:
        st.info("Importe seu histórico do Letterboxd para comparar música e cinema.")
    else:
        watched = films_df[~films_df["is_watchlist"].fillna(False)].copy()
        genre_counts: dict[str, int] = {}
        for raw in watched["genres"].fillna(""):
            for genre in str(raw).split(","):
                genre = genre.strip()
                if genre:
                    genre_counts[genre] = genre_counts.get(genre, 0) + 1
        mood = describe_music_mood(music_df)
        missing_metrics = [column for column in ["energy", "valence", "danceability"] if column not in music_df.columns or music_df[column].notna().sum() == 0]
        if missing_metrics:
            labels = {"energy": "energia", "valence": "valência", "danceability": "dançabilidade"}
            missing_labels = ", ".join(labels[column] for column in missing_metrics)
            st.warning(f"Métricas indisponíveis nesta sincronização: {missing_labels}. O Cinefy não substitui dados ausentes por valores neutros.")
        st.subheader("Duas linguagens, um mesmo repertório")
        left, right = st.columns(2)
        with left, st.container(border=True):
            card_title("headphones", "Som")
            st.metric("Assinatura musical", mood["headline"])
            st.metric("Energia média", format_percent(mood.get("energy")))
            st.metric("Valência média", format_percent(mood.get("valence")))
            st.metric("Dançabilidade", format_percent(mood.get("danceability")))
        with right, st.container(border=True):
            card_title("film", "Cinema")
            if genre_counts:
                dominant = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                st.markdown("".join(f"<span class='aero-pill'>{html.escape(genre)} · {count}</span>" for genre, count in dominant), unsafe_allow_html=True)
            else:
                st.warning("Os gêneros dos seus filmes ainda não foram preenchidos. Edite-os na aba Letterboxd.")
        if genre_counts:
            text = make_mood_mirror_text(mood, genre_counts)
            st.markdown(f"<div class='callout'><h3>Leitura estética do período</h3><p>{html.escape(text)}</p><small class='muted'>É uma interpretação lúdica dos seus dados, não uma avaliação psicológica.</small></div>", unsafe_allow_html=True)
            genre_df = pd.DataFrame([{"Gênero": k, "Filmes": v} for k, v in genre_counts.items()]).sort_values("Filmes", ascending=False)
            fig = px.pie(genre_df, names="Gênero", values="Filmes", hole=.48)
            aero_layout(fig, legend_title_text="Gêneros")
            st.plotly_chart(fig, width="stretch")

# --------------------------- inverse recommendations ------------------------
elif page == "Recomendação inversa":
    page_header("Powered by Music", "Descubra o que assistir com base nos artistas e gêneros que dominam seus fones.", "star")
    if music_df.empty:
        st.info("Sincronize seu Spotify primeiro.")
    elif films_df.empty:
        st.info("Importe também sua watchlist do Letterboxd para receber recomendações.")
    else:
        watchlist = films_df[films_df["is_watchlist"].fillna(False)].copy()
        if watchlist.empty:
            st.warning("Sua watchlist está vazia ou ainda não foi importada. Importe `watchlist.csv` do Letterboxd.")
        else:
            recommendations = inverse_recommendations(music_df, watchlist)
            st.subheader("Sua próxima sessão")
            if recommendations.empty:
                st.info("Ainda não há gêneros musicais ou métricas observadas suficientes para produzir recomendações. Sincronize novamente o Spotify ou aguarde dados disponíveis.")
            else:
                for idx, row in recommendations.head(8).iterrows():
                    year = f" ({int(row['year'])})" if pd.notna(row.get("year")) else ""
                    st.markdown(
                        f"<div class='glass-card'><div class='metric-label'>#{int(row['rank'])} · COMPATIBILIDADE ESTÉTICA {row['match_score']:.0%}</div>"
                        f"<h3 style='margin:.25rem 0'>{html.escape(str(row['title']))}{html.escape(year)}</h3>"
                        f"<span class='aero-pill'>{html.escape(str(row.get('genres') or 'Gêneros pendentes'))}</span>"
                        f"<p class='muted'>{html.escape(str(row['reason']))}</p></div>", unsafe_allow_html=True)

st.divider()
st.caption("Cinefy é um projeto pessoal experimental. Os resultados são leituras estéticas heurísticas, não classificações objetivas de obras ou pessoas.")
st.caption("Este produto utiliza a API do TMDB, mas não é endossado nem certificado pelo TMDB. Dados e imagens cinematográficas fornecidos por TMDB.")
