from flask import Flask, abort, flash, render_template_string, render_template, jsonify, request, redirect, url_for, session
from flask import json
from urllib.request import urlopen
from werkzeug.utils import secure_filename     
import hmac
from datetime import date as date_iso
import os
import sqlite3
from functools import wraps

app = Flask(__name__)                                                                                                                  
# Clé secrète des sessions. Sans SECRET_KEY, une clé temporaire déconnecte tout le monde au redémarrage.
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(32)
# Empêche un autre site d'envoyer les formulaires à la place d'un utilisateur connecté
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


@app.route('/')
def acceuil():
    return render_template('accueil.html', produits_arretes=lire_produits_arretes())

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
        conn.commit()
        conn.close()
        
        # Message de succès
        success_message = f"La référence {ref} a été ajoutée avec succès."
        return render_template('form_ranger.html', success=True, success_message=success_message)
    
    except Exception as e:
        conn.close()
        # En cas d'erreur, afficher un message d'erreur
        
        error_message = f"Impossible d'ajouter cette référence à cet emplacement."
        error_message += f"\r\nVérifier si l'emplacement est libre ou si la référence n'est pas déjà présente ailleurs."
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
    cursor.execute('DELETE FROM inventaire WHERE ALLEE_ID = ? AND ID = ?', (allee_id, id))
    conn.commit()
    conn.close()
    
    return render_template('form_vider.html', message = "L'emplacement %s-%s est libéré" % (allee_id, id))

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
        conn.execute('DELETE FROM CATALOGUE WHERE REF = ?', (ref,))
        conn.commit()
        flash(f"Référence {ref} supprimée du catalogue.")
    finally:
        conn.close()
    return redirect(url_for('pilotage'))
