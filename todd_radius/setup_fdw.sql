-- ============================================================
-- CREATE FOREIGN TABLES - MySQL RADIUS
-- Correr en PostgreSQL DESPUÉS de tener el server radius_mysql
-- ============================================================

-- userinfo
DROP FOREIGN TABLE IF EXISTS userinfo;
CREATE FOREIGN TABLE userinfo (
    id integer,
    username varchar(64),
    firstname varchar(128),
    lastname varchar(128),
    email varchar(255),
    department varchar(128),
    company varchar(255),
    workphone varchar(32),
    homephone varchar(32),
    mobilephone varchar(32),
    address text,
    city varchar(128),
    state varchar(128),
    country varchar(128),
    zip varchar(16),
    notes text,
    changeuserinfo varchar(8),
    portalloginpassword varchar(128),
    tv boolean,
    tvuser varchar(128),
    tvpass varchar(128),
    enableportallogin integer,
    creationdate timestamp,
    creationby varchar(64),
    updatedate timestamp,
    updateby varchar(64)
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'userinfo');

-- radcheck
DROP FOREIGN TABLE IF EXISTS radcheck;
CREATE FOREIGN TABLE radcheck (
    id integer,
    username varchar(64),
    attribute varchar(128),
    op varchar(32),
    value varchar(255)
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'radcheck');

-- radreply
DROP FOREIGN TABLE IF EXISTS radreply;
CREATE FOREIGN TABLE radreply (
    id integer,
    username varchar(64),
    attribute varchar(128),
    op varchar(32),
    value varchar(255)
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'radreply');

-- radusergroup
DROP FOREIGN TABLE IF EXISTS radusergroup;
CREATE FOREIGN TABLE radusergroup (
    username varchar(64),
    groupname varchar(128),
    priority integer
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'radusergroup');

-- radacct
DROP FOREIGN TABLE IF EXISTS radacct;
CREATE FOREIGN TABLE radacct (
    radacctid integer,
    acctsessionid varchar(64),
    acctuniqueid varchar(64),
    username varchar(64),
    groupname varchar(128),
    realm varchar(128),
    nasipaddress varchar(64),
    nasportid varchar(64),
    nasporttype varchar(32),
    acctstarttime timestamp,
    acctstoptime timestamp,
    acctsessiontime integer,
    acctauthentic varchar(32),
    connectinfo_start varchar(255),
    connectinfo_stop varchar(255),
    acctinputoctets bigint,
    acctoutputoctets bigint,
    calledstationid varchar(128),
    callingstationid varchar(128),
    acctterminatecause varchar(32),
    servicetype varchar(32),
    framedprotocol varchar(32),
    framedipaddress varchar(64)
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'radacct');

-- radpostauth
DROP FOREIGN TABLE IF EXISTS radpostauth;
CREATE FOREIGN TABLE radpostauth (
    id integer,
    username varchar(64),
    password varchar(128),
    reply varchar(255),
    authdate timestamp
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'radpostauth');

-- nas
DROP FOREIGN TABLE IF EXISTS nas;
CREATE FOREIGN TABLE nas (
    id integer,
    nasname varchar(128),
    shortname varchar(32),
    type varchar(32),
    ports integer,
    secret varchar(64),
    server varchar(64),
    community varchar(32),
    description varchar(255)
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'nas');

-- radippool
DROP FOREIGN TABLE IF EXISTS radippool;
CREATE FOREIGN TABLE radippool (
    id integer,
    pool_name varchar(128),
    framedipaddress varchar(64),
    nasipaddress varchar(64),
    calledstationid varchar(128),
    callingstationid varchar(128),
    expiry_time timestamp,
    username varchar(64),
    pool_key varchar(128)
) SERVER radius_mysql OPTIONS (dbname 'radius', table_name 'radippool');

-- ============================================================
-- VERIFICAR
-- ============================================================
SELECT COUNT(*) AS total_usuarios FROM userinfo;
SELECT COUNT(*) AS total_radcheck FROM radcheck;
SELECT COUNT(*) AS total_radreply FROM radreply;
SELECT COUNT(*) AS total_radusergroup FROM radusergroup;
SELECT COUNT(*) AS total_radacct FROM radacct;
SELECT COUNT(*) AS total_radpostauth FROM radpostauth;
SELECT COUNT(*) AS total_nas FROM nas;
SELECT COUNT(*) AS total_radippool FROM radippool;
