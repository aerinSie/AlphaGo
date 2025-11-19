import pygame
import sys
from collections import deque

# --- 1. 遊戲參數設定 ---
BOARD_SIZE = 9  # 棋盤大小 (9x9)
SQUARE_SIZE = 50  # 每個格子的邊長 (像素)
LINE_THICKNESS = 2
MARGIN = 50  # 邊緣留白
WIDTH = HEIGHT = BOARD_SIZE * SQUARE_SIZE + 2 * MARGIN

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BROWN = (205, 133, 63)  # 棋盤顏色
RED = (255, 0, 0)

# 初始化 Pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("基礎圍棋 (9x9)")
font = pygame.font.Font(None, 36)

# --- 2. 數據結構 ---
# 棋盤狀態: 0=空, 1=黑棋, 2=白棋
board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
current_player = 1  # 1: Black, 2: White
captured_stones = {1: 0, 2: 0}  # 提子計數 {黑: 0, 白: 0}
previous_board = None  # 用於判斷打劫


# --- 3. 核心邏輯函數 ---

def get_neighbors(r, c):
    """獲取一個點周圍四個鄰居的座標 (R, C)"""
    neighbors = []
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    for dr, dc in directions:
        nr, nc = r + dr, c + dc
        if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
            neighbors.append((nr, nc))
    return neighbors


def find_group_and_liberties(r, c, board_state):
    """
    使用 BFS 找出 (r, c) 點所屬的棋群，並計算該棋群的「氣」（Liberties）。
    返回: (棋群座標集合, 氣點座標集合)
    """
    target_color = board_state[r][c]
    if target_color == 0:
        return set(), set()

    group = set()
    liberties = set()
    queue = deque([(r, c)])

    while queue:
        cr, cc = queue.popleft()

        if (cr, cc) in group:
            continue

        group.add((cr, cc))

        for nr, nc in get_neighbors(cr, cc):
            neighbor_color = board_state[nr][nc]

            if neighbor_color == 0:
                # 氣點
                liberties.add((nr, nc))
            elif neighbor_color == target_color:
                # 同色棋子，加入隊列繼續搜索
                if (nr, nc) not in group:
                    queue.append((nr, nc))

    return group, liberties


def capture_stones(board_state, r, c):
    """
    檢查並提走落子 (r, c) 周圍所有氣為 0 的對方棋子。
    返回提走的棋子總數。
    """
    opponent_color = 3 - board_state[r][c]  # 1 -> 2, 2 -> 1
    captured_count = 0
    stones_to_remove = set()

    # 檢查落子點周圍的四個異色棋群
    for nr, nc in get_neighbors(r, c):
        if board_state[nr][nc] == opponent_color and (nr, nc) not in stones_to_remove:
            group, liberties = find_group_and_liberties(nr, nc, board_state)

            if len(liberties) == 0:
                # 氣為零，提走該群棋子
                stones_to_remove.update(group)

    # 執行提子
    for cr, cc in stones_to_remove:
        board_state[cr][cc] = 0
        captured_count += 1

    return captured_count


def is_valid_move(r, c, current_color, board_state, prev_board):
    """
    判斷落子是否有效 (不自殺且不打劫)。
    """
    if not (0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE) or board_state[r][c] != 0:
        # return False, None  # 位置無效或已有子
        return False, None, 0  # 返回 False, None (新棋盤), 0 (提子數)

    # 1. 模擬落子
    temp_board = [row[:] for row in board_state]
    temp_board[r][c] = current_color

    # 2. 檢查並執行提子
    captured = capture_stones(temp_board, r, c)

    # 3. 檢查自殺
    if captured == 0:
        # 如果沒有提子，檢查自己的氣
        my_group, my_liberties = find_group_and_liberties(r, c, temp_board)
        if len(my_liberties) == 0:
            # return False, None  # 自殺
            return False, None, 0  # 自殺

    # 4. 檢查打劫 (Ko Rule)
    if prev_board is not None and temp_board == prev_board:
        # return False, None  # 打劫
        return False, None, 0  # 打劫

    return True, temp_board, captured  # 落子有效


# --- 4. 繪圖函數 ---

def draw_board(screen):
    """繪製棋盤線和背景"""
    screen.fill(BROWN)

    # 繪製線條
    for i in range(BOARD_SIZE):
        coord = i * SQUARE_SIZE + MARGIN
        # 垂直線
        pygame.draw.line(screen, BLACK, (coord, MARGIN), (coord, HEIGHT - MARGIN), LINE_THICKNESS)
        # 水平線
        pygame.draw.line(screen, BLACK, (MARGIN, coord), (WIDTH - MARGIN, coord), LINE_THICKNESS)

    # 標記星位 (9x9 中心點)
    star_points = [
        (2 * SQUARE_SIZE + MARGIN, 2 * SQUARE_SIZE + MARGIN),
        (6 * SQUARE_SIZE + MARGIN, 2 * SQUARE_SIZE + MARGIN),
        (2 * SQUARE_SIZE + MARGIN, 6 * SQUARE_SIZE + MARGIN),
        (6 * SQUARE_SIZE + MARGIN, 6 * SQUARE_SIZE + MARGIN),
        (4 * SQUARE_SIZE + MARGIN, 4 * SQUARE_SIZE + MARGIN)  # 天元
    ]
    for x, y in star_points:
        pygame.draw.circle(screen, BLACK, (x, y), 5)


def draw_stones(screen, board_state):
    """繪製棋子"""
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board_state[r][c] != 0:
                center_x = c * SQUARE_SIZE + MARGIN
                center_y = r * SQUARE_SIZE + MARGIN
                color = BLACK if board_state[r][c] == 1 else WHITE
                pygame.draw.circle(screen, color, (center_x, center_y), SQUARE_SIZE // 2 - 2)


def draw_info(screen):
    """繪製遊戲資訊"""
    info_text = f"Player: {'Black' if current_player == 1 else 'White'} ({'●' if current_player == 1 else '○'})"
    black_cap_text = f"Black Captures: {captured_stones[2]}"
    white_cap_text = f"White Captures: {captured_stones[1]}"

    info_surf = font.render(info_text, True, BLACK)
    black_cap_surf = font.render(black_cap_text, True, BLACK)
    white_cap_surf = font.render(white_cap_text, True, BLACK)

    screen.blit(info_surf, (10, 10))
    screen.blit(black_cap_surf, (10, HEIGHT - 40))
    screen.blit(white_cap_surf, (WIDTH - 200, HEIGHT - 40))


# --- 5. 主循環 ---

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN:
            x, y = event.pos

            # 轉換像素座標到棋盤座標 (R, C)
            if MARGIN - SQUARE_SIZE / 2 < x < WIDTH - MARGIN + SQUARE_SIZE / 2 and \
                    MARGIN - SQUARE_SIZE / 2 < y < HEIGHT - MARGIN + SQUARE_SIZE / 2:

                # 找到最接近的網格交叉點
                c = round((x - MARGIN) / SQUARE_SIZE)
                r = round((y - MARGIN) / SQUARE_SIZE)

                # 執行落子判斷
                is_ok, new_board, captured_count = is_valid_move(r, c, current_player, board, previous_board)

                if is_ok:
                    # 記錄當前狀態作為下一輪的比較對象 (打劫判斷)
                    previous_board = [row[:] for row in board]

                    # 更新棋盤狀態
                    board = new_board

                    # 更新提子數
                    captured_stones[current_player] += captured_count

                    # 切換玩家
                    current_player = 3 - current_player
                else:
                    print("Invalid move: Suicide, already occupied, or Ko rule violation.")

    # 繪製畫面
    draw_board(screen)
    draw_stones(screen, board)
    draw_info(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()