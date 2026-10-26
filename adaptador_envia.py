"""Consulta el HTML oficial. No infiere estados desde textos generales."""
from datetime import datetime
import re
import time
import unicodedata

from bs4 import BeautifulSoup
import requests

URL = 'https://hub.envia.co/landingrastreo/Rastreo/Index'


class ConsultaError(Exception):
    def __init__(self, mensaje, detener_lote=False):
        super().__init__(mensaje)
        self.detener_lote = detener_lote


def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto)
    return ' '.join(''.join(c for c in texto if not unicodedata.combining(c)).upper().split())


# Pares observados en la línea de tiempo oficial el 26/10/2026.
PARES = {
    'ENTREGAMOS TU ENVIO': '¡Misión cumplida! Tu envío fue entregado.',
    '¡PREPARATE PARA RECIBIRLO!': 'Estamos haciendo las entregas en tu sector.',
    '¡UPS! ALGO PASA CON TU ENVIO': 'Algo sucedió en el camino. ¡Lo estamos solucionando!',
    '¡FALTA POCO!': 'Ya tenemos tu envío en la ciudad de entrega.',
    'TU ENVIO ESTA EN MOVIMIENTO.': 'Estamos recorriendo kilómetros para llegar al destino de tu envío.',
    'TU GUIA FUE GENERADA': 'Pronto recogeremos tu envío e iniciaremos esta nueva experiencia logística.',
}


def unico(nodo, selector):
    elementos = nodo.select(selector)
    if len(elementos) != 1:
        raise ConsultaError('Cambió la estructura del rastreador')
    return elementos[0].get_text(' ', strip=True)


def analizar_html(contenido, guia):
    soup = BeautifulSoup(contenido, 'html.parser')
    numeros = soup.select('.tracking-card .tracking-number')
    if len(numeros) != 1 or numeros[0].get_text(strip=True) != guia:
        raise ConsultaError('La respuesta no confirma la guía solicitada')
    eventos = soup.select('.timeline-event')
    if not eventos:
        raise ConsultaError('No hay eventos verificables')
    fechas = []
    for evento in eventos:
        for nodo in [evento, *evento.parents]:
            estilo = re.sub(r'\s+', '', nodo.get('style', '')).lower()
            if nodo.has_attr('hidden') or nodo.get('aria-hidden') == 'true' or 'display:none' in estilo:
                raise ConsultaError('Hay eventos ocultos o ambiguos')
        texto_fecha = unico(evento, '.event-date')
        try:
            fecha = datetime.strptime(texto_fecha, '%d/%m/%Y')
        except ValueError:
            raise ConsultaError('Fecha de evento ausente o desconocida') from None
        fechas.append(fecha)
    # El portal observado presenta el evento vigente primero.
    # Dentro de un día se respeta su orden, sin inventar horas ni prioridades.
    if any(a < b for a, b in zip(fechas, fechas[1:])):
        raise ConsultaError('El orden del historial cambió')
    titulo = unico(eventos[0], '.event-content h3')
    detalle = unico(eventos[0], '.event-content p')
    esperado = PARES.get(normalizar(titulo))
    if esperado is None or normalizar(detalle) != normalizar(esperado):
        raise ConsultaError('Estado vigente desconocido o evidencia contradictoria')
    return {'guia': guia, 'estado_actual': titulo, 'evidencia_actual': titulo,
            'fuente': URL, 'evento_fecha': fechas[0].strftime('%d/%m/%Y')}


def consultar(guia):
    if not isinstance(guia, str) or not re.fullmatch(r'[0-9]{5,30}', guia):
        raise ConsultaError('Formato de guía inválido')
    for intento in range(2):
        try:
            respuesta = requests.get(URL, params={'guia': guia},
                                     headers={'User-Agent': 'SeguimientoEnvios/2.0'},
                                     timeout=(5, 10), allow_redirects=False)
        except requests.RequestException:
            if intento == 0:
                time.sleep(1)
                continue
            raise ConsultaError('Error de conexión con Envía') from None
        codigo = respuesta.status_code
        if codigo in (401, 403, 429):
            raise ConsultaError('Envía restringió las consultas. Revisa el acceso y la frecuencia', True)
        if codigo in (500, 502, 503, 504) and intento == 0:
            time.sleep(1)
            continue
        if codigo != 200:
            raise ConsultaError('Respuesta HTTP no válida')
        if 'html' not in respuesta.headers.get('Content-Type', '').lower():
            raise ConsultaError('El portal devolvió un formato desconocido')
        return analizar_html(respuesta.content, guia)
    raise ConsultaError('Consulta incompleta')
