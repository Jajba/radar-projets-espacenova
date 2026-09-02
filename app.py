import re
import pandas as pd
import streamlit as st
from sqlalchemy import select, desc

from db import engine, init_db, sources, leads, errors, runs, documents


st.set_page_config(
    page_title='Radar Projets EspaceNova',
    page_icon='📡',
    layout='wide'
)

init_db()


def query_df(stmt):
    with engine.connect() as conn:
        return pd.read_sql(stmt, conn)


def safe(value, default='Non indiqué'):
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    value = str(value).strip()

    if not value or value.lower() in ('nan', 'none'):
        return default

    return value


def norm(value):
    value = safe(value, '').lower()

    value = (
        value
        .replace('é', 'e')
        .replace('è', 'e')
        .replace('ê', 'e')
        .replace('à', 'a')
        .replace('â', 'a')
        .replace('ç', 'c')
    )

    return re.sub(
        r'[^a-z0-9]+',
        ' ',
        value
    ).strip()


def prepare_opportunities(df):
    """
    Nettoyage d'affichage supplémentaire.

    Important :
    cela ne modifie pas PostgreSQL.
    Cela évite simplement d'afficher plusieurs
    fois le même signal dans le dashboard.
    """

    if df.empty:
        return df

    f = df.copy()

    score_rank = {
        'A': 3,
        'B': 2,
        'C': 1
    }

    f['_rank'] = (
        f['commercial_score']
        .map(score_rank)
        .fillna(0)
    )

    f['_company'] = (
        f['company_sci']
        .apply(norm)
    )

    f['_project'] = (
        f['project']
        .apply(norm)
    )

    f['_territory'] = (
        f['territory']
        .apply(norm)
    )

    f['_url'] = (
        f['source_url']
        .fillna('')
        .astype(str)
        .str.split('?')
        .str[0]
        .str.rstrip('/')
    )

    # Si entreprise + projet sont connus,
    # on regroupe les PDF parlant de la même affaire.
    def business_key(row):

        company = row['_company']
        project = row['_project']

        if (
            company
            and company != 'non indique'
            and project
            and project != 'non indique'
        ):
            return (
                'BUSINESS|'
                + row['_territory']
                + '|'
                + company
                + '|'
                + project
            )

        # Sinon au minimum :
        # un même document ne doit pas apparaître
        # vingt fois.
        return (
            'DOCUMENT|'
            + str(row['source_id'])
            + '|'
            + row['_url']
        )

    f['_business_key'] = f.apply(
        business_key,
        axis=1
    )

    f = f.sort_values(
        [
            '_rank',
            'confidence_pct',
            'detected_at'
        ],
        ascending=[
            False,
            False,
            False
        ]
    )

    f = f.drop_duplicates(
        subset=['_business_key'],
        keep='first'
    )

    return f.drop(
        columns=[
            '_rank',
            '_company',
            '_project',
            '_territory',
            '_url',
            '_business_key'
        ],
        errors='ignore'
    )


def score_icon(score):

    if score == 'A':
        return '🔥🔥🔥'

    if score == 'B':
        return '🔥🔥'

    return '🔥'


# -----------------------------------------------------
# Chargement
# -----------------------------------------------------

src = query_df(
    select(sources)
)

raw_leads = query_df(
    select(leads)
    .order_by(
        desc(leads.c.detected_at)
    )
)

lds = prepare_opportunities(
    raw_leads
)

err = query_df(
    select(errors)
    .order_by(
        desc(errors.c.occurred_at)
    )
    .limit(200)
)

rns = query_df(
    select(runs)
    .order_by(
        desc(runs.c.started_at)
    )
    .limit(20)
)

docs = query_df(
    select(documents)
)


# -----------------------------------------------------
# Header
# -----------------------------------------------------

st.title(
    '📡 Radar Projets EspaceNova'
)

st.caption(
    'Détection d’opportunités foncières, immobilières '
    'et d’investissement dans le Grand Est'
)


active = (
    int(
        src['active']
        .fillna(False)
        .sum()
    )
    if len(src)
    else 0
)

priority_a = (
    int(
        (
            lds['commercial_score']
            == 'A'
        ).sum()
    )
    if len(lds)
    else 0
)

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    'Sources actives',
    active
)

c2.metric(
    'Documents suivis',
    len(docs)
)

c3.metric(
    'Opportunités uniques',
    len(lds),
    delta=(
        f'{len(raw_leads) - len(lds)} doublons masqués'
        if len(raw_leads) > len(lds)
        else None
    )
)

c4.metric(
    'Priorité A',
    priority_a
)

c5.metric(
    'Erreurs récentes',
    len(err)
)


if len(rns):

    last_run = rns.iloc[0]

    cov = (
        f"{int(last_run['sources_ok'])}"
        f"/"
        f"{int(last_run['sources_total'])}"
    )

    st.info(
        f"📡 Dernier scan : "
        f"{cov} sources couvertes • "
        f"{int(last_run['documents_new'])} nouveaux documents • "
        f"{int(last_run['leads_new'])} nouvelles détections"
    )


# -----------------------------------------------------
# Navigation
# -----------------------------------------------------

page = st.sidebar.radio(
    'Navigation',
    [
        '🎯 Opportunités',
        '🌐 Sources',
        '📄 Documents',
        '⚠️ Erreurs',
        '📊 Historique scans',
        '🛡️ Règles qualité'
    ]
)


# -----------------------------------------------------
# OPPORTUNITÉS
# -----------------------------------------------------

if page == '🎯 Opportunités':

    st.subheader(
        'Opportunités commerciales'
    )

    if len(lds) == 0:

        st.warning(
            'Aucune opportunité détectée pour le moment.'
        )

    else:

        f1, f2, f3, f4 = st.columns(4)

        scores = f1.multiselect(
            'Priorité',
            ['A', 'B', 'C'],
            default=['A', 'B']
        )

        families_list = sorted(
            lds[
                'signal_family'
            ]
            .dropna()
            .astype(str)
            .unique()
        )

        families = f2.multiselect(
            'Famille',
            families_list,
            default=families_list
        )

        territories = sorted(
            lds[
                'territory'
            ]
            .dropna()
            .astype(str)
            .unique()
        )

        selected_territories = (
            f3.multiselect(
                'Territoire',
                territories
            )
        )

        q = f4.text_input(
            'Recherche'
        )

        f = lds.copy()

        if scores:

            f = f[
                f['commercial_score']
                .isin(scores)
            ]

        if families:

            f = f[
                f['signal_family']
                .isin(families)
            ]

        if selected_territories:

            f = f[
                f['territory']
                .isin(
                    selected_territories
                )
            ]

        if q:

            mask = pd.Series(
                False,
                index=f.index
            )

            for col in [
                'company_sci',
                'end_user',
                'territory',
                'commune',
                'zone_site',
                'project',
                'facts',
                'evidence_excerpt'
            ]:

                mask |= (
                    f[col]
                    .astype(str)
                    .str.contains(
                        q,
                        case=False,
                        na=False
                    )
                )

            f = f[mask]

        st.write(
            f"**{len(f)} opportunité(s) affichée(s)**"
        )

        # On évite de charger 500 blocs d'un coup.
        max_display = st.slider(
            'Nombre maximum de fiches affichées',
            10,
            100,
            30,
            step=10
        )

        f = f.head(
            max_display
        )

        # -------------------------------------------------
        # Une opportunité = une fiche
        # -------------------------------------------------

        for _, row in f.iterrows():

            score = safe(
                row['commercial_score'],
                'C'
            )

            company = safe(
                row['company_sci']
            )

            project = safe(
                row['project']
            )

            territory = safe(
                row['territory']
            )

            confidence = safe(
                row['confidence_pct'],
                '0'
            )

            title = (
                f"{score_icon(score)} "
                f"{score} — "
                f"{company} — "
                f"{project} — "
                f"{territory}"
            )

            with st.expander(
                title
            ):

                a, b, c, d = st.columns(4)

                a.metric(
                    'Priorité',
                    score
                )

                b.metric(
                    'Confiance',
                    f"{confidence}%"
                )

                c.write(
                    '**Territoire**'
                )

                c.write(
                    territory
                )

                d.write(
                    '**Type de signal**'
                )

                d.write(
                    safe(
                        row['signal_type']
                    )
                )

                st.markdown(
                    '### 🎯 Opportunité détectée'
                )

                st.write(
                    project
                )

                st.markdown(
                    '### 🏢 Porteur / entreprise'
                )

                st.write(
                    company
                )

                end_user = safe(
                    row['end_user']
                )

                if (
                    end_user
                    != 'Non indiqué'
                ):
                    st.write(
                        '**Utilisateur final :** '
                        + end_user
                    )

                st.markdown(
                    '### ✅ Faits extraits de la source'
                )

                st.write(
                    safe(
                        row['facts']
                    )
                )

                st.markdown(
                    '### 💡 Lecture commerciale'
                )

                st.write(
                    safe(
                        row['deductions']
                    )
                )

                st.markdown(
                    '### ❓ Informations à compléter'
                )

                st.write(
                    safe(
                        row['unknowns']
                    )
                )

                st.markdown(
                    '### 📌 Preuve'
                )

                st.info(
                    safe(
                        row['evidence_excerpt']
                    )
                )

                source_url = safe(
                    row['source_url'],
                    ''
                )

                if source_url:

                    st.markdown(
                        f"🔗 **[Ouvrir le document source]"
                        f"({source_url})**"
                    )

                st.caption(
                    'Détecté le : '
                    + safe(
                        row['detected_at']
                    )
                )

        st.divider()

        st.subheader(
            'Vue tableau'
        )

        show = [
            'commercial_score',
            'confidence_pct',
            'company_sci',
            'territory',
            'project',
            'signal_type',
            'source_url',
            'detected_at'
        ]

        st.dataframe(
            f[show],
            use_container_width=True,
            hide_index=True,
            column_config={
                'source_url':
                    st.column_config.LinkColumn(
                        'Source'
                    )
            }
        )


# -----------------------------------------------------
# SOURCES
# -----------------------------------------------------

elif page == '🌐 Sources':

    st.subheader(
        'Sources surveillées'
    )

    st.dataframe(
        src,
        use_container_width=True,
        hide_index=True,
        column_config={
            'url':
                st.column_config.LinkColumn(
                    'URL'
                )
        }
    )


# -----------------------------------------------------
# DOCUMENTS
# -----------------------------------------------------

elif page == '📄 Documents':

    st.subheader(
        'Documents suivis'
    )

    if len(docs):

        display_docs = (
            docs.sort_values(
                'first_seen_at',
                ascending=False
            )
        )

    else:

        display_docs = docs

    st.dataframe(
        display_docs,
        use_container_width=True,
        hide_index=True,
        column_config={
            'url':
                st.column_config.LinkColumn(
                    'Document'
                )
        }
    )


# -----------------------------------------------------
# ERREURS
# -----------------------------------------------------

elif page == '⚠️ Erreurs':

    st.subheader(
        'Erreurs techniques récentes'
    )

    st.dataframe(
        err,
        use_container_width=True,
        hide_index=True,
        column_config={
            'url':
                st.column_config.LinkColumn(
                    'URL'
                )
        }
    )


# -----------------------------------------------------
# RUNS
# -----------------------------------------------------

elif page == '📊 Historique scans':

    st.subheader(
        'Historique des scans'
    )

    st.dataframe(
        rns,
        use_container_width=True,
        hide_index=True
    )


# -----------------------------------------------------
# QUALITÉ
# -----------------------------------------------------

else:

    st.subheader(
        'Règles anti-hallucination'
    )

    st.markdown(
        '''
- **FAIT** : uniquement ce qui est explicitement présent dans une source publique.
- **DÉDUCTION** : interprétation commerciale clairement identifiée.
- **INCONNU** : reste **Non indiqué**.
- Une opportunité conserve obligatoirement **le document source**.
- Une opportunité affiche aussi **l’extrait ayant déclenché la détection**.
- Les PDF illisibles sont classés **OCR_REQUIRED**.
- Un même document ne doit produire qu'une opportunité principale.
- Plusieurs documents concernant la même entreprise et le même projet doivent être regroupés.
- La priorité **A** est réservée aux projets comportant des éléments concrets.
'''
    )
