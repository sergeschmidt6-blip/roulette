import streamlit as st
import pandas as pd
import random
import requests
import base64
import json

st.set_page_config(page_title="Marche Triomphale — Calage Strict", layout="wide", initial_sidebar_state="expanded")

FIGURES_GENERIQUES = ["ooo", "oox", "oxo", "oxx", "xxx", "xxo", "xox", "xoo"]

# --- GITHUB ---
TOKEN = st.secrets.get("GITHUB_TOKEN", "")
REPO = st.secrets.get("GITHUB_REPO", "")
FILE_PATH = "permanence.txt"
URL_API = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

def charger_permanence_cloud():
    if not TOKEN or not REPO: return []
    try:
        headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
        response = requests.get(URL_API, headers=headers)
        if response.status_code == 200:
            donnees = response.json()
            contenu_texte = base64.b64decode(donnees["content"]).decode("utf-8")
            contenu_nettoye = contenu_texte.replace("\n", "").replace(" ", "").strip()
            if not contenu_nettoye: return []
            return [int(x) for x in contenu_nettoye.split(",") if x != ""]
    except Exception: pass
    return []

def sauvegarder_permanence_cloud(nouvelle_liste):
    if not TOKEN or not REPO: return
    try:
        headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
        contenu_texte = ",".join([str(x) for x in nouvelle_liste])
        contenu_base64 = base64.b64encode(contenu_texte.encode("utf-8")).decode("utf-8")
        response_get = requests.get(URL_API, headers=headers)
        sha = response_get.json()["sha"] if response_get.status_code == 200 else None
        data = {"message": "Mise à jour permanence", "content": contenu_base64}
        if sha: data["sha"] = sha
        requests.put(URL_API, headers=headers, data=json.dumps(data))
    except Exception: pass

# --- CLASSE JOUEUR RECALIBRÉE ---
class JoueurMT:
    def __init__(self, id_j, chance_type, fig_generique, dec):
        self.id = id_j
        self.chance_type = chance_type 
        self.fig_generique = fig_generique  
        self.dec_initial = dec  # 0, 1 ou 2
        
        self.retard_constate = False 
        self.solde_global = 0  
        self.survenues_carton_actuel = 0  
        
        self.tampon_bloc_3 = []
        self.resultat_coup_precedent = None

    def obtenir_traduction_figure(self):
        mappage = {
            "RN": {"o": "R", "x": "N"},
            "PI": {"o": "R", "x": "N"}, 
            "PM": {"o": "R", "x": "N"}  
        }
        return "".join([mappage[self.chance_type][lettre] for lettre in self.fig_generique])

    def determiner_position_interne(self, coup_absolu_table):
        """
        Calcule la position exacte du coup dans le carton (1 à 24) et dans le bloc (1, 2 ou 3)
        en fonction de la ligne absolue de la table et du décalage structurel.
        """
        # Ex: Si Dec=1, le joueur commence à la ligne absolue 2 de la table.
        # Son index de jeu commence à : coup_absolu_table - 1 - 1
        idx_jeu = coup_absolu_table - 1 - self.dec_initial
        
        if idx_jeu < 0:
            return None, None # Le joueur est en phase d'observation pure avant son premier carton
            
        pos_carton = (idx_jeu % 24) + 1
        pos_bloc = (idx_jeu % 3) + 1
        return pos_carton, pos_bloc

    def intention(self, coup_absolu_table):
        # Récupération de la position que ce joueur aura AU PROCHAIN COUP de la table
        pos_carton, pos_bloc = self.determiner_position_interne(coup_absolu_table)
        
        # Si le joueur n'a pas encore démarré son rail ou s'il n'est pas qualifié en retard
        if pos_carton is None or not self.retard_constate:
            return None
            
        fig_traduite = self.obtenir_traduction_figure()
        idx_lettre = pos_bloc - 1
        
        if pos_bloc == 1:
            return fig_traduite[idx_lettre]
        elif pos_bloc == 2:
            if self.resultat_coup_precedent == "GAGNÉ": return fig_traduite[idx_lettre]
            return None
        elif pos_bloc == 3:
            if self.resultat_coup_precedent == "GAGNÉ": return fig_traduite[idx_lettre]
            return None

    def actualiser(self, tirage_epure, est_zero, coup_absolu_table):
        if est_zero: return

        # On regarde où se situe le joueur AU COUP EN COURS qui vient d'être joué
        pos_carton, pos_bloc = self.determiner_position_interne(coup_absolu_table)
        
        # Si la ligne actuelle correspond à sa phase d'observation de début de partie
        if pos_carton is None:
            return

        # On capture ce qu'il aurait dû miser (s'il était qualifié) pour valider le résultat
        intent_actif = self.intention(coup_absolu_table)

        fig_traduite = self.obtenir_traduction_figure()
        
        # Remplissage du bloc de 3
        self.tampon_bloc_3.append(tirage_epure)
        if len(self.tampon_bloc_3) == 3:
            if "".join(self.tampon_bloc_3) == fig_traduite:
                self.survenues_carton_actuel += 1
            self.tampon_bloc_3 = [] 

        # Mémoire du coup pour le droit de jouer le sous-coup suivant
        if intent_actif:
            if tirage_epure == intent_actif: self.resultat_coup_precedent = "GAGNÉ"
            else: self.resultat_coup_precedent = "PERDU"
        else:
            self.resultat_coup_precedent = "NON_JOUÉ"

        if pos_bloc == 3:
            self.resultat_coup_precedent = None

        # CLÔTURE STRICTE DU CARTON (Ligne 24, 48, 72... propre à son rail)
        if pos_carton == 24:
            if self.survenues_carton_actuel == 0: evolution = -1
            elif self.survenues_carton_actuel == 1: evolution = 0
            else: evolution = self.survenues_carton_actuel - 1

            self.solde_global += evolution
            self.retard_constate = (self.solde_global < 0)
            
            # Reset comptable du carton, mais le rail continue au coup suivant !
            self.survenues_carton_actuel = 0
            self.tampon_bloc_3 = []
            self.resultat_coup_precedent = None

# --- INITIALISATION DE SESSION ---
if "historique" not in st.session_state:
    st.session_state.historique = charger_permanence_cloud()

def analyser_numero(num):
    if num == 0: return "0", "0", "0"
    rouges = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    return ("R" if num in rouges else "N"), ("R" if num % 2 == 0 else "N"), ("R" if num >= 19 else "N")

# --- INTERFACE SIDEBAR ---
st.sidebar.header("⚙️ CONTRÔLE DES RAILS FIXED")
capital_placeholder = st.sidebar.empty()

if st.sidebar.button("🔄 Réimporter depuis le Serveur", use_container_width=True):
    st.session_state.historique = charger_permanence_cloud()
    st.rerun()

import_txt = st.sidebar.text_area("Coller une série de numéros :", placeholder="Ex: 14,32,0,5")
if st.sidebar.button("📥 Importer la série", use_container_width=True) and import_txt:
    try:
        nettoye = import_txt.replace("\n", "").replace(" ", "")
        st.session_state.historique.extend([int(x) for x in nettoye.split(",") if x != ""])
        sauvegarder_permanence_cloud(st.session_state.historique)
        st.rerun()
    except ValueError: pass

nb_sim = st.sidebar.number_input("Générer des coups aléatoires :", min_value=10, max_value=1000, value=100, step=100)
if st.sidebar.button(f"⚡ Injecter {nb_sim} coups", use_container_width=True):
    st.session_state.historique.extend([random.randint(0, 36) for _ in range(nb_sim)])
    sauvegarder_permanence_cloud(st.session_state.historique)
    st.rerun()

if st.sidebar.checkbox("⚠️ Déverrouiller la RAZ") and st.sidebar.button("🔴 EFFACER TOUTES LES DONNÉES", use_container_width=True):
    st.session_state.historique = []
    sauvegarder_permanence_cloud([])
    st.rerun()

# --- CLAVIER NUMÉRIQUE ---
st.subheader("📥 Enregistrer un numéro")
grille_clavier = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
    [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]
]
rouges_liste = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]

for rangee in grille_clavier:
    cols = st.columns(len(rangee))
    for idx, n in enumerate(rangee):
        if n == 0: label = f"🟢 {n}"
        else: label = f"🔴 {n}" if n in rouges_liste else f"⚫ {n}"
        if cols[idx].button(label, use_container_width=True, key=f"clavier_num_{n}"):
            st.session_state.historique.append(n)
            sauvegarder_permanence_cloud(st.session_state.historique)
            st.rerun()

# --- INSTANCIATION DE L'ARMÉE ---
armee_locale = {"RN": [], "PI": [], "PM": []}
id_j = 1
for chance in ["RN", "PI", "PM"]:
    for dec in [0, 1, 2]:
        for fig in FIGURES_GENERIQUES:
            armee_locale[chance].append(JoueurMT(id_j, chance, fig, dec))
            id_j += 1

capital_calcule = 0.0
total_boules_global = len(st.session_state.historique)
coup_absolu_epure = 0

# Traitement chronologique strict
for num in st.session_state.historique:
    rn, pi, pm = analyser_numero(num)
    est_zero = (num == 0)
    
    if not est_zero: 
        coup_absolu_epure += 1

    if not est_zero:
        mises_du_coup = {}
        for chance in ["RN", "PI", "PM"]:
            v_r = sum(1 for j in armee_locale[chance] if j.intention(coup_absolu_epure) == "R")
            v_n = sum(1 for j in armee_locale[chance] if j.intention(coup_absolu_epure) == "N")
            mises_du_coup[chance] = v_r - v_n

        for chance, (tirage_code, code_r, code_n) in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "R", "N"))]:
            net_mised = mises_du_coup[chance]
            if net_mised != 0:
                if (net_mised > 0 and tirage_code == code_r) or (net_mised < 0 and tirage_code == code_n): 
                    capital_calcule += abs(net_mised)
                else: 
                    capital_calcule -= abs(net_mised)
    else:
        for chance in ["RN", "PI", "PM"]:
            v_r = sum(1 for j in armee_locale[chance] if j.intention(coup_absolu_epure) == "R")
            v_n = sum(1 for j in armee_locale[chance] if j.intention(coup_absolu_epure) == "N")
            net_mised = v_r - v_n
            if net_mised != 0:
                capital_calcule -= abs(net_mised) * 0.5

    for j in armee_locale["RN"]: j.actualiser(rn, est_zero, coup_absolu_epure)
    for j in armee_locale["PI"]: j.actualiser(pi, est_zero, coup_absolu_epure)
    for j in armee_locale["PM"]: j.actualiser(pm, est_zero, coup_absolu_epure)

# --- CALCUL DU PROCHAIN COUP ---
prochain_coup_absolu = coup_absolu_epure + 1
position_dans_carton_suivante = ((prochain_coup_absolu - 1) % 24) + 1

votes = {"RN": {"R": 0, "N": 0}, "PI": {"R": 0, "N": 0}, "PM": {"R": 0, "N": 0}}
for chance in ["RN", "PI", "PM"]:
    for j in armee_locale[chance]:
        intent = j.intention(prochain_coup_absolu)
        if intent: votes[chance][intent] += 1

qualifies_rn = sum(1 for j in armee_locale["RN"] if j.retard_constate)
qualifies_pi = sum(1 for j in armee_locale["PI"] if j.retard_constate)
qualifies_pm = sum(1 for j in armee_locale["PM"] if j.retard_constate)

capital_placeholder.markdown(
    f"""
    ### 💰 **{capital_calcule} p.**
    * Total boules : **{total_boules_global}**
    * Boules épurées : **{coup_absolu_epure}**
    * ---
    * Position Table : **{position_dans_carton_suivante} / 24**
    * ---
    * Groupes en Retard :
      * R/N : **{qualifies_rn}/24**
      * P/I : **{qualifies_pi}/24**
      * P/M : **{qualifies_pm}/24**
    """
)

st.header("🎯 ORDRES DE MISES — LOGIQUE DE RAILS PARALLÈLES")
if coup_absolu_epure < 26:
    st.info("⏳ **Observation initiale...** En attente de la ligne 26 pour caler tous les décalages.")
else:
    st.success(f"⚔️ Prêt pour la ligne épurée n°{prochain_coup_absolu}.")

c1, c2, c3 = st.columns(3)
def generer_bloc_mise(titre, v_r, v_n, label_r, label_n):
    bal = v_r - v_n
    lettre_r, lettre_n = label_r.split()[0], label_n.split()[0]
    with st.container(border=True):
        st.subheader(titre)
        if coup_absolu_epure < 26: st.markdown("### ⏳ **OBSERVATION**")
        elif bal > 0: st.markdown(f"### 🟢 **{label_r} : {bal} p.**")
        elif bal < 0: st.markdown(f"### 🟢 **{label_n} : {abs(bal)} p.**")
        else: st.markdown("### ⏸️ **NE RIEN MISER**")
        st.caption(f"Votes : {v_r} {lettre_r} vs {v_n} {lettre_n}")

with c1: generer_bloc_mise("Rouge / Noir", votes["RN"]["R"], votes["RN"]["N"], "ROUGE 🔴", "NOIR ⚫")
with c2: generer_bloc_mise("Pair / Impair", votes["PI"]["R"], votes["PI"]["N"], "PAIR 🔢", "IMPAIR 🔀")
with c3: generer_bloc_mise("Passe / Manque", votes["PM"]["R"], votes["PM"]["N"], "PASSE ⬆️", "MANQUE ⬇️")

st.write("---")
with st.expander("🔍 INSPECTEUR DES ALIGNEMENTS DE CYCLES"):
    choix_chance = st.radio("Sélectionnez la chance à auditer :", ["RN", "PI", "PM"], horizontal=True)
    lbl_a, lbl_b = {"RN": ("ROUGE", "NOIR"), "PI": ("PAIR", "IMPAIR"), "PM": ("PASSE", "MANQUE")}[choix_chance]

    donnees_audit = []
    for j in armee_locale[choix_chance]:
        fig_visuelle = j.obtenir_traduction_figure().replace("R", lbl_a[0]).replace("N", lbl_b[0])
        intention_brute = j.intention(prochain_coup_absolu)
        intention_visuelle = lbl_a if intention_brute == "R" else (lbl_b if intention_brute == "N" else "🚫 En sommeil")
        solde_texte = f"+{j.solde_global}" if j.solde_global > 0 else str(j.solde_global)
        
        pos_carton, pos_bloc = j.determiner_position_interne(prochain_coup_absolu)
        pos_carton_txt = f"{pos_carton} / 24" if pos_carton else "En attente"
        type_coup_txt = f"Coup {pos_bloc} (Lettre {pos_bloc})" if pos_bloc else "En attente"

        donnees_audit.append({
            "ID Group": j.id,
            "Figure Code": j.fig_generique,  
            "Décalage Config": j.dec_initial,
            "Figure Réelle": fig_visuelle,
            "EN RETARD": f"✅ OUI" if j.retard_constate else "❌ NON",
            "SOLDE GLOBAL": solde_texte,
            "Position Carton": pos_carton_txt,
            "Type Coup Prochain": type_coup_txt,
            "Action Prochaine": intention_visuelle
        })
    st.dataframe(pd.DataFrame(donnees_audit), use_container_width=True, hide_index=True)
# --- AFFICHAGE DE LA PERMANENCE EN BAS DE PAGE ---
st.write("---")
with st.expander(f"📋 Voir la Permanence Enregistrée ({len(st.session_state.historique)} boules)"):
    if st.session_state.historique:
        # Affichage sous forme de blocs de texte espacés pour une lecture facile
        st.code(", ".join([str(x) for x in st.session_state.historique]))
    else:
        st.info("Aucun numéro dans la permanence pour le moment.")
