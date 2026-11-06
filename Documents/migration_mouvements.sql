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

-- Reprise du stock existant : un article et une entree pour chaque ligne d'inventaire.
insert into ARTICLES (REF, ALLEE_ID, EMPLACEMENT_ID, DATE_ENTREE)
select i.REF, i.ALLEE_ID, i.ID, i.Date
from INVENTAIRE i
where not exists (select 1 from ARTICLES a where a.REF = i.REF and a.STATUT = 'EN_STOCK');

insert into MOUVEMENTS (ARTICLE_ID, REF, TYPE, ALLEE_ID, EMPLACEMENT_ID, SOURCE, DATE_EVENEMENT)
select a.ARTICLE_ID, a.REF, 'ENTREE', a.ALLEE_ID, a.EMPLACEMENT_ID, 'REPRISE', a.DATE_ENTREE
from ARTICLES a
where not exists (select 1 from MOUVEMENTS m where m.ARTICLE_ID = a.ARTICLE_ID);
