import streamlit as st
import pandas as pd
import random

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Marche Triomphale - 72 Joueurs", layout="wide", initial_sidebar_state="expanded")

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

# --- INITIALISATION DE L'ARMÉE DES 72 JOUEURS ---
if "armee" not in st.session_state:
    armee = {"RN": [], "PI": [], "PM": []}
    id_j = 1
    for chance in ["RN", "PI", "PM"]:
        for dec in [0, 1, 2]:
            for fig in FIGURES:
                armee[chance].append(JoueurGlissant(id_j, chance, fig, dec))
                id_j += 1
    st.session_state.armee = armee
    st.session_state.historique = []
    st.session_state.capital_reel = 0.0

# --- TRADUCTEUR DE NUMÉROS RÉELS ---
def analyser_numero(num):
    if num == 0: 
        return "0", "0", "0"
    rouges = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    rn = "R" if num in rouges else "N"
    pi = "R" if num % 2 == 0 else "N"
    pm = "R" if num >= 19 else "N"
    return rn, pi, pm

# --- INTERFACE GRAPHIQUE ---
st.title("🎰 La Marche Triomphale — Assistant Multi-Chances (72 Joueurs)")
st.write("Suivi en temps réel des balances différentielles et mémoire continue.")

# --- BARRE LATÉRALE (SIDEBAR) ---
st.sidebar.header("⚙️ OPTIONS & SIMULATION")
st.sidebar.metric(label="💰 CAISSE RÉELLE (Unités)", value=f"{st.session_state.capital_reel} p.")

# Bouton Générateur de Nombres Aléatoires
st.sidebar.subheader("🎲 Générateur Automatique")
if st.sidebar.button("⚡ Injecter +100 coups aléatoires", use_container_width=True):
    for _ in range(100):
        # Génère un nombre entre 0 et 36 (37 possibilités équitables)
        nouveau_num = random.randint(0, 36)
        st.session_state.historique.append(nouveau_num)
    st.rerun()

st.sidebar.write("---")
# Réinitialisation déplacée dans la barre pour plus de clarté
if st.sidebar.button("🔄 Réinitialiser la permanence", use_container_width=True):
    st.session_state.clear()
    st.rerun()

# Clavier de Saisie Universel
st.subheader("📥 Enregistrer manuellement un numéro")
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

# --- MOTEUR DE CALCULS ---
votes = {"RN": {"R": 0, "N": 0}, "PI": {"R": 0, "N": 0}, "PM": {"R": 0, "N": 0}}

# Réinitialisation pour reconstruction
for chance in ["RN", "PI", "PM"]:
    for j in st.session_state.armee[chance]:
        j.index_etape = 0
        j.statut = "JOUER"
        j.retard_constate = False
        j.solde_virtuel = 0
        j.compteur_carton = 0
        j.cartons_passes = 0
        if j.id <= 8 or (j.id >= 25 and j.id <= 32) or (j.id >= 49 and j.id <= 56): j.dec = 0
        elif j.id <= 16 or (j.id >= 33 and j.id <= 40) or (j.id >= 57 and j.id <= 64): j.dec = 1
        else: j.dec = 2

capital_calculé = 0.0

for idx, num in enumerate(st.session_state.historique):
    rn, pi, pm = analyser_numero(num)
    est_zero = (num == 0)
    
    mises_du_coup = {}
    for chance, codes in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "R", "N"))]:
        v_r = sum(1 for j in st.session_state.armee[chance] if j.intention() == "R")
        v_n = sum(1 for j in st.session_state.armee[chance] if j.intention() == "N")
        mises_du_coup[chance] = v_r - v_n

    for chance, (tirage_code, code_r, code_n) in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "R", "N"))]:
        mise_engagee = mises_du_coup[chance]
        if mise_engagee != 0:
            if est_zero:
                capital_calculé -= abs(mise_engagee) * 0.5
            elif (mise_engagee > 0 and tirage_code == code_r) or (mise_engagee < 0 and tirage_code == code_n):
                capital_calculé += abs(mise_engagee)
            else:
                capital_calculé -= abs(mise_engagee)

    for j in st.session_state.armee["RN"]: j.actualiser(rn, est_zero)
    for j in st.session_state.armee["PI"]: j.actualiser(pi, est_zero)
    for j in st.session_state.armee["PM"]: j.actualiser(pm, est_zero)

st.session_state.capital_reel = capital_calculé

for chance in ["RN", "PI", "PM"]:
    for j in st.session_state.armee[chance]:
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
        st.caption(f"Forces : {v_r} ({label_r}) | {v_n} ({label_n})")

with c1: generer_bloc_mise("Rouge / Noir", votes["RN"]["R"], votes["RN"]["N"], "ROUGE 🔴", "NOIR ⚫")
with c2: generer_bloc_mise("Pair / Impair", votes["PI"]["R"], votes["PI"]["N"], "PAIR 🔢", "IMPAIR 🔀")
with c3: generer_bloc_mise("Passe / Manque", votes["PM"]["R"], votes["PM"]["N"], "PASSE ⬆️", "MANQUE ⬇️")

# --- VISUALISATION DE LA PERMANENCE COURANTE ---
st.write("---")
st.subheader(f"📇 Permanence en cours ({len(st.session_state.historique)} boules enregistrées)")
if st.session_state.historique:
    st.info(", ".join([str(x) for x in st.session_state.historique]))
else:
    st.write("*Le tableau est vide. Utilisez le bouton de simulation à gauche ou cliquez sur les numéros.*")