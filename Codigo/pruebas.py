
from decorator import EMPTY


board = [[EMPTY for _ in range(10)] for _ in range(10)]
print(tuple(tuple(row) for row in board))
