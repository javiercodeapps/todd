from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestToddTxtImportEncadenado(TransactionCase):
    """Regresión para el encolado secuencial de lotes.

    Encolar todos los lotes a la vez hace que N jobs de queue_job actualicen la
    misma fila de ``todd_txt_import`` en ``_sumar_progreso``. Con Odoo 19
    (REPEATABLE READ) eso termina en SerializationFailure (40001).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Import = cls.env['todd.txt.import']

    def test_el_chain_recorre_los_mismos_rangos_que_el_plan(self):
        for total in (1, 2, 5000, 5001, 10000, 12345, 25000, 99999):
            plan = list(self.Import._rangos_lote(total))
            start, end = plan[0]
            encadenado = [(start, end)]
            while True:
                siguiente = self.Import._siguiente_rango(end, total)
                if siguiente is None:
                    break
                encadenado.append(siguiente)
                end = siguiente[1]
            self.assertEqual(encadenado, plan, f'total={total}')

    def test_ultimo_lote_no_encola_nada(self):
        rec = self.Import.create({'filename': 'test.txt'})
        delayable = MagicMock()
        with patch.object(type(rec), 'with_delay', return_value=delayable) as wd:
            rec._encolar_siguiente_lote(12346, 12345, 'test.txt')
        wd.assert_not_called()

    def test_lote_intermedio_encola_solo_el_siguiente(self):
        rec = self.Import.create({'filename': 'test.txt'})
        delayable = MagicMock()
        with patch.object(type(rec), 'with_delay', return_value=delayable) as wd:
            rec._encolar_siguiente_lote(5001, 12345, 'test.txt')

        wd.assert_called_once()
        self.assertEqual(wd.call_args.kwargs['channel'], 'root')
        self.assertEqual(
            wd.call_args.kwargs['identity_key'],
            f'todd.txt.import.{rec.id}.5001.10001',
        )
        delayable._procesar_lote.assert_called_once_with(5001, 10001, 12345)
