-- Migration pour l'agent de stock.
-- Ajoute des tables sans toucher a EMPLACEMENTS ni INVENTAIRE.
-- Peut etre relancee sans risque : rien n'est cree ou insere en double.
-- Les fournisseurs sont fictifs (domaine reserve example.com).

create table if not exists FOURNISSEURS (
     FOURNISSEUR_ID integer primary key,
     NOM varchar(100) not null unique,
     EMAIL varchar(255) not null);

-- References suivies. Une reference reste ici quand son emplacement est vide.
-- Elle n'en sort que si son stock est vide et qu'elle est non rentable ou trop ancienne.
-- DATE_ENTREE garde la date du dernier rangement, perdue quand l'emplacement est vide.
create table if not exists CATALOGUE (
     REF varchar(50) primary key,
     FOURNISSEUR_ID integer not null references FOURNISSEURS (FOURNISSEUR_ID),
     STOCK_MIN integer not null default 1 check (STOCK_MIN >= 0),
     QTE_COMMANDE integer not null default 1 check (QTE_COMMANDE > 0),
     RENTABLE integer not null default 1 check (RENTABLE in (0, 1)),
     DATE_ENTREE date,
     DATE_ARRET date);

-- Reglages modifiables sans toucher au code. Une seule ligne.
create table if not exists PARAMETRES (
     PARAMETRE_ID integer primary key check (PARAMETRE_ID = 1),
     ANCIENNETE_MAX_MOIS integer not null check (ANCIENNETE_MAX_MOIS > 0));

-- Clients. CONSENTEMENT = 1 : le client accepte de recevoir des messages.
create table if not exists CLIENTS (
     CLIENT_ID integer primary key,
     NOM varchar(100) not null,
     EMAIL varchar(255) not null unique,
     CONSENTEMENT integer not null default 0 check (CONSENTEMENT in (0, 1)));

-- Quel client apprecie quel produit.
create table if not exists CLIENTS_PRODUITS (
     CLIENT_ID integer not null references CLIENTS (CLIENT_ID),
     REF varchar(50) not null,
     primary key (CLIENT_ID, REF));

-- Un seul message d'arret par client et par reference.
create table if not exists MESSAGES (
     MESSAGE_ID integer primary key,
     CLIENT_ID integer not null references CLIENTS (CLIENT_ID),
     REF varchar(50) not null,
     STATUT varchar(10) not null default 'A_VALIDER'
          check (STATUT in ('A_VALIDER', 'VALIDE', 'ENVOYE', 'ANNULE')),
     DATE_CREATION text not null default (datetime('now')),
     DATE_ENVOI text,
     unique (CLIENT_ID, REF));

-- Pas de cle etrangere sur REF : l'historique des commandes reste lisible
-- apres la suppression d'une reference du catalogue.
create table if not exists COMMANDES (
     COMMANDE_ID integer primary key,
     REF varchar(50) not null,
     FOURNISSEUR_ID integer not null references FOURNISSEURS (FOURNISSEUR_ID),
     QUANTITE integer not null check (QUANTITE > 0),
     STATUT varchar(10) not null default 'A_VALIDER'
          check (STATUT in ('A_VALIDER', 'VALIDEE', 'ENVOYEE', 'RECUE', 'CLOTUREE', 'ANNULEE')),
     DATE_CREATION text not null default (datetime('now')),
     DATE_ENVOI text,
     DATE_RECEPTION text);

-- Une seule commande en cours par reference. RECUE reste "en cours" tant que
-- l'article n'est pas range, sinon l'agent recommanderait entre-temps.
create unique index if not exists UN_COMMANDE_EN_COURS
     on COMMANDES (REF) where STATUT in ('A_VALIDER', 'VALIDEE', 'ENVOYEE', 'RECUE');

-- References rentables, pas trop anciennes et sans arret decide.
drop view if exists V_REFERENCES_VALABLES;
create view V_REFERENCES_VALABLES as
select c.REF
from CATALOGUE c, PARAMETRES p
where c.RENTABLE = 1
  and c.DATE_ARRET is null
  and (c.DATE_ENTREE is null
       or c.DATE_ENTREE >= date('now', '-' || p.ANCIENNETE_MAX_MOIS || ' months'));

-- References a commander : valables, sous le minimum, sans commande en cours.
drop view if exists V_A_COMMANDER;
create view V_A_COMMANDER as
select c.REF, c.FOURNISSEUR_ID, f.NOM as FOURNISSEUR, f.EMAIL, c.QTE_COMMANDE,
       (select count(*) from INVENTAIRE i where i.REF = c.REF) as EN_STOCK
from CATALOGUE c
join FOURNISSEURS f on f.FOURNISSEUR_ID = c.FOURNISSEUR_ID
where c.REF in (select REF from V_REFERENCES_VALABLES)
  and (select count(*) from INVENTAIRE i where i.REF = c.REF) < c.STOCK_MIN
  and not exists (select 1 from COMMANDES o
                  where o.REF = c.REF
                    and o.STATUT in ('A_VALIDER', 'VALIDEE', 'ENVOYEE', 'RECUE'));

-- Articles a liquider en promo : non valables et encore en stock.
drop view if exists V_A_LIQUIDER;
create view V_A_LIQUIDER as
select i.REF, i.Date, i.ALLEE_ID, i.ID, c.RENTABLE, c.DATE_ARRET
from INVENTAIRE i
join CATALOGUE c on c.REF = i.REF
where c.REF not in (select REF from V_REFERENCES_VALABLES);

-- References a supprimer du catalogue : non valables et stock entierement vide.
drop view if exists V_A_SUPPRIMER;
create view V_A_SUPPRIMER as
select c.REF
from CATALOGUE c
where c.REF not in (select REF from V_REFERENCES_VALABLES)
  and not exists (select 1 from INVENTAIRE i where i.REF = c.REF);

-- Messages a preparer : arret decide, client d'accord, pas encore de message.
drop view if exists V_MESSAGES_A_PREPARER;
create view V_MESSAGES_A_PREPARER as
select cp.REF, c.DATE_ARRET, cl.CLIENT_ID, cl.NOM, cl.EMAIL
from CLIENTS_PRODUITS cp
join CATALOGUE c on c.REF = cp.REF
join CLIENTS cl on cl.CLIENT_ID = cp.CLIENT_ID
where c.DATE_ARRET is not null
  and cl.CONSENTEMENT = 1
  and not exists (select 1 from MESSAGES m
                  where m.CLIENT_ID = cp.CLIENT_ID and m.REF = cp.REF);

-- Produits annonces en bandeau : arret decide et stock encore disponible.
drop view if exists V_PRODUITS_ARRETES;
create view V_PRODUITS_ARRETES as
select c.REF, c.DATE_ARRET
from CATALOGUE c
where c.DATE_ARRET is not null
  and exists (select 1 from INVENTAIRE i where i.REF = c.REF);

-- Seuil d'anciennete : 3 mois
insert or ignore into PARAMETRES (PARAMETRE_ID, ANCIENNETE_MAX_MOIS) values (1, 3);

-- Donnees fictives
insert or ignore into FOURNISSEURS (FOURNISSEUR_ID, NOM, EMAIL) values
(1, 'Fournisseur Alpha (fictif)', 'commandes@alpha.example.com'),
(2, 'Fournisseur Bravo (fictif)', 'commandes@bravo.example.com'),
(3, 'Fournisseur Charlie (fictif)', 'commandes@charlie.example.com');

-- Chaque reference en stock entre au catalogue, repartie entre les 3 fournisseurs.
insert or ignore into CATALOGUE (REF, FOURNISSEUR_ID, DATE_ENTREE)
select REF, (cast(REF as integer) % 3) + 1, Date from INVENTAIRE;

-- Chaque rangement ajoute la reference au catalogue si besoin et rafraichit sa date.
drop trigger if exists TR_INVENTAIRE_RANGEMENT;
create trigger TR_INVENTAIRE_RANGEMENT after insert on INVENTAIRE
begin
     insert or ignore into CATALOGUE (REF, FOURNISSEUR_ID, DATE_ENTREE)
     values (new.REF, (cast(new.REF as integer) % 3) + 1, new.Date);
     update CATALOGUE set DATE_ENTREE = new.Date where REF = new.REF;
end;
