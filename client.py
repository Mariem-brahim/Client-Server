#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
client.py — Client TCP IPv4 interactif.

Mini-projet Master SSI : application client-serveur avec les appels système socket.

Déroulement (cf. schéma du cours) :
    socket() -> connect() -> [ sendall() -> recv() ] x N -> close()

Protocole applicatif (identique dans server.py) :
    chaque message = en-tête de 4 octets (longueur N, big-endian) + N octets UTF-8.

Usage :
    python3 client.py                         # se connecte à IP_SERVEUR (défini ci-dessous)
    python3 client.py --hote 127.0.0.1        # autre adresse, ponctuellement
Tapez /quit (ou Ctrl+D, Ctrl+C) pour se déconnecter proprement.
"""

import argparse
import socket
import struct
import sys

# --------------------------------------------------------------------------
# Paramètres
# --------------------------------------------------------------------------
# >>> À MODIFIER UNE SEULE FOIS : adresse IP de la machine qui exécute server.py <<<
# (le serveur l'affiche au démarrage : « Adresse IP de ce serveur sur le réseau : ... »)
# Mettre "127.0.0.1" si le client et le serveur sont sur la même machine.
IP_SERVEUR = "192.168.1.136"
PORT_PAR_DEFAUT = 5000
TAILLE_ENTETE = 4
TAILLE_MAX = 64 * 1024
DELAI_CONNEXION = 5      # secondes max pour établir la connexion TCP
DELAI_REPONSE = 30       # secondes max pour recevoir la réponse à un message


# --------------------------------------------------------------------------
# Exceptions propres au protocole
# --------------------------------------------------------------------------
class ConnexionFermee(Exception):
    """Le serveur a fermé la connexion : recv() a renvoyé 0 octet."""


class MessageInvalide(Exception):
    """Les données reçues ne respectent pas le protocole."""


# --------------------------------------------------------------------------
# Protocole : mêmes fonctions que dans server.py
# --------------------------------------------------------------------------
def recevoir_exactement(sock, n):
    """Lit exactement n octets (boucle sur recv() pour gérer les réceptions partielles)."""
    donnees = bytearray()
    while len(donnees) < n:
        morceau = sock.recv(n - len(donnees))
        if not morceau:
            raise ConnexionFermee("le serveur a fermé la connexion")
        donnees.extend(morceau)
    return bytes(donnees)


def recevoir_message(sock):
    """Reçoit un message complet : en-tête de 4 octets puis contenu UTF-8."""
    (taille,) = struct.unpack("!I", recevoir_exactement(sock, TAILLE_ENTETE))
    if taille > TAILLE_MAX:
        raise MessageInvalide(f"taille annoncée trop grande ({taille} octets)")
    try:
        return recevoir_exactement(sock, taille).decode("utf-8")
    except UnicodeDecodeError as erreur:
        raise MessageInvalide("contenu non UTF-8") from erreur


def envoyer_message(sock, texte):
    """Envoie un message complet (longueur + contenu) avec sendall()."""
    contenu = texte.encode("utf-8")
    if len(contenu) > TAILLE_MAX:
        raise MessageInvalide(f"message trop long (max {TAILLE_MAX} octets)")
    sock.sendall(struct.pack("!I", len(contenu)) + contenu)


def fermer_connexion(sock):
    """Ferme proprement la socket (sans jamais lever d'exception)."""
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    sock.close()


# --------------------------------------------------------------------------
# Logique du client
# --------------------------------------------------------------------------
def connecter(hote, port):
    """socket() + connect() ; renvoie la socket connectée ou lève une exception."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # TCP / IPv4
    sock.settimeout(DELAI_CONNEXION)     # évite d'attendre indéfiniment un hôte muet
    try:
        sock.connect((hote, port))       # poignée de main TCP (SYN, SYN-ACK, ACK)
    except BaseException:
        sock.close()                     # pas de fuite de descripteur en cas d'échec
        raise
    return sock


def boucle_dialogue(sock):
    """Lit les saisies de l'utilisateur, les envoie, affiche les réponses."""
    while True:
        try:
            texte = input("Vous > ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D (fin de saisie) ou Ctrl+C : on se déconnecte poliment.
            print("\n(déconnexion demandée)")
            texte = "/quit"

        if not texte:
            continue                     # on n'envoie pas de message vide

        envoyer_message(sock, texte)                 # sendall
        reponse = recevoir_message(sock)             # recv (avec délai DELAI_REPONSE)
        print(f"Serveur > {reponse}")

        if texte.lower() == "/quit":
            break


def main():
    parser = argparse.ArgumentParser(description="Client TCP IPv4 (mini-projet sockets).")
    parser.add_argument("--hote", default=IP_SERVEUR,
                        help=f"adresse IP du serveur (défaut : {IP_SERVEUR})")
    parser.add_argument("--port", type=int, default=PORT_PAR_DEFAUT, help="port TCP du serveur")
    args = parser.parse_args()

    # ---- 1. Connexion : erreurs possibles AVANT tout échange ----
    print(f"Connexion à {args.hote}:{args.port}...")
    try:
        sock = connecter(args.hote, args.port)
    except ConnectionRefusedError:
        print("Erreur : connexion refusée. Le serveur est-il démarré sur ce port ?")
        return 1
    except socket.timeout:
        print(f"Erreur : pas de réponse de {args.hote} après {DELAI_CONNEXION} s.")
        return 1
    except socket.gaierror:
        print(f"Erreur : adresse « {args.hote} » invalide ou introuvable.")
        return 1
    except OSError as erreur:
        print(f"Erreur réseau lors de la connexion : {erreur}")
        return 1

    ip_locale, port_local = sock.getsockname()
    print(f"Connecté (adresse locale {ip_locale}:{port_local}).")

    # ---- 2. Dialogue : erreurs possibles PENDANT l'échange ----
    code_retour = 0
    try:
        # Si le serveur est occupé avec un autre client, la connexion TCP est
        # établie (file de listen) mais accept() n'a pas encore eu lieu :
        # on attend le message de bienvenue sans limite de temps.
        print("En attente du serveur (il traite peut-être un autre client)...")
        sock.settimeout(None)
        print(f"Serveur > {recevoir_message(sock)}")

        sock.settimeout(DELAI_REPONSE)
        boucle_dialogue(sock)
    except ConnexionFermee:
        print("\nLe serveur a fermé la connexion de façon inattendue.")
        code_retour = 2
    except socket.timeout:
        print(f"\nErreur : aucune réponse du serveur depuis {DELAI_REPONSE} s.")
        code_retour = 2
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        print("\nLa connexion a été interrompue brutalement par le serveur.")
        code_retour = 2
    except MessageInvalide as erreur:
        print(f"\nErreur de protocole : {erreur}")
        code_retour = 2
    except KeyboardInterrupt:
        print("\nInterruption pendant l'attente du serveur.")
    except OSError as erreur:
        print(f"\nErreur réseau : {erreur}")
        code_retour = 2
    finally:
        fermer_connexion(sock)           # close() : toujours exécuté
        print("Connexion fermée.")
    return code_retour


if __name__ == "__main__":
    sys.exit(main())
