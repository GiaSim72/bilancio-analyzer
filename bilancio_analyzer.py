import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import base64

# ------------------------------
# CONFIGURAZIONE PAGINA STREAMLIT
# ------------------------------
st.set_page_config(
    page_title="Analisi Bilancio Professionale",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# FUNZIONI DI ELABORAZIONE DATI
# ------------------------------

@st.cache_data
def load_excel(file):
    """Carica il file Excel, filtra solo righe con TIPOCONTO = 'G' e pulisce."""
    df = pd.read_excel(file, sheet_name=0, header=1)
    df.columns = ['Mastro', 'DescrizioneMastro', 'Conto', 'DescrizioneConto',
                  'Importo', 'SEZBIL', 'ORDINE', 'TIPOCONTO', 'I']
    df = df[df['TIPOCONTO'] == 'G'].copy()
    df['Importo'] = pd.to_numeric(df['Importo'], errors='coerce').fillna(0)
    return df

def calcola_totale_sezione(df, sezione):
    return df[df['SEZBIL'] == sezione]['Importo'].sum()

def verifica_quadratura(df):
    tot_attivo = calcola_totale_sezione(df, 'A')
    tot_passivo = calcola_totale_sezione(df, 'P')
    tot_ricavi = calcola_totale_sezione(df, 'R')
    tot_costi = calcola_totale_sezione(df, 'C')
    utile = tot_ricavi - tot_costi
    diff_sp = tot_attivo - tot_passivo
    return {
        'Totale Attivo (A)': tot_attivo,
        'Totale Passivo (P)': tot_passivo,
        'Differenza SP': diff_sp,
        'Totale Ricavi (R)': tot_ricavi,
        'Totale Costi (C)': tot_costi,
        'Utile/Perdita': utile
    }

# MAPPATURE
SP_MAP = {
    '01010': ('Attivo Circolante', 'Liquidità immediate'),
    '01020': ('Attivo Circolante', 'Liquidità immediate'),
    '01025': ('Attivo Immobilizzato', 'Immobilizzazioni finanziarie'),
    '01030': ('Attivo Immobilizzato', 'Immobilizzazioni finanziarie'),
    '01040': ('Attivo Circolante', 'Crediti vs clienti'),
    '01050': ('Attivo Circolante', 'Crediti vs altri'),
    '01060': ('Attivo Circolante', 'Rimanenze'),
    '01061': ('Attivo Circolante', 'Rimanenze'),
    '01070': ('Attivo Immobilizzato', 'Immobilizzazioni materiali'),
    '01080': ('Attivo Immobilizzato', 'Immobilizzazioni immateriali'),
    '01090': ('Attivo Circolante', 'Ratei e risconti attivi'),
    '01100': ('Attivo Circolante', 'Crediti tributari'),
    '02010': ('Passivo Corrente', 'Debiti vs fornitori'),
    '02020': ('Passivo Corrente', 'Debiti tributari'),
    '02030': ('Passivo Corrente', 'Debiti vs banche'),
    '02040': ('Passivo Corrente', 'Debiti vs banche'),
    '02050': ('Passivo Corrente', 'Altri debiti (dipendenti)'),
    '02060': ('Passivo Corrente', 'Debiti tributari e previdenziali'),
    '02061': ('Passivo Corrente', 'Debiti tributari e previdenziali'),
    '02070': ('Passivo Corrente', 'Altri debiti (diversi)'),
    '02080': ('Passivo Corrente', 'Debiti tributari'),
    '02100': ('Passivo Consolidato', 'Fondi rischi e oneri'),
    '02110': ('Attivo Immobilizzato', 'F.do ammortamento'),
    '02120': ('Passivo Consolidato', 'F.do TFR'),
    '02200': ('Patrimonio Netto', 'Capitale e riserve'),
    '02130': ('Passivo Corrente', 'Ratei e risconti passivi'),
}

CE_MAP = {
    '04010': 'Ricavi',
    '04013': 'Ricavi',
    '04015': 'Ricavi',
    '04030': 'Ricavi',
    '03010': 'Acquisti',
    '03015': 'Acquisti',
    '03020': 'Rimanenze iniziali',
    '04080': 'Rimanenze finali',
    '03060': 'Costo personale diretto',
    '03030': 'Costi commerciali/amm/ge',
    '03040': 'Costi commerciali/amm/ge',
    '03050': 'Costi commerciali/amm/ge',
    '03061': 'Costi commerciali/amm/ge',
    '03062': 'Costi commerciali/amm/ge',
    '03100': 'Costi commerciali/amm/ge',
    '03075': 'Accantonamenti',
    '03070': 'Ammortamenti',
    '03080': 'Oneri finanziari',
    '03090': 'Oneri finanziari',
    '04020': 'Proventi finanziari',
}

def get_prefisso(conto):
    s = str(conto).strip()
    return s[:5] if len(s) >= 5 else s

def riclassifica_sp(df, perc_breve_banche=0.1):
    sp = {
        'Attivo Immobilizzato': {},
        'Attivo Circolante': {},
        'Passivo Corrente': {},
        'Passivo Consolidato': {},
        'Patrimonio Netto': {}
    }
    f_amm = 0.0
    crediti_tributari = 0.0

    for _, row in df.iterrows():
        conto = row['Conto']
        importo = row['Importo']
        sezbil = row['SEZBIL']
        pref = get_prefisso(conto)

        if pref == '02020' and importo < 0:
            crediti_tributari += abs(importo)
            continue

        if pref in SP_MAP:
            macro, sotto = SP_MAP[pref]

            if pref == '02110':
                f_amm += importo
                continue

            if pref in ['02030', '02040']:
                quota_breve = importo * perc_breve_banche
                quota_ml = importo - quota_breve
                if 'Debiti vs banche' not in sp['Passivo Corrente']:
                    sp['Passivo Corrente']['Debiti vs banche'] = 0
                sp['Passivo Corrente']['Debiti vs banche'] += quota_breve
                if 'Debiti vs banche ML' not in sp['Passivo Consolidato']:
                    sp['Passivo Consolidato']['Debiti vs banche ML'] = 0
                sp['Passivo Consolidato']['Debiti vs banche ML'] += quota_ml
                continue

            if macro not in sp:
                sp[macro] = {}
            if sotto not in sp[macro]:
                sp[macro][sotto] = 0
            sp[macro][sotto] += importo

    if crediti_tributari > 0:
        if 'Crediti tributari' not in sp['Attivo Circolante']:
            sp['Attivo Circolante']['Crediti tributari'] = 0
        sp['Attivo Circolante']['Crediti tributari'] += crediti_tributari

    if 'Immobilizzazioni materiali' in sp['Attivo Immobilizzato']:
        sp['Attivo Immobilizzato']['Immobilizzazioni materiali'] -= f_amm

    totali = {macro: sum(sp[macro].values()) for macro in sp}
    return sp, totali

def riclassifica_ce(df):
    gruppi = {}
    for _, row in df.iterrows():
        conto = row['Conto']
        importo = row['Importo']
        sezbil = row['SEZBIL']
        pref = get_prefisso(conto)

        if pref in CE_MAP:
            voce = CE_MAP[pref]
            if voce not in gruppi:
                gruppi[voce] = 0
            if sezbil == 'R':
                gruppi[voce] += importo
            else:
                gruppi[voce] -= importo

    ricavi = gruppi.get('Ricavi', 0)
    rim_iniz = gruppi.get('Rimanenze iniziali', 0)
    rim_fin = gruppi.get('Rimanenze finali', 0)
    var_rim = rim_fin - rim_iniz
    valore_produzione = ricavi + var_rim

    acquisti = gruppi.get('Acquisti', 0)
    costo_personale_dir = gruppi.get('Costo personale diretto', 0)
    costo_del_venduto = acquisti + costo_personale_dir

    margine_industriale = valore_produzione - costo_del_venduto
    costi_commerciali = gruppi.get('Costi commerciali/amm/ge', 0)
    ebitda = margine_industriale - costi_commerciali
    ammortamenti = gruppi.get('Ammortamenti', 0)
    accantonamenti = gruppi.get('Accantonamenti', 0)
    ebit = ebitda - ammortamenti - accantonamenti
    oneri_fin = gruppi.get('Oneri finanziari', 0)
    prov_fin = gruppi.get('Proventi finanziari', 0)
    saldo_fin = prov_fin - oneri_fin
    risultato_ante_imposte = ebit + saldo_fin

    tot_ricavi = calcola_totale_sezione(df, 'R')
    tot_costi = calcola_totale_sezione(df, 'C')
    utile_netto = tot_ricavi - tot_costi

    ce = {
        'Ricavi': ricavi,
        'Variazione rimanenze': var_rim,
        'Valore della produzione': valore_produzione,
        'Acquisti': acquisti,
        'Costo personale diretto': costo_personale_dir,
        'Costo del venduto': costo_del_venduto,
        'Margine industriale': margine_industriale,
        'Costi commerciali/amm/ge': costi_commerciali,
        'EBITDA': ebitda,
        'Ammortamenti': ammortamenti,
        'Accantonamenti': accantonamenti,
        'EBIT': ebit,
        'Saldo gestione finanziaria': saldo_fin,
        'Risultato ante imposte': risultato_ante_imposte,
        'Utile netto (da quadratura)': utile_netto
    }
    return ce

def calcola_kpi(sp_totali, sp_dett, ce, quadratura):
    att_circ = sp_totali.get('Attivo Circolante', 0)
    pass_corr = sp_totali.get('Passivo Corrente', 0)
    liquidita_imm = sp_dett['Attivo Circolante'].get('Liquidità immediate', 0)
    crediti_vs_clienti = sp_dett['Attivo Circolante'].get('Crediti vs clienti', 0)
    crediti_vs_altri = sp_dett['Attivo Circolante'].get('Crediti vs altri', 0)
    crediti_trib = sp_dett['Attivo Circolante'].get('Crediti tributari', 0)
    liquidita_diff = crediti_vs_clienti + crediti_vs_altri + crediti_trib
    rimanenze = sp_dett['Attivo Circolante'].get('Rimanenze', 0)
    pn = sp_totali.get('Patrimonio Netto', 0)
    pass_cons = sp_totali.get('Passivo Consolidato', 0)
    ricavi = ce.get('Ricavi', 0)
    ebitda = ce.get('EBITDA', 0)
    ebit = ce.get('EBIT', 0)
    utile = quadratura['Utile/Perdita']
    oneri_fin = ce.get('Oneri finanziari', 0)
    if oneri_fin < 0:
        oneri_fin = abs(oneri_fin)
    tot_attivo = sp_totali.get('Attivo Immobilizzato', 0) + sp_totali.get('Attivo Circolante', 0)
    costo_venduto = ce.get('Costo del venduto', 0)

    kpi = {
        'Current ratio': att_circ / pass_corr if pass_corr != 0 else np.inf,
        'Quick ratio': (liquidita_imm + liquidita_diff) / pass_corr if pass_corr != 0 else np.inf,
        'Giorni credito': (crediti_vs_clienti / ricavi * 365) if ricavi != 0 else 0,
        'Leverage': (pass_corr + pass_cons) / pn if pn != 0 else np.inf,
        'Copertura oneri finanziari': ebitda / oneri_fin if oneri_fin != 0 else np.inf,
        'ROE': utile / pn if pn != 0 else 0,
        'ROI': ebit / tot_attivo if tot_attivo != 0 else 0,
        'ROS': ebit / ricavi if ricavi != 0 else 0,
        'Rotazione magazzino': costo_venduto / rimanenze if rimanenze != 0 else 0
    }

    soglie = {
        'Current ratio': [2, 1.5],
        'Quick ratio': [1, 0.7],
        'Giorni credito': [60, 90],
        'Leverage': [2, 3],
        'Copertura oneri finanziari': [5, 3],
        'ROE': [0.1, 0.05],
        'ROI': [0.08, 0.04],
        'ROS': [0.05, 0.02],
        'Rotazione magazzino': [6, 3]
    }

    semafori = {}
    for k, v in kpi.items():
        soglia_verde, soglia_gialla = soglie[k]
        if k in ['Giorni credito', 'Leverage']:
            if v <= soglia_verde:
                semafori[k] = '🟢'
            elif v <= soglia_gialla:
                semafori[k] = '🟡'
            else:
                semafori[k] = '🔴'
        else:
            if v >= soglia_verde:
                semafori[k] = '🟢'
            elif v >= soglia_gialla:
                semafori[k] = '🟡'
            else:
                semafori[k] = '🔴'
    return kpi, semafori

# ------------------------------
# INTERFACCIA STREAMLIT
# ------------------------------
def main():
    st.sidebar.title("📁 Caricamento Bilanci")
    uploaded_files = st.sidebar.file_uploader(
        "Carica uno o più file Excel",
        type=['xlsx'],
        accept_multiple_files=True
    )

    if 'dataframes' not in st.session_state:
        st.session_state.dataframes = {}
    if 'quadrature' not in st.session_state:
        st.session_state.quadrature = {}
    if 'sp' not in st.session_state:
        st.session_state.sp = {}
    if 'ce' not in st.session_state:
        st.session_state.ce = {}
    if 'kpi' not in st.session_state:
        st.session_state.kpi = {}

    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.dataframes:
                df = load_excel(file)
                st.session_state.dataframes[file.name] = df
                st.session_state.quadrature[file.name] = verifica_quadratura(df)
                sp_dett, sp_totali = riclassifica_sp(df, perc_breve_banche=0.1)
                st.session_state.sp[file.name] = (sp_dett, sp_totali)
                ce = riclassifica_ce(df)
                st.session_state.ce[file.name] = ce
                kpi, semafori = calcola_kpi(sp_totali, sp_dett, ce, st.session_state.quadrature[file.name])
                st.session_state.kpi[file.name] = (kpi, semafori)

    st.title("📋 Dashboard di Analisi Bilancio")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.button("📤 Carica file", disabled=True, help="Usa il pannello laterale")
    with col2:
        if st.button("🏦 SP Riclassificato"):
            st.session_state.pagina = "SP"
    with col3:
        if st.button("📉 CE Costo del venduto"):
            st.session_state.pagina = "CE"
    with col4:
        if st.button("📊 KPI e Semafori"):
            st.session_state.pagina = "KPI"
    with col5:
        if st.button("🔄 Confronto"):
            st.session_state.pagina = "CONFRONTO"
    with col6:
        if st.button("📄 Report CEO"):
            st.session_state.pagina = "REPORT"

    col_q = st.columns([1,5])
    with col_q[0]:
        if st.button("✅ Verifica quadratura"):
            st.session_state.pagina = "QUADRATURA"

    if 'pagina' not in st.session_state:
        st.session_state.pagina = "HOME"

    # HOME
    if st.session_state.pagina == "HOME":
        st.header("Benvenuto nell'analisi professionale di bilancio")
        st.markdown("""
        Questa dashboard ti consente di:
        - **Caricare** i file Excel estratti dal gestionale.
        - **Riclassificare** automaticamente Stato Patrimoniale (criterio finanziario) e Conto Economico (costo del venduto).
        - **Visualizzare** i dettagli dei conti che compongono ogni aggregato.
        - **Calcolare** i principali KPI con semafori immediati.
        - **Confrontare** più periodi.
        - **Generare** un report PDF professionale per il CEO.

        **Istruzioni**: utilizza il pannello laterale per caricare uno o più file. Poi clicca sui pulsanti sopra per esplorare le analisi.
        """)
        if st.session_state.dataframes:
            st.success(f"✅ {len(st.session_state.dataframes)} file caricati: {', '.join(st.session_state.dataframes.keys())}")
        else:
            st.info("📂 Nessun file caricato. Inizia dal pannello laterale.")

    # STATO PATRIMONIALE
    elif st.session_state.pagina == "SP":
        st.header("🏦 Stato Patrimoniale - Riclassificazione Finanziaria")
        if not st.session_state.sp:
            st.warning("Carica almeno un file prima di visualizzare.")
        else:
            nome_file = st.selectbox("Seleziona il file", list(st.session_state.sp.keys()))
            sp_dett, sp_totali = st.session_state.sp[nome_file]
            for macro, classi in sp_dett.items():
                with st.expander(f"{macro} - Totale € {sp_totali[macro]:,.2f}", expanded=True):
                    df_macro = pd.DataFrame([
                        {"Sottoclasse": sotto, "Importo (€)": importo}
                        for sotto, importo in classi.items()
                    ])
                    st.dataframe(df_macro.style.format({"Importo (€)": "{:,.2f}"}), use_container_width=True)
                    if st.button(f"🔍 Vedi conti origine per {macro}", key=f"drill_{macro}_{nome_file}"):
                        df_orig = st.session_state.dataframes[nome_file]
                        conti_mostra = []
                        for _, row in df_orig.iterrows():
                            pref = get_prefisso(row['Conto'])
                            if pref in SP_MAP:
                                m, s = SP_MAP[pref]
                                if m == macro and s in classi:
                                    if pref in ['02110','02030','02040']:
                                        continue
                                    conti_mostra.append({
                                        'Conto': row['Conto'],
                                        'Descrizione': row['DescrizioneConto'],
                                        'Importo': row['Importo']
                                    })
                        if conti_mostra:
                            st.write("**Conti che compongono la macroclasse:**")
                            st.dataframe(pd.DataFrame(conti_mostra).style.format({"Importo": "{:,.2f}"}))
                        else:
                            st.info("Nessun conto dettagliato (alcune voci sono calcoli interni).")
            tot_attivo = sp_totali.get('Attivo Immobilizzato',0) + sp_totali.get('Attivo Circolante',0)
            tot_passivo_pn = sp_totali.get('Passivo Corrente',0) + sp_totali.get('Passivo Consolidato',0) + sp_totali.get('Patrimonio Netto',0)
            st.metric("Totale Attivo", f"€ {tot_attivo:,.2f}")
            st.metric("Totale Passivo + PN", f"€ {tot_passivo_pn:,.2f}")

    # CONTO ECONOMICO
    elif st.session_state.pagina == "CE":
        st.header("📉 Conto Economico - Schema a Costo del Venduto")
        if not st.session_state.ce:
            st.warning("Carica almeno un file.")
        else:
            nome_file = st.selectbox("Seleziona il file", list(st.session_state.ce.keys()))
            ce = st.session_state.ce[nome_file]
            df_ce = pd.DataFrame(list(ce.items()), columns=["Voce", "Importo"])
            st.dataframe(df_ce.style.format({"Importo": "{:,.2f}"}), use_container_width=True)
            voci_graf = ["Ricavi", "Valore della produzione", "Margine industriale", "EBITDA", "EBIT", "Utile netto (da quadratura)"]
            df_graf = df_ce[df_ce["Voce"].isin(voci_graf)].copy()
            if not df_graf.empty:
                fig = px.bar(df_graf, x="Voce", y="Importo", title="Confronto principali grandezze economiche")
                st.plotly_chart(fig, use_container_width=True)
            if st.button("🔍 Mostra dettaglio conti per voce"):
                df_orig = st.session_state.dataframes[nome_file]
                conti_dettaglio = []
                for _, row in df_orig.iterrows():
                    pref = get_prefisso(row['Conto'])
                    if pref in CE_MAP:
                        voce = CE_MAP[pref]
                        segno = 1 if row['SEZBIL'] == 'R' else -1
                        conti_dettaglio.append({
                            'Voce CE': voce,
                            'Conto': row['Conto'],
                            'Descrizione': row['DescrizioneConto'],
                            'Importo originale': row['Importo'],
                            'Importo con segno': row['Importo'] * segno
                        })
                if conti_dettaglio:
                    st.dataframe(pd.DataFrame(conti_dettaglio).style.format({"Importo originale": "{:,.2f}", "Importo con segno": "{:,.2f}"}))

    # KPI
    elif st.session_state.pagina == "KPI":
        st.header("📊 KPI e Semafori")
        if not st.session_state.kpi:
            st.warning("Carica almeno un file.")
        else:
            nome_file = st.selectbox("Seleziona il file", list(st.session_state.kpi.keys()))
            kpi, semafori = st.session_state.kpi[nome_file]
            cols = st.columns(3)
            i = 0
            for k, v in kpi.items():
                with cols[i % 3]:
                    st.metric(k, f"{v:.2f}", delta=semafori[k])
                    i += 1

    # CONFRONTO
    elif st.session_state.pagina == "CONFRONTO":
        st.header("🔄 Confronto tra bilanci")
        if len(st.session_state.dataframes) < 2:
            st.warning("Carica almeno due file per il confronto.")
        else:
            files = list(st.session_state.dataframes.keys())
            df_conf = pd.DataFrame()
            for f in files:
                kpi, _ = st.session_state.kpi[f]
                df_conf[f] = pd.Series(kpi)
            df_conf = df_conf.T
            st.dataframe(df_conf.style.format("{:.2f}"))
            fig = px.line(df_conf.T, title="Andamento KPI")
            st.plotly_chart(fig, use_container_width=True)

    # REPORT CEO (versione semplificata senza PDF)
    elif st.session_state.pagina == "REPORT":
        st.header("📄 Report per il CEO (anteprima HTML)")
        if not st.session_state.dataframes:
            st.warning("Carica almeno un file.")
        else:
            nome_file = st.selectbox("Seleziona il file per il report", list(st.session_state.dataframes.keys()))
            if st.button("📥 Genera anteprima report"):
                sp_dett, sp_totali = st.session_state.sp[nome_file]
                ce = st.session_state.ce[nome_file]
                kpi, semafori = st.session_state.kpi[nome_file]
                quad = st.session_state.quadrature[nome_file]

                st.subheader("📊 Report Strategico di Bilancio")
                st.write(f"**File:** {nome_file}")
                st.write(f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")

                st.subheader("🔍 Sintesi KPI")
                kpi_df = pd.DataFrame(list(kpi.items()), columns=["Indice", "Valore"])
                kpi_df["Semaforo"] = kpi_df["Indice"].map(semafori)
                st.dataframe(kpi_df.style.format({"Valore": "{:.2f}"}))

                st.subheader("🏦 Stato Patrimoniale Riclassificato")
                sp_rows = []
                for macro, classi in sp_dett.items():
                    for sotto, importo in classi.items():
                        sp_rows.append({"Macroclasse": macro, "Sottoclasse": sotto, "Importo (€)": importo})
                sp_df = pd.DataFrame(sp_rows)
                st.dataframe(sp_df.style.format({"Importo (€)": "{:,.2f}"}))

                st.subheader("📉 Conto Economico a Costo del Venduto")
                ce_df = pd.DataFrame(list(ce.items()), columns=["Voce", "Importo"])
                st.dataframe(ce_df.style.format({"Importo": "{:,.2f}"}))

                st.subheader("💬 Commenti strategici")
                if kpi['Current ratio'] < 1.5:
                    st.warning("🔴 **Liquidità**: la capacità di far fronte agli impegni a breve è critica. Valutare un rafforzamento delle disponibilità liquide o una rinegoziazione dei debiti a breve.")
                elif kpi['Current ratio'] < 2:
                    st.info("🟡 **Liquidità**: adeguata, ma migliorabile riducendo i giorni di incasso o ottimizzando il magazzino.")
                else:
                    st.success("🟢 **Liquidità**: ottima solidità finanziaria a breve.")

                if kpi['ROE'] < 0.05:
                    st.warning("🔴 **Redditività**: il rendimento del capitale proprio è basso. Analizzare le cause e valutare piani di efficienza.")
                elif kpi['ROE'] < 0.1:
                    st.info("🟡 **Redditività**: nella media, ma con margini di miglioramento.")
                else:
                    st.success("🟢 **Redditività**: eccellente capacità di remunerare il capitale investito.")

                if kpi['Leverage'] > 3:
                    st.warning("🔴 **Indebitamento**: l'azienda è molto indebitata. Attenzione alla sostenibilità degli oneri finanziari.")
                elif kpi['Leverage'] > 2:
                    st.info("🟡 **Indebitamento**: moderato, monitorare la dinamica dei flussi di cassa.")
                else:
                    st.success("🟢 **Indebitamento**: equilibrio finanziario solido.")

                if kpi['Rotazione magazzino'] < 3:
                    st.warning("🔴 **Efficienza**: il magazzino ruota lentamente. Possibili eccessi di scorta o obsolescenza.")
                elif kpi['Rotazione magazzino'] < 6:
                    st.info("🟡 **Efficienza**: rotazione accettabile, ottimizzabile.")
                else:
                    st.success("🟢 **Efficienza**: eccellente gestione del magazzino.")

                st.info("💡 Per un report PDF professionale con grafici e layout, si consiglia di utilizzare la versione con WeasyPrint. Attualmente è attiva l'anteprima HTML.")

    # QUADRATURA
    elif st.session_state.pagina == "QUADRATURA":
        st.header("✅ Verifica Quadratura dei Dati")
        if not st.session_state.quadrature:
            st.warning("Nessun file caricato.")
        else:
            for nome, quad in st.session_state.quadrature.items():
                st.subheader(f"File: {nome}")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Totale Attivo (A)", f"€ {quad['Totale Attivo (A)']:,.2f}")
                    st.metric("Totale Passivo (P)", f"€ {quad['Totale Passivo (P)']:,.2f}")
                    diff_sp = quad['Differenza SP']
                    if abs(diff_sp) < 0.01:
                        st.success(f"Differenza SP: € {diff_sp:.2f} ✅")
                    else:
                        st.error(f"Differenza SP: € {diff_sp:.2f} ❌")
                with col2:
                    st.metric("Totale Ricavi (R)", f"€ {quad['Totale Ricavi (R)']:,.2f}")
                    st.metric("Totale Costi (C)", f"€ {quad['Totale Costi (C)']:,.2f}")
                    st.metric("Utile/Perdita", f"€ {quad['Utile/Perdita']:,.2f}")
                with st.expander("📋 Elenco conti con TIPOCONTO = G"):
                    df_orig = st.session_state.dataframes[nome]
                    st.dataframe(df_orig[['Conto','DescrizioneConto','Importo','SEZBIL']].style.format({"Importo":"{:,.2f}"}))

if __name__ == "__main__":
    main()