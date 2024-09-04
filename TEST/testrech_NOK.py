from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
import time



# Spécifiez le chemin vers l'exécutable geckodriver
service = Service(executable_path='/usr/local/bin/geckodriver')

# Initialisez les options Firefox
options = Options()
options.add_argument('--headless')  # Pour exécuter Firefox en mode headless

# Initialisez le pilote Firefox avec le service et les options
driver = webdriver.Firefox(service=service, options=options)

# Ouvrir le site Python
driver.get("https://jeksos.alwaysdata.net/recherche")

# Afficher le titre de la page
print(driver.title)

# Trouver le champ reference
ref = driver.find_element(By.NAME, "reference")


# Effacer le contenu s'il y a du texte dedans
ref.clear()

# Entrer la requête de recherche dans la barre de recherche
ref.send_keys("87654321")


# Trouver l'élément bouton de recherche
envoie_val = driver.find_element(By.NAME, "recherche")

# Simuler la pression de la touche Entrée
envoie_val.send_keys(Keys.RETURN)

# attendre le resultat du serveur
time.sleep(1)


# Trouver le champ resultat nok
try:
 	resultat = driver.find_element(By.NAME, "resultat_nok")
 	print("Pas de resultat.")
except:
     print("Erreur de recherche.")


# Fermer le navigateur
driver.close()
