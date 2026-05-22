import streamlit as st
import pandas as pd
import random
import requests
import base64
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Marche Triomphale — Moteur Certifié", layout="wide", initial_sidebar_state="expanded")

FIGURES = ["RRR", "RRN", "RNR", "RNN", "NNN", "NNR", "NRN", "NRR"]

# --- CONNEXION CLOUD GITHUB ---
TOKEN = st.secrets.get("GITHUB_TOKEN", "")
REPO = st.secrets.get("GITHUB_REPO", "")
FILE_PATH = "permanence.txt"
URL_API = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

def charger_permanence_cloud():
    if not TOKEN or not REPO: return []
    headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(URL_API, headers=headers)
    if response.status_code == 200:
        donnees = response.json()
        contenu_base64 = donnees["content"]
        contenu_texte = base64.b64decode(contenu_base64).decode("utf-8")
        if contenu_texte.strip() == "": return []
        return [int(x) for x in contenu_texte.strip().split(",") if x != ""]
    return []

def sauvegarder_permanence_cloud(nouvelle_liste):
    if not TOKEN or not REPO: return
    headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
    contenu_texte = ",".join([str(x) for x in nouvelle_liste])
    contenu_base64 = base64.b64encode(contenu_texte.encode("utf-8")).decode("utf-8")
    response_get = requests.get(URL_API, headers=headers)
    sha = response_get.json()["sha"] if response_get.status_code == 200 else None
    data = {"message": "Mise à jour permanence", "content": contenu_base64}
    if sha: data["sha"] = sha
    requests.put(URL_API, headers=headers, data=json.dumps(data))

# --- STRUCTURE DU JOUEUR INDÉPENDANT ---
class JoueurGlissant:
    def __init__(self, id_j, chance_type, fig, dec):
        self.id = id_j
        self.chance_type = chance_type 
        self.fig = fig
        self.dec_initial = dec  # Sauvegarde pour réinitialisation à chaque carton
        self.dec_courant = dec  
        self.index_etape = 0
        self.statut = "JOUER"
        self.retard_constate = False
        self.solde_du_carton = 0  
        self.compteur_coups_carton = 0

    def intention(self):
        # Un joueur ne donne un ordre RÉEL que s'il a purgé son décalage,
        # s'il n'est pas suspendu (ARRET) et s'il est qualifié par son retard.
        if self.dec_courant > 0 or self.statut == "ARRET" or not self.retard_constate:
            return None
        return self.fig[self.index_etape]

    def actualiser(self, tirage_epure, est_zero):
        # Gestion stricte du décalage initial (Phase d'attente passive)
        if self.dec_courant > 0:
            if not est_zero: 
                self.dec_courant -= 1
            return

        gain_virtuel = 0
        if est_zero:
            # Le zéro impacte la comptabilité si le joueur est actif sur la table
            if self.statut == "JOUER" and self.retard_constate: 
                gain_virtuel = -0.5
        else:
            self.compteur_coups_carton += 1
            attendu = self.fig[self.index_etape]
            
            # Calcul du résultat du coup (commun au jeu réel et virtuel)
            if tirage_epure == attendu:
                gain_virtuel = 1
                # L'arrêt ne bloque le joueur que s'il mise de l'argent réel
                if self.retard_constate and self.statut == "JOUER":
                    self.index_etape += 1
                else:
                    self.index_etape += 1
            else:
                gain_virtuel = -1
                if self.retard_constate and self.statut == "JOUER":
                    self.statut = "ARRET"
                    self.index_etape += 1
                else:
                    self.index_etape += 1

        self.solde_du_carton += gain_virtuel

        # Cycle des figures de 3 coups
        if not est_zero and self.index_etape >= 3:
            self.index_etape = 0
            if self.retard_constate:
                self.statut = "JOUER"

        # CLÔTURE STRICTE DU CARTON DE 24 COUPS ÉPURÉS
        if not est_zero and self.compteur_coups_carton == 24:
            norme_du_carton = 3
            
            # Évaluation de la qualification pour le carton suivant
            self.retard_constate = self.solde_du_carton < norme_du_carton
            
            # Remise à zéro complète et application du décalage pour le prochain bloc
            self.solde_du_carton = 0
            self.compteur_coups_carton = 0
            self.dec_courant = self.dec_initial  # Rétablit l'asynchronisme de la vague
            self.index_etape = 0
            self.statut = "JOUER"

# --- CHARGEMENT INITIAL ---
if "historique" not in st.session_state:
    st.session_state.historique = charger_permanence_cloud()
if "capital_reel" not in st.session_state:
    st.session_state.capital_reel = 0.0

def analyser_numero(num):
    if num == 0: return "0", "0", "0"
    rouges = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    rn = "R" if num in rouges else "N"
    pi = "R" if num % 2 == 0 else "N"
    pm = "R" if num >= 19 else "N"
    return rn, pi, pm

# --- SIDEBAR ---
st.sidebar.header("⚙️ CONTRÔLE DE SESSION")
capital_placeholder = st.sidebar.empty()

st.sidebar.subheader("🗃️ Importation Externe")
import_txt = st.sidebar.text_area("Coller une série :", placeholder="Ex: 14,32,0,5")
if st.sidebar.button("📥 Forcer l'importation de masse", use_container_width=True):
    if import_txt:
        try:
            nettoye = import_txt.replace("\n", "").replace(" ", "")
            liste_numeros = [int(x) for x in nettoye.split(",") if x != ""]
            if all(0 <= n <= 36 for n in liste_numeros):
                st.session_state.historique.extend(liste_numeros)
                sauvegarder_permanence_cloud(st.session_state.historique)
                st.rerun()
        except ValueError: st.sidebar.error("Format incorrect.")

st.sidebar.write("---")
st.sidebar.subheader("🎲 Simulateur")
nb_sim = st.sidebar.number_input("Nombre de coups :", min_value=10, max_value=2000, value=100, step=100)
if st.sidebar.button(f"⚡ Injecter +{nb_sim} coups", use_container_width=True):
    st.session_state.historique.extend([random.randint(0, 36) for _ in range(nb_sim)])
    sauvegarder_permanence_cloud(st.session_state.historique)
    st.rerun()

st.sidebar.write("---")
st.sidebar.subheader("🚨 Zone de Danger")
confirm_reset = st.sidebar.checkbox("⚠️ Déverrouiller le bouton")
if confirm_reset:
    if st.sidebar.button("🔴 SUPPRIMER TOUT DU SERVEUR", use_container_width=True):
        st.session_state.historique = []
        sauvegarder_permanence_cloud([])
        st.rerun()

# --- CLAVIER DE SAISIE ---
st.subheader("📥 Enregistrer un numéro sorti au Casino")
cols_clavier = st.columns(13)
with cols_clavier[0]:
    if st.button("🟢 0", use_container_width=True):
        st.session_state.historique.append(0)
        sauvegarder_permanence_cloud(st.session_state.historique)
        st.rerun()

for n in range(1, 37):
    col_idx = ((n - 1) % 12) + 1
    rouges = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    label = f"🔴 {n}" if n in rouges else f"⚫ {n}"
    with cols_clavier[col_idx]:
        if st.button(label, use_container_width=True):
            st.session_state.historique.append(n)
            sauvegarder_permanence_cloud(st.session_state.historique)
            st.rerun()

# --- INSTANCIATION DE L'ARMÉE VIRTUELLES ---
armee_locale = {"RN": [], "PI": [], "PM": []}
id_j = 1
for chance in ["RN", "PI", "PM"]:
    for dec in [0, 1, 2]:
        for fig in FIGURES:
            armee_locale[chance].append(JoueurGlissant(id_j, chance, fig, dec))
            id_j += 1

capital_calcule = 0.0

# --- TOURNANT DE RECONSTRUCTION CHRONOLOGIQUE ---
for num in st.session_state.historique:
    rn, pi, pm = analyser_numero(num)
    est_zero = (num == 0)
    
    # 1. Collecte des intentions de mise AVANT la sortie du numéro
    mises_du_coup = {}
    for chance in ["RN", "PI", "PM"]:
        v_r = sum(1 for j in armee_locale[chance] if j.intention() == "R")
        v_n = sum(1 for j in armee_locale[chance] if j.intention() == "N")
        mises_du_coup[chance] = v_r - v_n

    # 2. Calcul des encaissements / décaissements réels
    for chance, (tirage_code, code_r, code_n) in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "R", "N"))]:
        net_mised = mises_du_coup[chance]
        if net_mised != 0:
            if est_zero:
                capital_calcule -= abs(net_mised) * 0.5
            elif (net_mised > 0 and tirage_code == code_r) or (net_mised < 0 and tirage_code == code_n):
                capital_calcule += abs(net_mised)
            else:
                capital_calcule -= abs(net_mised)

    # 3. Mise à jour de l'historique de chaque joueur
    for j in armee_locale["RN"]: j.actualiser(rn, est_zero)
    for j in armee_locale["PI"]: j.actualiser(pi, est_zero)
    for j in armee_locale["PM"]: j.actualiser(pm, est_zero)

st.session_state.capital_reel = capital_calcule

total_boules = len(st.session_state.historique)
zeros_purgés = sum(1 for x in st.session_state.historique if x == 0)
boules_epurees = total_boules - zeros_purgés

# Préparation du coup suivant
votes = {"RN": {"R": 0, "N": 0}, "PI": {"R": 0, "N": 0}, "PM": {"R": 0, "N": 0}}
for chance in ["RN", "PI", "PM"]:
    for j in armee_locale[chance]:
        intent = j.intention()
        if intent: votes[chance][intent] += 1

# Extraction des vrais qualifiés dynamiques
qualifies_rn = sum(1 for j in armee_locale["RN"] if j.retard_constate)
qualifies_pi = sum(1 for j in armee_locale["PI"] if j.retard_constate)
qualifies_pm = sum(1 for j in armee_locale["PM"] if j.retard_constate)

capital_placeholder.markdown(
    f"""
    ### 💰 **{st.session_state.capital_reel} p.**
    * Total boules : **{total_boules}**
    * Boules épurées : **{boules_epurees}**
    * ---
    * Joueurs qualifiés :
      * R/N : **{qualifies_rn}/24**
      * P/I : **{qualifies_pi}/24**
      * P/M : **{qualifies_pm}/24**
    """
)

# --- PANEL DES ORDRES DE JEU ---
st.header("🎯 ORDRES DE MISES POUR LE PROCHAIN COUP")

if boules_epurees < 26:
    st.info("⏳ **Observation des vagues...** Attente du décalage (26 boules épurées requises).")
else:
    st.success("⚔️ **Session active.** Fluidité des vagues synchronisée.")

c1, c2, c3 = st.columns(3)

def generer_bloc_mise(titre, v_r, v_n, label_r, label_n):
    bal = v_r - v_n
    with st.container(border=True):
        st.subheader(titre)
        if boules_epurees < 26:
            st.markdown("### ⏳ **OBSERVATION**")
        elif bal > 0: 
            st.markdown(f"### 🟢 **{label_r} : {bal} p.**")
        elif bal < 0: 
            st.markdown(f"### 🟢 **{label_n} : {abs(bal)} p.**")
        else: 
            st.markdown("### ⏸️ **NE RIEN MISER**")
        st.caption(f"Votes instantanés : {v_r} R vs {v_n} N")

with c1: generer_bloc_mise("Rouge / Noir", votes["RN"]["R"], votes["RN"]["N"], "ROUGE 🔴", "NOIR ⚫")
with c2: generer_bloc_mise("Pair / Impair", votes["PI"]["R"], votes["PI"]["N"], "PAIR 🔢", "IMPAIR 🔀")
with c3: generer_bloc_mise("Passe / Manque", votes["PM"]["R"], votes["PM"]["N"], "PASSE ⬆️", "MANQUE ⬇️")

# ==============================================================================
# --- AJOUT ICI : OUTIL D'AUDIT ET DE VÉRIFICATION DES JOUEURS ---
# ==============================================================================
st.write("---")
with st.expander("🔍 INSPECTEUR DE L'ARMÉE VIRTUELLE (Outil de Vérification)"):
    choix_chance = st.radio("Sélectionnez la chance à auditer :", ["RN", "PI", "PM"], horizontal=True)
    
    donnees_audit = []
    for j in armee_locale[choix_chance]:
        donnees_audit.append({
            "ID Joueur": j.id,
            "Figure Cible": j.fig,
            "Décalage Config": j.dec_initial,
            "Décalage Restant": j.dec_courant,
            "Index Étape (0-2)": j.index_etape,
            "Statut Actuel": j.statut,
            "QUALIFIÉ (Retard)": "✅ OUI" if j.retard_constate else "❌ NON",
            "Solde Carton Actuel": f"{j.solde_du_carton} u.",
            "Coups Joués dans Carton": f"{j.compteur_coups_carton} / 24",
            "Intention Prochaine": j.intention() if j.intention() else "🚫 Aucune"
        })
    
    df_audit = pd.DataFrame(donnees_audit)
    st.dataframe(df_audit, use_container_width=True, hide_index=True)
# ==============================================================================

st.write("---")
st.subheader(f"📇 Permanence sauvegardée ({total_boules} boules)")
if st.session_state.historique:
    if len(st.session_state.historique) > 150:
        st.info(f"... [Fichier long] ... , " + ", ".join([str(x) for x in st.session_state.historique[-150:]]))
    else:
        st.info(", ".join([str(x) for x in st.session_state.historique]))
else: 
    st.write("*Aucune donnée enregistrée sur le cloud.*")
