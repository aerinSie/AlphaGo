import pygame
import sys
from collections import deque
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time # 用於生成時間戳作為 Game ID

# --- 2. Google Sheet 設定 ---
# 請將 service_account.json 替換成您的憑證檔案名稱
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
try:
    # 嘗試載入憑證，如果找不到檔案會報錯
    CREDS = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPE)
except FileNotFoundError:
    print("WARNING: service_account.json not found. Google Sheet upload disabled.")
    CREDS = None

# 請替換成您建立的 Google Sheet 名稱
SHEET_NAME = "AlphaGoApi"

# --- 1. 遊戲參數設定 ---
# BOARD_SIZE, WIDTH, HEIGHT will be set dynamically
BOARD_SIZE = 9
SQUARE_SIZE = 50  # 每個格子的邊長 (像素)
LINE_THICKNESS = 2
MARGIN = 50  # 邊緣留白
WIDTH = HEIGHT = BOARD_SIZE * SQUARE_SIZE + 2 * MARGIN

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
# BROWN = (205, 133, 63)  # 棋盤顏色
BROWN = (160, 120, 90) #🪵 現代原木 (Modern Oak)
RED = (255, 0, 0)
LIGHT_GRAY = (200, 200, 200) # For buttons
DARK_GRAY = (100, 100, 100)

# 初始化 Pygame
pygame.init()
# screen will be set in run_game
screen = None
pygame.display.set_caption("AlphaGo")

# 嘗試指定一個常見的 Unicode 字體路徑
try:
    # 範例：如果您的系統有 Arial，請使用絕對或相對路徑
    # 替換成您系統中實際的字體路徑
    UNICODE_FONT_PATH = "Arial.ttf"
    font = pygame.font.Font(UNICODE_FONT_PATH, 30)
    print(f"Loaded font: {UNICODE_FONT_PATH}")
except pygame.error:
    print("Warning: Could not load specified Unicode font. Falling back to default.")
    font = pygame.font.Font(None, 30)

# --- 2. 數據結構 (Globals) ---
# 這些將在 run_game 中重置
board = []
current_player = 1
captured_stones = {1: 0, 2: 0}
previous_board = None
move_history = []

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

    # 棋盤網格的最外側座標，即最後一條線的位置
    MAX_GRID_COORD = (BOARD_SIZE - 1) * SQUARE_SIZE + MARGIN
    # 繪製線條
    for i in range(BOARD_SIZE):
        coord = i * SQUARE_SIZE + MARGIN

        # 垂直線：從 Y=MARGIN 畫到 Y=MAX_GRID_COORD
        pygame.draw.line(screen, BLACK,
                         (coord, MARGIN),
                         (coord, MAX_GRID_COORD),
                         LINE_THICKNESS)

        # 水平線：從 X=MARGIN 畫到 X=MAX_GRID_COORD
        pygame.draw.line(screen, BLACK,
                         (MARGIN, coord),
                         (MAX_GRID_COORD, coord),
                         LINE_THICKNESS)

    # 標記星位
    star_points = []
    if BOARD_SIZE == 9:
        star_points = [
            (2 * SQUARE_SIZE + MARGIN, 2 * SQUARE_SIZE + MARGIN),
            (6 * SQUARE_SIZE + MARGIN, 2 * SQUARE_SIZE + MARGIN),
            (2 * SQUARE_SIZE + MARGIN, 6 * SQUARE_SIZE + MARGIN),
            (6 * SQUARE_SIZE + MARGIN, 6 * SQUARE_SIZE + MARGIN),
            (4 * SQUARE_SIZE + MARGIN, 4 * SQUARE_SIZE + MARGIN)  # 天元
        ]
    elif BOARD_SIZE == 19:
        # 19路星位 (3, 9, 15) -> index 3, 9, 15 -> 4th, 10th, 16th line
        points = [3, 9, 15]
        for r in points:
            for c in points:
                star_points.append((c * SQUARE_SIZE + MARGIN, r * SQUARE_SIZE + MARGIN))

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


def draw_info(screen, back_btn_rect, mouse_pos):
    """繪製遊戲資訊"""
    info_text = f"Player: {'Black' if current_player == 1 else 'White'} ({'●' if current_player == 1 else '○'})"
    black_cap_text = f"Black Captures: {captured_stones[2]}"
    white_cap_text = f"White Captures: {captured_stones[1]}"

    info_surf = font.render(info_text, True, BLACK)
    black_cap_surf = font.render(black_cap_text, True, BLACK)
    white_cap_surf = font.render(white_cap_text, True, BLACK)

    screen.blit(info_surf, (10, 10))
    screen.blit(black_cap_surf, (10, HEIGHT - 40))
    screen.blit(white_cap_surf, (WIDTH - 250, HEIGHT - 40))
    
    # Draw Back Button
    draw_button(screen, back_btn_rect, "Back", back_btn_rect.collidepoint(mouse_pos))


# --- 3. 核心邏輯函數 之後新增 ---
def upload_move_history_to_sheet(history_data):
    """將落子歷史紀錄上傳到 Google Sheet"""

    if not CREDS:
        print("Google Sheet upload failed: Credentials not loaded.")
        return

    # 1. 格式化數據

    # 建立一個唯一的遊戲 ID (例如: 時間戳)
    game_id = time.strftime("%Y%m%d_%H%M%S")

    # 將每一手棋格式化為 'B(r,c)' 或 'W(r,c)'
    move_sequence = []
    for move in history_data:
        player_char = 'B' if move['player'] == 1 else 'W'
        r, c = move['move']
        # 顯示為人類可讀的座標 (例如 1-19, 這裡使用 0-8)
        move_str = f"{player_char}({r},{c})"
        move_sequence.append(move_str)

    # 2. 連接並寫入 Sheet
    try:
        client = gspread.authorize(CREDS)
        sheet = client.open(SHEET_NAME).sheet1  # 預設寫入第一個工作表

        # 準備寫入的數據: [Game ID, 提子數, Move 1, Move 2, ...]
        row_data = [game_id] + [f"B Cap: {captured_stones[2]}, W Cap: {captured_stones[1]}"] + move_sequence

        # 確保有標題行 (如果 Sheet 是空的)
        if not sheet.row_values(1):
            header = ["Game ID", "Final Captures"] + [f"Move {i + 1}" for i in range(len(move_sequence))]
            sheet.append_row(header)

        # 寫入新的行數據
        sheet.append_row(row_data)
        print(f"成功將 {len(move_sequence)} 步棋記錄上傳到 Google Sheet！")

    except Exception as e:
        print(f"Google Sheet 上傳時發生錯誤: {e}")

# --- Entry Screen ---

def draw_button(screen, rect, text, hover=False):
    color = LIGHT_GRAY if not hover else DARK_GRAY
    pygame.draw.rect(screen, color, rect)
    pygame.draw.rect(screen, BLACK, rect, 2)
    
    text_surf = font.render(text, True, BLACK if not hover else WHITE)
    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)

def show_entry_screen():
    entry_width, entry_height = 400, 300
    entry_screen = pygame.display.set_mode((entry_width, entry_height))
    pygame.display.set_caption("AlphaGo - Select Board Size")
    
    btn_9_rect = pygame.Rect(50, 100, 120, 60)
    btn_19_rect = pygame.Rect(230, 100, 120, 60)
    
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None # Signal to exit app
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_9_rect.collidepoint(mouse_pos):
                    return 9
                if btn_19_rect.collidepoint(mouse_pos):
                    return 19
        
        entry_screen.fill(WHITE)
        
        title_surf = font.render("Select Board Size", True, BLACK)
        title_rect = title_surf.get_rect(center=(entry_width // 2, 50))
        entry_screen.blit(title_surf, title_rect)
        
        draw_button(entry_screen, btn_9_rect, "9 x 9", btn_9_rect.collidepoint(mouse_pos))
        draw_button(entry_screen, btn_19_rect, "19 x 19", btn_19_rect.collidepoint(mouse_pos))
        
        pygame.display.flip()

# --- Main Game Loop ---

def run_game(size):
    global BOARD_SIZE, WIDTH, HEIGHT, SQUARE_SIZE, screen, board, current_player, captured_stones, previous_board, move_history
    
    BOARD_SIZE = size
    
    # Dynamic resizing
    MAX_HEIGHT = 800
    # Calculate max possible square size to fit in MAX_HEIGHT
    # HEIGHT = BOARD_SIZE * SQUARE_SIZE + 2 * MARGIN
    # MAX_HEIGHT >= BOARD_SIZE * sq + 2 * MARGIN
    # sq <= (MAX_HEIGHT - 2 * MARGIN) / BOARD_SIZE
    
    calculated_sq = (MAX_HEIGHT - 2 * MARGIN) // BOARD_SIZE
    SQUARE_SIZE = min(50, calculated_sq) # Cap at 50
    
    WIDTH = HEIGHT = BOARD_SIZE * SQUARE_SIZE + 2 * MARGIN
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(f"AlphaGo ({BOARD_SIZE}x{BOARD_SIZE})")
    
    # Reset game state
    board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    current_player = 1
    captured_stones = {1: 0, 2: 0}
    previous_board = None
    move_history = []
    
    # Back Button Rect (Top Right)
    back_btn_rect = pygame.Rect(WIDTH - 110, 10, 100, 40)
    
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return 'EXIT'
    
            # 新增: 按下 E 鍵結束遊戲並上傳
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_e:
                    if move_history:
                        print(move_history)
                        # 呼叫上傳函數
                        upload_move_history_to_sheet(move_history)
                    return 'EXIT' # Or maybe just return to menu? Let's keep it as exit for now or user preference. 
                    # Actually, usually E just ends the game. Let's assume it exits the game loop but maybe we want to go back to menu?
                    # For now, let's stick to existing behavior: running = False -> return None (implied)
                    running = False
    
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back_btn_rect.collidepoint(mouse_pos):
                    return 'BACK'

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
                        # 💖 關鍵: 儲存歷史紀錄 - 必須在這裡執行
                        # **重點：這裡儲存的是落子前的盤面**
                        move_history.append({
                            'board': [row[:] for row in board],
                            'player': current_player,
                            'move': (r, c)
                        })
    
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
        draw_info(screen, back_btn_rect, mouse_pos)
    
        pygame.display.flip()
    
    return 'EXIT'

if __name__ == "__main__":
    while True:
        selected_size = show_entry_screen()
        if selected_size is None:
            break
        result = run_game(selected_size)
        if result == 'EXIT':
            break
        # If result == 'BACK', loop continues and shows entry screen again
        
    pygame.quit()
    sys.exit()