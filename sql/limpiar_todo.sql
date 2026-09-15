-- ============================================
-- SCRIPT: Borrar TODOS los datos de Todd
-- ============================================

SET session_replication_role = 'replica';

DELETE FROM todd_factura;
DELETE FROM todd_servicio;
DELETE FROM res_users WHERE id NOT IN (1, 2, 3, 4);
DELETE FROM res_partner WHERE id NOT IN (1, 2, 3, 4);

SET session_replication_role = 'origin';

-- Verificar
SELECT 'facturas' AS tabla, COUNT(*) AS total FROM todd_factura
UNION ALL SELECT 'servicios', COUNT(*) FROM todd_servicio
UNION ALL SELECT 'partners', COUNT(*) FROM res_partner WHERE id NOT IN (1, 2, 3, 4)
UNION ALL SELECT 'usuarios', COUNT(*) FROM res_users WHERE id NOT IN (1, 2, 3, 4);
