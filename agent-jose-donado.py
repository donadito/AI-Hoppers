## imports
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import time
import math
from concurrent.futures import ThreadPoolExecutor

## Configuración del juego

BOARD_SIZE = 10
P1 = "P1"
P2 = "P2"
EMPTY = None

PROGRESS_WEIGHT = 0.60
CAMP_WEIGHT = 0.40

P1_CAMP = frozenset(
    (row, col)
    for row in range(5)
    for col in range(5 - row)
)

P2_CAMP = frozenset(
    (BOARD_SIZE - 1 - row, BOARD_SIZE - 1 - col)
    for row, col in P1_CAMP
)

DIRECTIONS = tuple(
    (dr, dc)
    for dr in (-1, 0, 1)
    for dc in (-1, 0, 1)
    if (dr, dc) != (0, 0)
)





### Estado y reglas


@dataclass(frozen=True)
class State:
    """Tablero inmutable y jugador al que corresponde mover."""
    board: tuple
    turn: str


def initial_state():
    """Construye el tablero inicial."""
    board = [
        [EMPTY for _ in range(BOARD_SIZE)]
        for _ in range(BOARD_SIZE)
    ]

    for row, col in P1_CAMP:
        board[row][col] = P1

    for row, col in P2_CAMP:
        board[row][col] = P2

    return State(
        board=tuple(tuple(row) for row in board),
        turn=P1
    )


def player(state):
    return state.turn


def other_player(candidate):
    return P2 if candidate == P1 else P1


def inside_board(position):
    row, col = position
    return (
        0 <= row < BOARD_SIZE
        and 0 <= col < BOARD_SIZE
    )


def _completed_target_camp(state, candidate):
    """Victoria con la interpretación anti-bloqueo del proyecto."""
    target = P2_CAMP if candidate == P1 else P1_CAMP
    occupants = [
        state.board[row][col]
        for row, col in target
    ]

    return (
        all(piece is not EMPTY for piece in occupants)
        and candidate in occupants
    )


def winner(state):
    previous_player = other_player(player(state))

    if _completed_target_camp(state, previous_player):
        return previous_player

    if _completed_target_camp(state, player(state)):
        return player(state)

    return None


def terminal(state):
    return winner(state) is not None


def utility(state):
    game_winner = winner(state)

    if game_winner == P1:
        return 1

    if game_winner == P2:
        return -1

    return 0


### Control de tiempo

class SearchTimeout(Exception):
    """Interrumpe la búsqueda cuando se agota el tiempo."""
    pass


def check_time(deadline):
    if time.perf_counter() >= deadline:
        raise SearchTimeout

### Generador de acciones


def _iter_actions(state, deadline=float("inf")):
    """
    Genera acciones una por una.

    Esto permite obtener una jugada de respaldo sin calcular
    primero todas las cadenas de saltos.
    """
    check_time(deadline)

    if terminal(state):
        return

    candidate = player(state)
    board = [list(row) for row in state.board]

    # Primero generar los pasos simples.
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            check_time(deadline)

            if board[row][col] != candidate:
                continue

            origin = (row, col)

            for dr, dc in DIRECTIONS:
                destination = (row + dr, col + dc)

                if (
                    inside_board(destination)
                    and board[destination[0]][destination[1]] is EMPTY
                ):
                    yield (origin, destination)

    ## Después generar saltos simples y encadenados.
    def explore(current, path, visited):
        check_time(deadline)
        row, col = current

        for dr, dc in DIRECTIONS:
            check_time(deadline)

            middle = (row + dr, col + dc)
            landing = (row + 2 * dr, col + 2 * dc)

            if not inside_board(middle):
                continue

            if not inside_board(landing):
                continue

            if board[middle[0]][middle[1]] is EMPTY:
                continue

            if board[landing[0]][landing[1]] is not EMPTY:
                continue

            if landing in visited:
                continue

            board[row][col] = EMPTY
            board[landing[0]][landing[1]] = candidate

            new_path = path + (landing,)

            try:
                # Cada prefijo de la cadena es una acción válida.
                yield new_path

                yield from explore(
                    landing,
                    new_path,
                    visited | {landing}
                )
            finally:
                # Restaurar la copia incluso al interrumpir la búsqueda.
                board[landing[0]][landing[1]] = EMPTY
                board[row][col] = candidate

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            check_time(deadline)

            if board[row][col] == candidate:
                origin = (row, col)

                yield from explore(
                    origin,
                    (origin,),
                    frozenset({origin})
                )


def actions(state):
    """Devuelve el conjunto completo de acciones legales."""
    return set(_iter_actions(state))


def _state_after_legal_action(state, action):
    """Aplica una acción ya validada sin modificar el estado original."""
    origin = action[0]
    destination = action[-1]

    board = [list(row) for row in state.board]
    board[origin[0]][origin[1]] = EMPTY
    board[destination[0]][destination[1]] = player(state)

    return State(
        board=tuple(tuple(row) for row in board),
        turn=other_player(player(state))
    )


def result(state, action):
    """Valida la acción y devuelve el nuevo estado."""
    if action not in actions(state):
        raise ValueError(f"Jugada ilegal: {action}")

    return _state_after_legal_action(state, action)


def _ordered_successors(state, deadline):
    """Revisa primero las victorias inmediatas."""
    successors = []
    candidate = player(state)

    for action in _iter_actions(state, deadline):
        check_time(deadline)

        child = _state_after_legal_action(state, action)
        priority = 0 if winner(child) == candidate else 1

        successors.append((priority, action, child))

    check_time(deadline)
    successors.sort(key=lambda item: (item[0], item[1]))
    check_time(deadline)

    for _, action, child in successors:
        check_time(deadline)
        yield action, child


## Lógica de la Heurística 


def piece_progress(position, candidate):
    row, col = position
    maximum_distance = 2 * (BOARD_SIZE - 1)

    if candidate == P1:
        return (row + col) / maximum_distance

    return (
        (BOARD_SIZE - 1 - row)
        + (BOARD_SIZE - 1 - col)
    ) / maximum_distance


def total_progress(state, candidate):
    return sum(
        piece_progress((row, col), candidate)
        for row in range(BOARD_SIZE)
        for col in range(BOARD_SIZE)
        if state.board[row][col] == candidate
    )


def progress_balance(state):
    return (
        total_progress(state, P1)
        - total_progress(state, P2)
    ) / len(P1_CAMP)


def pieces_in_target_camp(state, candidate):
    target = P2_CAMP if candidate == P1 else P1_CAMP

    return sum(
        state.board[row][col] == candidate
        for row, col in target
    )


def camp_balance(state):
    return (
        pieces_in_target_camp(state, P1)
        - pieces_in_target_camp(state, P2)
    ) / len(P1_CAMP)


def heuristic(state):
    """Valores positivos favorecen a P1; negativos, a P2."""
    if terminal(state):
        return float(utility(state))

    return (
        PROGRESS_WEIGHT * progress_balance(state)
        + CAMP_WEIGHT * camp_balance(state)
    )






# MINIMAX CON PODA ALFA-BETA

def _max_value_ab(state, depth, alpha, beta, deadline):
    check_time(deadline)

    if terminal(state):
        return float(utility(state))

    if depth == 0:
        return heuristic(state)

    value = float("-inf")
    found_action = False

    for _, child in _ordered_successors(state, deadline):
        found_action = True

        value = max(
            value,
            _min_value_ab(
                child, depth - 1, alpha, beta, deadline
            )
        )

        if value >= beta:
            return value

        alpha = max(alpha, value)

    # Evita propagar infinito en un estado sin acciones.
    return value if found_action else heuristic(state)


def _min_value_ab(state, depth, alpha, beta, deadline):
    check_time(deadline)

    if terminal(state):
        return float(utility(state))

    if depth == 0:
        return heuristic(state)

    value = float("inf")
    found_action = False

    for _, child in _ordered_successors(state, deadline):
        found_action = True

        value = min(
            value,
            _max_value_ab(
                child, depth - 1, alpha, beta, deadline
            )
        )

        if value <= alpha:
            return value

        beta = min(beta, value)

    return value if found_action else heuristic(state)


def minimax_alpha_beta(state, depth=2, deadline=None):
    """Devuelve la mejor acción encontrada a una profundidad fija."""
    if not isinstance(depth, int) or depth < 1:
        raise ValueError("depth debe ser un entero mayor o igual que 1")

    if deadline is None:
        deadline = float("inf")

    check_time(deadline)

    if terminal(state):
        return None

    maximizing = player(state) == P1
    best_value = float("-inf") if maximizing else float("inf")
    best_action = None

    alpha = float("-inf")
    beta = float("inf")

    for action, child in _ordered_successors(state, deadline):
        if maximizing:
            value = _min_value_ab(
                child, depth - 1, alpha, beta, deadline
            )

            if best_action is None or value > best_value:
                best_value = value
                best_action = action

            alpha = max(alpha, best_value)

            if best_value == 1:
                break

        else:
            value = _max_value_ab(
                child, depth - 1, alpha, beta, deadline
            )

            if best_action is None or value < best_value:
                best_value = value
                best_action = action

            beta = min(beta, best_value)

            if best_value == -1:
                break

    check_time(deadline)
    return best_action

## PROFUNDIDAD ITERATIVA

def iterative_deepening_agent(
    state,
    time_limit=30,
    max_depth=None
):
    """Conserva la acción de la última profundidad completada."""
    if not math.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit debe ser positivo y finito")

    if max_depth is not None:
        if not isinstance(max_depth, int) or max_depth < 1:
            raise ValueError("max_depth debe ser un entero positivo")

    start_time = time.perf_counter()
    safety_margin = min(0.10, time_limit * 0.10)
    deadline = start_time + time_limit - safety_margin

    if terminal(state):
        return None

    # Obtener únicamente la primera acción como respaldo.
    # Esta operación no enumera todas las rutas posibles.
    generator = _iter_actions(state)

    try:
        best_action = next(generator, None)
    finally:
        generator.close()

    if best_action is None:
        return None

    depth = 1

    while max_depth is None or depth <= max_depth:
        try:
            check_time(deadline)

            action = minimax_alpha_beta(
                state,
                depth=depth,
                deadline=deadline
            )

            if action is not None:
                best_action = action

            depth += 1

        except SearchTimeout:
            break

    return best_action


### Minimax agent 
class MinimaxAgent:
    """Agente independiente de la interfaz gráfica."""

    def __init__(self, time_limit=30, max_depth=None):
        if not math.isfinite(time_limit) or not 0 < time_limit <= 30:
            raise ValueError(
                "time_limit debe ser mayor que 0 y como máximo 30"
            )

        if max_depth is not None:
            if not isinstance(max_depth, int) or max_depth < 1:
                raise ValueError(
                    "max_depth debe ser un entero positivo"
                )

        self.time_limit = time_limit
        self.max_depth = max_depth

    def choose_action(self, state):
        """
        Recibe un objeto con atributos board y turn
        Devuelve:
            ((fila_origen, columna_origen), ..., (fila_destino, columna_destino))

        Devuelve None si el estado es terminal o no hay acciones.
        """
    
        local_state = State(
            board=tuple(tuple(row) for row in state.board),
            turn=state.turn
        )

        if local_state.turn not in (P1, P2):
            raise ValueError("state.turn debe ser 'P1' o 'P2'")

        if (
            len(local_state.board) != BOARD_SIZE
            or any(
                len(row) != BOARD_SIZE
                for row in local_state.board
            )
        ):
            raise ValueError("state.board debe ser de 10 × 10")

        if any(
            piece not in (EMPTY, P1, P2)
            for row in local_state.board
            for piece in row
        ):
            raise ValueError(
                "Las casillas deben contener 'P1', 'P2' o None"
            )

        return iterative_deepening_agent(
            local_state,
            time_limit=self.time_limit,
            max_depth=self.max_depth
        )


# Solo para probar. No afecta el funcionamiento una vez lo abran... Fresh.
if __name__ == "__main__":
    state = initial_state()
    agent = MinimaxAgent(time_limit=1)

    start = time.perf_counter()
    action = agent.choose_action(state)
    elapsed = time.perf_counter() - start

    print("Acción:", action)
    print("Tiempo:", round(elapsed, 4), "segundos")
    print("Acción legal:", action in actions(state))