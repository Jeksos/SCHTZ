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

# Ouvrir la page d'ajout de référence
driver.get("https://jeksos.alwaysdata.net/formulaire_ranger")

# Attendre que la page se charge
time.sleep(1)

# Trouver les champs du formulaire et entrer les valeurs

# Champ Allée
allee = driver.find_element(By.NAME, "Allée")
allee.select_by_value("A")   # Sélectionner l'allée A

# Champ Emplacement
emplacement = driver.find_element(By.NAME, "emplacement")
emplacement.select_by_value("100")  # Sélectionner l'emplacement 100

# Champ Référence
reference = driver.find_element(By.NAME, "reference")
reference.clear()
reference.send_keys("3019746")  # Entrer la référence à ajouter

# Champ Date
date = driver.find_element(By.NAME, "date")
date.send_keys("2024-09-05")  # Entrer une date valide

# Soumettre le formulaire
submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
submit_button.click()

# Attendre la réponse du serveur après soumission
time.sleep(2)

# Vérifier si l'ajout a réussi (par exemple, si un message de succès est affiché)
try:
    success_message = driver.find_element(By.XPATH, "//div[@id='message' and contains(text(), 'succès')]")
    print("Ajout de la référence réussi.")
except:
    print("L'ajout de la référence a échoué.")

# Fermer le navigateur
driver.quit()
