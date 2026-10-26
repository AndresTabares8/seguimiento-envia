import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from adaptador_envia import analizar_html, consultar, ConsultaError
from seguimiento_envia import clasificar, escribir_pagina, main

GUIA = '000001234567'


def evento(fecha, titulo, detalle):
    return f'<div class="timeline-event"><div class="event-date">{fecha}</div><div class="event-content"><h3>{titulo}</h3><p>{detalle}</p></div></div>'


def pagina(eventos):
    return f'<html><meta charset="utf-8"><div class="tracking-card"><span class="tracking-number">{GUIA}</span></div>{eventos}</html>'


ENTREGA = evento('24/10/2026', 'Entregamos tu envío', '¡Misión cumplida! Tu envío fue entregado.')
REPARTO = evento('24/10/2026', '¡Prepárate para recibirlo!', 'Estamos haciendo las entregas en tu sector.')
NOVEDAD = evento('26/10/2026', '¡Ups! Algo pasa con tu envío', 'Algo sucedió en el camino. ¡Lo estamos solucionando!')


class RastreadorTest(unittest.TestCase):
    def test_novedad_mas_reciente_supera_entrega_historica(self):
        r = analizar_html(pagina(NOVEDAD + ENTREGA + REPARTO), GUIA)
        self.assertEqual(clasificar(r, GUIA), 'Novedad')
        self.assertEqual(r['evento_fecha'], '26/10/2026')

    def test_entrega_actual_y_eventos_mismo_dia(self):
        self.assertEqual(clasificar(analizar_html(pagina(ENTREGA + REPARTO), GUIA), GUIA), 'Entregado')

    def test_reparto_sin_buscar_entrega_fuera_del_historial(self):
        contenido = pagina(REPARTO) + '<p>¡Misión cumplida! Tu envío fue entregado.</p>'
        self.assertEqual(clasificar(analizar_html(contenido, GUIA), GUIA), 'En reparto')

    def test_guia_ajena_no_confirma(self):
        with self.assertRaises(ConsultaError):
            analizar_html(pagina(ENTREGA), '999999999999')

    def test_orden_invalido(self):
        with self.assertRaises(ConsultaError):
            analizar_html(pagina(ENTREGA + NOVEDAD), GUIA)

    def test_descripcion_contradictoria(self):
        with self.assertRaises(ConsultaError):
            analizar_html(pagina(evento('26/10/2026', 'Entregamos tu envío', 'No se ha entregado')), GUIA)

    def test_estado_nuevo_no_usa_historial_conocido(self):
        with self.assertRaises(ConsultaError):
            analizar_html(pagina(evento('26/10/2026', 'Estado nuevo', 'Por revisar') + ENTREGA), GUIA)

    def test_fecha_ausente_y_captcha(self):
        for contenido in [pagina(ENTREGA.replace('24/10/2026', '')), '<html>Captcha</html>']:
            with self.assertRaises(ConsultaError):
                analizar_html(contenido, GUIA)

    def test_evento_oculto(self):
        with self.assertRaises(ConsultaError):
            analizar_html(pagina(ENTREGA.replace('class="timeline-event"', 'class="timeline-event" hidden')), GUIA)

    @patch('adaptador_envia.requests.get')
    def test_429_suspende_sin_reintentar(self, get):
        get.return_value = Mock(status_code=429)
        with self.assertRaises(ConsultaError) as contexto:
            consultar(GUIA)
        self.assertTrue(contexto.exception.detener_lote)
        self.assertEqual(get.call_count, 1)

    @patch('adaptador_envia.time.sleep')
    @patch('adaptador_envia.requests.get')
    def test_timeout_acotado_y_sin_guia_en_error(self, get, sleep):
        get.side_effect = requests.Timeout('Dato privado: ' + GUIA)
        with self.assertRaises(ConsultaError) as contexto:
            consultar(GUIA)
        self.assertNotIn(GUIA, str(contexto.exception))
        self.assertEqual(get.call_count, 2)

    @patch('adaptador_envia.requests.get')
    def test_http_ok_analiza_bytes(self, get):
        get.return_value = Mock(status_code=200, headers={'Content-Type': 'text/html'}, content=pagina(NOVEDAD).encode('utf-8'))
        self.assertEqual(clasificar(consultar(GUIA), GUIA), 'Novedad')

    def test_salida_publica_no_copia_datos_extra(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as carpeta:
            try:
                os.chdir(carpeta)
                escribir_pagina([{'referencia': 'G01', 'estado': 'Novedad', 'consulta_utc': '2026-10-26T12:00:00+00:00', 'guia': GUIA, 'destinatario': 'Persona privada'}], '2026-10-26T12:00:00+00:00')
                for ruta in Path('site').iterdir():
                    texto = ruta.read_text(encoding='utf-8')
                    self.assertNotIn(GUIA, texto)
                    self.assertNotIn('Persona privada', texto)
            finally:
                os.chdir(original)

    @patch('seguimiento_envia.time.sleep')
    @patch('seguimiento_envia.consultar', side_effect=ConsultaError('Bloqueo', True))
    @patch('seguimiento_envia.leer_guias', return_value=[f'{i:012}' for i in range(19)])
    def test_bloqueo_detiene_el_lote(self, leer, consulta, dormir):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as carpeta:
            try:
                os.chdir(carpeta)
                with patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}):
                    main()
                self.assertEqual(consulta.call_count, 1)
                import json
                self.assertEqual(json.loads(Path('salud.json').read_text())['sin_verificar'], 19)
            finally:
                os.chdir(original)
