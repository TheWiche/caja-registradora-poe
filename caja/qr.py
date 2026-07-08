"""Generador de códigos QR en Python puro (sin librerías externas).

Implementa el subconjunto del estándar ISO/IEC 18004 necesario para
codificar una URL corta en modo byte, nivel de corrección L, versiones
1 a 5 (hasta 108 bytes de datos — de sobra para una dirección local
como «http://192.168.1.20:54321/p/9f3a2b»). No se implementan
versiones ≥7 (evita el bloque de "información de versión" adicional
del estándar) ni la interleave de múltiples bloques Reed-Solomon
(innecesaria a este tamaño), lo que mantiene el generador compacto y
verificable.

`autotest()` valida la aritmética internamente (cuerpo de Galois y
Reed-Solomon) pero no reemplaza una prueba real con la cámara de un
teléfono.
"""

# ---------------------------------------------------------------- GF(256)

_EXP = [0] * 512
_LOG = [0] * 256


def _construir_gf256():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_construir_gf256()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


# ---------------------------------------------------------------- Reed-Solomon

def _generador_rs(nsym: int):
    # Se construye en orden ascendente (índice 0 = término constante) porque
    # así es trivial multiplicar por (x + alfa^i) en cada paso; al final se
    # invierte para dejar el coeficiente líder en el índice 0, que es lo que
    # espera la división sintética de rs_encode.
    gen = [1]
    for i in range(nsym):
        nuevo = [0] * (len(gen) + 1)
        for j, coef in enumerate(gen):
            nuevo[j] ^= _gf_mul(coef, _EXP[i])
            nuevo[j + 1] ^= coef
        gen = nuevo
    return gen[::-1]


def rs_encode(datos: list, nsym: int) -> list:
    gen = _generador_rs(nsym)
    resto = datos + [0] * nsym
    for i in range(len(datos)):
        coef = resto[i]
        if coef != 0:
            for j, g in enumerate(gen):
                resto[i + j] ^= _gf_mul(g, coef)
    return resto[len(datos):]


def _evaluar_polinomio(codigo: list, x: int) -> int:
    resultado = 0
    for coef in codigo:
        resultado = _gf_mul(resultado, x) ^ coef
    return resultado


# ---------------------------------------------------------------- capacidades

MAX_VERSION = 5
DATA_CAPACITY_L = {1: 19, 2: 34, 3: 55, 4: 80, 5: 108}
ECC_L = {1: 7, 2: 10, 3: 15, 4: 20, 5: 26}
_ALINEACION = {2: 18, 3: 22, 4: 26, 5: 30}

_FINDER = (
    "1111111",
    "1000001",
    "1011101",
    "1011101",
    "1011101",
    "1000001",
    "1111111",
)

_GENERADOR_FORMATO = 0x537
_MASCARA_FORMATO = 0x5412
_NIVEL_L = 0b01


def _elegir_version(n_bytes: int) -> int:
    requerido = 4 + 8 + 8 * n_bytes
    for version in range(1, MAX_VERSION + 1):
        if requerido <= DATA_CAPACITY_L[version] * 8:
            return version
    raise ValueError(
        f"El texto es demasiado largo para el QR local (máximo "
        f"{DATA_CAPACITY_L[MAX_VERSION]} bytes, se recibieron {n_bytes})."
    )


def _entero_a_bits(valor: int, n: int) -> list:
    return [(valor >> k) & 1 for k in range(n - 1, -1, -1)]


def _bits_a_bytes(bits: list) -> list:
    return [
        int("".join(str(b) for b in bits[i:i + 8]), 2)
        for i in range(0, len(bits), 8)
    ]


def _bits_de_datos(datos: bytes, version: int) -> list:
    capacidad_bits = DATA_CAPACITY_L[version] * 8
    bits = []
    bits += _entero_a_bits(0b0100, 4)      # modo byte
    bits += _entero_a_bits(len(datos), 8)  # contador (válido para v1-9)
    for b in datos:
        bits += _entero_a_bits(b, 8)
    bits += [0] * max(0, min(4, capacidad_bits - len(bits)))
    while len(bits) % 8 != 0:
        bits.append(0)
    relleno = (0xEC, 0x11)
    i = 0
    while len(bits) < capacidad_bits:
        bits += _entero_a_bits(relleno[i % 2], 8)
        i += 1
    return bits[:capacidad_bits]


# ---------------------------------------------------------------- matriz

def _colocar_buscador(matriz, es_funcion, size, r0, c0):
    for dr in range(7):
        for dc in range(7):
            matriz[r0 + dr][c0 + dc] = (_FINDER[dr][dc] == "1")
            es_funcion[r0 + dr][c0 + dc] = True
    for dr in range(-1, 8):
        for dc in (-1, 7):
            r, c = r0 + dr, c0 + dc
            if 0 <= r < size and 0 <= c < size:
                matriz[r][c] = False
                es_funcion[r][c] = True
    for dc in range(-1, 8):
        for dr in (-1, 7):
            r, c = r0 + dr, c0 + dc
            if 0 <= r < size and 0 <= c < size:
                matriz[r][c] = False
                es_funcion[r][c] = True


def _colocar_zigzag(matriz, es_funcion, size, bits):
    idx = 0
    subiendo = True
    col = size - 1
    while col >= 1:
        if col == 6:
            col -= 1
        for i in range(size):
            fila = (size - 1 - i) if subiendo else i
            for c in (col, col - 1):
                if not es_funcion[fila][c]:
                    valor = bits[idx] if idx < len(bits) else 0
                    matriz[fila][c] = bool(valor)
                    idx += 1
        subiendo = not subiendo
        col -= 2


def _condicion_mascara(m: int, r: int, c: int) -> bool:
    if m == 0:
        return (r + c) % 2 == 0
    if m == 1:
        return r % 2 == 0
    if m == 2:
        return c % 3 == 0
    if m == 3:
        return (r + c) % 3 == 0
    if m == 4:
        return (r // 2 + c // 3) % 2 == 0
    if m == 5:
        return (r * c) % 2 + (r * c) % 3 == 0
    if m == 6:
        return ((r * c) % 2 + (r * c) % 3) % 2 == 0
    if m == 7:
        return ((r + c) % 2 + (r * c) % 3) % 2 == 0
    raise ValueError(m)


def _penal_corrida(secuencia) -> int:
    total = 0
    actual = secuencia[0]
    largo = 1
    for v in secuencia[1:]:
        if v == actual:
            largo += 1
        else:
            if largo >= 5:
                total += 3 + (largo - 5)
            actual, largo = v, 1
    if largo >= 5:
        total += 3 + (largo - 5)
    return total


_PATRON_A = (True, False, True, True, True, False, True,
             False, False, False, False)
_PATRON_B = tuple(reversed(_PATRON_A))


def _penalizacion(matriz, size) -> int:
    total = 0
    for r in range(size):
        total += _penal_corrida(matriz[r])
    for c in range(size):
        total += _penal_corrida([matriz[r][c] for r in range(size)])
    for r in range(size - 1):
        for c in range(size - 1):
            v = matriz[r][c]
            if (matriz[r][c + 1] == v and matriz[r + 1][c] == v
                    and matriz[r + 1][c + 1] == v):
                total += 3
    for r in range(size):
        fila = tuple(matriz[r])
        for c in range(size - 10):
            ventana = fila[c:c + 11]
            if ventana == _PATRON_A or ventana == _PATRON_B:
                total += 40
    for c in range(size):
        columna = tuple(matriz[r][c] for r in range(size))
        for r in range(size - 10):
            ventana = columna[r:r + 11]
            if ventana == _PATRON_A or ventana == _PATRON_B:
                total += 40
    oscuros = sum(v for fila in matriz for v in fila)
    porcentaje = oscuros * 100 / (size * size)
    total += int(abs(porcentaje - 50) / 5) * 10
    return total


def _bits_formato(mascara: int) -> int:
    datos = (_NIVEL_L << 3) | mascara
    valor = datos << 10
    for i in range(4, -1, -1):
        if valor & (1 << (i + 10)):
            valor ^= _GENERADOR_FORMATO << i
    codigo = (datos << 10) | valor
    return codigo ^ _MASCARA_FORMATO


def _escribir_formato(matriz, size, mascara):
    bits = _bits_formato(mascara)

    def bit(i):
        return bool((bits >> i) & 1)

    pos1 = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
            (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    pos2 = [(size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
            (size - 5, 8), (size - 6, 8), (size - 7, 8), (8, size - 8),
            (8, size - 7), (8, size - 6), (8, size - 5), (8, size - 4),
            (8, size - 3), (8, size - 2), (8, size - 1)]
    for i in range(15):
        r, c = pos1[i]
        matriz[r][c] = bit(14 - i)
        r, c = pos2[i]
        matriz[r][c] = bit(14 - i)


def generar_matriz(texto: str) -> list:
    """Devuelve la matriz (lista de listas de bool; True = módulo oscuro)."""
    datos = texto.encode("utf-8")
    version = _elegir_version(len(datos))
    size = version * 4 + 17
    matriz = [[False] * size for _ in range(size)]
    es_funcion = [[False] * size for _ in range(size)]

    _colocar_buscador(matriz, es_funcion, size, 0, 0)
    _colocar_buscador(matriz, es_funcion, size, 0, size - 7)
    _colocar_buscador(matriz, es_funcion, size, size - 7, 0)

    for i in range(8, size - 8):
        v = (i % 2 == 0)
        matriz[6][i] = v
        es_funcion[6][i] = True
        matriz[i][6] = v
        es_funcion[i][6] = True

    if version in _ALINEACION:
        c0 = _ALINEACION[version]
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                r, c = c0 + dr, c0 + dc
                borde = abs(dr) == 2 or abs(dc) == 2
                matriz[r][c] = borde or (dr == 0 and dc == 0)
                es_funcion[r][c] = True

    rd, cd = 4 * version + 9, 8
    matriz[rd][cd] = True
    es_funcion[rd][cd] = True

    for i in range(9):
        es_funcion[8][i] = True
        es_funcion[i][8] = True
    for i in range(size - 8, size):
        es_funcion[8][i] = True
    for i in range(size - 7, size):
        es_funcion[i][8] = True

    bits_datos = _bits_de_datos(datos, version)
    codewords = _bits_a_bytes(bits_datos)
    ecc = rs_encode(list(codewords), ECC_L[version])
    bits_finales = []
    for b in codewords + ecc:
        bits_finales += _entero_a_bits(b, 8)
    _colocar_zigzag(matriz, es_funcion, size, bits_finales)

    mejor_mascara = mejor_matriz = mejor_puntaje = None
    for m in range(8):
        candidato = [fila[:] for fila in matriz]
        for r in range(size):
            for c in range(size):
                if not es_funcion[r][c] and _condicion_mascara(m, r, c):
                    candidato[r][c] = not candidato[r][c]
        puntaje = _penalizacion(candidato, size)
        if mejor_puntaje is None or puntaje < mejor_puntaje:
            mejor_puntaje, mejor_mascara, mejor_matriz = puntaje, m, candidato

    _escribir_formato(mejor_matriz, size, mejor_mascara)
    return mejor_matriz


# ---------------------------------------------------------------- autoprueba

def autotest() -> list:
    """Verificaciones matemáticas internas (cuerpo de Galois y Reed-Solomon).

    No sustituye una prueba real escaneando con un teléfono, pero detecta
    con alta confianza errores fundamentales en la aritmética del generador.
    """
    fallos = []
    for a in range(1, 256):
        inv = _EXP[(255 - _LOG[a]) % 255]
        if _gf_mul(a, inv) != 1:
            fallos.append(f"GF(256): {a} no tiene inverso multiplicativo correcto")

    for version, ecc_n in ECC_L.items():
        datos = list(range(DATA_CAPACITY_L[version]))
        ecc = rs_encode(list(datos), ecc_n)
        codigo = datos + ecc
        for i in range(ecc_n):
            if _evaluar_polinomio(codigo, _EXP[i % 255]) != 0:
                fallos.append(f"Reed-Solomon versión {version}: síndrome {i} "
                              "no es cero")

    for version in range(1, MAX_VERSION + 1):
        cap = DATA_CAPACITY_L[version]
        texto = "A" * max(1, cap - 3)
        try:
            matriz = generar_matriz(texto)
        except Exception as error:
            fallos.append(f"generar_matriz falló en versión {version}: {error}")
            continue
        size = len(matriz)
        if size != version * 4 + 17:
            fallos.append(f"tamaño de matriz incorrecto para versión {version}")
        if not (matriz[0][0] and matriz[3][3] and not matriz[1][1]):
            fallos.append(f"patrón buscador superior-izquierdo mal formado "
                          f"(v{version})")
        if not (matriz[0][size - 1] and matriz[size - 1][0]):
            fallos.append(f"patrones buscadores restantes mal formados "
                          f"(v{version})")
        for i in range(8, size - 8):
            if matriz[6][i] != (i % 2 == 0):
                fallos.append(f"patrón de sincronización incorrecto (v{version})")
                break
    return fallos
