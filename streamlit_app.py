import json, re, unicodedata
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Revisão — Paripe/Tubarão", page_icon="🩺", layout="wide")

PASTA = Path(__file__).parent
LISTAS = ["Bahia Pesca A-88 (APEMJA)","Bahia Pesca Z-67","Ministério da Pesca (RGP)",
          "SEMOP Paripe (Ambulantes)","Vereadora Eliete (Pescadores)","Secretaria de Saúde (Moradores)",
          "Bahia Sem Fome (Beneficiários)"]
SRC = ["A-88","Z-67","Ministério","SEMOP","Vereadora","Saúde","Sem Fome"]
NUCLEO = {"São Tomé de Paripe","Tubarão"}
BASE_COLS = ["ID_Pessoa_Unico","Nome","CPF_Mascarado","Categoria_Principal","Todas_Categorias",
             "Bairro_Consolidado","Bairros_Todos","Logradouro","Faixa_Etaria","Sexo","Raca_Cor",
             "N_Listas","Listas_Origem"]
BAIRRO_XY = {
 "São Tomé de Paripe":[-12.8237,-38.4861],"Tubarão":[-12.8344,-38.4782],"Paripe":[-12.8417,-38.4679],
 "Paripe/Tubarão":[-12.8360,-38.4760],"Praia Grande":[-12.8727,-38.4774],"Plataforma":[-12.8946,-38.4831],
 "Periperi":[-12.8669,-38.4771],"Itacaranha":[-12.8855,-38.4834],"Coutos":[-12.8503,-38.4745],
 "Fazenda Coutos":[-12.8520,-38.4700],"Fazenda Coutos III":[-12.8540,-38.4690],
 "São João do Cabrito":[-12.9002,-38.4760],"Alto da Terezinha":[-12.8833,-38.4768],
 "Rio Sena":[-12.8900,-38.4790],"Nova Constituinte":[-12.8800,-38.4810],"Pirajá":[-12.8930,-38.4530]}

def sa(s): return "".join(c for c in unicodedata.normalize("NFKD",str(s or "")) if not unicodedata.combining(c)).upper()
def rua(l):
    t=re.split(r'\s*-\s*', sa(l).strip())[0]; t=re.split(r',',t)[0]
    t=re.sub(r'\bS/?N\b','',t); return re.sub(r'\s+',' ',t).strip()
def t(x): return "" if x is None else str(x).strip()

# ---------------------------------------------------------------- acesso
def porta():
    if st.session_state.get("ok"): return True
    st.title("🔒 Revisão da base — Paripe/Tubarão")
    st.caption("Ferramenta interna de uso restrito (LGPD).")
    pw = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar"):
        if pw == st.secrets.get("app_password",""):
            st.session_state["ok"]=True; st.rerun()
        else: st.error("Senha incorreta.")
    return False

@st.cache_resource
def planilha():
    info = json.loads(st.secrets["service_account_json"])
    scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
    creds=Credentials.from_service_account_info(info, scopes=scopes)
    return gscli(creds)
def gscli(creds):
    gc=gspread.authorize(creds); return gc.open(st.secrets["sheet_name"])

def ler(aba):
    return planilha().worksheet(aba).get_all_records()

@st.cache_data(ttl=120)
def geocoded():
    p = PASTA/"geocoded.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

# ---------------------------------------------------------------- painel ao vivo
def build_data(base, pend_dup):
    geo=geocoded()
    bairros,cats,faixas,sexos,racas,points,recs=[],[],[],[],[],[],[]
    pkey={}
    def idx(lst,v):
        if v not in lst: lst.append(v)
        return lst.index(v)
    def gp(lat,lon,label,street,bidx,nuc):
        k=f"{lat:.5f},{lon:.5f}"
        if k not in pkey: pkey[k]=len(points); points.append([lat,lon,label,1 if street else 0,1 if nuc else 0,bidx])
        return pkey[k]
    for p in base:
        bn=t(p.get("Bairro_Consolidado"))
        b=idx(bairros,bn or "(sem bairro)")
        c=idx(cats,t(p.get("Categoria_Principal")) or "(sem categoria)")
        fx=idx(faixas,t(p.get("Faixa_Etaria")) or "(n/d)")
        sx=idx(sexos,(t(p.get("Sexo")) or "(n/d)").title())
        rc=idx(racas,(t(p.get("Raca_Cor")) or "(n/d)").title())
        mask=0; ls=[x.strip() for x in t(p.get("Listas_Origem")).split(";")]
        for i,l in enumerate(LISTAS):
            if l in ls: mask|=(1<<i)
        pt=-1; lg=t(p.get("Logradouro"))
        if lg:
            key=f"{rua(lg)}|{bn}"
            if key in geo:
                lat,lon=geo[key]; pt=gp(lat,lon,rua(lg).title(),True,b,bn in NUCLEO)
        if pt==-1 and bn in BAIRRO_XY:
            lat,lon=BAIRRO_XY[bn]; pt=gp(lat,lon,bn+" (centro do bairro)",False,b,bn in NUCLEO)
        try: nl=int(p.get("N_Listas") or 1)
        except: nl=1
        recs.append([b,c,fx,sx,rc,nl,mask,pt])
    return dict(bairros=bairros,cats=cats,faixas=faixas,sexos=sexos,racas=racas,sources=SRC,
                sourcesFull=LISTAS,recs=recs,points=points,brutos=21282,
                dups=pend_dup,dupc={"Pendentes de revisão":pend_dup},geoStreets=len(geo))

def pagina_painel():
    st.subheader("📊 Painel da população afetada (ao vivo)")
    tpl = PASTA/"dashboard_template.html"
    if not tpl.exists():
        st.warning("Falta o 'dashboard_template.html' no repositório."); return
    with st.spinner("Carregando base da planilha..."):
        base = ler("Pessoas_Unicas")
        dup = ler("Revisar_Duplicidades")
        pend = sum(1 for r in dup if not t(r.get("Decisao")))
        DATA = build_data(base, pend)
    html = tpl.read_text(encoding="utf-8").replace("__DATA__", json.dumps(DATA, ensure_ascii=False))
    components.html(html, height=2400, scrolling=True)

# ---------------------------------------------------------------- revisão endereços
def pagina_enderecos(revisor):
    st.subheader("📍 Revisão de endereços")
    if "end" not in st.session_state:
        st.session_state.end_ws = planilha().worksheet("Revisar_Enderecos")
        st.session_state.end = st.session_state.end_ws.get_all_records()
    ws=st.session_state.end_ws; dados=st.session_state.end
    pend=[i for i,r in enumerate(dados) if not t(r.get("Decisao"))]
    st.progress((len(dados)-len(pend))/len(dados) if dados else 0,
                text=f"{len(dados)-len(pend)} de {len(dados)} revisadas · {len(pend)} pendentes")
    lista=pend if st.checkbox("Mostrar só pendentes",True) else list(range(len(dados)))
    if not lista: st.success("Tudo revisado! 🎉"); return
    pos=st.session_state.get("ep",0)%len(lista); i=lista[pos]; r=dados[i]; linha=i+2
    c1,c2=st.columns([3,2])
    with c1:
        st.markdown(f"### {r['Nome']}")
        st.write(f"**ID:** {r['ID_Pessoa']} · **CPF:** {r['CPF_Masc']}")
        st.write(f"**Categoria:** {r['Categoria']}")
        st.write(f"**Listas:** {r['Listas_Origem']}")
        if t(r.get('Decisao')): st.info(f"Já revisado: {r['Decisao']} · {r.get('Bairro_Confirmado','')}")
    with c2:
        sn=t(r.get('Sugestao_Nome_Saude'))
        st.markdown("#### Sugestão (por nome na base de Saúde)")
        if sn and sn!="(sem correspondência)":
            st.write(f"**Nome:** {sn}"); st.write(f"**Bairro:** {r.get('Sugestao_Bairro','')}")
            st.write(f"**Endereço:** {r.get('Sugestao_Endereco','')}")
            q=r.get('Qtd_Mesmo_Nome','')
            if str(q).isdigit() and int(q)>1: st.warning(f"⚠️ {q} pessoas com esse nome — possível homônimo.")
        else: st.write("_Sem correspondência automática._")
    bairro=st.text_input("Bairro confirmado", value=t(r.get('Sugestao_Bairro')), key=f"b{i}")
    obs=st.text_input("Observações", value=t(r.get('Observacoes')), key=f"o{i}")
    def salvar(dec, bf):
        d=datetime.now().strftime("%d/%m/%Y %H:%M"); vals=[dec,bf,revisor,d,obs]
        ws.update(range_name=f"K{linha}", values=[vals])
        for k,v in zip(["Decisao","Bairro_Confirmado","Revisor","Data_Revisao","Observacoes"],vals): dados[i][k]=v
        st.session_state.ep=pos+1; st.rerun()
    b1,b2,b3,b4=st.columns(4)
    if b1.button("✅ Confirmar",use_container_width=True,disabled=not revisor): salvar("Confirmar",bairro)
    if b2.button("❌ Rejeitar",use_container_width=True,disabled=not revisor): salvar("Rejeitar","")
    if b3.button("🚫 Não encontrado",use_container_width=True,disabled=not revisor): salvar("Não encontrado","")
    if b4.button("⏭️ Pular",use_container_width=True): st.session_state.ep=pos+1; st.rerun()
    if not revisor: st.caption("Informe seu nome na barra lateral para liberar os botões.")

# ---------------------------------------------------------------- revisão duplicidades
def pagina_duplicidades(revisor):
    st.subheader("👥 Revisão de duplicidades")
    if "dup" not in st.session_state:
        st.session_state.dup_ws = planilha().worksheet("Revisar_Duplicidades")
        st.session_state.dup = st.session_state.dup_ws.get_all_records()
    ws=st.session_state.dup_ws; dados=st.session_state.dup
    classes=["Provável duplicidade","Possível duplicidade","Precisa de revisão humana"]
    filtro=st.selectbox("Prioridade",["(todas)"]+classes,index=1)
    base=[i for i,r in enumerate(dados) if filtro=="(todas)" or r.get("Classificacao")==filtro]
    pend=[i for i in base if not t(dados[i].get("Decisao"))]
    feitas=sum(1 for r in dados if t(r.get("Decisao")))
    st.progress(feitas/len(dados) if dados else 0, text=f"{feitas} de {len(dados)} pares decididos")
    lista=pend if st.checkbox("Mostrar só pendentes",True) else base
    if not lista: st.success("Nada pendente neste filtro! 🎉"); return
    pos=st.session_state.get("dp",0)%len(lista); i=lista[pos]; r=dados[i]; linha=i+2
    st.caption(f"Par {r['Par_ID']} · {r['Classificacao']} · score {r['Score']}")
    c1,c2=st.columns(2)
    for col,suf in [(c1,"A"),(c2,"B")]:
        with col:
            st.markdown(f"#### Registro {suf}")
            st.write(f"**Nome:** {r['Nome_'+suf]}")
            st.write(f"**ID:** {r['ID_'+suf]} · **CPF:** {r['CPF_'+suf]}")
            st.write(f"**Listas:** {r['Listas_'+suf]}")
    st.write(f"Mesma nasc.: **{r['Mesma_Nasc']}** · Mesmo bairro: **{r['Mesmo_Bairro']}**")
    if t(r.get('Decisao')): st.info(f"Já decidido: {r['Decisao']}")
    def salvar(dec):
        d=datetime.now().strftime("%d/%m/%Y %H:%M")
        ws.update(range_name=f"O{linha}", values=[[dec,revisor,d]])
        for k,v in zip(["Decisao","Revisor","Data_Revisao"],[dec,revisor,d]): dados[i][k]=v
        st.session_state.dp=pos+1; st.rerun()
    b1,b2,b3=st.columns(3)
    if b1.button("🟰 Mesma pessoa",use_container_width=True,disabled=not revisor): salvar("Mesma pessoa")
    if b2.button("↔️ Pessoas diferentes",use_container_width=True,disabled=not revisor): salvar("Pessoas diferentes")
    if b3.button("⏭️ Pular",use_container_width=True): st.session_state.dp=pos+1; st.rerun()
    if not revisor: st.caption("Informe seu nome na barra lateral para liberar os botões.")

# ---------------------------------------------------------------- aplicar (o botão)
def aplicar_revisoes():
    sh=planilha()
    base=sh.worksheet("Pessoas_Unicas").get_all_records()
    end=sh.worksheet("Revisar_Enderecos").get_all_records()
    dup=sh.worksheet("Revisar_Duplicidades").get_all_records()
    people={t(r["ID_Pessoa_Unico"]):dict(r) for r in base}

    n_end=0
    for r in end:
        if t(r.get("Decisao")).lower().startswith("confirm"):
            pid=t(r.get("ID_Pessoa"))
            if pid in people:
                bairro=t(r.get("Bairro_Confirmado")) or t(r.get("Sugestao_Bairro"))
                if bairro:
                    people[pid]["Bairro_Consolidado"]=bairro
                    if not t(people[pid].get("Bairros_Todos")): people[pid]["Bairros_Todos"]=bairro
                if not t(people[pid].get("Logradouro")) and t(r.get("Sugestao_Endereco")):
                    people[pid]["Logradouro"]=t(r.get("Sugestao_Endereco"))
                n_end+=1

    parent={p:p for p in people}
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    n_pairs=0
    for r in dup:
        if t(r.get("Decisao")).lower().startswith("mesma"):
            a,b=t(r.get("ID_A")),t(r.get("ID_B"))
            if a in people and b in people:
                ra,rb=find(a),find(b)
                if ra!=rb: parent[rb]=ra
                n_pairs+=1
    grupos=defaultdict(list)
    for p in people: grupos[find(p)].append(p)

    def melhor(v): 
        v=[x for x in v if t(x)]; return max(v,key=lambda x:len(t(x))) if v else ""
    novas=[]; n_fund=0
    for ids in grupos.values():
        if len(ids)==1: novas.append(people[ids[0]]); continue
        n_fund+=len(ids)-1; regs=[people[i] for i in ids]
        ls=sorted(set(l.strip() for p in regs for l in t(p.get("Listas_Origem")).split(";") if l.strip()),
                  key=lambda x: LISTAS.index(x) if x in LISTAS else 99)
        bs=[t(p.get("Bairro_Consolidado")) for p in regs if t(p.get("Bairro_Consolidado"))]
        bairro=next((b for b in bs if b in NUCLEO), bs[0] if bs else "")
        cats=sorted(set(c.strip() for p in regs for c in t(p.get("Todas_Categorias")).split(";") if c.strip()))
        m=dict(max(regs,key=lambda p:len(t(p.get("Nome")))))
        m["Nome"]=melhor([p.get("Nome") for p in regs]); m["Bairro_Consolidado"]=bairro
        m["Bairros_Todos"]="; ".join(sorted(set(bs))); m["Todas_Categorias"]="; ".join(cats)
        m["Logradouro"]=melhor([p.get("Logradouro") for p in regs])
        m["Listas_Origem"]="; ".join(ls); m["N_Listas"]=len(ls)
        novas.append(m)
    novas.sort(key=lambda p:t(p.get("Nome")))
    for n,p in enumerate(novas,1): p["ID_Pessoa_Unico"]=f"P{n:05d}"

    # backup + sobrescrever a aba
    cur=sh.worksheet("Pessoas_Unicas").get_all_values()
    try: wsb=sh.worksheet("Pessoas_Unicas_Backup")
    except gspread.WorksheetNotFound: wsb=sh.add_worksheet("Pessoas_Unicas_Backup",rows=2,cols=2)
    wsb.clear(); wsb.update(range_name="A1", values=cur)
    matriz=[BASE_COLS]+[[t(p.get(c)) for c in BASE_COLS] for p in novas]
    wb=sh.worksheet("Pessoas_Unicas"); wb.clear()
    wb.update(range_name="A1", values=matriz, value_input_option="RAW")
    pend=sum(1 for r in dup if not t(r.get("Decisao")))
    return dict(end=n_end, pairs=n_pairs, fund=n_fund, antes=len(base), depois=len(novas), pend=pend)

def pagina_aplicar():
    st.subheader("⚙️ Atualizar base (aplicar revisões)")
    st.write("Aplica na base as decisões já registradas: confirma endereços e funde as duplicidades "
             "marcadas como **mesma pessoa**. Gera um **backup** automático antes de substituir.")
    st.info("Faça isso de tempos em tempos, depois que a equipe avançar nas revisões. "
            "O painel passa a refletir a base atualizada imediatamente.")
    ok=st.checkbox("Entendo que isso vai atualizar a base (há backup automático).")
    if st.button("🔄 Atualizar base agora", type="primary", disabled=not ok):
        with st.spinner("Aplicando decisões e gravando na planilha..."):
            try:
                r=aplicar_revisoes()
                st.cache_data.clear()
                st.success("Base atualizada com sucesso!")
                st.write(f"- Endereços confirmados aplicados: **{r['end']}**")
                st.write(f"- Pares 'mesma pessoa': **{r['pairs']}** → **{r['fund']}** registros fundidos")
                st.write(f"- Pessoas únicas: **{r['antes']} → {r['depois']}**")
                st.write(f"- Duplicidades ainda pendentes: **{r['pend']}**")
                st.caption("Abra a página 'Painel' para ver os números atualizados.")
            except Exception as e:
                st.error("Não consegui atualizar. Verifique se a aba 'Pessoas_Unicas' existe na planilha.")
                st.exception(e)

# ---------------------------------------------------------------- principal
def main():
    if not porta(): return
    with st.sidebar:
        st.header("Revisão Paripe/Tubarão")
        revisor=st.text_input("Seu nome (revisor)", key="revisor")
        pagina=st.radio("Página",["Painel","Endereços","Duplicidades","Atualizar base"])
        if st.button("🔄 Recarregar dados"):
            for k in ["end","end_ws","dup","dup_ws"]: st.session_state.pop(k,None)
            st.cache_data.clear(); st.rerun()
        if st.button("Sair"): st.session_state.clear(); st.rerun()
        st.caption("Decisões gravam direto na planilha do Google, visíveis para toda a equipe.")
    try:
        if pagina=="Painel": pagina_painel()
        elif pagina=="Endereços": pagina_enderecos(revisor)
        elif pagina=="Duplicidades": pagina_duplicidades(revisor)
        else: pagina_aplicar()
    except Exception as e:
        st.error("Erro ao acessar a planilha. Confira o compartilhamento com a conta de serviço, "
                 "o nome em 'sheet_name' e se as abas existem (Pessoas_Unicas, Revisar_Enderecos, Revisar_Duplicidades).")
        st.exception(e)

if __name__=="__main__":
    main()
