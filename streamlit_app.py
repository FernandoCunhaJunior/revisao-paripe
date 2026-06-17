import json
from datetime import datetime

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Revisão — Paripe/Tubarão", page_icon="🩺", layout="wide")

NUCLEO = {"São Tomé de Paripe", "Tubarão"}

# ----------------------------------------------------------------------------
# Acesso (senha simples compartilhada)
# ----------------------------------------------------------------------------
def porta_de_entrada():
    if st.session_state.get("ok"):
        return True
    st.title("🔒 Revisão da base — Paripe/Tubarão")
    st.caption("Ferramenta interna de uso restrito (LGPD). Acesso somente da equipe autorizada.")
    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar"):
        if senha == st.secrets.get("app_password", ""):
            st.session_state["ok"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False

# ----------------------------------------------------------------------------
# Conexão com a planilha
# ----------------------------------------------------------------------------
@st.cache_resource
def conectar():
    info = json.loads(st.secrets["service_account_json"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open(st.secrets["sheet_name"])

def carregar(aba):
    sh = conectar()
    ws = sh.worksheet(aba)
    registros = ws.get_all_records()  # lista de dicts (linha 2 em diante)
    return ws, registros

def gravar(ws, linha_planilha, intervalo, valores):
    ws.update(range_name=f"{intervalo}{linha_planilha}", values=[valores])

# ----------------------------------------------------------------------------
# Páginas
# ----------------------------------------------------------------------------
def pagina_enderecos(revisor):
    st.subheader("📍 Revisão de endereços — pessoas sem morada informada")
    if "end_ws" not in st.session_state:
        ws, dados = carregar("Revisar_Enderecos")
        st.session_state.end_ws = ws
        st.session_state.end_dados = dados
    ws = st.session_state.end_ws
    dados = st.session_state.end_dados

    pendentes = [i for i, r in enumerate(dados) if not str(r.get("Decisao", "")).strip()]
    feitas = len(dados) - len(pendentes)
    st.progress(feitas / len(dados) if dados else 0,
                text=f"{feitas} de {len(dados)} revisadas · {len(pendentes)} pendentes")

    so_pendentes = st.checkbox("Mostrar só pendentes", value=True)
    lista = pendentes if so_pendentes else list(range(len(dados)))
    if not lista:
        st.success("Tudo revisado nesta aba! 🎉")
        return

    pos = st.session_state.get("end_pos", 0) % len(lista)
    i = lista[pos]
    r = dados[i]
    linha = i + 2  # linha real na planilha

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f"### {r['Nome']}")
        st.write(f"**ID:** {r['ID_Pessoa']}  ·  **CPF:** {r['CPF_Masc']}")
        st.write(f"**Categoria:** {r['Categoria']}")
        st.write(f"**Listas de origem:** {r['Listas_Origem']}")
        if str(r.get("Decisao", "")).strip():
            st.info(f"Já revisado: **{r['Decisao']}** · bairro {r['Bairro_Confirmado']} · {r['Revisor']}")
    with c2:
        st.markdown("#### Sugestão de endereço (por nome na base de Saúde)")
        sug_nome = str(r.get("Sugestao_Nome_Saude", ""))
        if sug_nome and sug_nome != "(sem correspondência)":
            st.write(f"**Nome correspondente:** {sug_nome}")
            st.write(f"**Bairro:** {r.get('Sugestao_Bairro','')}")
            st.write(f"**Endereço:** {r.get('Sugestao_Endereco','')}")
            st.write(f"**Confiança (nome):** {r.get('Score_Nome','')}")
            qtd = r.get("Qtd_Mesmo_Nome", "")
            if str(qtd).isdigit() and int(qtd) > 1:
                st.warning(f"⚠️ Há {qtd} pessoas com esse mesmo nome na base de Saúde — possível homônimo. Confirme com cuidado.")
        else:
            st.write("_Sem correspondência automática. Endereço precisa ser obtido manualmente._")

    st.divider()
    bairro = st.text_input("Bairro confirmado", value=str(r.get("Sugestao_Bairro", "")), key=f"b{i}")
    obs = st.text_input("Observações (opcional)", value=str(r.get("Observacoes", "")), key=f"o{i}")

    def salvar(decisao, bairro_final):
        impacto = ""
        if decisao == "Confirmar":
            impacto = "Direto" if bairro_final in NUCLEO else ("Indireto" if bairro_final else "")
        data = datetime.now().strftime("%d/%m/%Y %H:%M")
        valores = [decisao, bairro_final, impacto, revisor, data, obs]
        gravar(ws, linha, "K", valores)  # colunas K..P
        # atualiza cópia local
        for k, v in zip(["Decisao", "Bairro_Confirmado", "Impacto_Final", "Revisor", "Data_Revisao", "Observacoes"], valores):
            dados[i][k] = v
        st.session_state.end_pos = pos + 1
        st.rerun()

    b1, b2, b3, b4 = st.columns(4)
    if b1.button("✅ Confirmar sugestão", use_container_width=True, disabled=not revisor):
        salvar("Confirmar", bairro)
    if b2.button("❌ Rejeitar sugestão", use_container_width=True, disabled=not revisor):
        salvar("Rejeitar", "")
    if b3.button("🚫 Não encontrado", use_container_width=True, disabled=not revisor):
        salvar("Não encontrado", "")
    if b4.button("⏭️ Pular", use_container_width=True):
        st.session_state.end_pos = pos + 1
        st.rerun()
    if not revisor:
        st.caption("Informe seu nome na barra lateral para liberar os botões de decisão.")


def pagina_duplicidades(revisor):
    st.subheader("👥 Revisão de duplicidades — pares possivelmente da mesma pessoa")
    if "dup_ws" not in st.session_state:
        ws, dados = carregar("Revisar_Duplicidades")
        st.session_state.dup_ws = ws
        st.session_state.dup_dados = dados
    ws = st.session_state.dup_ws
    dados = st.session_state.dup_dados

    classes = ["Provável duplicidade", "Possível duplicidade", "Precisa de revisão humana"]
    filtro = st.selectbox("Prioridade (classificação)", ["(todas)"] + classes, index=1)
    base = [i for i, r in enumerate(dados)
            if filtro == "(todas)" or r.get("Classificacao") == filtro]
    pendentes = [i for i in base if not str(dados[i].get("Decisao", "")).strip()]
    feitas_total = sum(1 for r in dados if str(r.get("Decisao", "")).strip())
    st.progress(feitas_total / len(dados) if dados else 0,
                text=f"{feitas_total} de {len(dados)} pares decididos no total")

    lista = pendentes if st.checkbox("Mostrar só pendentes", value=True) else base
    if not lista:
        st.success("Nada pendente neste filtro! 🎉")
        return

    pos = st.session_state.get("dup_pos", 0) % len(lista)
    i = lista[pos]
    r = dados[i]
    linha = i + 2

    st.caption(f"Par {r['Par_ID']} · {r['Classificacao']} · {r['Tipo_Match']} · score {r['Score']}")
    c1, c2 = st.columns(2)
    for col, suf in [(c1, "A"), (c2, "B")]:
        with col:
            st.markdown(f"#### Registro {suf}")
            st.write(f"**Nome:** {r[f'Nome_{suf}']}")
            st.write(f"**ID:** {r[f'ID_{suf}']}  ·  **CPF:** {r[f'CPF_{suf}']}")
            st.write(f"**Listas:** {r[f'Listas_{suf}']}")
    st.write(f"Mesma data de nascimento: **{r['Mesma_Nasc']}** · Mesmo bairro: **{r['Mesmo_Bairro']}**")
    if str(r.get("Decisao", "")).strip():
        st.info(f"Já decidido: **{r['Decisao']}** ({r['Revisor']})")

    def salvar(decisao):
        data = datetime.now().strftime("%d/%m/%Y %H:%M")
        gravar(ws, linha, "O", [decisao, revisor, data])  # colunas O..Q
        for k, v in zip(["Decisao", "Revisor", "Data_Revisao"], [decisao, revisor, data]):
            dados[i][k] = v
        st.session_state.dup_pos = pos + 1
        st.rerun()

    b1, b2, b3 = st.columns(3)
    if b1.button("🟰 Mesma pessoa", use_container_width=True, disabled=not revisor):
        salvar("Mesma pessoa")
    if b2.button("↔️ Pessoas diferentes", use_container_width=True, disabled=not revisor):
        salvar("Pessoas diferentes")
    if b3.button("⏭️ Pular", use_container_width=True):
        st.session_state.dup_pos = pos + 1
        st.rerun()
    if not revisor:
        st.caption("Informe seu nome na barra lateral para liberar os botões.")


def pagina_resumo():
    st.subheader("📊 Progresso da revisão")
    for aba, rotulo in [("Revisar_Enderecos", "Endereços"), ("Revisar_Duplicidades", "Duplicidades")]:
        _, dados = carregar(aba)
        feitas = sum(1 for r in dados if str(r.get("Decisao", "")).strip())
        st.metric(rotulo, f"{feitas} / {len(dados)} revisados")
    st.caption("Atualize a página para puxar o estado mais recente da planilha.")


# ----------------------------------------------------------------------------
# Principal
# ----------------------------------------------------------------------------
def main():
    if not porta_de_entrada():
        return

    with st.sidebar:
        st.header("Revisão Paripe/Tubarão")
        revisor = st.text_input("Seu nome (revisor)", key="revisor")
        pagina = st.radio("Página", ["Endereços", "Duplicidades", "Resumo"])
        if st.button("🔄 Recarregar dados da planilha"):
            for k in ["end_ws", "end_dados", "dup_ws", "dup_dados"]:
                st.session_state.pop(k, None)
            st.rerun()
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()
        st.caption("As decisões são gravadas direto na planilha do Google e ficam visíveis para toda a equipe.")

    try:
        if pagina == "Endereços":
            pagina_enderecos(revisor)
        elif pagina == "Duplicidades":
            pagina_duplicidades(revisor)
        else:
            pagina_resumo()
    except Exception as e:
        st.error("Erro ao acessar a planilha. Verifique se ela foi compartilhada com o e-mail da conta de serviço como Editor, e se o nome em 'sheet_name' está exato.")
        st.exception(e)


if __name__ == "__main__":
    main()
