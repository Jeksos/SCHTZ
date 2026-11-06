-- Migration du suivi des articles et du journal des mouvements.
-- Ajoute des tables sans toucher a INVENTAIRE, qui reste la reference du stock.
-- Lancee a chaque demarrage de l'application : rien n'est cree ou insere en double.

-- Un article physique. Il garde sa ligne apres sa sortie pour conserver l'historique.
-- CODE recevra plus tard le code scanne ou l'EPC du tag RFID. Il reste vide en saisie manuelle.
create table if not exists ARTICLES (
     ARTICLE_ID integer primary key,
     CODE varchar(100),
     REF varchar(50) not null,
     ALLEE_ID char(1) not null,
     EMPLACEMENT_ID numeric(3) not null,
     STATUT varchar(10) not null default 'EN_STOCK' check (STATUT in ('EN_STOCK', 'SORTI')),
     DATE_ENTREE date not null,
     DATE_SORTIE text);

create unique index if not exists UN_ARTICLE_CODE on ARTICLES (CODE) where CODE is not null;
create index if not exists IX_ARTICLE_REF on ARTICLES (REF, STATUT);

-- Journal des entrees et sorties. SOURCE indique le moyen de saisie :
-- tous les moyens, avec ou sans lecteur, ecrivent le meme evenement.
-- DATE_EVENEMENT est en heure UTC.
create table if not exists MOUVEMENTS (
     MOUVEMENT_ID integer primary key,
     ARTICLE_ID integer not null references ARTICLES (ARTICLE_ID),
     REF varchar(50) not null,
     TYPE varchar(10) not null check (TYPE in ('ENTREE', 'SORTIE')),
     ALLEE_ID char(1) not null,
     EMPLACEMENT_ID numeric(3) not null,
     SOURCE varchar(20) not null
          check (SOURCE in ('REPRISE', 'MANUEL', 'SMARTPHONE', 'LECTEUR_PORTABLE', 'LECTEUR_FIXE')),
     UTILISATEUR varchar(20),
     DATE_EVENEMENT text not null default (datetime('now')));

create index if not exists IX_MOUVEMENT_ARTICLE on MOUVEMENTS (ARTICLE_ID);

-- Produits a probleme : abime, casse, hors service, defaut de fabrication, piece manquante,
-- erreur de produit recu ou erreur de commande. Le signalement ne change pas l'inventaire.
-- ARTICLE_ID et COMMANDE_ID restent vides quand ils ne s'appliquent pas :
-- un mauvais produit recu n'est par exemple jamais entre en stock.
-- ANOMALIES, premiere version sans ces motifs, n'a jamais recu de donnees.
drop table if exists ANOMALIES;
create table if not exists SIGNALEMENTS (
     SIGNALEMENT_ID integer primary key,
     ARTICLE_ID integer references ARTICLES (ARTICLE_ID),
     COMMANDE_ID integer references COMMANDES (COMMANDE_ID),
     REF varchar(50) not null,
     MOTIF varchar(20) not null
          check (MOTIF in ('ABIME', 'CASSE', 'HORS_SERVICE', 'DEFAUT_FABRICATION', 'PIECE_MANQUANTE',
                           'ERREUR_PRODUIT', 'ERREUR_COMMANDE')),
     COMMENTAIRE varchar(500),
     STATUT varchar(10) not null default 'OUVERT' check (STATUT in ('OUVERT', 'TRAITE')),
     UTILISATEUR varchar(20),
     DATE_SIGNALEMENT text not null default (datetime('now')));

create index if not exists IX_SIGNALEMENT_REF on SIGNALEMENTS (REF, STATUT);

-- Stock plein de chaque reference, regle par le chef. Sans reglage, pas de commande automatique.
create table if not exists REGLAGES_STOCK (
     REF varchar(50) primary key,
     STOCK_PLEIN integer not null check (STOCK_PLEIN > 0));

-- Seuil de commande automatique, en pourcentage du stock plein. Une seule ligne.
create table if not exists PARAMETRES_COMMANDE (
     PARAMETRE_ID integer primary key check (PARAMETRE_ID = 1),
     SEUIL_POURCENT integer not null check (SEUIL_POURCENT between 1 and 100));

insert or ignore into PARAMETRES_COMMANDE (PARAMETRE_ID, SEUIL_POURCENT) values (1, 20);

-- References a commander. Avec un stock plein : au seuil ou en dessous.
-- Sans stock plein : l'ancienne regle du stock minimum, utilisee par l'agent.
drop view if exists V_A_COMMANDER;
create view V_A_COMMANDER as
select c.REF, c.FOURNISSEUR_ID, f.NOM as FOURNISSEUR, f.EMAIL,
       -- Avec un stock plein, on commande ce qui manque pour y revenir
       case when r.STOCK_PLEIN is not null
            then r.STOCK_PLEIN - (select count(*) from INVENTAIRE i where i.REF = c.REF)
            else c.QTE_COMMANDE
       end as QTE_COMMANDE,
       (select count(*) from INVENTAIRE i where i.REF = c.REF) as EN_STOCK,
       r.STOCK_PLEIN
from CATALOGUE c
join FOURNISSEURS f on f.FOURNISSEUR_ID = c.FOURNISSEUR_ID
left join REGLAGES_STOCK r on r.REF = c.REF
where c.REF in (select REF from V_REFERENCES_VALABLES)
  and case when r.STOCK_PLEIN is not null
           then (select count(*) from INVENTAIRE i where i.REF = c.REF) * 100
                <= r.STOCK_PLEIN * (select SEUIL_POURCENT from PARAMETRES_COMMANDE)
                and (select count(*) from INVENTAIRE i where i.REF = c.REF) < r.STOCK_PLEIN
           else (select count(*) from INVENTAIRE i where i.REF = c.REF) < c.STOCK_MIN
      end
  and not exists (select 1 from COMMANDES o
                  where o.REF = c.REF
                    and o.STATUT in ('A_VALIDER', 'VALIDEE', 'ENVOYEE', 'RECUE'));

-- Articles a liquider, avec la raison : le motif decide par le chef, ou la raison que l'application connait.
drop view if exists V_A_LIQUIDER;
create view V_A_LIQUIDER as
select i.REF, i.Date, i.ALLEE_ID, i.ID, c.RENTABLE, c.DATE_ARRET, c.MOTIF_ARRET,
       case when c.DATE_ARRET is not null then coalesce(c.MOTIF_ARRET, 'Non renseigné')
            when c.RENTABLE = 0 then 'Pas rentable'
            else 'Trop ancien'
       end as RAISON
from INVENTAIRE i
join CATALOGUE c on c.REF = i.REF
where c.REF not in (select REF from V_REFERENCES_VALABLES);

-- Stock et quantite attendue des references reglees. Une commande recue n'attend plus
-- que les articles pas encore ranges depuis sa reception.
drop view if exists V_STOCK_REGLE;
create view V_STOCK_REGLE as
select r.REF, r.STOCK_PLEIN,
       (select count(*) from INVENTAIRE i where i.REF = r.REF) as EN_STOCK,
       coalesce((select sum(case when o.STATUT = 'RECUE'
                                 then max(o.QUANTITE - (select count(*) from MOUVEMENTS m
                                                        where m.REF = o.REF and m.TYPE = 'ENTREE'
                                                          and m.DATE_EVENEMENT > o.DATE_RECEPTION), 0)
                                 else o.QUANTITE end)
                 from COMMANDES o
                 where o.REF = r.REF and o.STATUT in ('A_VALIDER', 'VALIDEE', 'ENVOYEE', 'RECUE')), 0) as EN_COMMANDE
from REGLAGES_STOCK r;

-- Reprise du stock existant : un article et une entree pour chaque ligne d'inventaire.
insert into ARTICLES (REF, ALLEE_ID, EMPLACEMENT_ID, DATE_ENTREE)
select i.REF, i.ALLEE_ID, i.ID, i.Date
from INVENTAIRE i
where not exists (select 1 from ARTICLES a
                  where a.REF = i.REF and a.ALLEE_ID = i.ALLEE_ID and a.EMPLACEMENT_ID = i.ID
                    and a.STATUT = 'EN_STOCK');

insert into MOUVEMENTS (ARTICLE_ID, REF, TYPE, ALLEE_ID, EMPLACEMENT_ID, SOURCE, DATE_EVENEMENT)
select a.ARTICLE_ID, a.REF, 'ENTREE', a.ALLEE_ID, a.EMPLACEMENT_ID, 'REPRISE', a.DATE_ENTREE
from ARTICLES a
where not exists (select 1 from MOUVEMENTS m where m.ARTICLE_ID = a.ARTICLE_ID);
