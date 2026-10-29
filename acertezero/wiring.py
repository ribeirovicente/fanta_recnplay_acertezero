"""Mapeamento proposto para as duas Bases completas da Arena.

Cada posição da tupla corresponde à porta RJ45-1..RJ45-5 da Base.
Os quatro GPIOs já validados permanecem nas posições 1 de J1 e J2.
"""

ARENA_FULL_INPUTS = {
    1: (5, 6, 12, 13, 19),
    2: (24, 20, 21, 25, 9),
}

ARENA_FULL_OUTPUTS = {
    1: (4, 17, 18, 26, 27),
    2: (23, 7, 8, 10, 11),
}
