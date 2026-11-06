from flask import Flask, abort, flash, render_template_string, render_template, jsonify, request, redirect, url_for, session
from flask import json
from urllib.request import urlopen
from werkzeug.utils import secure_filename     
import hmac
from datetime import date as date_iso, datetime, timezone
import os
import re
import shutil
import sqlite3
from functools import wraps

# Sans fuseau disponible sur le serveur, le journal s'affiche en heure UTC plutôt que de bloquer le site
try:
    from zoneinfo import ZoneInfo
    FUSEAU_PARIS = ZoneInfo('Europe/Paris')
except Exception:
    FUSEAU_PARIS = None

app = Flask(__name__)                                                                                                                  
# Nom attendu par uWSGI sur Alwaysdata
application = app
# Clé secrète des sessions. Sans SECRET_KEY, une clé temporaire déconnecte tout le monde au redémarrage.
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(32)
# Empêche un autre site d'envoyer les formulaires à la place d'un utilisateur connecté
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Une ancienne base n'accepte qu'une ligne par référence dans INVENTAIRE.
# On reconstruit la table une seule fois, après une copie de sauvegarde de la base.
def reference_est_unique(conn):
    return any(colonne[1] == 'REF' and colonne[5] for colonne in conn.execute('PRAGMA table_info(INVENTAIRE)'))

def lever_limite_par_reference(conn):
    if not reference_est_unique(conn):
        return
    if not os.path.exists('schutz.db.avant_multi_articles'):
        shutil.copy2('schutz.db', 'schutz.db.avant_multi_articles')
    conn.isolation_level = None
    # Sans ce réglage, renommer la table échoue car les vues la cherchent pendant le renommage
    conn.execute('PRAGMA legacy_alter_table = ON')
    conn.execute('BEGIN IMMEDIATE')
    try:
        # Un autre processus a pu faire le travail pendant l'attente du verrou
        if reference_est_unique(conn):
            declencheurs = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'INVENTAIRE'").fetchall()
            conn.execute('''CREATE TABLE INVENTAIRE_NOUVELLE (
                REF varchar(50) not null,
                Date date not null,
                ALLEE_ID char(1) not null,
                ID numeric(1) not null,
                constraint FKALLEE unique (ALLEE_ID, ID),
                foreign key (ALLEE_ID, ID) references EMPLACEMENTS)''')
            conn.execute('INSERT INTO INVENTAIRE_NOUVELLE (REF, Date, ALLEE_ID, ID) SELECT REF, Date, ALLEE_ID, ID FROM INVENTAIRE')
            conn.execute('DROP TABLE INVENTAIRE')
            conn.execute('ALTER TABLE INVENTAIRE_NOUVELLE RENAME TO INVENTAIRE')
            conn.execute('CREATE INDEX IX_INVENTAIRE_REF ON INVENTAIRE (REF)')
            for (sql,) in declencheurs:
                conn.execute(sql)
        conn.execute('COMMIT')
    except sqlite3.Error:
        conn.execute('ROLLBACK')
        raise
    finally:
        conn.execute('PRAGMA legacy_alter_table = OFF')
        conn.isolation_level = ''

# Met la base à jour au démarrage. Une erreur ici ne doit pas empêcher le site de démarrer.
def appliquer_migration_mouvements():
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Documents', 'migration_mouvements.sql')
    conn = sqlite3.connect('schutz.db')
    try:
        lever_limite_par_reference(conn)
        with open(chemin, encoding='utf-8') as fichier:
            conn.executescript(fichier.read())
    except (OSError, sqlite3.Error):
        app.logger.exception('Migration du journal des mouvements impossible')
    finally:
        conn.close()

appliquer_migration_mouvements()


@app.route('/')
def acceuil():
    return render_template('accueil.html', produits_arretes=lire_produits_arretes())

# Affiche une date AAAA-MM-JJ au format JJ/MM/AAAA
@app.template_filter('date_fr')
def date_fr(valeur):
    try:
        return date_iso.fromisoformat(str(valeur)).strftime('%d/%m/%Y')
    except ValueError:
        return valeur

# Affiche une date du journal à l'heure de Paris. Une date sans heure reste une simple date.
@app.template_filter('date_heure_fr')
def date_heure_fr(valeur):
    if len(str(valeur)) <= 10:
        return date_fr(valeur)
    try:
        moment = datetime.fromisoformat(str(valeur)).replace(tzinfo=timezone.utc)
    except ValueError:
        return valeur
    if FUSEAU_PARIS is None:
        return moment.strftime('%d/%m/%Y %H:%M UTC')
    return moment.astimezone(FUSEAU_PARIS).strftime('%d/%m/%Y %H:%M')

# Références dont l'arrêt est annoncé. Liste vide si la migration n'a pas encore été lancée.
def lire_produits_arretes():
    conn = sqlite3.connect('schutz.db')
    try:
        return conn.execute('SELECT REF, DATE_ARRET FROM V_PRODUITS_ARRETES ORDER BY DATE_ARRET, REF').fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

# Fonction pour créer une clé "authentifie" dans la session utilisateur
def est_authentifie():
    return session.get('authentifie')

# Protège une page : sans connexion, redirection vers le formulaire d'authentification
def connexion_requise(vue):
    @wraps(vue)
    def verifier(*args, **kwargs):
        if not est_authentifie():
            return redirect(url_for('authentification'))
        return vue(*args, **kwargs)
    return verifier

# Compare un mot de passe saisi à celui de l'environnement. Sans variable définie, l'accès est refusé.
def mot_de_passe_valide(saisi, variable):
    attendu = os.environ.get(variable)
    return bool(attendu) and hmac.compare_digest(saisi.encode(), attendu.encode())

# Route de lecture restreinte aux utilisateurs authentifiés
@app.route('/inventaire', methods=['GET'])
def inventaire():
    if not est_authentifie():
        # Si l'utilisateur n'est pas authentifié, redirection vers le formulaire d'authentification
        return redirect(url_for('authentification'))
    
    # Si l'utilisateur est authentifié, afficher la page de lecture des données
    conn = sqlite3.connect('schutz.db')
    cursor = conn.cursor()
    
    # Lecture des données dans la base de données
    cursor.execute('SELECT REF, Date, ALLEE_ID, ID FROM inventaire')
    data = cursor.fetchall()
    conn.close()

    return render_template('page_inventaire.html', data=data)

@app.route('/authentification_user', methods=['GET', 'POST'])
def authentification():
    if request.method == 'POST':
        # Vérifier les identifiants
        if request.form['username'] == 'chef' and mot_de_passe_valide(request.form['password'], 'CHEF_PASSWORD'):
            session['authentifie'] = True
            session['chef'] = True
            # Rediriger vers la route lecture après une authentification réussie
            return redirect(url_for('MenuAccueil'))
        elif request.form['username'] == 'techos' and mot_de_passe_valide(request.form['password'], 'TECHOS_PASSWORD'):
            session['authentifie'] = True
            session['chef'] = False
            # Rediriger vers la route lecture après une authentification réussie
            return redirect(url_for('MenuAccueil'))
        else:
            # Afficher un message d'erreur si les identifiants sont incorrects
            return render_template('form_authentification.html', error="Identifiants incorrects")

    return render_template('form_authentification.html', error=False)

@app.route('/menu_accueil')
def MenuAccueil():
    if not est_authentifie():
        return redirect(url_for('authentification'))

    # Afficher la page HTML
    if session['chef'] == True:
        return render_template('page_chef.html')
    return render_template('page_techos.html')


# ----- Articles et journal des mouvements -----
# Tous les moyens de saisie passent par ces deux fonctions, avec ou sans lecteur.
# Elles écrivent sans valider : l'appelant valide avec le changement d'inventaire.

def utilisateur_connecte():
    return 'chef' if session.get('chef') else 'techos'

def ecrire_mouvement(cursor, article_id, ref, type_mouvement, allee_id, emplacement_id, source):
    cursor.execute('INSERT INTO MOUVEMENTS (ARTICLE_ID, REF, TYPE, ALLEE_ID, EMPLACEMENT_ID, SOURCE, UTILISATEUR) '
                   'VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (article_id, ref, type_mouvement, allee_id, emplacement_id, source, utilisateur_connecte()))

def enregistrer_entree(cursor, ref, allee_id, emplacement_id, date_entree, source):
    cursor.execute('INSERT INTO ARTICLES (REF, ALLEE_ID, EMPLACEMENT_ID, DATE_ENTREE) VALUES (?, ?, ?, ?)',
                   (ref, allee_id, emplacement_id, date_entree))
    ecrire_mouvement(cursor, cursor.lastrowid, ref, 'ENTREE', allee_id, emplacement_id, source)

def enregistrer_sortie(cursor, ref, allee_id, emplacement_id, date_entree, source):
    ligne = cursor.execute("SELECT ARTICLE_ID FROM ARTICLES WHERE REF = ? AND ALLEE_ID = ? AND EMPLACEMENT_ID = ? AND STATUT = 'EN_STOCK'",
                           (ref, allee_id, emplacement_id)).fetchone()
    if ligne:
        article_id = ligne[0]
    else:
        # Ligne d'inventaire ajoutée hors de l'application depuis le dernier démarrage
        cursor.execute('INSERT INTO ARTICLES (REF, ALLEE_ID, EMPLACEMENT_ID, DATE_ENTREE) VALUES (?, ?, ?, ?)',
                       (ref, allee_id, emplacement_id, date_entree))
        article_id = cursor.lastrowid
    cursor.execute("UPDATE ARTICLES SET STATUT = 'SORTI', DATE_SORTIE = datetime('now') WHERE ARTICLE_ID = ?", (article_id,))
    ecrire_mouvement(cursor, article_id, ref, 'SORTIE', allee_id, emplacement_id, source)
    return article_id


# Crée une commande à valider pour chaque référence réglée passée sous le seuil.
# Écrit sans valider, comme les fonctions ci-dessus. Renvoie les références commandées.
def creer_commandes_automatiques(cursor):
    lignes = cursor.execute('SELECT REF, FOURNISSEUR_ID, QTE_COMMANDE FROM V_A_COMMANDER WHERE STOCK_PLEIN IS NOT NULL').fetchall()
    cursor.executemany('INSERT INTO COMMANDES (REF, FOURNISSEUR_ID, QUANTITE) VALUES (?, ?, ?)', lignes)
    return [ligne[0] for ligne in lignes]

def texte_commandes_creees(references):
    return f" Commande à valider créée pour : {', '.join(references)}." if references else ''


@app.route('/formulaire_ranger')
@connexion_requise
def FormulaireRanger():
    # Afficher la page HTML
    return render_template('form_ranger.html')

@app.route('/ajouter_composant', methods=['POST'])
@connexion_requise
def RangerComposant():
    try:  # Ajouter le bloc try pour gérer les erreurs
        allee_id = request.form['allee']
        id = request.form['emplacement']
        ref = request.form['reference']
        date = request.form['date']

        conn = sqlite3.connect('schutz.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO inventaire (REF, Date, ALLEE_ID, ID) VALUES (?, ?, ?, ?)', (ref, date, allee_id, id))
        enregistrer_entree(cursor, ref, allee_id, id, date, 'MANUEL')
        conn.commit()
        conn.close()
        
        # Message de succès
        success_message = f"La référence {ref} a été ajoutée avec succès."
        return render_template('form_ranger.html', success=True, success_message=success_message)
    
    except Exception as e:
        conn.close()
        # En cas d'erreur, afficher un message d'erreur
        
        error_message = f"Impossible d'ajouter cette référence à cet emplacement."
        error_message += f"\r\nVérifier si l'emplacement est libre."
        return render_template('form_ranger.html', error=True, error_message=error_message)

@app.route('/formulaire_vider')
def FormulaireVider():
    if not est_authentifie():
        return redirect(url_for('authentification'))
    return render_template('form_vider.html')

@app.route('/vider_emplacement', methods=['POST'])
@connexion_requise
def ViderEmplacement():
    allee_id = request.form['allee']
    id = request.form['emplacement']

    conn = sqlite3.connect('schutz.db')
    cursor = conn.cursor()
    # Un emplacement déjà vide ne crée aucun mouvement
    lignes = cursor.execute('SELECT REF, Date FROM inventaire WHERE ALLEE_ID = ? AND ID = ?', (allee_id, id)).fetchall()
    cursor.execute('DELETE FROM inventaire WHERE ALLEE_ID = ? AND ID = ?', (allee_id, id))
    for ref, date_entree in lignes:
        enregistrer_sortie(cursor, ref, allee_id, id, date_entree, 'MANUEL')
    commandes_creees = creer_commandes_automatiques(cursor)
    conn.commit()
    conn.close()
    
    return render_template('form_vider.html', message = "L'emplacement %s-%s est libéré." % (allee_id, id) + texte_commandes_creees(commandes_creees))

# ----- Saisie par scan -----
# La page marche avec la caméra du téléphone, ou à la main si la caméra n'est pas disponible.

@app.route('/scan', methods=['GET', 'POST'])
@connexion_requise
def scan():
    if request.method == 'GET':
        return render_template('page_scan.html')

    action = request.form.get('action')
    ref = request.form.get('reference', '').strip()
    emplacement = request.form.get('emplacement', '').strip().upper()
    source = 'SMARTPHONE' if request.form.get('source') == 'SMARTPHONE' else 'MANUEL'
    # Un code-barres de fabricant ne doit pas créer une référence au catalogue
    if not re.fullmatch(r'[1-9][0-9]{6}', ref):
        flash(f"« {ref} » n'est pas une référence valide (7 chiffres).")
        return redirect(url_for('scan'))
    if emplacement and not re.fullmatch(r'[A-Z]-[0-9]{1,4}', emplacement):
        flash(f"« {emplacement} » n'est pas un emplacement valide (exemple : A-100).")
        return redirect(url_for('scan'))
    allee_id, emplacement_id = emplacement.split('-') if emplacement else ('', '')

    conn = sqlite3.connect('schutz.db')
    try:
        cursor = conn.cursor()
        if action == 'ENTREE':
            if not emplacement:
                flash("Indique l'emplacement où ranger l'article.")
                return redirect(url_for('scan'))
            date_entree = date_iso.today().isoformat()
            try:
                cursor.execute('INSERT INTO inventaire (REF, Date, ALLEE_ID, ID) VALUES (?, ?, ?, ?)',
                               (ref, date_entree, allee_id, emplacement_id))
            except sqlite3.IntegrityError:
                flash(f"L'emplacement {emplacement} est déjà occupé.")
                return redirect(url_for('scan'))
            enregistrer_entree(cursor, ref, allee_id, emplacement_id, date_entree, source)
            conn.commit()
            flash(f"Référence {ref} rangée en {emplacement}.")
        elif action == 'SORTIE':
            ligne, erreur = trouver_ligne_a_retirer(cursor, ref, 'SORTIE', allee_id, emplacement_id)
            if erreur:
                flash(erreur)
                return redirect(url_for('scan'))
            date_entree, allee_id, emplacement_id = ligne
            cursor.execute('DELETE FROM inventaire WHERE ALLEE_ID = ? AND ID = ?', (allee_id, emplacement_id))
            enregistrer_sortie(cursor, ref, allee_id, emplacement_id, date_entree, source)
            commandes_creees = creer_commandes_automatiques(cursor)
            conn.commit()
            flash(f"Référence {ref} sortie de {allee_id}-{emplacement_id}." + texte_commandes_creees(commandes_creees))
        else:
            flash('Choisis entrée ou sortie.')
    finally:
        conn.close()
    return redirect(url_for('scan'))

# Étiquettes QR à imprimer pour les emplacements et les références
@app.route('/etiquettes')
@connexion_requise
def etiquettes():
    conn = sqlite3.connect('schutz.db')
    emplacements = conn.execute("SELECT ALLEE_ID || '-' || ID FROM EMPLACEMENTS "
                                "UNION SELECT ALLEE_ID || '-' || ID FROM INVENTAIRE ORDER BY 1").fetchall()
    references = conn.execute('SELECT REF FROM CATALOGUE ORDER BY REF').fetchall()
    conn.close()
    return render_template('page_etiquettes.html', emplacements=[e[0] for e in emplacements], references=[r[0] for r in references])


# ----- Produits à problème -----
# Un produit signalé sort du stock : il n'est plus disponible et l'agent peut en recommander.

MOTIFS_SIGNALEMENT = {
    'ABIME': 'Abîmé',
    'CASSE': 'Cassé',
    'HORS_SERVICE': 'Hors service (ne fonctionne pas)',
    'DEFAUT_FABRICATION': 'Défaut de fabrication',
    'PIECE_MANQUANTE': 'Pièce manquante',
    'ERREUR_PRODUIT': 'Erreur de produit reçu',
    'ERREUR_COMMANDE': 'Erreur de commande',
}
# Ces erreurs peuvent concerner un produit jamais rangé : sans emplacement, le stock ne bouge pas.
MOTIFS_ERREUR = ('ERREUR_PRODUIT', 'ERREUR_COMMANDE')

def afficher_signalements():
    conn = connexion_agent()
    signalements = conn.execute(
        'SELECT s.REF, s.MOTIF, s.COMMENTAIRE, s.UTILISATEUR, s.DATE_SIGNALEMENT, a.ALLEE_ID, a.EMPLACEMENT_ID '
        'FROM SIGNALEMENTS s LEFT JOIN ARTICLES a ON a.ARTICLE_ID = s.ARTICLE_ID '
        'ORDER BY s.SIGNALEMENT_ID DESC LIMIT 50').fetchall()
    conn.close()
    return render_template('page_signalements.html', signalements=signalements, motifs=MOTIFS_SIGNALEMENT)

# Retrouve la ligne de stock à retirer. Renvoie (ligne, erreur).
def trouver_ligne_a_retirer(cursor, ref, motif, allee_id, emplacement_id):
    if allee_id or emplacement_id:
        if not (allee_id and emplacement_id):
            return None, "Indique l'allée et l'emplacement, ou aucun des deux."
        ligne = cursor.execute('SELECT Date, ALLEE_ID, ID FROM inventaire WHERE REF = ? AND ALLEE_ID = ? AND ID = ?',
                               (ref, allee_id, emplacement_id)).fetchone()
        if ligne is None:
            return None, f"La référence {ref} n'est pas à l'emplacement {allee_id}-{emplacement_id}."
        return ligne, None
    if motif in MOTIFS_ERREUR:
        return None, None
    lignes = cursor.execute('SELECT Date, ALLEE_ID, ID FROM inventaire WHERE REF = ?', (ref,)).fetchall()
    if not lignes:
        return None, f"La référence {ref} n'est pas en stock."
    if len(lignes) > 1:
        return None, f"La référence {ref} est à plusieurs emplacements : indique lequel."
    return lignes[0], None

@app.route('/signalements', methods=['GET', 'POST'])
@connexion_requise
def signalements():
    if request.method == 'GET':
        return afficher_signalements()

    ref = request.form.get('reference', '').strip()
    motif = request.form.get('motif', '')
    allee_id = request.form.get('allee', '').strip().upper()
    emplacement_id = request.form.get('emplacement', '').strip()
    commentaire = request.form.get('commentaire', '').strip()[:500] or None
    if not ref or motif not in MOTIFS_SIGNALEMENT:
        flash('Indique une référence et un motif.')
        return redirect(url_for('signalements'))

    conn = sqlite3.connect('schutz.db')
    try:
        cursor = conn.cursor()
        ligne, erreur = trouver_ligne_a_retirer(cursor, ref, motif, allee_id, emplacement_id)
        if erreur:
            flash(erreur)
            return redirect(url_for('signalements'))
        article_id = None
        if ligne:
            date_entree, allee_id, emplacement_id = ligne
            cursor.execute('DELETE FROM inventaire WHERE ALLEE_ID = ? AND ID = ?', (allee_id, emplacement_id))
            article_id = enregistrer_sortie(cursor, ref, allee_id, emplacement_id, date_entree, 'MANUEL')
        cursor.execute('INSERT INTO SIGNALEMENTS (ARTICLE_ID, REF, MOTIF, COMMENTAIRE, UTILISATEUR) VALUES (?, ?, ?, ?, ?)',
                       (article_id, ref, motif, commentaire, utilisateur_connecte()))
        commandes_creees = creer_commandes_automatiques(cursor)
        conn.commit()
    finally:
        conn.close()
    if ligne:
        flash(f"Référence {ref} retirée du stock (emplacement {allee_id}-{emplacement_id})." + texte_commandes_creees(commandes_creees))
    else:
        flash(f"Signalement enregistré pour la référence {ref}. Le stock ne change pas.")
    return redirect(url_for('signalements'))


@app.route('/recherche', methods=['GET', 'POST'])
@connexion_requise
def recherche():
    if request.method == 'POST':
        ref = request.form['reference']
        
        conn = sqlite3.connect('schutz.db')
        cursor = conn.cursor()
        
        # Recherche dans la base de données
        cursor.execute('SELECT REF, Date, ALLEE_ID, ID FROM inventaire WHERE REF = ?', (ref,))
        data = cursor.fetchall()
        
        conn.close()
        
        # Si aucun résultat, envoyer un message d'erreur
        if not data:
            return render_template('form_recherche.html', data=None, message="Aucun résultat trouvé pour cette référence.")
        
        # Si des résultats sont trouvés, les afficher
        return render_template('form_recherche.html', data=data)
    
    return render_template('form_recherche.html')
    

@app.route('/logout')
def logout():
    # Déconnexion de l'utilisateur
    session.pop('authentifie', None)
    # Rediriger vers le formulaire d'authentification
    return redirect(url_for('acceuil'))

if __name__ == "__main__":
    app.run(debug=True)

@app.route('/verifier_disponibilite', methods=['POST'])
@connexion_requise
def verifier_disponibilite():
    ref = request.form.get('reference')

    # Connexion à la base de données
    conn = sqlite3.connect('schutz.db')
    cursor = conn.cursor()

    # Requête pour vérifier si la référence existe dans la base de données
    cursor.execute('SELECT COUNT(*) FROM inventaire WHERE REF = ?', (ref,))
    result = cursor.fetchone()

    conn.close()

    # Si le nombre de lignes avec cette référence est supérieur à 0, elle est disponible
    if result and result[0] > 0:
        return jsonify({'disponible': True, 'message': 'La référence est disponible.'})
    else:
        return jsonify({'disponible': False, 'message': 'La référence est indisponible.'})


# ----- API de l'agent de stock -----
# L'agent lit les listes et prépare des brouillons (statut A_VALIDER).
# Il ne peut ni envoyer, ni supprimer, ni décider un arrêt.

def agent_requis(vue):
    @wraps(vue)
    def verifier(*args, **kwargs):
        jeton = os.environ.get('AGENT_API_TOKEN')
        entete = request.headers.get('Authorization', '')
        if not jeton or not hmac.compare_digest(entete.encode(), f'Bearer {jeton}'.encode()):
            return jsonify({'erreur': 'Non autorisé'}), 401
        return vue(*args, **kwargs)
    return verifier

def connexion_agent():
    conn = sqlite3.connect('schutz.db')
    conn.row_factory = sqlite3.Row
    return conn

def lire_vue(vue):
    conn = connexion_agent()
    lignes = conn.execute(f'SELECT * FROM {vue}').fetchall()
    conn.close()
    return jsonify([dict(ligne) for ligne in lignes])

@app.route('/api/agent/a-commander')
@agent_requis
def api_a_commander():
    return lire_vue('V_A_COMMANDER')

@app.route('/api/agent/a-liquider')
@agent_requis
def api_a_liquider():
    return lire_vue('V_A_LIQUIDER')

@app.route('/api/agent/a-supprimer')
@agent_requis
def api_a_supprimer():
    return lire_vue('V_A_SUPPRIMER')

@app.route('/api/agent/messages-a-preparer')
@agent_requis
def api_messages_a_preparer():
    return lire_vue('V_MESSAGES_A_PREPARER')

@app.route('/api/agent/commandes', methods=['POST'])
@agent_requis
def api_creer_commande():
    ref = (request.get_json(silent=True) or {}).get('ref')
    conn = connexion_agent()
    try:
        ligne = conn.execute('SELECT FOURNISSEUR_ID, QTE_COMMANDE FROM V_A_COMMANDER WHERE REF = ?', (ref,)).fetchone()
        if ligne is None:
            return jsonify({'erreur': "Cette référence n'est pas à commander."}), 409
        curseur = conn.execute('INSERT INTO COMMANDES (REF, FOURNISSEUR_ID, QUANTITE) VALUES (?, ?, ?)',
                               (ref, ligne['FOURNISSEUR_ID'], ligne['QTE_COMMANDE']))
        conn.commit()
        return jsonify({'commande_id': curseur.lastrowid, 'ref': ref, 'statut': 'A_VALIDER'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'erreur': 'Une commande est déjà en cours pour cette référence.'}), 409
    finally:
        conn.close()

@app.route('/api/agent/messages', methods=['POST'])
@agent_requis
def api_creer_messages():
    ref = (request.get_json(silent=True) or {}).get('ref')
    conn = connexion_agent()
    try:
        curseur = conn.execute('INSERT OR IGNORE INTO MESSAGES (CLIENT_ID, REF) '
                               'SELECT CLIENT_ID, REF FROM V_MESSAGES_A_PREPARER WHERE REF = ?', (ref,))
        conn.commit()
        return jsonify({'ref': ref, 'messages_crees': curseur.rowcount, 'statut': 'A_VALIDER'}), 201
    finally:
        conn.close()


# ----- Page de pilotage du chef -----
# C'est ici qu'un humain décide les arrêts et valide ce que l'agent a préparé.

def chef_requis(vue):
    @wraps(vue)
    def verifier(*args, **kwargs):
        if not est_authentifie():
            return redirect(url_for('authentification'))
        if not session.get('chef'):
            abort(403)
        return vue(*args, **kwargs)
    return verifier

SOURCES_MOUVEMENT = {
    'REPRISE': 'Reprise du stock',
    'MANUEL': 'Saisie manuelle',
    'SMARTPHONE': 'Smartphone',
    'LECTEUR_PORTABLE': 'Lecteur portable',
    'LECTEUR_FIXE': 'Lecteur fixe',
}

@app.route('/mouvements')
@chef_requis
def journal_mouvements():
    limite = 200
    conn = connexion_agent()
    mouvements = conn.execute('SELECT * FROM MOUVEMENTS ORDER BY MOUVEMENT_ID DESC LIMIT ?', (limite,)).fetchall()
    conn.close()
    return render_template('page_mouvements.html', mouvements=mouvements, sources=SOURCES_MOUVEMENT, limite=limite)

@app.route('/pilotage')
@chef_requis
def pilotage():
    conn = connexion_agent()
    donnees = {
        'a_liquider': conn.execute('SELECT * FROM V_A_LIQUIDER ORDER BY DATE_ARRET IS NOT NULL, Date').fetchall(),
        'a_supprimer': conn.execute('SELECT * FROM V_A_SUPPRIMER ORDER BY REF').fetchall(),
        'commandes': conn.execute(
            "SELECT o.COMMANDE_ID, o.REF, o.QUANTITE, f.NOM AS FOURNISSEUR FROM COMMANDES o "
            "JOIN FOURNISSEURS f ON f.FOURNISSEUR_ID = o.FOURNISSEUR_ID "
            "WHERE o.STATUT = 'A_VALIDER' ORDER BY o.DATE_CREATION").fetchall(),
        'commandes_en_cours': conn.execute(
            "SELECT o.COMMANDE_ID, o.REF, o.QUANTITE, f.NOM AS FOURNISSEUR FROM COMMANDES o "
            "JOIN FOURNISSEURS f ON f.FOURNISSEUR_ID = o.FOURNISSEUR_ID "
            "WHERE o.STATUT = 'VALIDEE' ORDER BY o.DATE_CREATION").fetchall(),
        'reglages': conn.execute(
            "SELECT r.REF, r.STOCK_PLEIN, c.QTE_COMMANDE, "
            "(SELECT count(*) FROM INVENTAIRE i WHERE i.REF = r.REF) AS EN_STOCK "
            "FROM REGLAGES_STOCK r JOIN CATALOGUE c ON c.REF = r.REF ORDER BY r.REF").fetchall(),
        'seuil': conn.execute('SELECT SEUIL_POURCENT FROM PARAMETRES_COMMANDE').fetchone()[0],
        'messages': conn.execute(
            "SELECT m.MESSAGE_ID, m.REF, c.NOM, c.EMAIL, ca.DATE_ARRET FROM MESSAGES m "
            "JOIN CLIENTS c ON c.CLIENT_ID = m.CLIENT_ID "
            "LEFT JOIN CATALOGUE ca ON ca.REF = m.REF "
            "WHERE m.STATUT = 'A_VALIDER' ORDER BY m.DATE_CREATION").fetchall(),
    }
    conn.close()
    return render_template('page_pilotage.html', **donnees)

@app.route('/pilotage/arret', methods=['POST'])
@chef_requis
def pilotage_arret():
    ref = request.form.get('reference', '').strip()
    date_arret = request.form.get('date_arret', '')
    try:
        date_iso.fromisoformat(date_arret)
    except ValueError:
        flash("La date d'arrêt n'est pas valide.")
        return redirect(url_for('pilotage'))

    conn = connexion_agent()
    try:
        modifie = conn.execute('UPDATE CATALOGUE SET DATE_ARRET = ? WHERE REF = ?', (date_arret, ref)).rowcount
        if not modifie:
            flash(f"La référence {ref} n'est pas au catalogue.")
            return redirect(url_for('pilotage'))
        # Plus besoin de racheter ce produit : on annule ce qui n'est pas encore parti.
        conn.execute("UPDATE COMMANDES SET STATUT = 'ANNULEE' WHERE REF = ? AND STATUT IN ('A_VALIDER', 'VALIDEE')", (ref,))
        crees = conn.execute('INSERT OR IGNORE INTO MESSAGES (CLIENT_ID, REF) '
                             'SELECT CLIENT_ID, REF FROM V_MESSAGES_A_PREPARER WHERE REF = ?', (ref,)).rowcount
        conn.commit()
        flash(f"Arrêt de la référence {ref} enregistré. Messages clients préparés : {crees}.")
    finally:
        conn.close()
    return redirect(url_for('pilotage'))

def lire_entier_positif(champ):
    try:
        valeur = int(request.form.get(champ, ''))
    except ValueError:
        return None
    return valeur if valeur > 0 else None

# Le chef règle le stock plein et le lot habituel d'une référence
@app.route('/pilotage/reglage', methods=['POST'])
@chef_requis
def pilotage_reglage():
    ref = request.form.get('reference', '').strip()
    stock_plein = lire_entier_positif('stock_plein')
    lot = lire_entier_positif('lot')
    if stock_plein is None or lot is None:
        flash('Le stock plein et le lot doivent être supérieurs à zéro.')
        return redirect(url_for('pilotage'))
    conn = connexion_agent()
    try:
        cursor = conn.cursor()
        if not cursor.execute('UPDATE CATALOGUE SET QTE_COMMANDE = ? WHERE REF = ?', (lot, ref)).rowcount:
            flash(f"La référence {ref} n'est pas au catalogue.")
            return redirect(url_for('pilotage'))
        cursor.execute('INSERT INTO REGLAGES_STOCK (REF, STOCK_PLEIN) VALUES (?, ?) '
                       'ON CONFLICT (REF) DO UPDATE SET STOCK_PLEIN = excluded.STOCK_PLEIN', (ref, stock_plein))
        commandes_creees = creer_commandes_automatiques(cursor)
        conn.commit()
        flash(f"Référence {ref} réglée." + texte_commandes_creees(commandes_creees))
    finally:
        conn.close()
    return redirect(url_for('pilotage'))

# Le chef connaît son stock : il peut commander à tout moment, sans attendre le seuil
@app.route('/pilotage/commander', methods=['POST'])
@chef_requis
def pilotage_commander():
    ref = request.form.get('reference', '').strip()
    quantite = lire_entier_positif('quantite')
    if quantite is None:
        flash('Indique un lot supérieur à zéro.')
        return redirect(url_for('pilotage'))
    conn = connexion_agent()
    try:
        ligne = conn.execute('SELECT FOURNISSEUR_ID, DATE_ARRET FROM CATALOGUE WHERE REF = ?', (ref,)).fetchone()
        if ligne is None:
            flash(f"La référence {ref} n'est pas au catalogue.")
        elif ligne['DATE_ARRET']:
            flash(f"La référence {ref} est arrêtée : commande refusée.")
        else:
            conn.execute("INSERT INTO COMMANDES (REF, FOURNISSEUR_ID, QUANTITE, STATUT) VALUES (?, ?, ?, 'VALIDEE')",
                         (ref, ligne['FOURNISSEUR_ID'], quantite))
            conn.commit()
            flash(f"Commande de {quantite} × {ref} enregistrée.")
    except sqlite3.IntegrityError:
        flash(f"Une commande est déjà en cours pour la référence {ref}.")
    finally:
        conn.close()
    return redirect(url_for('pilotage'))

# Une commande reçue libère la référence : le seuil peut de nouveau déclencher une commande
@app.route('/pilotage/commandes/<int:commande_id>/cloturer', methods=['POST'])
@chef_requis
def pilotage_cloturer(commande_id):
    conn = connexion_agent()
    modifie = conn.execute("UPDATE COMMANDES SET STATUT = 'CLOTUREE', DATE_RECEPTION = datetime('now') "
                           "WHERE COMMANDE_ID = ? AND STATUT = 'VALIDEE'", (commande_id,)).rowcount
    conn.commit()
    conn.close()
    flash('Commande marquée comme reçue.' if modifie else "Cette commande n'est plus en cours.")
    return redirect(url_for('pilotage'))

def changer_statut(table, colonne, identifiant, statut):
    conn = connexion_agent()
    modifie = conn.execute(f"UPDATE {table} SET STATUT = ? WHERE {colonne} = ? AND STATUT = 'A_VALIDER'",
                           (statut, identifiant)).rowcount
    conn.commit()
    conn.close()
    return modifie

@app.route('/pilotage/commandes/<int:commande_id>/<action>', methods=['POST'])
@chef_requis
def pilotage_commande(commande_id, action):
    statuts = {'valider': 'VALIDEE', 'annuler': 'ANNULEE'}
    if action not in statuts:
        abort(404)
    if action == 'valider':
        # Le lot reste à l'appréciation du chef
        quantite = lire_entier_positif('quantite')
        if quantite is None:
            flash('Indique un lot supérieur à zéro.')
            return redirect(url_for('pilotage'))
        conn = connexion_agent()
        conn.execute("UPDATE COMMANDES SET QUANTITE = ? WHERE COMMANDE_ID = ? AND STATUT = 'A_VALIDER'", (quantite, commande_id))
        conn.commit()
        conn.close()
    if changer_statut('COMMANDES', 'COMMANDE_ID', commande_id, statuts[action]):
        flash('Commande validée.' if action == 'valider' else 'Commande annulée.')
    else:
        flash("Cette commande n'est plus à valider.")
    return redirect(url_for('pilotage'))

@app.route('/pilotage/messages/<int:message_id>/<action>', methods=['POST'])
@chef_requis
def pilotage_message(message_id, action):
    statuts = {'valider': 'VALIDE', 'annuler': 'ANNULE'}
    if action not in statuts:
        abort(404)
    if changer_statut('MESSAGES', 'MESSAGE_ID', message_id, statuts[action]):
        flash('Message validé.' if action == 'valider' else 'Message annulé.')
    else:
        flash("Ce message n'est plus à valider.")
    return redirect(url_for('pilotage'))

@app.route('/pilotage/supprimer', methods=['POST'])
@chef_requis
def pilotage_supprimer():
    ref = request.form.get('reference', '')
    conn = connexion_agent()
    try:
        if conn.execute('SELECT 1 FROM V_A_SUPPRIMER WHERE REF = ?', (ref,)).fetchone() is None:
            flash(f"La référence {ref} ne peut pas être supprimée.")
            return redirect(url_for('pilotage'))
        # Le stock est vide : les messages pas encore partis n'ont plus d'intérêt.
        conn.execute("UPDATE MESSAGES SET STATUT = 'ANNULE' WHERE REF = ? AND STATUT IN ('A_VALIDER', 'VALIDE')", (ref,))
        conn.execute('DELETE FROM CLIENTS_PRODUITS WHERE REF = ?', (ref,))
        conn.execute('DELETE FROM REGLAGES_STOCK WHERE REF = ?', (ref,))
        conn.execute('DELETE FROM CATALOGUE WHERE REF = ?', (ref,))
        conn.commit()
        flash(f"Référence {ref} supprimée du catalogue.")
    finally:
        conn.close()
    return redirect(url_for('pilotage'))
