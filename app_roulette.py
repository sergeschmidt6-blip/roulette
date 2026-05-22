import streamlit as st
import pandas as pd
import random
import requests
import base64
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Marche Triomphale — Logique de Blocs Fixes", layout="wide", initial_sidebar_state="expanded")

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

# --- STRUCTURE DU JOUEUR (LOGIQUE DE BLOCS EXACTE) ---
class JoueurMT:
    def __init__(self, id_j, chance_type, fig_generique, dec):
        self.id = id_j
        self.chance_type = chance_type 
        self.fig_generique = fig_generique  
        self.dec_initial = dec  
        self.dec_courant = dec  
        
        # Statuts de qualification
        self.retard_constate = False 
        self.compteur_coups_carton = 0
        
        # Historique global pour le calcul de l'écart / retard
        self.apparitions_totales = 0
        self.total_opportunites = 0
        
        # Fenêtre glissante locale pour identifier la formation de la figure
        self.memoire_glissante = []
        
        # Mémoire du résultat du coup précédent au sein du bloc de 3 coups courant
        # Peut être : "GAGNÉ", "PERDU", None
        self.resultat_coup_precedent = None

    def obtenir_traduction_figure(self):
        mappage = {
            "RN": {"o": "R", "x": "N"},
            "PI": {"o": "R", "x": "N"}, 
            "PM": {"o": "R", "x": "N"}  
        }
        dico = mappage[self.chance_type]
        return "".join([dico[lettre] for lettre in self.fig_generique])

    def determiner_type_coup(self, coup_absolu):
        # Repérage de la position du coup (1 à 24) dans la structure des 8 blocs fixes
        pos = ((coup_absolu - 1) % 24) + 1
        if pos in [1, 4, 7, 10, 13, 16, 19, 22]:
            return 1
        elif pos in [2, 5, 8, 11, 14, 17, 20, 23]:
            return 2
        else:
            return 3

    def intention(self, coup_absolu):
        # Si le décalage initial du joueur n'est pas purgé ou s'il n'est pas qualifié, pas de mise
        if self.dec_courant > 0 or not self.retard_constate:
            return None
            
        type_coup = self.determiner_type_coup(coup_absolu)
        fig_traduite = self.obtenir_traduction_figure()
        idx_lettre = (coup_absolu - 1) % 3  # Index de la lettre (0, 1 ou 2) dans la figure de 3
        
        # Application stricte de vos 3 règles de mise
        if type_coup == 1:
            # Règle 1 : Les coups 1, 4, 7... sont toujours joués
            return fig_traduite[idx_lettre]
            
        elif type_coup == 2:
            # Règle 2 : Ne sont joués que si le précédent (Coup 1) était gagné
            if self.resultat_coup_precedent == "GAGNÉ":
                return fig_traduite[idx_lettre]
            return None
            
        elif type_coup == 3:
            # Règle 3 : Le 3ème coup n'est joué que si le 2ème était gagné
            if self.resultat_coup_precedent == "GAGNÉ":
                return fig_traduite[idx_lettre]
            return None

    def actualiser(self, tirage_epure, est_zero, coup_absolu):
        if self.dec_courant > 0:
            if not est_zero: 
                self.dec_courant -= 1
            return

        if est_zero:
            return # Le zéro suspend l'analyse mais ne casse pas la structure du bloc épuré

        self.compteur_coups_carton += 1
        fig_traduite = self.obtenir_traduction_figure()
        type_coup = self.determiner_type_coup(coup_absolu)
        
        # 1. Analyse glissante de la permanence (Comptabilité de l'historique global)
        self.memoire_glissante.append(tirage_epure)
        if len(self.memoire_glissante) > 3:
            self.memoire_glissante.pop(0)
            
        if len(self.memoire_glissante) == 3:
            self.total_opportunites += 1
            if "".join(self.memoire_glissante) == fig_traduite:
                self.apparitions_totales += 1

        # 2. Enregistrement du résultat pour le coup en cours (Sert de mémoire pour le coup suivant du bloc)
        intent = self.intention(coup_absolu)
        if intent:
            if tirage_epure == intent:
                self.resultat_coup_precedent = "GAGNÉ"
            else:
                self.resultat_coup_precedent = "PERDU"
        else:
            # Si le coup n'a pas été joué (Saut), la mémoire devient None ou PERDU pour bloquer le coup 3
            self.resultat_coup_precedent = "NON_JOUÉ"

        # 3. Fin de bloc de 3 coups : réinitialisation de la mémoire du coup précédent
        if type_coup == 3:
            self.resultat_coup_precedent = None

        # 4. FIN DU CARTON DE 24 COUPS ÉPURÉS : RECALCUL DES RETARDS SUR LA BASE DU SOLDE GLOBAL
        if self.compteur_coups_carton == 24:
            # Calcul de la norme théorique globale depuis le début
            # Dans une suite de n opportunités, chaque figure doit statistiquement apparaître (Opportunités / 8)
            if self.total_opportunites > 0:
                norme_theorique_globale = self.total_opportunites / 8.0
                # Le groupe est qualifié en RETARD si ses apparitions réelles sont inférieures à la norme
                self.retard_constate = self.apparitions_totales < norme_theorique_globale
            else:
                self.retard_constate = False
            
            # Reset des indicateurs du carton (Le décalage se réactive pour trier la synchronisation des vagues)
            self.compteur_coups_carton = 0
            self.dec_courant = self.dec_initial  
            self.resultat_coup_precedent = None

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

# --- SIDEBAR DE CONTRÔLE ---
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

# --- CLAVIER DE SAISIE MANUELLE ---
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
            armee_locale[chance].append(JoueurMT(id_j, chance, fig, dec))
            id_j += 1

capital_calcule = 0.0
total_boules_global = len(st.session_state.historique)

# Compteur de coups absolu épuré (sans les zéros) pour caler les blocs de 1 à 24
coup_absolu_epure = 0

# --- RECONSTRUCTION CHRONOLOGIQUE STRICTE ---
for num in st.session_state.historique:
    rn, pi, pm = analyser_numero(num)
    est_zero = (num == 0)
    
    if not est_zero:
        coup_absolu_epure += 1

    mises_du_coup = {}
    for chance in ["RN", "PI", "PM"]:
        v_r = sum(1 for j in armee_locale[chance] if j.intention(coup_absolu_epure) == "R")
        v_n = sum(1 for j in armee_locale[chance] if j.intention(coup_absolu_epure) == "N")
        mises_du_coup[chance] = v_r - v_n

    for chance, (tirage_code, code_r, code_n) in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "R", "N"))]:
        net_mised = mises_du_coup[chance]
        if net_mised != 0:
            if est_zero:
                capital_calcule -= abs(net_mised) * 0.5
            elif (net_mised > 0 and tirage_code == code_r) or (net_mised < 0 and tirage_code == code_n):
                capital_calcule += abs(net_mised)
            else:
                capital_calcule -= abs(net_mised)

    for j in armee_locale["RN"]: j.actualiser(rn, est_zero, coup_absolu_epure)
    for j in armee_locale["PI"]: j.actualiser(pi, est_zero, coup_absolu_epure)
    for j in armee_locale["PM"]: j.actualiser(pm, est_zero, coup_absolu_epure)

st.session_state.capital_reel = capital_calcule

# Préparation du coup suivant (le coup à jouer à la table)
prochain_coup_absolu = coup_absolu_epure + 1
position_dans_carton = ((prochain_coup_absolu - 1) % 24) + 1

# Calcul des votes pour le prochain coup à venir
votes = {"RN": {"R": 0, "N": 0}, "PI": {"R": 0, "N": 0}, "PM": {"R": 0, "N": 0}}
for chance in ["RN", "PI", "PM"]:
    for j in armee_locale[chance]:
        intent = j.intention(prochain_coup_absolu)
        if intent: votes[chance][intent] += 1

qualifies_rn = sum(1 for j in armee_locale["RN"] if j.retard_constate)
qualifies_pi = sum(1 for j in armee_locale["PI"] if j.retard_constate)
qualifies_pm = sum(1 for j in armee_locale["PM"] if j.retard_constate)

# Affichage des métriques de session
zeros_purgés = sum(1 for x in st.session_state.historique if x == 0)
capital_placeholder.markdown(
    f"""
    ### 💰 **{st.session_state.capital_reel} p.**
    * Total boules : **{total_boules_global}**
    * Boules épurées : **{coup_absolu_epure}**
    * ---
    * Position Carton : **{position_dans_carton} / 24**
    * ---
    * Groupes Qualifiés (Retard Global) :
      * R/N : **{qualifies_rn}/24**
      * P/I : **{qualifies_pi}/24**
      * P/M : **{qualifies_pm}/24**
    """
)

# --- PANEL DES ORDRES DE JEU ---
st.header("🎯 ORDRES DE MISES POUR LE PROCHAIN COUP")

if coup_absolu_epure < 26:
    st.info("⏳ **Phase d'Observation...** Attente de la première synchronisation complète des vagues (26 boules requises).")
else:
    st.success(f"⚔️ **Session active.** Analyse du coup épuré n°{prochain_coup_absolu} (Position fixe : Étape {((prochain_coup_absolu-1)%3)+1} du bloc).")

c1, c2, c3 = st.columns(3)

def generer_bloc_mise(titre, v_r, v_n, label_r, label_n):
    bal = v_r - v_n
    lettre_r = label_r.split()[0]
    lettre_n = label_n.split()[0]
    
    with st.container(border=True):
        st.subheader(titre)
        if coup_absolu_epure < 26:
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

# --- EXPANDER : INSPECTEUR ET VÉRIFICATION ---
st.write("---")
with st.expander("🔍 INSPECTEUR CHIRURGICAL DE L'ARMÉE (Vérification des Blocs Fixes)"):
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
        intention_brute = j.intention(prochain_coup_absolu)
        
        if intention_brute == "R": intention_visuelle = lbl_a
        elif intention_brute == "N": intention_visuelle = lbl_b
        else: intention_visuelle = "🚫 Saut (Condition non remplie)"

        # Calcul de la norme théorique globale pour l'affichage de contrôle
        norme_theorique = round(j.total_opportunites / 8.0, 2) if j.total_opportunites > 0 else 0.0

        type_c_prochain = j.determiner_type_coup(prochain_coup_absolu)
        lettre_visée = (prochain_coup_absolu - 1) % 3

        donnees_audit.append({
            "ID Group": j.id,
            "Figure Code": j.fig_generique,  
            "Figure Réelle": fig_visuelle,
            "Décalage Config": j.dec_initial,
            "EN RETARD (Global)": f"✅ OUI" if j.retard_constate else "❌ NON",
            "Apparitions globales": f"{j.apparitions_totales} / {norme_theorique} th.",
            "Type Coup Prochain": f"Coup {type_c_prochain} (Lettre {lettre_visée+1})",
            "Mémoire Coup Précédent": "Aucune (Début de bloc)" if type_c_prochain == 1 else f"Dernier coup {j.resultat_coup_precedent}",
            "Action Prochaine": intention_visuelle
        })
    
    df_audit = pd.DataFrame(donnees_audit)
    st.dataframe(df_audit, use_container_width=True, hide_index=True)

st.write("---")
st.subheader(f"📇 Permanence enregistrée ({total_boules_global} boules)")
if st.session_state.historique:
    if len(st.session_state.historique) > 150:
        st.info(f"... [Permanence active] ... , " + ", ".join([str(x) for x in st.session_state.historique[-150:]]))
    else:
        st.info(", ".join([str(x) for x in st.session_state.historique]))
else: 
    st.write("*Le serveur cloud est vide. Enregistrez un numéro pour démarrer.*")
