from flask import Flask, render_template_string, render_template, jsonify, request, redirect, url_for, session
from flask import json
from urllib.request import urlopen
from werkzeug.utils import secure_filename   
import sqlite3 

app = Flask(__name__)                                                                                                                  
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'  # Clé secrète pour les sessions  


@app.route('/')
def hello_world():
    return render_template('hello.html')

# Fonction pour créer une clé "authentifie" dans la session utilisateur
def est_authentifie():
    return session.get('authentifie')

# Route de lecture restreinte aux utilisateurs authentifiés
@app.route('/lecture', methods=['GET'])
def lecture():
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

    return render_template('page_lecture.html', data=data)

@app.route('/authentification_user', methods=['GET', 'POST'])
def authentification():
    if request.method == 'POST':
        # Vérifier les identifiants
        if request.form['username'] == 'chef' and request.form['password'] == 'equipe':  # password à cacher par la suite
            session['authentifie'] = True
            session['chef'] = True
            # Rediriger vers la route lecture après une authentification réussie
            return redirect(url_for('menu_accueil'))
        elif request.form['username'] == 'techos' and request.form['password'] == 'tech1':  # password à cacher par la suite
            session['authentifie'] = True
            session['chef'] = False
            # Rediriger vers la route lecture après une authentification réussie
            return redirect(url_for('recherche'))
        else:
            # Afficher un message d'erreur si les identifiants sont incorrects
            return render_template('formulaire_authentification.html', error="Identifiants incorrects")

    return render_template('formulaire_authentification.html', error=False)

@app.route('/menu_accueil')
def AccueilChef():
    # Afficher la page HTML
    if session['chef'] == True:
        return render_template('page_chef.html')
    return render_template('page_techos.html')


@app.route('/formulaire_ranger')
def FormulaireRanger():
    if not est_authentifie():
        return redirect(url_for('authentification'))
    # Afficher la page HTML
    return render_template('form_ranger.html')

@app.route('/ajouter_composant', methods=['POST'])
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
def ViderEmplacement():
    allee_id = request.form['allee']
    id = request.form['emplacement']

    conn = sqlite3.connect('schutz.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM inventaire WHERE ALLEE_ID = ? AND ID = ?', (allee_id, id))
    conn.commit()
    conn.close()
    
    # Rediriger vers la page d'accueil après l'opération
    return redirect('/formulaire_vider')

@app.route('/recherche', methods=['GET', 'POST'])
def ReadBDD():
    if request.method == 'POST':
        ref = request.form['reference']
        conn = sqlite3.connect('schutz.db')
        cursor = conn.cursor()
        cursor.execute('SELECT REF, Date, ALLEE_ID, ID FROM inventaire WHERE REF = ?', (ref,))
        data = cursor.fetchall()
        conn.close()
        return render_template('form_recherche.html', data=data)
    return render_template('form_recherche.html')

@app.route('/logout')
def logout():
    # Déconnexion de l'utilisateur
    session.pop('authentifie', None)
    # Rediriger vers le formulaire d'authentification
    return redirect(url_for('/'))

if __name__ == "__main__":
    app.run(debug=True)

@app.route('/verifier_disponibilite', methods=['POST'])
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
