from flask import Flask, render_template_string, render_template, jsonify, request, redirect, url_for, session
from flask import render_template
from flask import json
from urllib.request import urlopen
from werkzeug.utils import secure_filename   
import sqlite3 

app = Flask(__name__)                                                                                                                  
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'  # Clé secrète pour les sessions  

# Fonction pour créer une clé "authentifie" dans la session utilisateur
def est_authentifie():
    return session.get('authentifie')

@app.route('/')
def hello_world():
    return render_template('hello.html')


@app.route('/authentification_user', methods=['GET', 'POST'])
def authentification():
    if request.method == 'POST':
        # Vérifier les identifiants
        if request.form['username'] == 'chef' and request.form['password'] == 'equipe': # password à cacher par la suite
            session['authentifie'] = True
            # Rediriger vers la route lecture après une authentification réussie
            return render_template('page_chef.html')
        elif request.form['username'] == 'techos' and request.form['password'] == 'tech1': # password à cacher par la suite
            session['authentifie'] = True
            # Rediriger vers la route lecture après une authentification réussie
            return redirect(url_for('recherche'))
        else:
            # Afficher un message d'erreur si les identifiants sont incorrects
            return render_template('formulaire_authentification.html', error=True)

    return render_template('formulaire_authentification.html', error=False)

@app.route('/formulaire_ranger')
def FormulaireRanger():
    # Afficher la page HTML
    return render_template('form_ranger.html')

@app.route('/ajouter_composant', methods=['POST'])
def RangerComposant():
    allee_id = request.form['allee']
    id = request.form['emplacement']
    ref = request.form['reference']
    date = request.form['date']

    conn = sqlite3.connect('schutz.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO inventaire (REF, Date, ALLEE_ID, ID) VALUES (?, ?, ?, ?)', (ref, date, allee_id, id))
    conn.commit()
    conn.close()
    
    # Rediriger vers la page d'accueil après l'enregistrement
    return redirect('/formulaire_ranger')

@app.route('/formulaire_vider')
def FormulaireVider():
    # Afficher la page HTML pour vider un emplacement
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

if __name__ == "__main__":
    app.run(debug=True)



@app.route('/verifier_disponibilite', methods=['POST'])
def verifier_disponibilite():
    if request.method == 'POST':
        ref = request.form.get('reference')

        # Connexion à la base de données
        conn = sqlite3.connect('schutz.db')
        cursor = conn.cursor()

        # Requête pour vérifier si la référence existe dans la base de données
        cursor.execute('SELECT COUNT(*) FROM inventaire WHERE REF = ?', (ref,))
        result = cursor.fetchone()

        conn.close()

        # Si le nombre de lignes avec cette référence est supérieur à 0, elle est disponible
        if result[0] > 0:
            return jsonify({'disponible': True, 'message': 'La référence est disponible.'})
        else:
            return jsonify({'disponible': False, 'message': 'La référence est indisponible.'})
