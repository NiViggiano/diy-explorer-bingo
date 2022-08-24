from enum import IntEnum
from tkinter import Tk, Canvas


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


class Visibility(IntEnum):

    INVISIBLE = 0
    VISIBLE = 1
    ALWAYS = 2


class _Square_View:
    def __init__(self, canvas: Canvas, left, top, square_width, square_height, text):
        self.left = left
        self.top = top
        self.text = text
        self.square_width = square_width
        self.square_height = square_height
        self.canvas = canvas
        self.text_shape = None
        self.draw_empty()

    @staticmethod
    def pixel_to_point(size: int) -> float:
        scaled = size * 0.75
        # round to nearest half pt
        return round(scaled * 2.0) / 2.0

    @staticmethod
    def pixel_to_int_point(size: int) -> int:
        return round(size * 0.75)

    def make_rectangle(self, color, divs, idx):
        width = self.square_width / divs
        return self.canvas.create_rectangle(
            self.left + idx * width,
            self.top,
            self.left + (idx + 1) * width,
            self.top + self.square_height,
            fill=rgb_to_hex(color),
            outline="white",
        )

    def draw_empty(self):
        self.recs = {self.make_rectangle((40, 40, 40), 1, 0)}

    def make_visible(self):
        # TODO hardcoded height/width
        ratio = 1 / (len(self.text)) ** 0.5
        height_px = round(self.square_height * ratio)

        self.text_shape = self.canvas.create_text(
            self.left + self.square_width / 2,
            self.top + self.square_height / 2,
            text=self.text,
            fill="white",
            activefill="black",
            width=self.square_width * 0.95,
            font=("arial", self.pixel_to_int_point(height_px)),
            justify="center",
        )

    def make_invisible(self):
        self.canvas.delete(self.text_shape)
        self.text_shape = None

    def redraw_text(self):
        if self.text_shape is not None:
            self.make_invisible()
            self.make_visible()

    def redraw_rectangle(self, colors):
        for rec in self.recs:
            self.canvas.delete(rec)
        self.recs = set()
        for i in range(len(colors)):
            self.recs.add(self.make_rectangle(colors[i], len(colors), i))
        if len(self.recs) == 0:
            self.draw_empty()
        self.redraw_text()


class _Square_Model:
    def __init__(self, board_size, board_idx):
        self.board_size = board_size
        self.board_idx = board_idx
        self.visible = Visibility.INVISIBLE
        self.colors = set()  # !!! Colors should be in (R, G, B) form, NOT hex yet!

    def __repr__(self):
        border = "------------"
        ret = border + "\n"
        for color in self.colors:
            ret += "|" + rgb_to_hex(color) + "|\n"
        for i in range(4 - len(self.colors)):
            ret += "|         |\n"
        return ret + border

    def mark(self, color):
        if color not in self.colors:
            self.colors.add(color)
            return (True, sorted(self.colors))
        else:
            self.colors.remove(color)
            return (False, sorted(self.colors))


class Game:
    def __init__(self, board_size):
        self.size: int = board_size
        if board_size % 2:
            self.middle = (board_size * board_size) // 2
        else:
            self.middle = (board_size * board_size) // 2 - (board_size // 2)

    def row(self, idx):
        return idx // self.size

    def col(self, idx):
        return idx % self.size

    def adjacent_indices(self, idx):
        row = self.row(idx)
        col = self.col(idx)
        ret = []
        if row > 0:
            ret.append(idx - self.size)
        if row < self.size - 1:
            ret.append(idx + self.size)
        if col > 0:
            ret.append(idx - 1)
        if col < self.size - 1:
            ret.append(idx + 1)
        return ret


class Game_Model(Game):
    def __init__(self, board_size, all_visible=False):
        super().__init__(board_size)
        self.squares = [_Square_Model(board_size, i) for i in range(board_size * board_size)]
        if all_visible:
            for square in self.squares:
                square.visible = Visibility.ALWAYS
        else:
            self.squares[self.middle].visible = Visibility.ALWAYS
            if board_size % 2:
                for idx in self.adjacent_indices(self.middle):
                    self.squares[idx].visible = Visibility.ALWAYS
            else:
                self.squares[self.middle - 1].visible = Visibility.ALWAYS
                self.squares[self.middle + board_size].visible = Visibility.ALWAYS
                self.squares[self.middle + board_size - 1].visible = Visibility.ALWAYS

    def __repr__(self):
        ret = "\n".join([repr(square) for square in self.squares])
        return ret

    def mark(self, idx, color):
        return self.squares[idx].mark(color)

    def explore_surrounding(self, idx):
        envisioned = []
        for adj_idx in self.adjacent_indices(idx):
            if self.squares[adj_idx].visible == Visibility.INVISIBLE:
                self.squares[adj_idx].visible = Visibility.VISIBLE
                envisioned.append(adj_idx)
        return envisioned

    def surrounded_by_color(self, idx, color):
        for adj_idx in self.adjacent_indices(idx):
            if color in self.squares[adj_idx].colors:
                return True
        return False

    def unexplore_surrounding(self, idx, color):
        devisioned = []
        for adj_idx in self.adjacent_indices(idx):
            if self.squares[adj_idx].visible == Visibility.VISIBLE and not self.surrounded_by_color(adj_idx, color):
                self.squares[adj_idx].visible = Visibility.INVISIBLE
                devisioned.append(adj_idx)
        return devisioned


class Game_View(Game):
    def __init__(self, board_size, canvas, goal_indices, goal_list, all_visible=False):
        super().__init__(board_size)
        self.canvas = canvas
        self.square_width = canvas.width / board_size
        self.square_height = canvas.height / board_size
        self.squares = [
            _Square_View(
                canvas, self.left(i), self.top(i), self.square_width, self.square_height, goal_list[goal_indices[i]]
            )
            for i in range(board_size * board_size)
        ]
        if all_visible:
            for square in self.squares:
                square.make_visible()
        else:
            self.squares[self.middle].make_visible()
            if board_size % 2:
                for idx in self.adjacent_indices(self.middle):
                    self.squares[idx].make_visible()
            else:
                self.squares[self.middle - 1].make_visible()
                self.squares[self.middle + board_size].make_visible()
                self.squares[self.middle + board_size - 1].make_visible()

    def left(self, idx):
        return (idx % self.size) * self.square_width

    def top(self, idx):
        return (idx // self.size) * self.square_height

    def redraw_rectangle(self, idx, colors):
        self.squares[idx].redraw_rectangle(colors)

    def make_visible(self, idx):
        self.squares[idx].make_visible()

    def make_invisible(self, idx):
        self.squares[idx].make_invisible()


class Game_Controller(Game):
    def __init__(self, board_size, color, goal_indices, goal_list, board_width, board_height, all_visible=False):
        super().__init__(board_size)
        self.root = Tk()
        self.color = color
        self.canvas = Canvas(self.root, width=board_width, height=board_height)
        self.canvas.width = board_width
        self.canvas.height = board_height
        self.goal_indices = goal_indices
        self.goal_list = goal_list
        self.all_visible = all_visible
        self.model: Game_Model = Game_Model(board_size, all_visible)
        self.view: Game_View = Game_View(board_size, self.canvas, goal_indices, goal_list, all_visible)
        self.canvas.pack()
        self.root.bind("<Button-1>", self.mouse_pressed)

    def __repr__(self):
        return repr(self.model)

    def run(self):
        self.root.mainloop()

    def mark(self, idx, color):
        (added, colors) = self.model.mark(idx, color)
        self.view.redraw_rectangle(idx, colors)
        if color == self.color:
            if added:
                for newly_visible in self.model.explore_surrounding(idx):
                    self.view.make_visible(newly_visible)

            else:
                for newly_invisible in self.model.unexplore_surrounding(idx, color):
                    self.view.make_invisible(newly_invisible)

    def mouse_pressed(self, event):
        col = int(event.x * self.size / self.canvas.width)
        row = int(event.y * self.size / self.canvas.height)
        idx = row * self.size + col
        if int(self.model.squares[idx].visible) > 0:
            self.mark(idx, self.color)
            return idx
        else:
            return None
