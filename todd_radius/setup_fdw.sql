-- ============================================================
-- SCRIPT DE SETUP FDW PARA TODD RADIUS
-- Correr como superuser en PostgreSQL ANTES de instalar el módulo
-- ============================================================

-- 1. Crear extensión mysql_fdw (si no existe)
CREATE EXTENSION IF NOT EXISTS mysql_fdw;

-- 2. Eliminar configuración anterior (si existe)
DROP USER MAPPING IF EXISTS PUBLIC SERVER radius_mysql;
DROP SERVER IF EXISTS radius_mysql CASCADE;

-- 3. Crear servidor FDW apuntando a MySQL
CREATE SERVER radius_mysql
    FOREIGN DATA WRAPPER mysql_fdw
    OPTIONS (host '10.0.2.12', port '3306');

-- 4. Crear mapeo de usuario
-- IMPORTANTE: reemplazar 'odoo_user' con el usuario de PostgreSQL que usa Odoo
CREATE USER MAPPING FOR odoo_user
    SERVER radius_mysql
    OPTIONS (username 'radius-gestion', password 'p4Bl1c');

-- 5. Importar tablas desde MySQL a PostgreSQL
-- Solo las tablas que necesitamos
IMPORT FOREIGN SCHEMA radius
    LIMIT TO (userinfo, radcheck, radreply, radusergroup, radacct, radpostauth, nas, radippool)
    FROM SERVER radius_mysql
    INTO public;

-- 6. Verificar que las tablas existen
SELECT foreign_table_name
FROM information_schema.foreign_tables
WHERE foreign_table_schema = 'public'
ORDER BY foreign_table_name;

-- 7. Probar consulta
SELECT COUNT(*) AS total_usuarios FROM userinfo;
