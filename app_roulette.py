import streamlit as st
import pandas as pd
import random
import requests
import base64
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Marche Triomphale — Mémoire Éternelle", layout="wide", initial_sidebar_state="expanded")

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

# --- STRUCT DU JOUEUR ---
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
            if not est_zero: self.dec -= 1
            return

        gain = 0
        if est_zero:
            if self.statut == "JOUER": gain = -0.5
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

# --- CHARGEMENT ---
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

# --- CLAVIER ---
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

# --- RECONSTRUCTION CHRONOLOGIQUE STRICTE ---
armee_locale = {"RN": [], "PI": [], "PM": []}
id_j = 1
for chance in ["RN", "PI", "PM"]:
    for dec in [0, 1, 2]:
        for fig in FIGURES:
            armee_locale[chance].append(JoueurGlissant(id_j, chance, fig, dec))
            id_j += 1

capital_calcule = 0.0

# Traitement pas à pas
for num in st.session_state.historique:
    rn, pi, pm = analyser_numero(num)
    est_zero = (num == 0)
    
    # A. Relever les intentions AVANT que le numéro ne soit appliqué
    mises_du_coup = {}
    for chance in ["RN", "PI", "PM"]:
        v_r = sum(1 for j in armee_locale[chance] if j.intention() == "R")
        v_n = sum(1 for j in armee_locale[chance] if j.intention() == "N")
        mises_du_coup[chance] = v_r - v_n # Balance nette

    # B. Calculer l'impact financier immédiat du numéro sur la table
    for chance, (tirage_code, code_r, code_n) in [("RN", (rn, "R", "N")), ("PI", (pi, "R", "N")), ("PM", (pm, "R", "N"))]:
        net_mised = mises_du_coup[chance]
        if net_mised != 0:
            if est_zero:
                # Règle de partage de la roulette : demi-perte de la masse engagée net
                capital_calcule -= abs(net_mised) * 0.5
            elif (net_mised > 0 and tirage_code == code_r) or (net_mised < 0 and tirage_code == code_n):
                capital_calcule += abs(net_mised)
            else:
                capital_calcule -= abs(net_mised)

    # C. Maintenant seulement, faire progresser les joueurs internes
    for j in armee_locale["RN"]: j.actualiser(rn, est_zero)
    for j in armee_locale["PI"]: j.actualiser(pi, est_zero)
    for j in armee_locale["PM"]: j.actualiser(pm, est_zero)

st.session_state.capital_reel = capital_calcule
capital_placeholder.metric(label="💰 CAISSE RÉELLE (Unités)", value=f"{st.session_state.capital_reel} p.")

# Collecte des votes pour le PROCHAIN coup (Futur)
votes = {"RN": {"R": 0, "N": 0}, "PI": {"R": 0, "N": 0}, "PM": {"R": 0, "N": 0}}
for chance in ["RN", "PI", "PM"]:
    for j in armee_locale[chance]:
        intent = j.intention()
        if intent: votes[chance][intent] += 1

# --- AFFICHAGE DES ORDRES ---
st.header("🎯 ORDRES DE MISES POUR LE PROCHAIN COUP")
c1, c2, c3 = st.columns(3)

def generer_bloc_mise(titre, v_r, v_n, label_r, label_n):
    bal = v_r - v_n
    with st.container(border=True):
        st.subheader(titre)
        if bal > 0: st.markdown(f"### 🟢 **{label_r} : {bal} p.**")
        elif bal < 0: st.markdown(f"### 🟢 **{label_n} : {abs(bal)} p.**")
        else: st.markdown("### ⏸️ **NE RIEN MISER**")
        st.caption(f"Forces actives : {v_r} | {v_n}")

with c1: generer_bloc_mise("Rouge / Noir", votes["RN"]["R"], votes["RN"]["N"], "ROUGE 🔴", "NOIR ⚫")
with c2: generer_bloc_mise("Pair / Impair", votes["PI"]["R"], votes["PI"]["N"], "PAIR 🔢", "IMPAIR 🔀")
with c3: generer_bloc_mise("Passe / Manque", votes["PM"]["R"], votes["PM"]["N"], "PASSE ⬆️", "MANQUE ⬇️")

st.write("---")
st.subheader(f"📇 Permanence sauvegardée ({len(st.session_state.historique)} boules)")
if st.session_state.historique:
    if len(st.session_state.historique) > 150:
        st.info(f"... [Fichier long - 150 dernières boules affichées] ... , " + ", ".join([str(x) for x in st.session_state.historique[-150:]]))
    else:
        st.info(", ".join([str(x) for x in st.session_state.historique]))
else: st.write("*Aucune donnée enregistrée sur le cloud.*")
