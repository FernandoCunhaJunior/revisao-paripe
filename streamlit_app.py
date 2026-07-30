# -*- coding: utf-8 -*-
"""
Painel de Beneficiários — São Tomé de Paripe / Tubarão
App Streamlit para consultar a base consolidada, verificar a seleção dos 2.000
e visualizar a poligonal de 1.300 m.

Como executar (na sua máquina):
    pip install -r requirements.txt
    streamlit run app.py

Arquivos necessários na mesma pasta:
    app.py, app_data.csv, poligono.json
"""
import json
import re
import io
import unicodedata
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Beneficiários — São Tomé de Paripe", layout="wide")

DATA_CSV = "app_data.csv"
POLY_JSON = "poligono.json"
CORTE = 6.5


# ------------------------------------------------------------------ acesso (LGPD)
def checar_senha():
    """Tela de senha. Configure a senha em Settings > Secrets do Streamlit Cloud:
       app_password = "suaSenhaForte"
       Rodando localmente sem segredo definido, o acesso é liberado."""
    if "app_password" not in st.secrets:
        return True  # ambiente local/sem segredo
    if st.session_state.get("_ok"):
        return True
    st.title("🔒 Acesso restrito")
    st.caption("Dados pessoais (LGPD) — uso exclusivo da equipe do processo.")
    senha = st.text_input("Senha", type="password")
    if senha:
        if senha == st.secrets["app_password"]:
            st.session_state["_ok"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()


checar_senha()


def mascarar_cpf(cpf):
    s = str(cpf)
    if "*" in s:            # já vem mascarado do arquivo (repo público)
        return s
    d = re.sub(r"\D", "", s)
    if len(d) == 11:
        return f"***.***.{d[6:9]}-**"
    return "—" if not d else "***"

# ------------------------------------------------------------------ load
@st.cache_data
def carregar():
    df = pd.read_csv(DATA_CSV, dtype=str).fillna("")
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)
    df["fam_size"] = pd.to_numeric(df["fam_size"], errors="coerce").fillna(1).astype(int)
    df["idade_num"] = pd.to_numeric(df["idade"], errors="coerce")
    df["lat_num"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon_num"] = pd.to_numeric(df["lon"], errors="coerce")
    return df

@st.cache_data
def carregar_poly():
    import os
    for fn in (POLY_JSON, "poligonal.json"):
        if os.path.exists(fn):
            try:
                with open(fn, encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict) and d.get("polygon"):
                    if not d.get("center"):
                        lons = [p[0] for p in d["polygon"]]
                        lats = [p[1] for p in d["polygon"]]
                        d["center"] = [sum(lons) / len(lons), sum(lats) / len(lats)]
                    return d
            except Exception:
                pass
    return None

df = carregar()
poly = carregar_poly()

def semacento(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", s).strip()

def so_digitos(s):
    return re.sub(r"\D", "", str(s))

def to_excel_bytes(dataframe):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="dados")
    return buf.getvalue()

# ------------------------------------------------------------------ sidebar
st.sidebar.title("São Tomé de Paripe")
st.sidebar.caption("Base consolidada de beneficiários")
pagina = st.sidebar.radio(
    "Navegação",
    ["📊 Painel", "🔎 Busca e filtros", "🧾 Verificação individual", "🗺️ Mapa da poligonal"],
)
st.sidebar.markdown("---")
st.sidebar.metric("Pessoas na base", f"{len(df):,}".replace(",", "."))
st.sidebar.metric("Selecionados", f"{(df['selecionado']=='Sim').sum():,}".replace(",", "."))

COLS_TABELA = ["nome", "cpf", "cat", "atividade", "bairro", "dentro",
               "score", "selecionado", "fam", "fam_size", "telefone", "logradouro", "origem"]
RENAME = {"nome": "Nome", "cpf": "CPF", "cat": "Categoria", "atividade": "Atividade",
          "bairro": "Bairro", "dentro": "Poligonal", "score": "Score",
          "selecionado": "Selecionado", "fam": "ID Família", "fam_size": "Nº membros",
          "telefone": "Telefone", "logradouro": "Logradouro", "origem": "Listas de origem"}

# ================================================================== PAINEL
if pagina == "📊 Painel":
    st.title("📊 Painel geral")
    total = len(df)
    trab = int((df["worker"] == "True").sum())
    mor = total - trab
    dentro = int((df["dentro"] == "Dentro").sum())
    fam = df.loc[df["fam"] != "", "fam"].nunique()
    sel = int((df["selecionado"] == "Sim").sum())
    sel_trab = int(((df["selecionado"] == "Sim") & (df["worker"] == "True")).sum())
    if "grupo" in df.columns:
        g1 = int(df["grupo"].astype(str).str.startswith("1").sum())
    else:
        g1 = sel_trab
    g2 = sel - g1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pessoas únicas", f"{total:,}".replace(",", "."))
    c2.metric("Trabalhadores (perda de renda)", f"{trab:,}".replace(",", "."))
    c3.metric("Moradores", f"{mor:,}".replace(",", "."))
    c4.metric("Famílias identificadas", f"{fam:,}".replace(",", "."))
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Dentro da poligonal", f"{dentro:,}".replace(",", "."))
    c6.metric("Selecionados (2.000)", f"{sel:,}".replace(",", "."))
    c7.metric("Grupo 1 — perda de renda", f"{g1:,}".replace(",", "."))
    c8.metric("Grupo 2 — perda nutricional", f"{g2:,}".replace(",", "."))

    st.markdown("---")
    a, b = st.columns(2)
    with a:
        st.subheader("Por categoria")
        st.bar_chart(df["cat"].replace("", "—").value_counts())
    with b:
        st.subheader("Situação na poligonal")
        st.bar_chart(df["dentro"].replace("", "Indefinido").value_counts())

    a, b = st.columns(2)
    with a:
        st.subheader("Atividade (trabalhadores)")
        vc = df.loc[df["worker"] == "True", "atividade"].value_counts()
        st.bar_chart(vc)
    with b:
        st.subheader("Distribuição de score")
        st.bar_chart(df["score"].round().value_counts().sort_index())

# ================================================================== BUSCA / FILTROS
elif pagina == "🔎 Busca e filtros":
    st.title("🔎 Busca, filtros e exportação")

    termo = st.text_input("Buscar por nome ou CPF")
    f1, f2, f3, f4 = st.columns(4)
    cats = f1.multiselect("Categoria", sorted([c for c in df["cat"].unique() if c]))
    pols = f2.multiselect("Poligonal", ["Dentro", "Fora", "Indefinido"])
    sels = f3.multiselect("Selecionado", ["Sim", "Não"])
    bairros = f4.multiselect("Bairro", sorted([b for b in df["bairro"].unique() if b])[:200])
    smin, smax = st.slider("Faixa de score", 0.0, float(df["score"].max()), (0.0, float(df["score"].max())), 0.5)

    view = df.copy()
    if termo.strip():
        t = semacento(termo)
        td = so_digitos(termo)
        mask = view["nome"].map(semacento).str.contains(re.escape(t), na=False)
        if td:
            mask = mask | view["cpf"].str.contains(td, na=False)
        view = view[mask]
    if cats:
        view = view[view["cat"].isin(cats)]
    if pols:
        alvo = view["dentro"].replace("", "Indefinido")
        view = view[alvo.isin(pols)]
    if sels:
        view = view[view["selecionado"].isin(sels)]
    if bairros:
        view = view[view["bairro"].isin(bairros)]
    view = view[(view["score"] >= smin) & (view["score"] <= smax)]

    st.caption(f"{len(view):,} pessoa(s) encontrada(s)".replace(",", "."))
    tabela = view[COLS_TABELA].rename(columns=RENAME).copy()
    tabela["CPF"] = tabela["CPF"].map(mascarar_cpf)
    st.dataframe(tabela, use_container_width=True, height=460)

    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Baixar CSV (CPF mascarado)", tabela.to_csv(index=False).encode("utf-8"),
                       "recorte.csv", "text/csv")
    d2.download_button("⬇️ Baixar Excel (CPF mascarado)", to_excel_bytes(tabela),
                       "recorte.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ================================================================== VERIFICAÇÃO
elif pagina == "🧾 Verificação individual":
    st.title("🧾 Verificação individual")
    st.caption("Consulte uma pessoa e veja a pontuação, o domicílio e **por que entrou ou não** na seleção dos 2.000.")

    termo = st.text_input("Nome ou CPF da pessoa")
    if termo.strip():
        t = semacento(termo); td = so_digitos(termo)
        m = df["nome"].map(semacento).str.contains(re.escape(t), na=False)
        if td:
            m = m | df["cpf"].str.contains(td, na=False)
        cand = df[m]
        if len(cand) == 0:
            st.warning("Ninguém encontrado com esse nome/CPF.")
        else:
            rotulos = [f"{r['nome']} — CPF {mascarar_cpf(r['cpf']) if r['cpf'] else '(sem CPF)'} — {r['bairro'] or 's/ bairro'}"
                       for _, r in cand.iterrows()]
            i = st.selectbox("Selecione a pessoa", range(len(cand)), format_func=lambda k: rotulos[k])
            p = cand.iloc[i]

            sel = p["selecionado"] == "Sim"
            if sel:
                grupo_txt = str(p.get("grupo", "")).strip()
                st.success("✅ SELECIONADO(A) para a indenização" + (f" — {grupo_txt}" if grupo_txt else ""))
            else:
                st.error("❌ NÃO selecionado(a) nesta leva")
            st.write(f"**Motivo:** {p['motivo']}")

            # pendências de cadastro (a sanar) — não desclassificam, mas devem ser corrigidas
            pend = []
            if not str(p.get("cpf", "")).strip():
                pend.append("CPF ausente/inválido")
            if not str(p.get("nasc", "")).strip():
                pend.append("data de nascimento ausente")
            if sel and pend:
                st.warning("⚠️ **Selecionada, mas com cadastro a SANAR antes do pagamento:** "
                           + "; ".join(pend) + ". Regularize o(s) dado(s) para viabilizar a indenização.")
            if str(p.get("obs", "")).strip():
                st.caption("📝 Observações / irregularidades: " + str(p["obs"]))

            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Identificação**")
                st.write(f"Nome: {p['nome']}")
                st.write(f"CPF: {mascarar_cpf(p['cpf'])}")
                st.write(f"Nascimento: {p['nasc'] or '—'}  (idade: {p['idade'] or '—'})")
                st.write(f"Nome da mãe: {p['mae'] or '—'}")
            with c2:
                st.markdown("**Endereço / contato**")
                st.write(f"Logradouro: {p['logradouro'] or '—'}")
                st.write(f"Bairro: {p['bairro'] or '—'}  |  CEP: {p['cep'] or '—'}")
                st.write(f"Município: {p['municipio'] or '—'}")
                st.write(f"Telefone: {p['telefone'] or '—'}")
                st.write(f"Poligonal 1.300 m: **{p['dentro'] or 'Indefinido'}**")
            with c3:
                st.markdown("**Classificação**")
                st.write(f"Categoria: {p['cat'] or '—'}")
                st.write(f"Atividade: {p['atividade'] or '—'}")
                st.write(f"Bolsa Família: {'Sim' if p['pbf']=='True' else 'não consta'}")
                st.write(f"BPC: {'Sim' if p['bpc']=='True' else 'não consta'}")
                st.write(f"Tarifa social (Embasa): {'Sim' if p.get('tarifa_social')=='Sim' else 'não consta'}")
                st.write(f"Listas de origem: {p['origem'] or '—'}")

            st.markdown("---")
            colA, colB = st.columns([1, 1])
            with colA:
                st.markdown(f"**Pontuação de vulnerabilidade — total {p['score']}**")
                comp = json.loads(p["comp"])
                dfc = pd.DataFrame(
                    [{"Fator": k, "Pontos": v} for k, v in comp.items() if v]
                )
                if len(dfc):
                    st.table(dfc)
                else:
                    st.write("Sem fatores pontuados.")
                st.caption(f"Seleção por pontuação ponderada (1 titular por família). "
                           f"Nota de corte: {CORTE}.")
            with colB:
                st.markdown("**Domicílio / família**")
                fam = p["_fk"]
                membros = df[df["_fk"] == fam][["nome", "cpf", "cat", "score", "selecionado"]] \
                    .rename(columns={"nome": "Nome", "cpf": "CPF", "cat": "Categoria",
                                     "score": "Score", "selecionado": "Selecionado"}) \
                    .sort_values("Score", ascending=False)
                membros["CPF"] = membros["CPF"].map(mascarar_cpf)
                st.caption(f"{'Família ' + p['fam'] if p['fam'] else 'Sem família identificada (pessoa isolada)'} "
                           f"· {len(membros)} pessoa(s)")
                st.dataframe(membros, use_container_width=True, hide_index=True)

# ================================================================== MAPA
elif pagina == "🗺️ Mapa da poligonal":
    st.title("🗺️ Mapa da poligonal (raio 1.300 m)")
    st.caption("Polígono do KML e pessoas georreferenciadas (por logradouro). "
               "Pessoas sem coordenada não aparecem no mapa.")

    if not poly:
        st.warning("Arquivo do polígono (poligono.json) não encontrado no repositório — "
                   "o mapa fica indisponível, mas as demais páginas funcionam normalmente.")
        st.stop()

    modo = st.radio("Mostrar", ["Todos com coordenada", "Somente selecionados", "Dentro x Fora"],
                    horizontal=True)
    pts = df.dropna(subset=["lat_num", "lon_num"]).copy()
    if modo == "Somente selecionados":
        pts = pts[pts["selecionado"] == "Sim"]

    try:
        import pydeck as pdk

        def cor(row):
            if modo == "Somente selecionados":
                return [39, 174, 96]
            if row["selecionado"] == "Sim":
                return [39, 174, 96]
            if row["dentro"] == "Dentro":
                return [41, 128, 185]
            if row["dentro"] == "Fora":
                return [230, 126, 34]
            return [149, 165, 166]

        pts["cor"] = pts.apply(cor, axis=1)
        poly_layer = pdk.Layer(
            "PolygonLayer",
            data=[{"polygon": poly["polygon"]}],
            get_polygon="polygon",
            get_fill_color=[255, 0, 0, 30],
            get_line_color=[200, 0, 0],
            line_width_min_pixels=2,
            stroked=True, filled=True,
        )
        scatter = pdk.Layer(
            "ScatterplotLayer",
            data=pts,
            get_position="[lon_num, lat_num]",
            get_fill_color="cor",
            get_radius=25,
            pickable=True,
        )
        cx, cy = poly["center"]
        view = pdk.ViewState(latitude=cy, longitude=cx, zoom=13.2)
        st.pydeck_chart(pdk.Deck(
            layers=[poly_layer, scatter],
            initial_view_state=view,
            tooltip={"text": "{nome}\n{bairro}\nScore {score} — {selecionado}"},
            map_style="road",
        ))
        st.caption("🟢 selecionado · 🔵 dentro · 🟠 fora · ⚪ indefinido · contorno vermelho = poligonal 1.300 m")
    except Exception as e:  # fallback simples
        st.info("Mapa detalhado indisponível; exibindo pontos básicos.")
        st.map(pts.rename(columns={"lat_num": "lat", "lon_num": "lon"})[["lat", "lon"]])
        st.caption(f"({len(pts)} pontos) — detalhe: {e}")
