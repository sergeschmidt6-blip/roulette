import streamlit as st
import pandas as pd
import random

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Marche Triomphale - 72 Joueurs Pro", layout="wide", initial_sidebar_state="expanded")

FIGURES = ["RRR", "RRN", "RNR", "RNN", "NNN", "NNR", "NRN", "NRR"]

# --- LOGIQUE D'UN JOUEUR VIRTUEL ---
class JoueurGlissant:
    def __init__(self, id_j, chance_type, fig, dec):
        self.id = id_j
        self.chance_type = chance_type 
        self.fig = fig
        self.dec = dec
        self.index_etape = 0
        self.statut = "JOUER"
        self.retard_constate = False
        self.solde_virtuel = 0
        self.compteur_carton = 0
        self.cartons_passes = 0

    def intention(self):
        if self.dec > 0 or self.statut == "ARRET" or not self.retard_constate:
            return None
        return self.fig[self.index_etape]

    def actualiser(self, tirage_epure, est_zero):
        if self.dec > 0:
            if not est_zero:
                self.dec -= 1
            return

        gain = 0
        if est_zero:
            if self.statut == "JOUER":
                gain = -0.5
        else:
            self.compteur_carton += 1
            attendu = self.fig[self.index_etape]
            
            if self.statut == "JOUER":
                if tirage_epure == attendu:
                    gain = 1
                    self.index_etape += 1
                else:
                    gain = -1
                    self.statut = "ARRET"
                    self.index_etape += 1
            else:
                self.index_etape += 1

        self.solde_virtuel += gain

        if not est_zero and self.index_etape >= 3:
            self.index_etape = 0
            self.statut = "JOUER"

        if not est_zero and self.compteur_carton == 24:
            self.cartons_passes += 1
            norme = self.cartons_passes * 3
            self.retard_constate = self.solde_virtuel < norme
            self.compteur_carton = 0

# --- INITIALISATION ---
if "historique" not in st.session_state:
    st.session_state.historique = []
if "capital_reel" not in st.session_state:
    st.session_state.capital_reel = 0.0

# --- TRADUCTEUR DE NUMÉROS ---
def analyser_numero(num):
    if num == 0: 
        return "0", "0", "0"
    rouges = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    rn = "R" if num in rouges else "N"
    pi = "R" if num % 2 == 0 else "N"
    pm = "R" if num >= 19 else "N"
    return rn, pi, pm

# --- INTERFACE GRAPHIQUE ---
st.title("🎰 La Marche Triomphale — Analyseur Long Terme (72 Joueurs)")
st.write("Moteur de calcul à mémoire continue pour l'étude des grands retours à l'équilibre.")

# --- BARRE LATÉRALE (SIDEBAR) ---
st.sidebar.header("⚙️ CONTRÔLE DE SESSION")
st.sidebar.metric(label="💰 CAISSE RÉELLE (Unités)", value=f"{st.session_state.capital_reel} p.")

# Zone d'importation de secours (Saisie en bloc)
st.sidebar.subheader("🗃️ Importation / Secours")
import_txt = st.sidebar.text_area("Coller une série de numéros (séparés par des virgules) :", placeholder="Ex: 14,32,0,5,22,19")
if st.sidebar.button("📥 Importer la série", use_container_width=True):
    if import_txt:
        try:
            # Nettoyage et conversion du texte en liste de nombres
            nettoye = import_txt.replace("\n", "").replace(" ", "")
            liste_numeros = [int(x) for x in nettoye.split(",") if x != ""]
            # Validation des numéros de roulette
            if all(0 <= n <= 36 for n in liste_numeros):
                st.session_state.historique.extend(liste_numeros)
                st.sidebar.success(f"✅ +{len(liste_numeros)} numéros ajoutés !")
                st.rerun()
            else:
                st.sidebar.error("❌ Les numéros doivent être compris entre 0 et 36.")
        except ValueError:
            st.sidebar.error("❌ Format incorrect. Utilisez uniquement des chiffres et des virgules.")

st.sidebar.write("---")

# Générateur automatique pour les tests de masse
st.sidebar.subheader("🎲 Générateur de Masse")
nb_sim = st.sidebar.number_input("Nombre de coups à injecter :", min_value=10, max_value=10000, value=100, step=100)
if st.sidebar.button(f"⚡ Injecter +{nb_sim} coups", use_container_width=True):
    st.session_state.historique.extend([random.randint(0, 36) for _ in range(nb_sim)])
    st.rerun()

st.sidebar.write("---")

# Remise à zéro sécurisée
st.sidebar.subheader("🚨 Zone de Danger")
confirm_reset = st.sidebar.checkbox("⚠️ Activer le bouton de remise à zéro")
if confirm_reset:
    if st.sidebar.button("🔴 EFFACER TOUTE LA PERMANENCE", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- CLAVIER DE SAISIE MANUELLE ---
st.subheader("📥 Enregistrer un numéro (Sortie en direct)")
cols_clavier = st.columns(13)
with cols_clavier[0]:
    if st.button("🟢 0", use_container_width=True):
        st.session_state.historique.append(0)
        st.rerun()

for n in range(1, 37):
    col_idx = ((n - 1) % 12) + 1
    rouges = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    label = f"🔴 {n}" if n in rouges else f"⚫ {n}"
    with cols_clavier[col_idx]:
        if st.button(label, use_container_width=True):
            st.session_state.historique.append(n)
            st.rerun()

# --- RECONSTRUCTION DE L'ARMÉE DES 72 JOUEURS ET DES MISES ---
# Initialisation d'une armée locale fraîche pour retraiter fidèlement l'intégralité historique
armee_locale = {"RN": [], "PI": [], "PM": []}
id_j = 1
for chance in ["RN", "PI", "PM"]:
    for dec in [0, 1, 2]:
        for fig in FIGURES:
            armee_locale[chance].append(JoueurGlissant(id_j, chance, fig, dec))
            id_j += 1

votes = {"RN": {"R": 0, "N": 0}, "PI": {"R": 0, "N": 0}, "PM": {"R": 0, "N": 0}}
capital_calcule = 0.0

# Boucle ultra-rapide de retraitement historique
for num in st.session_state.historique:
    rn, pi, pm = analyser_numero(num)
    est_zero = (num == 0)
    
    # 1. Calcul des intentions AVANT ce tirage pour déterminer l'impact financier réel
    mises_du_coup = {}
    for chance in ["RN", "PI", "PM"]:
        v_r = sum(1 for j in armee_locale[chance] if j.intention() == "R")
        v_n = sum(1 for j in armee_locale[chance] if j.intention() == "N")
        mises_du_coup[chance] = v_r - v_n

    # 2. Application financière du tirage
    for chance, (tirage_code, code_r, code_n) in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "R", "N"))]:
        mise_engagee = mises_du_coup[chance]
        if mise_engagee != 0:
            if est_zero:
                capital_calcule -= abs(mise_engagee) * 0.5
            elif (mise_engagee > 0 and tirage_code == code_r) or (mise_engagee < 0 and tirage_code == code_n):
                capital_calcule += abs(mise_engagee)
            else:
                capital_calcule -= abs(mise_engagee)

    # 3. Actualisation des positions des joueurs
    for j in armee_locale["RN"]: j.actualiser(rn, est_zero)
    for j in armee_locale["PI"]: j.actualiser(pi, est_zero)
    for j in armee_locale["PM"]: j.actualiser(pm, est_zero)

st.session_state.capital_reel = capital_calcule

# Collecte des intentions pour la boule QUI VA SORTIR (Le Prochain Coup)
for chance in ["RN", "PI", "PM"]:
    for j in armee_locale[chance]:
        intent = j.intention()
        if intent: votes[chance][intent] += 1

# --- PANNEAU D'AFFICHAGE DES MISES NETTES ---
st.header("🎯 ORDRES DE MISES POUR LE PROCHAIN COUP")
c1, c2, c3 = st.columns(3)

def generer_bloc_mise(titre, v_r, v_n, label_r, label_n):
    bal = v_r - v_n
    with st.container(border=True):
        st.subheader(titre)
        if bal > 0:
            st.markdown(f"### 🟢 **{label_r} : {bal} p.**")
        elif bal < 0:
            st.markdown(f"### 🟢 **{label_n} : {abs(bal)} p.**")
        else:
            st.markdown("### ⏸️ **NE RIEN MISER**")
        st.caption(f"Forces en présence : {v_r} ({label_r}) | {v_n} ({label_n})")

with c1: generer_bloc_mise("Rouge / Noir", votes["RN"]["R"], votes["RN"]["N"], "ROUGE 🔴", "NOIR ⚫")
with c2: generer_bloc_mise("Pair / Impair", votes["PI"]["R"], votes["PI"]["N"], "PAIR 🔢", "IMPAIR 🔀")
with c3: generer_bloc_mise("Passe / Manque", votes["PM"]["R"], votes["PM"]["N"], "PASSE ⬆️", "MANQUE ⬇️")

# --- VISUALISATION DE LA PERMANENCE COURANTE ---
st.write("---")
st.subheader(f"📇 Permanence globale ({len(st.session_state.historique)} boules enregistrées)")
if st.session_state.historique:
    # Affichage intelligent des 150 derniers numéros pour ne pas saturer l'écran graphique
    if len(st.session_state.historique) > 150:
        st.info(f"... [Affichage des 150 derniers coups] ... , " + ", ".join([str(x) for x in st.session_state.historique[-150:]]))
    else:
        st.info(", ".join([str(x) for x in st.session_state.historique]))
else:
    st.write("*Le tableau de permanence est vide.*")
