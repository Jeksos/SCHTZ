-- *********************************************
-- * SQL MySQL generation                      
-- *--------------------------------------------
-- * DB-MAIN version: 11.0.2              
-- * Generator date: Sep 14 2021              
-- * Generation date: Thu Jul 25 15:45:43 2024 
-- * LUN file: C:\Users\SOSO\Documents\FORMATION\CNAM\projet\projas.lun 
-- * Schema: SCHUTZ/1 
-- ********************************************* 


-- Database Section
-- ________________ 

-- create database SCHUTZ;
-- use SCHUTZ;


-- Tables Section
-- _____________ 

drop table if exists INVENTAIRE;
drop table if exists EMPLACEMENTS;


-- Tables Section
-- _____________ 

create table EMPLACEMENTS (
     ALLEE_ID char(1) not null,
     ID numeric(1) not null,
     constraint ID_EMPLACEMENTS primary key (ALLEE_ID, ID));

create table INVENTAIRE (
     REF varchar(50) not null,
     Date date not null,
     ALLEE_ID char(1) not null,
     ID numeric(1) not null,
     constraint ID_INVENTAIRE primary key (REF),
     constraint SID_INVENTAIRE unique (Date),
     constraint FKALLEE unique (ALLEE_ID, ID),
     foreign key (ALLEE_ID, ID) references EMPLACEMENTS);


-- Index Section
-- _____________ 

create unique index ID_EMPLACEMENTS
     on EMPLACEMENTS (ALLEE_ID, ID);

create unique index ID_INVENTAIRE
     on INVENTAIRE (REF);

create unique index SID_INVENTAIRE
     on INVENTAIRE (Date);

create unique index FKALLEE
     on INVENTAIRE (ALLEE_ID, ID);

