import streamlit as st
import pandas as pd
import random
import requests
import base64
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Marche Triomphale — Fréquence des Retards", layout="wide", initial_sidebar_state="expanded")

FIGURES_GENERIQUES = ["ooo", "oox", "oxo", "oxx", "xxx", "xxo", "xox", "xoo"]

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

# --- STRUCTURE DU JOUEUR (GROUPE) ---
class JoueurGlissant:
    def __init__(self, id_j, chance_type, fig_generique, dec):
        self.id = id_j
        self.chance_type = chance_type 
        self.fig_generique = fig_generique  
        self.dec_initial = dec  
        self.dec_courant = dec  
        
        self.index_etape = 0         # Position dans la figure de 3 coups (0, 1 ou 2)
        self.statut = "JOUER"        # "JOUER" ou "ARRET" suite à une perte
        self.retard_constate = False # Devient True si apparitions < 3 à la fin du carton
        
        self.compteur_coups_carton = 0
        self.compteur_apparitions = 0  # COMPTABILITÉ STRICTE DES RETARDS (Fréquence d'apparition)
        self.historique_figure_en_cours = [] # Stocke les 3 coups pour valider si la figure s'est produite

    def obtenir_traduction_figure(self):
        mappage = {
            "RN": {"o": "R", "x": "N"},
            "PI": {"o": "R", "x": "N"}, 
            "PM": {"o": "R", "x": "N"}  
        }
        dico = mappage[self.chance_type]
        return "".join([dico[lettre] for lettre in self.fig_generique])

    def intention(self):
        # On ne donne un ordre de mise QUE si le décalage est purgé,
        # que le groupe est qualifié (en retard) et qu'il n'est pas en "ARRET"
        if self.dec_courant > 0 or self.statut == "ARRET" or not self.retard_constate:
            return None
        fig_traduite = self.obtenir_traduction_figure()
        return fig_traduite[self.index_etape]

    def actualiser(self, tirage_epure, est_zero):
        if self.dec_courant > 0:
            if not est_zero: 
                self.dec_courant -= 1
            return

        if est_zero:
            # Le zéro est neutre pour la comptabilité des apparitions de figures, 
            # mais suspend l'index si le joueur était en train de miser
            return

        self.compteur_coups_carton += 1
        fig_traduite = self.obtenir_traduction_figure()
        attendu = fig_traduite[self.index_etape]
        
        # 1. Collecte du tirage pour analyser l'apparition de la figure globale
        self.historique_figure_en_cours.append(tirage_epure)
        
        # 2. Gestion de la marche du jeu réel / virtuel
        if tirage_epure == attendu:
            # Coup gagnant -> On avance à l'étape suivante de la figure
            self.index_etape += 1
        else:
            # Coup perdant -> Si on jouait réellement, on applique l'ARRÊT immédiat
            if self.retard_constate and self.statut == "JOUER":
                self.statut = "ARRET"
            self.index_etape += 1

        # 3. Validation de la fin d'une figure de 3 coups
        if self.index_etape >= 3:
            # On vérifie si la figure complète de 3 coups correspond à la figure cible du joueur
            sequence_produite = "".join(self.historique_figure_en_cours)
            if sequence_produite == fig_traduite:
                self.compteur_apparitions += 1 # La figure est apparue !
            
            # Réinitialisation pour la prochaine figure de 3 coups
            self.index_etape = 0
            self.historique_figure_en_cours = []
            self.statut = "JOUER"

        # 4. FIN DU CARTON DE 24 COUPS ÉPURÉS : RECALCUL DES RETARDS
        if self.compteur_coups_carton == 24:
            # NORME THÉORIQUE = 3 apparitions. 
            # Le groupe est qualifié en RETARD uniquement s'il est apparu moins de 3 fois.
            self.retard_constate = self.compteur_apparitions < 3
            
            # Reset complet pour le carton suivant
            self.compteur_apparitions = 0
            self.compteur_coups_carton = 0
            self.dec_courant = self.dec_initial  
            self.index_etape = 0
            self.historique_figure_en_cours = []
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

# --- INSTANCIATION DE L'ARMÉE VIRTUELLE ---
armee_locale = {"RN": [], "PI": [], "PM": []}
id_j = 1
for chance in ["RN", "PI", "PM"]:
    for dec in [0, 1, 2]:
        for fig in FIGURES_GENERIQUES:
            armee_locale[chance].append(JoueurGlissant(id_j, chance, fig, dec))
            id_j += 1

capital_calcule = 0.0

# --- RECONSTRUCTION CHRONOLOGIQUE ---
for num in st.session_state.historique:
    rn, pi, pm = analyser_numero(num)
    est_zero = (num == 0)
    
    mises_du_coup = {}
    for chance in ["RN", "PI", "PM"]:
        v_r = sum(1 for j in armee_locale[chance] if j.intention() == "R")
        v_n = sum(1 for j in armee_locale[chance] if j.intention() == "N")
        mises_du_coup[chance] = v_r - v_n

    for chance, (tirage_code, code_r, code_n) in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "V", "M"))]:
        net_mised = mises_du_coup[chance]
        if net_mised != 0:
            if est_zero:
                capital_calcule -= abs(net_mised) * 0.5
            elif (net_mised > 0 and tirage_code == code_r) or (net_mised < 0 and tirage_code == code_n):
                capital_calcule += abs(net_mised)
            else:
                capital_calcule -= abs(net_mised)

    for j in armee_locale["RN"]: j.actualiser(rn, est_zero)
    for j in armee_locale["PI"]: j.actualiser(pi, est_zero)
    for j in armee_locale["PM"]: j.actualiser(pm, est_zero)

st.session_state.capital_reel = capital_calcule

total_boules = len(st.session_state.historique)
zeros_purgés = sum(1 for x in st.session_state.historique if x == 0)
boules_epurees = total_boules - zeros_purgés

votes = {"RN": {"R": 0, "N": 0}, "PI": {"R": 0, "N": 0}, "PM": {"R": 0, "N": 0}}
for chance in ["RN", "PI", "PM"]:
    for j in armee_locale[chance]:
        intent = j.intention()
        if intent: votes[chance][intent] += 1

qualifies_rn = sum(1 for j in armee_locale["RN"] if j.retard_constate)
qualifies_pi = sum(1 for j in armee_locale["PI"] if j.retard_constate)
qualifies_pm = sum(1 for j in armee_locale["PM"] if j.retard_constate)

capital_placeholder.markdown(
    f"""
    ### 💰 **{st.session_state.capital_reel} p.**
    * Total boules : **{total_boules}**
    * Boules épurées : **{boules_epurees}**
    * ---
    * Groupes en Retard :
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
    lettre_r = label_r.split()[0]
    lettre_n = label_n.split()[0]
    
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
        st.caption(f"Votes instantanés : {v_r} {lettre_r} vs {v_n} {lettre_n}")

with c1: generer_bloc_mise("Rouge / Noir", votes["RN"]["R"], votes["RN"]["N"], "ROUGE 🔴", "NOIR ⚫")
with c2: generer_bloc_mise("Pair / Impair", votes["PI"]["R"], votes["PI"]["N"], "PAIR 🔢", "IMPAIR 🔀")
with c3: generer_bloc_mise("Passe / Manque", votes["PM"]["R"], votes["PM"]["N"], "PASSE ⬆️", "MANQUE ⬇️")

# --- OUTIL D'AUDIT ET DE VÉRIFICATION VISUELLE ---
st.write("---")
with st.expander("🔍 INSPECTEUR DE L'ARMÉE VIRTUELLE (Outil de Vérification)"):
    choix_chance = st.radio("Sélectionnez la chance à auditer :", ["RN", "PI", "PM"], horizontal=True)
    
    labels_traduction = {
        "RN": ("ROUGE", "NOIR"),
        "PI": ("PAIR", "IMPAIR"),
        "PM": ("PASSE", "MANQUE")
    }
    lbl_a, lbl_b = labels_traduction[choix_chance]

    donnees_audit = []
    for j in armee_locale[choix_chance]:
        fig_visuelle = j.obtenir_traduction_figure().replace("R", lbl_a[0]).replace("N", lbl_b[0])
        intention_brute = j.intention()
        if intention_brute == "R": intention_visuelle = lbl_a
        elif intention_brute == "N": intention_visuelle = lbl_b
        else: intention_visuelle = "🚫 Aucune"

        donnees_audit.append({
            "ID Group": j.id,
            "Figure Code": j.fig_generique,  
            "Figure Réelle": fig_visuelle,
            "Décalage Config": j.dec_initial,
            "Décalage Restant": j.dec_courant,
            "Statut Actuel": j.statut,
            "EN RETARD (<3)": f"✅ OUI" if j.retard_constate else "❌ NON",
            "Apparitions dans ce Carton": f"{j.compteur_apparitions} / 3",
            "Progression Carton": f"{j.compteur_coups_carton} / 24",
            "Action Prochaine": intention_visuelle
        })
    
    df_audit = pd.DataFrame(donnees_audit)
    st.dataframe(df_audit, use_container_width=True, hide_index=True)

st.write("---")
st.subheader(f"📇 Permanence sauvegardée ({total_boules} boules)")
if st.session_state.historique:
    if len(st.session_state.historique) > 150:
        st.info(f"... [Fichier long] ... , " + ", ".join([str(x) for x in st.session_state.historique[-150:]]))
    else:
        st.info(", ".join([str(x) for x in st.session_state.historique]))
else: 
    st.write("*Aucune donnée enregistrée sur le cloud.*")
