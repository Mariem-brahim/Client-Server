# Mini-projet Sockets : application client-serveur TCP en Python

Application **client-serveur TCP/IPv4** en Python qui utilise directement les appels système socket : `socket()`, `bind()`, `listen()`, `accept()`, `connect()`, `sendall()`, `recv()` et `close()`.
Projet réalisé en Master SSI, dans le module *Architecture et Sécurité des Systèmes d'Exploitation*.

- **`server.py`** : serveur itératif. Il sert les clients **l'un après l'autre**, répond à chaque message et journalise les connexions et les échanges dans `logs/server.log`.
- **`client.py`** : client interactif. Il se connecte au serveur, envoie les messages saisis au clavier, affiche les réponses et transforme chaque erreur réseau en message clair.

Aucune dépendance externe : seule la bibliothèque standard de Python est utilisée.

## Fonctionnalités

- Serveur TCP/IPv4 itératif avec file d'attente `listen()` : les clients suivants patientent pendant qu'un client est servi.
- Protocole applicatif à **en-tête de longueur** (4 octets) : chaque message est reçu en entier, même si TCP le découpe.
- Commandes `/aide`, `/heure` et `/quit` ; tout autre texte est renvoyé en écho.
- Journalisation horodatée (console + fichier) : IP, port et date de connexion de chaque client, messages reçus et envoyés, fins de session.
- Serveur robuste : déconnexion brutale, inactivité ou message invalide sont journalisés, puis le serveur passe au client suivant.
- Arrêt propre du serveur avec `Ctrl+C` ou `SIGTERM`.
- Testé avec un serveur sous Kali Linux et des clients sous Kali Linux et Windows (voir [Tests réalisés](#tests-réalisés)).

## Structure du dépôt

```text
.
├── server.py        # serveur TCP itératif
├── client.py        # client TCP interactif
├── logs/
│   └── server.log   # journal du serveur (créé automatiquement)
└── Rapport.pdf      # rapport du mini-projet : architecture, tests, limites
```

## Prérequis

- **Python 3.6 ou plus récent.** Sous Windows, utiliser `python` ou `py` à la place de `python3`.
- Pour tester sur deux machines : elles doivent être sur le même réseau local, et le pare-feu de la machine serveur doit autoriser les connexions entrantes sur le port TCP choisi (5000 par défaut).

## Démarrage rapide (une seule machine)

```bash
git clone https://github.com/Mariem-brahim/Client-Server.git
cd Client-Server
```

Terminal 1, le serveur (il n'écoute que sur la machine locale) :

```bash
python3 server.py --hote 127.0.0.1
```

Terminal 2, le client :

```bash
python3 client.py --hote 127.0.0.1
```

Exemple de session côté client :

```text
Connexion à 127.0.0.1:5000...
Connecté (adresse locale 127.0.0.1:43310).
En attente du serveur (il traite peut-être un autre client)...
Serveur > Bienvenue sur le serveur TCP ! Tapez /aide pour la liste des commandes.
Vous > Bonjour serveur !
Serveur > [14:07:32] Message n°1 reçu (17 caractères) : Bonjour serveur !
Vous > /heure
Serveur > Date et heure du serveur : 22/11/2026 14:07:32
Vous > /quit
Serveur > Au revoir ! Connexion fermée par le serveur.
Connexion fermée.
```

Pour quitter, taper `/quit` (ou `Ctrl+C` / `Ctrl+D` : le client envoie alors `/quit` de lui-même). Pour arrêter le serveur : `Ctrl+C`.

## Utilisation sur deux machines

1. **Sur la machine serveur**, lancer :

   ```bash
   python3 server.py
   ```

   Le serveur écoute sur toutes les interfaces (`0.0.0.0:5000`). Il affiche son adresse IP sur le réseau et la commande à lancer côté client :

   ```text
   2026-11-22 14:07:50 [INFO] Serveur en écoute sur 0.0.0.0:5000 (TCP/IPv4, backlog=5, inactivité max=300 s).
   2026-11-22 14:07:50 [INFO] Adresse IP de ce serveur sur le réseau : 192.168.1.20 -> côté client : python3 client.py --hote 192.168.1.20 --port 5000
   2026-11-22 14:07:50 [INFO] En attente d'un client...
   ```

2. **Sur la machine client**, lancer la commande affichée par le serveur :

   ```bash
   python3 client.py --hote 192.168.1.20
   ```

   Pour ne plus avoir à saisir `--hote`, modifier une seule fois la constante `IP_SERVEUR` en haut de `client.py`. Elle vaut `192.168.1.136` dans ce dépôt, l'adresse du serveur Kali utilisé pour les tests.

## Référence

### Serveur : `server.py`

| Option | Défaut | Rôle |
|---|---|---|
| `--hote` | `0.0.0.0` | Adresse IP d'écoute. `0.0.0.0` = toutes les interfaces ; `127.0.0.1` = machine locale uniquement. |
| `--port` | `5000` | Port TCP d'écoute (un port supérieur à 1023 évite d'avoir besoin des droits root). |
| `--timeout` | `300` | Délai d'inactivité d'un client, en secondes, avant que sa connexion soit coupée. |
| `--log` | `logs/server.log` | Fichier journal (à côté de `server.py` par défaut). Indiquer un chemin avec un dossier, par exemple `logs/test.log` ou `./test.log`. |

Codes de retour : `0` à l'arrêt normal, `1` si le serveur ne peut pas démarrer.

### Client : `client.py`

| Option | Défaut | Rôle |
|---|---|---|
| `--hote` | `IP_SERVEUR` (`192.168.1.136`) | Adresse IP du serveur. |
| `--port` | `5000` | Port TCP du serveur. |

Délais : 5 s pour établir la connexion, 30 s pour recevoir la réponse à un message. L'attente du message de bienvenue n'est pas limitée, car le serveur peut être occupé avec un autre client.

Codes de retour : `0` fin normale, `1` connexion impossible, `2` erreur pendant l'échange.

### Commandes

Tapées côté client et interprétées par le serveur (sans tenir compte de la casse) :

| Commande | Effet |
|---|---|
| `/aide` | Affiche la liste des commandes. |
| `/heure` | Donne la date et l'heure du serveur. |
| `/quit` | Termine la session : le serveur répond « Au revoir ! Connexion fermée par le serveur. » puis ferme la connexion. |
| *autre texte* | Renvoyé en écho : `[HH:MM:SS] Message n°N reçu (L caractères) : …` |

`quit` sans barre oblique n'est **pas** une commande : c'est un message ordinaire, renvoyé en écho.

## Protocole applicatif

TCP transporte un flux d'octets : un `recv(n)` peut renvoyer moins de `n` octets. Chaque message est donc précédé de sa longueur :

| Champ | Taille | Contenu |
|---|---|---|
| Longueur `N` | 4 octets | entier non signé, big-endian (format `struct` : `"!I"`) |
| Données | `N` octets | texte encodé en UTF-8 |

Exemple : `/aide` (5 octets en UTF-8) est transmis sous la forme `00 00 00 05 2f 61 69 64 65`.

- Un message est lu avec `recevoir_exactement()`, qui boucle sur `recv()` jusqu'à avoir reçu tous les octets attendus, et envoyé avec `sendall()`.
- Taille maximale : 64 Kio par message. Au-delà, ou si le contenu n'est pas de l'UTF-8 valide, le message est rejeté et la connexion est coupée.
- Dès la connexion, le serveur envoie un message de bienvenue. Ensuite, chaque message du client reçoit exactement une réponse.

Enchaînement des appels système :

```text
Serveur : socket() → setsockopt(SO_REUSEADDR) → bind() → listen(5)
          → boucle : accept() → bienvenue → [ recv() → sendall() ]… → close() (socket du client)
          → à l'arrêt : close() de la socket d'écoute

Client  : socket() → connect() → recv() (bienvenue) → [ sendall() → recv() ]… → close()
```

## Journal du serveur

Le serveur écrit les mêmes lignes sur la console et dans `logs/server.log` (UTF-8, en mode ajout : les sessions précédentes sont conservées). Le dossier `logs/` est créé s'il n'existe pas. Chaque ligne porte la date, l'heure et le niveau (`INFO`, `WARNING` ou `ERROR`).

```text
2026-11-22 14:07:32 [INFO] Serveur en écoute sur 127.0.0.1:5000 (TCP/IPv4, backlog=5, inactivité max=300 s).
2026-11-22 14:07:32 [INFO] En attente d'un client...
[...]
2026-11-22 14:07:33 [INFO] Client n°2 connecté : IP=127.0.0.1, port=43312, le 22/11/2026 à 14:07:33.
2026-11-22 14:07:33 [INFO] [127.0.0.1:43312] REÇU    : 'Bonjour, ici le client 2'
2026-11-22 14:07:33 [INFO] [127.0.0.1:43312] ENVOYÉ  : '[14:07:33] Message n°1 reçu (24 caractères) : Bonjour, ici le client 2'
2026-11-22 14:07:33 [INFO] [127.0.0.1:43312] REÇU    : '/quit'
2026-11-22 14:07:33 [INFO] [127.0.0.1:43312] ENVOYÉ  : 'Au revoir ! Connexion fermée par le serveur.'
2026-11-22 14:07:33 [INFO] [127.0.0.1:43312] Déconnexion propre (/quit) après 2 message(s).
2026-11-22 14:07:33 [INFO] [127.0.0.1:43312] Socket de connexion fermée.
2026-11-22 14:07:33 [INFO] Fin de session du client n°2.
[...]
2026-11-22 14:07:33 [WARNING] [127.0.0.1:43326] Déconnexion inattendue : connexion fermée par le pair (2/4 octets reçus).
```

## Robustesse et dépannage

### Côté serveur

Le serveur ne s'arrête pas quand un client pose problème : l'incident est journalisé, la socket du client est fermée (`close()` dans un bloc `finally`), puis le serveur retourne à `accept()`.

| Situation | Entrée du journal |
|---|---|
| Client parti sans `/quit` | `WARNING` : Déconnexion inattendue : connexion fermée par le pair (x/n octets reçus) |
| Connexion réinitialisée ou rompue (`ConnectionResetError`, `BrokenPipeError`…) | `WARNING` : Connexion interrompue brutalement |
| Aucun message pendant `--timeout` secondes | `WARNING` : Aucun message depuis N s : connexion coupée |
| Message trop grand ou non UTF-8 | `WARNING` : Message invalide (…) : connexion coupée |
| Autre erreur réseau | `ERROR` : Erreur réseau |
| Démarrage impossible (port déjà utilisé, adresse inexistante, port inférieur à 1024 sans droits root) | `ERROR` : Impossible de démarrer le serveur sur … (code de retour 1) |

### Côté client

| Message affiché | Cause probable | Que faire |
|---|---|---|
| `Erreur : connexion refusée. Le serveur est-il démarré sur ce port ?` | Serveur non lancé, ou port différent. | Démarrer `server.py` ; vérifier que `--port` est identique des deux côtés. |
| `Erreur : pas de réponse de <IP> après 5 s.` | IP incorrecte, réseaux différents, ou pare-feu qui bloque le port. | Vérifier l'IP affichée par le serveur ; autoriser le port en entrée sur la machine serveur. |
| `Erreur : adresse « … » invalide ou introuvable.` | Adresse ou nom d'hôte invalide. | Corriger `--hote` (ou `IP_SERVEUR`). |
| `En attente du serveur (il traite peut-être un autre client)...` qui dure | Le serveur est itératif : il sert un autre client. | Attendre la fin de session de l'autre client (au plus `--timeout` secondes s'il est inactif). |
| `Le serveur a fermé la connexion de façon inattendue.` | Serveur arrêté, ou délai d'inactivité dépassé. | Relancer le client (et le serveur si besoin). |
| `Erreur : aucune réponse du serveur depuis 30 s.` | Serveur bloqué ou réseau coupé. | Vérifier le serveur, puis relancer. |

## Tests réalisés

Six tests ont été réalisés le 21/11/2026 sur un réseau local : le serveur tournait sous Kali Linux (`192.168.1.136`, port 5000) et les clients sous Kali Linux ou sous Windows (`192.168.1.140`). Tous ont donné le résultat attendu. Les captures d'écran correspondantes sont dans le [rapport](Rapport.pdf).

| # | Test | Résultat |
|---|---|---|
| 1 | Démarrage du serveur | Écoute sur `0.0.0.0:5000` ; affichage de l'IP à utiliser côté client. |
| 2 | Connexion d'un client et échange de messages | Message de bienvenue, réponses numérotées, accents transmis correctement. |
| 3 | Plusieurs clients successivement | Le deuxième client attend dans la file de `listen()`, puis est servi après le départ du premier. |
| 4 | Client sur une autre machine (Windows vers Kali) | Connexion et échange à travers le réseau local. |
| 5 | Déconnexions inattendues | Client fermé en pleine session, ou disparu avant son message : incident journalisé, le serveur reste disponible. |
| 6 | Journal des connexions et des échanges | Mêmes lignes horodatées écrites dans `logs/`. |

## Limites et pistes d'amélioration

- **Un seul client à la fois.** Un client inactif bloque les autres jusqu'à `--timeout` secondes (300 s par défaut). Un thread par client (`threading`) ou le module `selectors` permettrait de servir plusieurs clients en parallèle.
- **Pas de chiffrement ni d'authentification.** Les messages circulent et sont journalisés en clair. Le module `ssl` (TLS) chiffrerait les échanges, et limiter le nombre de connexions réduirait les abus. Sous Windows, l'option `SO_EXCLUSIVEADDRUSE` empêcherait en plus un autre programme de se lier au même port, ce que `SO_REUSEADDR` ne fait pas.

## Auteurs

- Brahim Mariem

Module *Architecture et Sécurité des Systèmes d'Exploitation* : M. Kachallah.
