import sqlite3

connection = sqlite3.connect('schutz.db')

with open('Documents/schema SCHUTZ.sql') as f:
    connection.executescript(f.read())

# cur = connection.cursor()
# requete = "INSERT INTO clients (nom, prenom, adresse) VALUES (?, ?, ?)"
# cur.execute(requete, ('DUPONT', 'Emilie', '123, Rue des Lilas, 75001 Paris'))
# cur.execute(requete, ('DUPONT', 'Sonia', '123, Rue des Lilas, 75001 Paris'))
# cur.execute(requete, ('DUPONT', 'Emilie', '123, Rue des Lilas, 75001 Paris'))

connection.commit()
connection.close()
