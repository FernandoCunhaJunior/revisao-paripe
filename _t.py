import sys, types, runpy
class Fake:
    def __init__(self,page,termo=""):
        self._page=page; self._termo=termo; self.sidebar=self; self.secrets={}; self.session_state={}
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def columns(self,n,*a,**k):
        n=n if isinstance(n,int) else len(n); return [self for _ in range(n)]
    def radio(self,l,o,*a,**k): return self._page
    def text_input(self,*a,**k): return self._termo
    def multiselect(self,*a,**k): return []
    def selectbox(self,l,o,*a,**k):
        o=list(o); return o[0] if o else 0
    def slider(self,l,lo,hi,val=None,*a,**k): return val if val is not None else (lo,hi)
    def cache_data(self,f): return f
    def set_page_config(self,*a,**k): return None
    def stop(self): raise SystemExit
    def __getattr__(self,n):
        def f(*a,**k): return None
        return f
def run(pg,termo=""):
    st=Fake(pg,termo); sys.modules["streamlit"]=st
    pdk=types.ModuleType("pydeck")
    for n in ["Layer","ViewState","Deck"]: setattr(pdk,n,lambda *a,**k:None)
    sys.modules["pydeck"]=pdk
    try: runpy.run_path("app.py",run_name="__main__"); return "OK"
    except SystemExit: return "OK(stop)"
    except Exception as e:
        import traceback; traceback.print_exc(); return f"ERRO {e}"
for pg in ["📊 Painel","🔎 Busca e filtros","🧾 Verificação individual","🗺️ Mapa da poligonal"]:
    print(pg,"->",run(pg))
print("Verif+termo ->", run("🧾 Verificação individual","MARIA"))
