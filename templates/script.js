document.addEventListener('DOMContentLoaded', () => {
    const formLinks = document.getElementById('formLinks');
    const formContainer = document.getElementById('formContainer');
    const userInfo = document.getElementById('userInfo');
    const rangerForm = document.getElementById('rangerForm');

    // Simulation de l'authentification
    const user = {
        role: 'chef_de_projet'  // Ou 'technicien'
    };

    // Affichage du rôle de l'utilisateur
    userInfo.innerHTML = `<p>Connecté en tant que : ${user.role}</p>`;

    // Formulaires disponibles pour le chef de projet et le technicien
    const forms = {
        'chef_de_projet': [
            { name: "Ranger un Composant", id: "rangerForm" },
            { name: "Vider un Emplacement", id: "viderForm" },
            { name: "Rechercher une Référence", id: "rechercherForm" },
            { name: "Vérifier Disponibilité", id: "verifierForm" }
        ],
        'technicien': [
            { name: "Rechercher une Référence", id: "rechercherForm" },
            { name: "Vérifier Disponibilité", id: "verifierForm" }
        ]
    };

    // Générer les liens en fonction du rôle
    const generateLinks = () => {
        formLinks.innerHTML = '';
        forms[user.role].forEach(form => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = "#";
            a.textContent = form.name;
            a.addEventListener('click', () => loadForm(form.id));
            li.appendChild(a);
            formLinks.appendChild(li);
        });
    };

    // Charger le formulaire correspondant
    const loadForm = (formId) => {
        formContainer.innerHTML = getFormHTML(formId);
        const form = document.getElementById(formId);
        if (formId === 'rangerForm') {
            form.addEventListener('submit', handleRangerForm);
        } else if (formId === 'viderForm') {
            form.addEventListener('submit', handleViderForm);
        } else if (formId === 'rechercherForm') {
            form.addEventListener('submit', handleRechercherForm);
        } else if (formId === 'verifierForm') {
            form.addEventListener('submit', handleVerifierForm);
        }
    };

    // Formulaires HTML
    const getFormHTML = (formId) => {
        if (formId === 'rangerForm') {
            return `
                <form id="rangerForm">
                    <label for="allee">Allée</label>
                    <select id="allee" name="allee" required>
                        <option value="">Sélectionnez une allée</option>
                        <option value="A">A</option>
                        <option value="B">B</option>
                        <option value="C">C</option>
                    </select>
                    <label for="emplacement">Emplacement</label>
                    <select id="emplacement" name="emplacement" required>
                        <option value="">Sélectionnez un emplacement</option>
                        <option value="100">100</option>
                        <option value="200">200</option>
                    </select>
                    <label for="reference">Référence</label>
                    <input type="text" id="reference" name="reference" required>
                    <label for="date">Date</label>
                    <input type="date" id="date" name="date" required>
                    <button type="submit">Valider</button>
                    <div id="message"></div>
                </form>
            `;
        } else if (formId === 'viderForm') {
            return `
                <form id="viderForm">
                    <label for="allee">Allée</label>
                    <select id="allee" name="allee" required>
                        <option value="">Sélectionnez une allée</option>
                        <option value="A">A</option>
                        <option value="B">B</option>
                    </select>
                    <label for="emplacement">Emplacement</label>
                    <select id="emplacement" name="emplacement" required>
                        <option value="">Sélectionnez un emplacement</option>
                        <option value="100">100</option>
                        <option value="200">200</option>
                    </select>
                    <button type="submit">Vider</button>
                    <div id="message"></div>
                </form>
            `;
        } else if (formId === 'rechercherForm') {
            return `
                <form id="rechercherForm">
                    <label for="reference">Référence</label>
                    <input type="text" id="reference" name="reference" required>
                    <button type="submit">Rechercher</button>
                    <div id="message"></div>
                </form>
            `;
        } else if (formId === 'verifierForm') {
            return `
                <form id="verifierForm">
                    <label for="allee">Allée</label>
                    <select id="allee" name="allee" required>
                        <option value="">Sélectionnez une allée</option>
                        <option value="A">A</option>
                        <option value="B">B</option>
                    </select>
                    <label for="emplacement">Emplacement</label>
                    <select id="emplacement" name="emplacement" required>
                        <option value="">Sélectionnez un emplacement</option>
                        <option value="100">100</option>
                        <option value="200">200</option>
                    </select>
                    <button type="submit">Vérifier</button>
                    <div id="message"></div>
                </form>

  // Gestion de l'authentification
  
const express = require('express');
const app = express();
const port = 3000;

// Middleware pour vérifier l'authentification et le rôle
const checkRole = (roles) => (req, res, next) => {
    const user = req.user; // Supposons que req.user est défini par un middleware d'authentification
    if (roles.includes(user.role)) {
        next();
    } else {
        res.status(403).send('Accès refusé');
    }
};

app.use(express.json());

// Route pour les chefs de projet
app.get('/manage_forms', checkRole(['chef_de_projet']), (req, res) => {
    res.send('Page avec les liens vers les formulaires');
});

// Route pour les techniciens
app.get('/view_forms', checkRole(['technicien']), (req, res) => {
    res.send('Page avec les liens vers les formulaires pour les techniciens');
});

app.listen(port, () => {
    console.log(`Serveur en fonctionnement sur http://localhost:${port}`);
});

    // Fonction pour afficher un message
    const afficherMessage = (message, isSuccess = true) => {
        const messageDiv = document.getElementById('message');
        messageDiv.textContent = message;
        messageDiv.style.color = isSuccess ? 'green' : 'red';
    };

    // Fonction pour vérifier la disponibilité de l'emplacement
    const checkLocationAvailability = async (allee, emplacement) => {
        try {
            const response = await fetch('/check_location_availability', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ allee, emplacement })
            });
            const result = await response.json();
            return result.available;
        } catch (error) {
            console.error('Erreur lors de la vérification de la disponibilité de l\'emplacement:', error);
            return false;
        }
    };

    if (rangerForm) {
        rangerForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const allee = document.getElementById('allee').value;
            const emplacement = document.getElementById('emplacement').value;
            const reference = document.getElementById('reference').value;
            const date = document.getElementById('date').value;

            if (allee && emplacement && reference && date) {
                const isAvailable = await checkLocationAvailability(allee, emplacement);
                if (isAvailable) {
                    afficherMessage("Composant rangé avec succès !");
                } else {
                    afficherMessage("L'emplacement est déjà occupé. Veuillez en choisir un autre.", false);
                }
            } else {
                afficherMessage("Veuillez remplir tous les champs", false);
            }
        });
    }
});
   

           
