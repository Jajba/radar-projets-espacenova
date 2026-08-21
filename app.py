import os
import pandas as pd
import streamlit as st
from sqlalchemy import select, func, desc
from db import engine, init_db, sources, leads, errors, runs, documents

st.set_page_config(page_title='Radar Projets EspaceNova', page_icon='📡', layout='wide')
init_db()

def query_df(stmt):
    with engine.connect() as conn: return pd.read_sql(stmt, conn)

st.title('Radar Projets EspaceNova')
st.caption('Détection de signaux fonciers, immobiliers et d’investissement — avec preuve source obligatoire')

src=query_df(select(sources))
lds=query_df(select(leads).order_by(desc(leads.c.detected_at)))
err=query_df(select(errors).order_by(desc(errors.c.occurred_at)).limit(200))
rns=query_df(select(runs).order_by(desc(runs.c.started_at)).limit(20))
docs=query_df(select(documents))

active = int(src['active'].fillna(False).sum()) if len(src) else 0
last_run = rns.iloc[0] if len(rns) else None
c1,c2,c3,c4,c5=st.columns(5)
c1.metric('Sources actives', active)
c2.metric('Documents suivis', len(docs))
c3.metric('Leads', len(lds))
c4.metric('Priorité A', int((lds['commercial_score']=='A').sum()) if len(lds) else 0)
c5.metric('Erreurs récentes', len(err))
if last_run is not None:
    cov=f"{int(last_run['sources_ok'])}/{int(last_run['sources_total'])}"
    st.info(f"Dernier scan : couverture {cov} sources • {int(last_run['documents_new'])} nouveaux documents • {int(last_run['leads_new'])} nouveaux leads")

page=st.sidebar.radio('Navigation',['Leads','Sources','Documents','Erreurs','Historique scans','Règles qualité'])

if page=='Leads':
    if len(lds)==0:
        st.warning('Aucun lead en base pour le moment. Lance le crawler : python crawler.py --run-once')
    else:
        a,b,c=st.columns(3)
        scores=a.multiselect('Score',['A','B','C'],default=['A','B','C'])
        fams=sorted([x for x in lds['signal_family'].dropna().astype(str).unique()])
        families=b.multiselect('Famille',fams,default=fams)
        q=c.text_input('Entreprise / territoire / projet')
        f=lds.copy()
        if scores: f=f[f['commercial_score'].isin(scores)]
        if families: f=f[f['signal_family'].isin(families)]
        if q:
            mask=pd.Series(False,index=f.index)
            for col in ['company_sci','end_user','territory','commune','zone_site','project','facts','evidence_excerpt']:
                mask |= f[col].astype(str).str.contains(q,case=False,na=False)
            f=f[mask]
        show=['commercial_score','confidence_pct','company_sci','territory','signal_type','project','facts','evidence_excerpt','source_url','detected_at']
        st.dataframe(f[show],use_container_width=True,hide_index=True,column_config={'source_url':st.column_config.LinkColumn('Source')})
elif page=='Sources':
    st.dataframe(src,use_container_width=True,hide_index=True,column_config={'url':st.column_config.LinkColumn('URL')})
elif page=='Documents':
    st.dataframe(docs.sort_values('first_seen_at',ascending=False) if len(docs) else docs,use_container_width=True,hide_index=True,column_config={'url':st.column_config.LinkColumn('Document')})
elif page=='Erreurs':
    st.dataframe(err,use_container_width=True,hide_index=True,column_config={'url':st.column_config.LinkColumn('URL')})
elif page=='Historique scans':
    st.dataframe(rns,use_container_width=True,hide_index=True)
else:
    st.subheader('Règles anti-hallucination')
    st.markdown('''
- **FAIT** : uniquement ce qui est explicitement présent dans une source publique.
- **DÉDUCTION** : interprétation commerciale clairement marquée comme telle.
- **INCONNU** : reste **Non indiqué** ; aucune complétion par supposition.
- Un lead doit conserver **l’URL source et un extrait justificatif**.
- Les PDF non lisibles sont marqués **OCR_REQUIRED** au lieu d’être interprétés.
''')
