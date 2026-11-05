-- Dates fictives pour tester l'agent : calculees depuis aujourd'hui,
-- avec un ecart de 5 jours entre chaque reference.
-- A ne pas lancer sur une base contenant de vraies donnees.
update INVENTAIRE
set Date = date('now', '-' || ((cast(REF as integer) - 3017935) * 5) || ' days');

update CATALOGUE
set DATE_ENTREE = (select i.Date from INVENTAIRE i where i.REF = CATALOGUE.REF)
where REF in (select REF from INVENTAIRE);

-- Clients fictifs (domaine reserve example.com). Le client 3 refuse les messages.
insert or ignore into CLIENTS (CLIENT_ID, NOM, EMAIL, CONSENTEMENT) values
(1, 'Client Un (fictif)', 'client1@example.com', 1),
(2, 'Client Deux (fictif)', 'client2@example.com', 1),
(3, 'Client Trois (fictif)', 'client3@example.com', 0);

insert or ignore into CLIENTS_PRODUITS (CLIENT_ID, REF) values
(1, '3017961'), (2, '3017961'), (3, '3017961'),
(1, '3017960'), (2, '3017936');
