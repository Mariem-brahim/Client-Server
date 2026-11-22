#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — Serveur TCP IPv4 itératif (un client à la fois, clients successifs).

Mini-projet Master SSI : application client-serveur avec les appels système socket.

Déroulement (cf. schéma du cours) :
    socket() -> bind() -> listen() -> [ accept() -> recv()/sendall() ... -> close() ] -> accept() ...

Protocole applicatif (identique dans client.py) :
    chaque message = en-tête de 4 octets (longueur N, entier non signé big-endian)
                     + N octets de texte UTF-8.
    Ce découpage règle le problème des réceptions partielles de TCP (flux d'octets).

Commandes reconnues : /aide, /heure, /quit. Tout autre texte est renvoyé en écho.

Usage :
    python3 server.py                       # écoute sur toutes les interfaces, port 5000
    python3 server.py --hote 127.0.0.1      # écoute uniquement en local (même machine)
    python3 server.py --port 6000 --timeout 300
"""

import argparse
import logging
import os
import signal
import socket
import struct
import sys
from datetime import datetime

# --------------------------------------------------------------------------
# Paramètres
# --------------------------------------------------------------------------
HOTE_PAR_DEFAUT = "0.0.0.0"     # toutes les interfaces : joignable depuis une autre machine du réseau
PORT_PAR_DEFAUT = 5000          # port > 1023 : pas besoin des droits root
BACKLOG = 5                     # taille de la file des connexions en attente d'accept()
TAILLE_ENTETE = 4               # en-tête = longueur du message sur 4 octets
TAILLE_MAX = 64 * 1024          # 64 Kio maximum par message (protection mémoire)
DELAI_INACTIVITE = 300          # secondes sans message avant de couper un client

DOSSIER_PROJET = os.path.dirname(os.path.abspath(__file__))
FICHIER_LOG_PAR_DEFAUT = os.path.join(DOSSIER_PROJET, "logs", "server.log")

AIDE = (
    "Commandes disponibles :\n"
    "  /aide   affiche cette aide\n"
    "  /heure  donne la date et l'heure du serveur\n"
    "  /quit   termine proprement la connexion\n"
    "  (tout autre texte est renvoyé en écho)"
)


# --------------------------------------------------------------------------
# Exceptions propres au protocole
# --------------------------------------------------------------------------
class ConnexionFermee(Exception):
    """Le pair a fermé la connexion : recv() a renvoyé 0 octet."""


class MessageInvalide(Exception):
    """Les données reçues ne respectent pas le protocole (taille, encodage)."""


# --------------------------------------------------------------------------
# Journalisation
# --------------------------------------------------------------------------
def configurer_journal(chemin_log):
    """Crée un logger qui écrit à la fois dans le fichier log et sur la console."""
    os.makedirs(os.path.dirname(chemin_log), exist_ok=True)

    journal = logging.getLogger("serveur")
    journal.setLevel(logging.INFO)
    format_ = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                "%Y-%m-%d %H:%M:%S")

    fichier = logging.FileHandler(chemin_log, encoding="utf-8")   # mode "a" : on ajoute
    fichier.setFormatter(format_)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(format_)

    journal.addHandler(fichier)
    journal.addHandler(console)
    return journal


# --------------------------------------------------------------------------
# Protocole : envoi / réception d'un message complet
# --------------------------------------------------------------------------
def recevoir_exactement(sock, n):
    """
    Lit exactement n octets sur la socket.

    recv(n) renvoie AU PLUS n octets : il peut en renvoyer moins (réception
    partielle). On boucle donc jusqu'à avoir tout reçu.
    recv() renvoie b"" quand le pair a fermé la connexion (FIN TCP).
    """
    donnees = bytearray()
    while len(donnees) < n:
        morceau = sock.recv(n - len(donnees))
        if not morceau:
            raise ConnexionFermee(f"connexion fermée par le pair "
                                  f"({len(donnees)}/{n} octets reçus)")
        donnees.extend(morceau)
    return bytes(donnees)


def recevoir_message(sock):
    """Reçoit un message complet : en-tête de 4 octets puis contenu UTF-8."""
    entete = recevoir_exactement(sock, TAILLE_ENTETE)
    (taille,) = struct.unpack("!I", entete)          # "!" = ordre réseau (big-endian)
    if taille > TAILLE_MAX:
        raise MessageInvalide(f"taille annoncée {taille} > {TAILLE_MAX} octets")
    contenu = recevoir_exactement(sock, taille)
    try:
        return contenu.decode("utf-8")
    except UnicodeDecodeError as erreur:
        raise MessageInvalide("contenu non UTF-8") from erreur


def envoyer_message(sock, texte):
    """Envoie un message complet : en-tête (longueur) + contenu, avec sendall()."""
    contenu = texte.encode("utf-8")
    if len(contenu) > TAILLE_MAX:
        raise MessageInvalide("message trop long")
    # sendall() boucle en interne sur send() jusqu'à ce que tout soit envoyé.
    sock.sendall(struct.pack("!I", len(contenu)) + contenu)


def fermer_connexion(sock):
    """Ferme proprement une socket de connexion (sans jamais lever d'exception)."""
    try:
        sock.shutdown(socket.SHUT_RDWR)   # envoie le FIN : « je n'enverrai plus rien »
    except OSError:
        pass                               # déjà fermée par le pair : rien à faire
    sock.close()                           # libère le descripteur de fichier


# --------------------------------------------------------------------------
# Logique applicative
# --------------------------------------------------------------------------
def construire_reponse(message, numero):
    """
    Calcule la réponse à un message.
    Renvoie (texte_reponse, fin_de_session).
    """
    commande = message.strip().lower()
    if commande == "/quit":
        return "Au revoir ! Connexion fermée par le serveur.", True
    if commande == "/heure":
        return "Date et heure du serveur : " + datetime.now().strftime("%d/%m/%Y %H:%M:%S"), False
    if commande == "/aide":
        return AIDE, False
    heure = datetime.now().strftime("%H:%M:%S")
    return f"[{heure}] Message n°{numero} reçu ({len(message)} caractères) : {message}", False


def traiter_client(conn, ip, port, journal, delai):
    """
    Dialogue avec UN client jusqu'à sa déconnexion (propre ou non).
    Ne lève jamais d'exception réseau : toute erreur termine la session de CE
    client uniquement, le serveur continue ensuite avec le client suivant.
    """
    client = f"{ip}:{port}"
    conn.settimeout(delai)   # recv() lèvera socket.timeout après `delai` s d'inactivité
    nb_messages = 0
    try:
        envoyer_message(conn, "Bienvenue sur le serveur TCP ! Tapez /aide pour la liste des commandes.")
        while True:
            message = recevoir_message(conn)                 # appel bloquant (recv)
            nb_messages += 1
            journal.info("[%s] REÇU    : %r", client, message)

            reponse, fin = construire_reponse(message, nb_messages)
            envoyer_message(conn, reponse)                   # sendall
            journal.info("[%s] ENVOYÉ  : %r", client, reponse)

            if fin:
                journal.info("[%s] Déconnexion propre (/quit) après %d message(s).",
                             client, nb_messages)
                break

    # --- Déconnexions inattendues et erreurs : on journalise et on continue ---
    except ConnexionFermee as erreur:
        journal.warning("[%s] Déconnexion inattendue : %s.", client, erreur)
    except socket.timeout:
        journal.warning("[%s] Aucun message depuis %d s : connexion coupée.", client, delai)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as erreur:
        journal.warning("[%s] Connexion interrompue brutalement : %s.", client, erreur)
    except MessageInvalide as erreur:
        journal.warning("[%s] Message invalide (%s) : connexion coupée.", client, erreur)
    except OSError as erreur:
        journal.error("[%s] Erreur réseau : %s.", client, erreur)
    finally:
        fermer_connexion(conn)                               # close() de la socket CLIENT
        journal.info("[%s] Socket de connexion fermée.", client)
    return nb_messages


def adresse_ip_locale():
    """
    Renvoie l'adresse IP de cette machine sur le réseau local (ex. 192.168.1.20).

    Astuce : on « connecte » une socket UDP vers une adresse extérieure. Pour UDP,
    connect() n'envoie AUCUN paquet : le noyau choisit seulement l'interface de
    sortie, dont getsockname() donne alors l'adresse IP.
    """
    sonde = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sonde.connect(("8.8.8.8", 80))
        return sonde.getsockname()[0]
    except OSError:
        return "127.0.0.1"          # pas de réseau : seule la boucle locale existe
    finally:
        sonde.close()


def creer_socket_serveur(hote, port):
    """socket() -> setsockopt() -> bind() -> listen() : prépare la socket d'écoute."""
    # AF_INET = IPv4 ; SOCK_STREAM = TCP (flux fiable, ordonné, orienté connexion)
    serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Permet de relancer le serveur immédiatement sur le même port
        # (sinon « Address already in use » tant que l'ancienne connexion est en TIME_WAIT).
        serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serveur.bind((hote, port))       # associe la socket à (adresse IP, port)
        serveur.listen(BACKLOG)          # passe en mode écoute passive
    except OSError:
        serveur.close()
        raise
    return serveur


def boucle_principale(hote, port, delai, journal):
    """Accepte les clients les uns après les autres, indéfiniment."""
    serveur = creer_socket_serveur(hote, port)
    journal.info("Serveur en écoute sur %s:%d (TCP/IPv4, backlog=%d, inactivité max=%d s).",
                 hote, port, BACKLOG, delai)
    if hote == "0.0.0.0":
        ip = adresse_ip_locale()
        journal.info("Adresse IP de ce serveur sur le réseau : %s -> côté client : "
                     "python3 client.py --hote %s --port %d", ip, ip, port)
    numero_client = 0
    try:
        while True:
            journal.info("En attente d'un client...")
            try:
                # accept() bloque jusqu'à une connexion et renvoie une NOUVELLE socket
                # dédiée à ce client, plus l'adresse (IP, port) du client.
                conn, (ip_client, port_client) = serveur.accept()
            except OSError as erreur:
                journal.error("accept() a échoué : %s", erreur)
                continue

            numero_client += 1
            date_connexion = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
            journal.info("Client n°%d connecté : IP=%s, port=%d, le %s.",
                         numero_client, ip_client, port_client, date_connexion)

            traiter_client(conn, ip_client, port_client, journal, delai)
            # Ici seule la connexion du client est fermée : le serveur reste actif.
            journal.info("Fin de session du client n°%d.", numero_client)

    except KeyboardInterrupt:
        journal.info("Arrêt demandé par l'administrateur (Ctrl+C).")
    finally:
        serveur.close()                  # close() de la socket d'ÉCOUTE = arrêt du serveur
        journal.info("Socket d'écoute fermée. Serveur arrêté (%d client(s) servi(s)).",
                     numero_client)


def main():
    parser = argparse.ArgumentParser(description="Serveur TCP IPv4 (mini-projet sockets).")
    parser.add_argument("--hote", default=HOTE_PAR_DEFAUT,
                        help="adresse IP d'écoute (0.0.0.0 = toutes les interfaces)")
    parser.add_argument("--port", type=int, default=PORT_PAR_DEFAUT, help="port TCP d'écoute")
    parser.add_argument("--timeout", type=int, default=DELAI_INACTIVITE,
                        help="délai d'inactivité d'un client, en secondes")
    parser.add_argument("--log", default=FICHIER_LOG_PAR_DEFAUT, help="chemin du fichier journal")
    args = parser.parse_args()

    journal = configurer_journal(args.log)

    # `kill <PID>` (SIGTERM) arrête aussi le serveur proprement : sys.exit() fait
    # remonter SystemExit, ce qui exécute le bloc finally (fermeture + log).
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

    try:
        boucle_principale(args.hote, args.port, args.timeout, journal)
    except OSError as erreur:
        # Typiquement : port déjà utilisé, adresse inexistante, port < 1024 sans root.
        journal.error("Impossible de démarrer le serveur sur %s:%d : %s",
                      args.hote, args.port, erreur)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
