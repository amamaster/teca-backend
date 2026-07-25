"""Genera imágenes PNG de ejemplo para los productos del seed.

Dibuja siluetas sencillas de cada tipo de mueble, al estilo del diseño del
proyecto. No usa librerías externas: escribe el PNG a mano con `zlib`, así no
hay que instalar nada adicional.

Estas imágenes son solo para que el catálogo no se vea vacío al arrancar.
Cuando subas fotos reales desde el panel, se reemplazan.
"""
import struct
import zlib
from pathlib import Path

ANCHO = ALTO = 600
FONDO = (245, 242, 237)      # crema, como el fondo del diseño
MUEBLE = (176, 176, 176)     # gris claro
SOMBRA = (140, 140, 140)     # gris medio para dar profundidad


class Lienzo:
    """Una imagen en memoria sobre la que se dibujan rectángulos y círculos."""

    def __init__(self, ancho: int, alto: int, fondo: tuple[int, int, int]):
        self.ancho = ancho
        self.alto = alto
        self.pixeles = bytearray(bytes(fondo) * ancho * alto)

    def rectangulo(self, x: int, y: int, ancho: int, alto: int, color: tuple[int, int, int]) -> None:
        for fila in range(max(0, y), min(self.alto, y + alto)):
            inicio = (fila * self.ancho + max(0, x)) * 3
            fin = (fila * self.ancho + min(self.ancho, x + ancho)) * 3
            if fin > inicio:
                self.pixeles[inicio:fin] = bytes(color) * ((fin - inicio) // 3)

    def circulo(self, cx: int, cy: int, radio: int, color: tuple[int, int, int]) -> None:
        for fila in range(max(0, cy - radio), min(self.alto, cy + radio + 1)):
            ancho_fila = int((radio**2 - (fila - cy) ** 2) ** 0.5) if abs(fila - cy) <= radio else 0
            self.rectangulo(cx - ancho_fila, fila, ancho_fila * 2, 1, color)

    def a_png(self) -> bytes:
        """Codifica el lienzo como PNG."""
        # Cada línea del PNG lleva delante un byte de filtro (0 = sin filtro)
        crudo = b"".join(
            b"\x00" + bytes(self.pixeles[fila * self.ancho * 3 : (fila + 1) * self.ancho * 3])
            for fila in range(self.alto)
        )

        def bloque(tipo: bytes, datos: bytes) -> bytes:
            contenido = tipo + datos
            return (
                struct.pack(">I", len(datos))
                + contenido
                + struct.pack(">I", zlib.crc32(contenido) & 0xFFFFFFFF)
            )

        cabecera = struct.pack(">IIBBBBB", self.ancho, self.alto, 8, 2, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + bloque(b"IHDR", cabecera)
            + bloque(b"IDAT", zlib.compress(crudo, 9))
            + bloque(b"IEND", b"")
        )


def _silla(c: Lienzo) -> None:
    c.rectangulo(200, 140, 200, 200, MUEBLE)   # respaldo
    c.rectangulo(170, 330, 260, 50, SOMBRA)    # asiento
    c.rectangulo(185, 380, 30, 110, MUEBLE)    # patas
    c.rectangulo(385, 380, 30, 110, MUEBLE)


def _lampara(c: Lienzo) -> None:
    c.rectangulo(230, 120, 140, 110, MUEBLE)   # pantalla
    c.rectangulo(290, 230, 20, 240, SOMBRA)    # tubo
    c.rectangulo(230, 470, 140, 25, MUEBLE)    # base


def _espejo(c: Lienzo) -> None:
    c.circulo(300, 280, 160, MUEBLE)
    c.circulo(300, 280, 135, FONDO)
    c.rectangulo(255, 450, 90, 30, SOMBRA)     # soporte


def _mesa(c: Lienzo) -> None:
    c.rectangulo(120, 240, 360, 40, SOMBRA)    # tablero
    c.rectangulo(150, 280, 30, 180, MUEBLE)    # patas
    c.rectangulo(420, 280, 30, 180, MUEBLE)


def _cama(c: Lienzo) -> None:
    c.rectangulo(110, 170, 380, 90, MUEBLE)    # cabecera
    c.rectangulo(100, 260, 400, 110, SOMBRA)   # colchón
    c.rectangulo(140, 285, 130, 55, FONDO)     # almohadas
    c.rectangulo(330, 285, 130, 55, FONDO)
    c.rectangulo(110, 370, 25, 80, MUEBLE)     # patas
    c.rectangulo(465, 370, 25, 80, MUEBLE)


def _sofa(c: Lienzo) -> None:
    c.rectangulo(110, 200, 380, 110, MUEBLE)   # respaldo
    c.rectangulo(100, 310, 400, 90, SOMBRA)    # asiento
    c.rectangulo(100, 230, 55, 170, MUEBLE)    # brazos
    c.rectangulo(445, 230, 55, 170, MUEBLE)
    c.rectangulo(140, 400, 25, 60, MUEBLE)     # patas
    c.rectangulo(435, 400, 25, 60, MUEBLE)


DIBUJOS = {
    "silla": _silla,
    "lampara": _lampara,
    "espejo": _espejo,
    "mesa": _mesa,
    "cama": _cama,
    "sofa": _sofa,
}


def generar(categoria: str, destino: Path) -> None:
    """Crea el PNG de la categoría indicada en la ruta dada."""
    lienzo = Lienzo(ANCHO, ALTO, FONDO)
    DIBUJOS.get(categoria, _mesa)(lienzo)
    destino.write_bytes(lienzo.a_png())
