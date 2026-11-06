import sqlite3

connection = sqlite3.connect('schutz.db')

with open('Documents/create schema.sql') as fcreate:
    connection.executescript(fcreate.read())
connection.commit()

with open('Documents/init_db_insert.sql') as finsert:
    connection.executescript(finsert.read())
connection.commit()

with open('Documents/migration_agent_stock.sql') as fmigration:
    connection.executescript(fmigration.read())
connection.commit()

with open('Documents/donnees_test_agent.sql') as ftest:
    connection.executescript(ftest.read())
connection.commit()

# Repart d'un journal vide puisque l'inventaire vient d'être recréé
connection.executescript('drop table if exists SIGNALEMENTS; drop table if exists MOUVEMENTS; drop table if exists ARTICLES;')
with open('Documents/migration_mouvements.sql', encoding='utf-8') as fmouvements:
    connection.executescript(fmouvements.read())
connection.commit()

connection.close()
