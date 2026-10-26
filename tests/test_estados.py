import unittest
from seguimiento_envia import clasificar, validar_guias


class EstadosTest(unittest.TestCase):
    def respuesta(self, estado):
        return {'guia': '0123456789', 'estado_actual': estado,
                'evidencia_actual': estado, 'fuente': 'https://envia.co/'}

    def test_estados(self):
        for entrada, esperado in [('ENTREGADO', 'Entregado'), ('NO ENTREGADO', 'Novedad'),
                                   ('EN REPARTO', 'En reparto'), ('CON NOVEDAD', 'Novedad'),
                                   ('en distribución', 'En reparto')]:
            with self.subTest(entrada=entrada):
                self.assertEqual(clasificar(self.respuesta(entrada), '0123456789'), esperado)

    def test_frases_ambiguas(self):
        for entrada in ['PENDIENTE DE ENTREGA', 'ENTREGADO / NOVEDAD', 'NO FUE ENTREGADO', '']:
            self.assertEqual(clasificar(self.respuesta(entrada), '0123456789'), 'Sin verificar')

    def test_guia_distinta(self):
        self.assertEqual(clasificar(self.respuesta('ENTREGADO'), '99999'), 'Sin verificar')

    def test_historial_no_es_evidencia_actual(self):
        r = self.respuesta('ENTREGADO')
        r['evidencia_actual'] = 'EN REPARTO, ENTREGADO, NOVEDAD'
        self.assertEqual(clasificar(r, '0123456789'), 'Sin verificar')

    def test_sin_fuente_o_fuente_ajena(self):
        for fuente in ['', 'https://envia.com/', 'https://envia.co.ejemplo.com/', 'http://envia.co/']:
            r = self.respuesta('ENTREGADO')
            r['fuente'] = fuente
            self.assertEqual(clasificar(r, '0123456789'), 'Sin verificar')

    def test_entrada_invalida(self):
        for respuesta in [None, [], {}, {'guia': '0123456789'}]:
            self.assertEqual(clasificar(respuesta, '0123456789'), 'Sin verificar')

    def test_validar_19_textos_y_ceros(self):
        guias = [f'{i:010}' for i in range(19)]
        self.assertEqual(validar_guias(guias), guias)

    def test_rechazar_duplicados_numeros_y_cantidad(self):
        for guias in [['12345'] * 19, list(range(19)), ['12345']]:
            with self.assertRaises(ValueError):
                validar_guias(guias)


if __name__ == '__main__':
    unittest.main()
